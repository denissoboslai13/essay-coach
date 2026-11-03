import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401  (registers the tables)
from app.ai.provider import get_provider
from app.db import get_session
from app.main import app
from app.schemas import AIFeedback, AIIssue, AIPreviousIssueCheck, AIRuleExplanation


class FakeProvider:
    """Returns queued responses instead of calling a real AI. Records every call."""

    def __init__(self) -> None:
        self.responses: list = []
        self.calls: list[dict] = []

    def generate(self, *, system, user, output):
        self.calls.append({"system": system, "user": user, "output": output})
        response = self.responses.pop(0)
        assert isinstance(response, output)
        return response


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


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def client(provider: FakeProvider):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_provider] = lambda: provider
    # Not used as a context manager, so the lifespan (real DB file) does not run
    yield TestClient(app)
    app.dependency_overrides.clear()
