from collections.abc import Iterator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()

# check_same_thread=False: FastAPI serves sync endpoints from a thread pool
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})


def _sql_default(column) -> str:
    """SQL literal for a NOT NULL column's Python default (needed by ALTER TABLE ADD COLUMN)."""
    value = column.default.arg if column.default is not None and not callable(column.default.arg) else None
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "''" if value is None else f"'{value}'"


def _add_missing_columns() -> None:
    """Minimal migration for the prototype: add columns that are in the models but not in an
    existing database. Does not handle renamed or removed columns."""
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column.type.compile(engine.dialect)}'
                if not column.nullable:
                    ddl += f" NOT NULL DEFAULT {_sql_default(column)}"
                conn.execute(text(ddl))


def _relax_not_null() -> None:
    """A column that became nullable in the models (e.g. usage_log.user_id, cleared on account deletion)
    stays NOT NULL in an existing database. SQLite can't change that in place, so the table is rebuilt."""
    inspector = inspect(engine)
    for table in SQLModel.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {c["name"]: c for c in inspector.get_columns(table.name)}
        if not any(c.nullable and c.name in existing and not existing[c.name]["nullable"] for c in table.columns):
            continue
        old = f"{table.name}__old"
        columns = ", ".join(f'"{c.name}"' for c in table.columns if c.name in existing)
        with engine.begin() as conn:
            # Index names must be free for the new table
            for index in inspector.get_indexes(table.name):
                conn.execute(text(f'DROP INDEX "{index["name"]}"'))
            conn.execute(text(f'ALTER TABLE "{table.name}" RENAME TO "{old}"'))
            table.create(conn)
            conn.execute(text(f'INSERT INTO "{table.name}" ({columns}) SELECT {columns} FROM "{old}"'))
            conn.execute(text(f'DROP TABLE "{old}"'))


def create_db_and_tables() -> None:
    from app import models  # noqa: F401  (registers the tables)

    SQLModel.metadata.create_all(engine)
    _add_missing_columns()
    _relax_not_null()


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
