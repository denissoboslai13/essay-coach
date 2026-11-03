"""Database tables.

User 1 -- n Essay 1 -- n Revision 1 -- n Issue
Every submission of the text is a new Revision, so we keep the full history
(which issues were found in which round) for later progress tracking.

LoginSession, Invite and UsageLog support login, invite-only registration and cost limits.
"""

from datetime import datetime, timezone

from sqlmodel import JSON, Column, Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    # Google's stable account id ("sub" claim). Emails can change, this does not
    google_sub: str = Field(unique=True, index=True)
    email: str = Field(index=True)
    name: str | None = None
    is_admin: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class LoginSession(SQLModel, table=True):
    __tablename__ = "login_session"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    # SHA-256 of the cookie value, so a leaked database does not leak usable sessions
    token_hash: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime


class Invite(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)
    # Who it was meant for, as a reminder for the admin
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    used_by_id: int | None = Field(default=None, foreign_key="user.id")
    used_at: datetime | None = None


class UsageLog(SQLModel, table=True):
    """One row per AI call, with its cost. Basis for the daily and monthly limits."""

    __tablename__ = "usage_log"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    # One user action (a review or a dispute) can make several AI calls (leak retry)
    request_id: str = Field(index=True)
    kind: str  # "review" | "dispute"
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    created_at: datetime = Field(default_factory=utcnow, index=True)


class Essay(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    # Nullable only for essays written before login existed (see `python -m app.admin assign-orphans`)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    topic: str
    # Snapshot of the difficulty modifiers active for this essay (see schemas.Modifiers)
    modifiers: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    # Set when a revision comes back with no issues
    completed: bool = False
    created_at: datetime = Field(default_factory=utcnow)

    revisions: list["Revision"] = Relationship(
        back_populates="essay",
        sa_relationship_kwargs={"order_by": "Revision.round"},
    )


class Revision(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    essay_id: int = Field(foreign_key="essay.id", index=True)
    round: int
    text: str
    word_count: int
    # One sentence about what the author does well (from the AI)
    strength: str | None = None
    created_at: datetime = Field(default_factory=utcnow)

    essay: Essay = Relationship(back_populates="revisions")
    issues: list["Issue"] = Relationship(
        back_populates="revision",
        sa_relationship_kwargs={"order_by": "Issue.rank"},
    )


class Issue(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    revision_id: int = Field(foreign_key="revision.id", index=True)
    # 1 = most important
    rank: int
    category: str
    passage: str
    problem: str
    question: str

    # Filled in by the next round: was this issue fixed in the revised text?
    resolution: str | None = None  # "fixed" | "not_fixed"
    resolution_comment: str | None = None

    # "I don't think that is an error" flow
    disputed: bool = False
    dispute_comment: str | None = None
    rule_explanation: str | None = None
    # "error" | "acceptable" | "style_preference". Anything but "error" dismisses the issue
    dispute_verdict: str | None = None
    # Dismissed issues are not flagged again in later rounds of the same essay
    dismissed: bool = False

    revision: Revision = Relationship(back_populates="issues")
