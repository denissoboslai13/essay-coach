"""Request/response shapes for the HTTP API and for the AI's structured output."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field

# --- Difficulty modifiers -------------------------------------------------

# How far above the word target an essay may go (like exam tasks: "about 350 words")
WORD_LIMIT_TOLERANCE = 0.10


class Modifiers(BaseModel):
    """All optional. Stored with every essay so progress can be compared like with like."""

    strict_grading: bool = False
    timer_minutes: int | None = Field(default=None, ge=1, le=180)
    harder_topics: bool = False
    # Word count target. Below it the AI flags underdevelopment, above max_words submission is refused
    min_words: int | None = Field(default=None, ge=50, le=2000)
    # Enforced only in the frontend (and bypassable), stored for the record
    paste_lock: bool = False

    @computed_field
    @property
    def max_words(self) -> int | None:
        return int(self.min_words * (1 + WORD_LIMIT_TOLERANCE)) if self.min_words else None


# --- AI structured output -------------------------------------------------

IssueCategory = Literal[
    "grammar",
    "vocabulary",
    "phraseology",
    "syntax",
    "cohesion",
    "conventions",
    "structure",
    "argumentation",
    "style",
]


class AIIssue(BaseModel):
    passage: str = Field(description="Exact passage copied from the essay, a phrase or sentence, not a single word.")
    category: IssueCategory
    problem: str = Field(description="Short, plain explanation of what is wrong. No corrected version.")
    question: str = Field(description="Guiding question that leads the writer to find the fix themselves.")


class AIPreviousIssueCheck(BaseModel):
    number: int = Field(description="Number of the issue in the list of issues from the previous round.")
    status: Literal["fixed", "not_fixed"]
    comment: str = Field(
        description="If fixed: one short sentence confirming why the new version is correct. "
        "If not fixed: one short sentence saying it still needs work. Never give the correction."
    )


class AIFeedback(BaseModel):
    previous_issues: list[AIPreviousIssueCheck] = Field(
        description="One entry per issue from the previous round. Empty if there was no previous round."
    )
    issues: list[AIIssue] = Field(description="At most 5 issues, most important first. Empty only if no issues remain.")
    strength: str = Field(description="One sentence about what the author does well.")


DisputeVerdict = Literal["error", "acceptable", "style_preference"]


class AIRuleExplanation(BaseModel):
    explanation: str = Field(description="Plain explanation of the rule and a clear verdict. Never the corrected version.")
    verdict: DisputeVerdict = Field(
        description="error = the passage really is wrong; acceptable = the passage is correct; "
        "style_preference = not an error, just one of several valid choices."
    )


# --- HTTP API -------------------------------------------------------------


class TopicsOut(BaseModel):
    topics: list[str]


class EssayCreate(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    modifiers: Modifiers = Modifiers()


class RevisionCreate(BaseModel):
    text: str = Field(min_length=1)


class DisputeCreate(BaseModel):
    comment: str | None = Field(default=None, max_length=1000)


class IssueOut(BaseModel):
    id: int
    rank: int
    category: str
    passage: str
    problem: str
    question: str
    resolution: str | None
    resolution_comment: str | None
    disputed: bool
    dispute_comment: str | None
    rule_explanation: str | None
    dispute_verdict: DisputeVerdict | None
    dismissed: bool


class RevisionOut(BaseModel):
    id: int
    round: int
    text: str
    word_count: int
    strength: str | None
    created_at: datetime
    issues: list[IssueOut]


class FeedbackOut(BaseModel):
    """Response to a submitted revision."""

    status: Literal["issues_found", "no_issues", "too_short", "too_long"]
    message: str | None = None
    revision: RevisionOut | None = None
    # Issues from the previous round, now with `resolution` filled in
    previous_issues: list[IssueOut] = []


class EssayOut(BaseModel):
    id: int
    topic: str
    modifiers: Modifiers
    completed: bool
    created_at: datetime
    revisions: list[RevisionOut]


# --- Login ----------------------------------------------------------------


class AuthConfigOut(BaseModel):
    """Public settings the login screen needs."""

    google_client_id: str


class GoogleLogin(BaseModel):
    # ID token from Google Identity Services (a signed JWT)
    credential: str = Field(min_length=1, max_length=4096)
    # Needed only the first time an account signs in
    invite_code: str | None = Field(default=None, max_length=64)


class QuotaOut(BaseModel):
    """What is left today. `None` = no daily limit (admin)."""

    reviews_left: int | None
    daily_reviews: int
    disputes_left: int | None
    daily_disputes: int
    budget_reached: bool


class MeOut(BaseModel):
    email: str
    name: str | None
    is_admin: bool
    # LOCAL_MODE: no login, so the frontend hides "Sign out"
    local_mode: bool
    quota: QuotaOut
