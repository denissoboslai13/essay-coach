import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401  (registers the tables)
from app.ai.provider import Completion, get_provider
from app.auth import SESSION_COOKIE, create_login_session
from app.config import get_settings
from app.db import get_session
from app.main import app
from app.models import User
from app.schemas import AIFeedback, AIIssue, AIPreviousIssueCheck, AIRuleExplanation

# Token counts every fake AI call reports
FAKE_INPUT_TOKENS = 1000
FAKE_OUTPUT_TOKENS = 500


class FakeProvider:
    """Returns queued responses instead of calling a real AI. Records every call."""

    def __init__(self) -> None:
        self.responses: list = []
        self.calls: list[dict] = []

    def generate(self, *, system, user, output, model):
        self.calls.append({"system": system, "user": user, "output": output, "model": model})
        response = self.responses.pop(0)
        assert isinstance(response, output)
        return Completion(output=response, model=model, input_tokens=FAKE_INPUT_TOKENS, output_tokens=FAKE_OUTPUT_TOKENS)


def make_feedback(n_issues: int, previous: dict[int, str] | None = None) -> AIFeedback:
    """`previous` maps previous-round issue numbers to "fixed" / "not_fixed"."""
    return AIFeedback(
        previous_issues=[
            AIPreviousIssueCheck(number=n, status=status, comment=f"{status} comment")
            for n, status in (previous or {}).items()
        ],
        issues=[
            AIIssue(
                passage=f"passage {i}",
                category="grammar",
                problem=f"problem {i}",
                question=f"question {i}?",
            )
            for i in range(1, n_issues + 1)
        ],
        strength="Clear paragraph structure.",
    )


def make_explanation(verdict: str = "error") -> AIRuleExplanation:
    return AIRuleExplanation(explanation="Countable nouns need an article. You decide.", verdict=verdict)


@pytest.fixture(autouse=True)
def login_settings(monkeypatch):
    """Tests must not depend on the developer's backend/.env (e.g. LOCAL_MODE=true there)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "local_mode", False)
    monkeypatch.setattr(settings, "admin_emails", "")


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def anon_client(engine, provider: FakeProvider):
    """A client that is not signed in."""

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_provider] = lambda: provider
    # Not used as a context manager, so the lifespan (real DB file) does not run
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def local_client(anon_client) -> TestClient:
    """Not signed in, but a browser on this machine (what LOCAL_MODE accepts)."""
    return TestClient(app, base_url="http://localhost:5173", client=("127.0.0.1", 50000))


@pytest.fixture
def make_client(engine, anon_client):
    """Factory: a new client signed in as a new user (overrides are shared with `anon_client`)."""

    def make(email: str = "learner@example.com", is_admin: bool = False) -> TestClient:
        with Session(engine) as session:
            user = User(google_sub=f"sub-{email}", email=email, is_admin=is_admin)
            session.add(user)
            session.commit()
            session.refresh(user)
            token = create_login_session(session, user)
        client = TestClient(app)
        client.cookies.set(SESSION_COOKIE, token)
        return client

    return make


@pytest.fixture
def client(make_client) -> TestClient:
    """Signed in as an ordinary learner. Most tests use this one."""
    return make_client()
