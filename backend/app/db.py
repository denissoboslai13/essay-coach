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


def create_db_and_tables() -> None:
    from app import models  # noqa: F401  (registers the tables)

    SQLModel.metadata.create_all(engine)
    _add_missing_columns()


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
