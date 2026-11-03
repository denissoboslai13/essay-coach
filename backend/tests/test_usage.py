"""Usage log, daily limits per user and the monthly budget."""

import pytest
from sqlmodel import Session, select

from app.config import get_settings
from app.models import UsageLog
from app.services.usage import FALLBACK_PRICE, cost_usd
from tests.conftest import FAKE_INPUT_TOKENS, FAKE_OUTPUT_TOKENS, make_explanation, make_feedback

ESSAY_TEXT = " ".join(["word"] * 80)


@pytest.fixture
def settings(monkeypatch):
    """Settings with known models and limits; `monkeypatch` restores them after the test."""
    s = get_settings()
    for name, value in {
        "anthropic_model": "claude-haiku-5-5",
        "anthropic_admin_model": "claude-sonnet-5-5",
        "daily_reviews_per_user": 2,
        "daily_disputes_per_user": 1,
        "monthly_budget_usd": 10.0,
    }.items():
        monkeypatch.setattr(s, name, value)
    return s


def new_essay(client) -> int:
    return client.post("/essays", json={"topic": "A school film evening"}).json()["id"]


def review(client, essay_id, text=ESSAY_TEXT):
    return client.post(f"/essays/{essay_id}/revisions", json={"text": text})


def logs(engine) -> list[UsageLog]:
    with Session(engine) as session:
        return list(session.exec(select(UsageLog)))


def test_cost_uses_model_price():
    # Haiku 5.5: $0.10 in / $0.50 out per million tokens
    assert cost_usd("claude-haiku-5-5", 1_000_000, 1_000_000) == pytest.approx(0.60)
    # Unknown models are priced as the most expensive one
    assert cost_usd("some-new-model", 1_000_000, 0) == pytest.approx(FALLBACK_PRICE[0])


def test_every_ai_call_is_logged(client, provider, engine, settings):
    review_essay = new_essay(client)
    provider.responses.append(make_feedback(1))
    review(client, review_essay)

    [log] = logs(engine)
    assert (log.kind, log.model) == ("review", "claude-haiku-5-5")
    assert (log.input_tokens, log.output_tokens) == (FAKE_INPUT_TOKENS, FAKE_OUTPUT_TOKENS)
    assert log.cost_usd == pytest.approx(cost_usd("claude-haiku-5-5", FAKE_INPUT_TOKENS, FAKE_OUTPUT_TOKENS))


def test_leak_retry_is_one_action(client, provider, engine, settings):
    leaky = make_feedback(1)
    leaky.issues[0].question = "How is definitely spelled?"
    provider.responses += [leaky, leaky.model_copy(deep=True)]
    review(client, new_essay(client), ESSAY_TEXT + " I would definately come again.")

    # Two AI calls are paid for, but they count as one check against the daily limit
    entries = logs(engine)
    assert len(entries) == 2 and len({e.request_id for e in entries}) == 1
    assert client.get("/auth/me").json()["quota"]["reviews_left"] == 1


def test_daily_review_limit(client, provider, settings):
    essay_id = new_essay(client)
    provider.responses += [make_feedback(1), make_feedback(1)]
    assert review(client, essay_id).status_code == 200
    assert review(client, essay_id).status_code == 200

    r = review(client, essay_id)
    assert r.status_code == 429
    assert "all 2 checks" in r.json()["detail"]
    # Refused before calling the AI
    assert len(provider.calls) == 2
    assert client.get("/auth/me").json()["quota"]["reviews_left"] == 0


def test_one_ai_action_at_a_time_per_user(client, make_client, provider, settings, engine):
    from app.models import User
    from app.services.usage import one_action_at_a_time

    essay_id = new_essay(client)
    with Session(engine) as session:
        user_id = session.exec(select(User.id).where(User.email == "learner@example.com")).one()

    # While one action of this user is running, a second one (e.g. sent in parallel) is refused
    with one_action_at_a_time(user_id):
        r = review(client, essay_id)
        assert r.status_code == 429
        assert "still running" in r.json()["detail"]
        # Other users are not blocked
        provider.responses.append(make_feedback(1))
        other = make_client("other@example.com")
        assert review(other, new_essay(other)).status_code == 200
    assert len(provider.calls) == 1

    # Released afterwards, also after the refused request
    provider.responses.append(make_feedback(1))
    assert review(client, essay_id).status_code == 200


def test_too_short_text_does_not_count(client, provider, settings):
    essay_id = new_essay(client)
    for _ in range(3):
        review(client, essay_id, "Too short.")
    assert client.get("/auth/me").json()["quota"]["reviews_left"] == 2


def test_dispute_limit_is_separate(client, provider, settings):
    essay_id = new_essay(client)
    provider.responses += [make_feedback(2), make_explanation(), make_explanation()]
    issues = review(client, essay_id).json()["revision"]["issues"]

    assert client.post(f"/issues/{issues[0]['id']}/dispute", json={"comment": None}).status_code == 200
    assert client.post(f"/issues/{issues[1]['id']}/dispute", json={"comment": None}).status_code == 429
    # Reviews are still available
    assert client.get("/auth/me").json()["quota"]["reviews_left"] == 1


def test_limits_are_per_user(client, make_client, provider, settings):
    provider.responses += [make_feedback(1)] * 3
    first = new_essay(client)
    review(client, first)
    review(client, first)

    other = make_client("other@example.com")
    assert review(other, new_essay(other)).status_code == 200


def test_admin_has_no_daily_limit_and_own_model(make_client, provider, settings):
    admin = make_client("admin@example.com", is_admin=True)
    essay_id = new_essay(admin)
    provider.responses += [make_feedback(1)] * 3
    for _ in range(3):
        assert review(admin, essay_id).status_code == 200
    assert {c["model"] for c in provider.calls} == {"claude-sonnet-5-5"}
    assert admin.get("/auth/me").json()["quota"]["reviews_left"] is None


def test_monthly_budget_stops_everyone(client, make_client, provider, settings, monkeypatch):
    essay_id = new_essay(client)
    provider.responses.append(make_feedback(1))
    review(client, essay_id)

    # The one call above already costs more than this budget
    monkeypatch.setattr(settings, "monthly_budget_usd", 0.0001)
    r = review(client, essay_id)
    assert r.status_code == 429
    assert "budget" in r.json()["detail"]

    admin = make_client("admin@example.com", is_admin=True)
    assert review(admin, new_essay(admin)).status_code == 429
    assert admin.get("/auth/me").json()["quota"]["budget_reached"] is True
    assert len(provider.calls) == 1
