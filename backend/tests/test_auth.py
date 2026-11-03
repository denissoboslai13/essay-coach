"""Login, invite-only registration, sessions and "users only see their own essays"."""

from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app import auth
from app.config import get_settings
from app.models import Invite, LoginSession, User, utcnow
from tests.conftest import make_explanation, make_feedback

ESSAY_TEXT = " ".join(["word"] * 80)


@pytest.fixture
def google(monkeypatch):
    """Replaces Google's token check. Set `google.claims` to what the token "contains"."""

    class FakeGoogle:
        claims = {"sub": "g-1", "email": "New.User@Gmail.com", "email_verified": True, "name": "New User"}

    def verify(credential):
        if credential == "bad-token":
            raise ValueError("invalid signature")
        return FakeGoogle.claims

    monkeypatch.setattr(auth, "verify_google_token", verify)
    return FakeGoogle


@pytest.fixture
def invite(engine) -> str:
    with Session(engine) as session:
        session.add(Invite(code="ABCD-EFGH"))
        session.commit()
    return "ABCD-EFGH"


def login(client, invite_code=None, credential="good-token"):
    return client.post("/auth/google", json={"credential": credential, "invite_code": invite_code})


def users(engine) -> list[User]:
    with Session(engine) as session:
        return list(session.exec(select(User)))


@pytest.mark.parametrize("method,path", [("get", "/auth/me"), ("get", "/topics"), ("get", "/essays"), ("post", "/essays")])
def test_endpoints_need_login(anon_client, method, path):
    assert anon_client.request(method, path, json={"topic": "Some topic"}).status_code == 401


def test_new_account_needs_invite(anon_client, google, engine):
    r = login(anon_client)
    assert r.status_code == 403
    assert r.json()["detail"] == auth.INVITE_REQUIRED
    assert users(engine) == []


def test_invite_registers_and_signs_in(anon_client, google, invite, engine):
    # Lower case and spaces are accepted
    r = login(anon_client, invite_code=" abcd-efgh ")
    assert r.status_code == 200
    assert r.json()["email"] == "new.user@gmail.com"
    assert auth.SESSION_COOKIE in r.cookies

    # The cookie now works for other endpoints
    assert anon_client.get("/auth/me").status_code == 200
    with Session(engine) as session:
        used = session.exec(select(Invite)).one()
        assert used.used_by_id == users(engine)[0].id


def test_invite_works_only_once(anon_client, google, invite, engine):
    assert login(anon_client, invite_code=invite).status_code == 200
    anon_client.post("/auth/logout")

    google.claims = {"sub": "g-2", "email": "someone@else.com", "email_verified": True}
    r = login(anon_client, invite_code=invite)
    assert r.status_code == 403
    assert "already been used" in r.json()["detail"]
    assert [u.email for u in users(engine)] == ["new.user@gmail.com"]


def test_wrong_invite_is_rejected(anon_client, google, invite):
    assert login(anon_client, invite_code="WRONG-CODE").status_code == 403


def test_existing_user_needs_no_invite(anon_client, google, invite):
    login(anon_client, invite_code=invite)
    anon_client.post("/auth/logout")
    assert login(anon_client).status_code == 200


def test_admin_email_needs_no_invite(anon_client, google, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_emails", "boss@example.com, new.user@gmail.com")
    r = login(anon_client)
    assert r.status_code == 200
    assert r.json()["is_admin"] is True


def test_invalid_google_token(anon_client, google):
    assert login(anon_client, credential="bad-token").status_code == 401


def test_unverified_email_is_rejected(anon_client, google, invite):
    google.claims = {**google.claims, "email_verified": False}
    assert login(anon_client, invite_code=invite).status_code == 401


def test_logout_ends_session(client, engine):
    assert client.get("/auth/me").status_code == 200
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401
    with Session(engine) as session:
        assert session.exec(select(LoginSession)).all() == []


def test_expired_session_is_rejected(client, engine):
    with Session(engine) as session:
        for login_session in session.exec(select(LoginSession)):
            login_session.expires_at = utcnow() - timedelta(minutes=1)
            session.add(login_session)
        session.commit()
    assert client.get("/auth/me").status_code == 401


def test_session_token_is_stored_hashed(client, engine):
    token = client.cookies.get(auth.SESSION_COOKIE)
    with Session(engine) as session:
        stored = session.exec(select(LoginSession)).one().token_hash
    assert stored != token and len(stored) == 64


def test_local_mode_needs_no_login(anon_client, monkeypatch, provider, engine):
    monkeypatch.setattr(get_settings(), "local_mode", True)
    # Admin emails are for the hosted version; local mode doesn't use them
    monkeypatch.setattr(get_settings(), "admin_emails", "owner@example.com")
    me = anon_client.get("/auth/me").json()
    assert (me["email"], me["is_admin"], me["local_mode"]) == (auth.LOCAL_EMAIL, True, True)

    provider.responses.append(make_feedback(1))
    essay_id = anon_client.post("/essays", json={"topic": "A school film evening"}).json()["id"]
    assert anon_client.post(f"/essays/{essay_id}/revisions", json={"text": ESSAY_TEXT}).status_code == 200
    # Always the same single account
    assert [u.email for u in users(engine)] == [auth.LOCAL_EMAIL]


def test_local_mode_takes_over_essays_without_owner(anon_client, monkeypatch, engine):
    from app.models import Essay

    with Session(engine) as session:
        session.add(Essay(topic="Written before login existed"))
        session.commit()

    monkeypatch.setattr(get_settings(), "local_mode", True)
    assert [e["topic"] for e in anon_client.get("/essays").json()] == ["Written before login existed"]


def test_local_mode_is_off_by_default(anon_client):
    assert anon_client.get("/auth/me").status_code == 401


# --- Ownership ---------------------------------------------------------------


def test_users_only_see_their_own_essays(client, make_client, provider):
    provider.responses += [make_feedback(1)]
    essay_id = client.post("/essays", json={"topic": "A school film evening"}).json()["id"]
    issue_id = client.post(f"/essays/{essay_id}/revisions", json={"text": ESSAY_TEXT}).json()["revision"]["issues"][0]["id"]

    other = make_client("other@example.com")
    assert other.get("/essays").json() == []
    assert other.get(f"/essays/{essay_id}").status_code == 404
    assert other.post(f"/essays/{essay_id}/revisions", json={"text": ESSAY_TEXT}).status_code == 404
    provider.responses.append(make_explanation())
    assert other.post(f"/issues/{issue_id}/dispute", json={"comment": None}).status_code == 404
    # The other user's attempts never reached the AI
    assert len(provider.calls) == 1

    assert len(client.get("/essays").json()) == 1


def test_finished_topics_are_per_user(client, make_client, provider):
    from app.topics import NORMAL_TOPICS

    provider.responses.append(make_feedback(0))
    essay_id = client.post("/essays", json={"topic": NORMAL_TOPICS[0]}).json()["id"]
    client.post(f"/essays/{essay_id}/revisions", json={"text": ESSAY_TEXT})

    other = make_client("other@example.com")
    offered = set()
    for _ in range(30):
        offered.update(other.get("/topics").json()["topics"])
    assert NORMAL_TOPICS[0] in offered
