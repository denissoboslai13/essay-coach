"""Account deletion, the privacy contact in the public config, backups and the NOT NULL migration."""

import sqlite3

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlmodel import Session, select

from app import admin, auth, db
from app.config import get_settings
from app.models import Essay, Invite, Issue, LoginSession, Revision, UsageLog, User
from tests.conftest import make_feedback

ESSAY_TEXT = " ".join(["word"] * 80)
EMAIL = "learner@example.com"


def write_essay(client, provider) -> int:
    essay_id = client.post("/essays", json={"topic": "A topic"}).json()["id"]
    provider.responses.append(make_feedback(2))
    assert client.post(f"/essays/{essay_id}/revisions", json={"text": ESSAY_TEXT}).status_code == 200
    return essay_id


def delete_me(client, email=EMAIL):
    return client.request("DELETE", "/auth/me", json={"confirm_email": email})


def count(engine, model) -> int:
    with Session(engine) as session:
        return len(session.exec(select(model)).all())


def test_delete_account_removes_user_data_but_keeps_costs(client, make_client, provider, engine):
    other = make_client("other@example.com")
    write_essay(client, provider)
    other_essay = write_essay(other, provider)
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == EMAIL)).one()
        session.add(Invite(code="ABCD-EFGH", used_by_id=user.id, used_at=user.created_at))
        session.commit()

    r = delete_me(client)
    assert r.status_code == 204
    assert "ec_session" in r.headers["set-cookie"]

    with Session(engine) as session:
        assert [u.email for u in session.exec(select(User))] == ["other@example.com"]
        assert [e.id for e in session.exec(select(Essay))] == [other_essay]
        assert len(session.exec(select(Revision)).all()) == 1
        assert len(session.exec(select(Issue)).all()) == 2
        assert len(session.exec(select(LoginSession)).all()) == 1
        # Costs still count toward the monthly budget, without a link to the person
        assert sorted(log.user_id is None for log in session.exec(select(UsageLog))) == [False, True]
        invite = session.exec(select(Invite)).one()
        assert invite.used_by_id is None and invite.used_at is not None

    # The old session cookie no longer works, the other user is untouched
    assert client.get("/auth/me").status_code == 401
    assert other.get(f"/essays/{other_essay}").status_code == 200


def test_delete_account_needs_matching_email(client, engine):
    r = delete_me(client, "someone-else@example.com")
    assert r.status_code == 400
    assert count(engine, User) == 1
    # Case and surrounding spaces don't matter
    assert delete_me(client, "  Learner@Example.com ").status_code == 204


def test_delete_account_needs_login(anon_client):
    assert delete_me(anon_client).status_code == 401


def test_delete_account_refused_in_local_mode(local_client, monkeypatch, engine):
    monkeypatch.setattr(get_settings(), "local_mode", True)
    assert delete_me(local_client, auth.LOCAL_EMAIL).status_code == 400
    assert count(engine, User) == 1


def test_used_invite_stays_used_after_account_deletion(anon_client, engine, monkeypatch):
    """Deleting the account must not make the invite code usable again."""
    monkeypatch.setattr(auth, "verify_google_token", lambda c: {"sub": "g-1", "email": EMAIL, "email_verified": True})
    with Session(engine) as session:
        session.add(Invite(code="ABCD-EFGH"))
        session.commit()
    login = {"credential": "token", "invite_code": "ABCD-EFGH"}
    assert anon_client.post("/auth/google", json=login).status_code == 200
    assert delete_me(anon_client).status_code == 204
    assert anon_client.post("/auth/google", json=login).status_code == 403


def test_auth_config_has_privacy_contact(anon_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "privacy_contact", "privacy@example.com")
    assert anon_client.get("/auth/config").json()["privacy_contact"] == "privacy@example.com"


def test_admin_delete_user(engine, client, provider, monkeypatch):
    write_essay(client, provider)
    with Session(engine) as session:
        admin.cmd_delete_user(session, admin.argparse.Namespace(email="LEARNER@example.com", yes=True))
    assert count(engine, User) == 0
    assert count(engine, Essay) == 0


@pytest.fixture
def file_engine(tmp_path, monkeypatch):
    """The admin module's engine pointed at a real database file."""
    engine = create_engine(f"sqlite:///{tmp_path / 'app.db'}")
    monkeypatch.setattr(admin, "engine", engine)
    monkeypatch.setattr(db, "engine", engine)
    db.create_db_and_tables()
    return engine


def test_backup_copies_database_and_keeps_newest(file_engine, tmp_path):
    with Session(file_engine) as session:
        session.add(User(google_sub="g", email="a@example.com"))
        session.commit()
    backups = tmp_path / "backups"
    old = [backups / f"essay_coach-2020010{i}-000000.db" for i in range(1, 4)]
    backups.mkdir()
    for path in old:
        path.write_bytes(b"")

    target = admin.backup_database(backups, keep=2)

    assert sorted(backups.iterdir()) == [old[2], target]
    with sqlite3.connect(target) as copy:
        assert copy.execute("SELECT email FROM user").fetchall() == [("a@example.com",)]


def test_migration_makes_usage_log_user_id_nullable(tmp_path, monkeypatch):
    """A database created before account deletion existed has usage_log.user_id NOT NULL."""
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE user (id INTEGER PRIMARY KEY, google_sub VARCHAR NOT NULL, email VARCHAR NOT NULL)"))
        conn.execute(
            text(
                "CREATE TABLE usage_log (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES user(id), "
                "request_id VARCHAR NOT NULL, kind VARCHAR NOT NULL, model VARCHAR NOT NULL, input_tokens INTEGER NOT NULL, "
                "output_tokens INTEGER NOT NULL, cost_usd FLOAT NOT NULL, created_at DATETIME NOT NULL)"
            )
        )
        conn.execute(text("CREATE INDEX ix_usage_log_user_id ON usage_log (user_id)"))
        conn.execute(text("INSERT INTO usage_log VALUES (1, 7, 'r', 'review', 'm', 10, 5, 0.5, '2026-11-01 10:00:00')"))
    monkeypatch.setattr(db, "engine", engine)

    db.create_db_and_tables()

    columns = {c["name"]: c for c in inspect(engine).get_columns("usage_log")}
    assert columns["user_id"]["nullable"]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT user_id, cost_usd FROM usage_log")).all() == [(7, 0.5)]
    # Running it again changes nothing
    db.create_db_and_tables()
