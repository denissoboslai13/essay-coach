"""Database tables.

Essay 1 -- n Revision 1 -- n Issue
Every submission of the text is a new Revision, so we keep the full history
(which issues were found in which round) for later progress tracking.
"""

from datetime import datetime, timezone

from sqlmodel import JSON, Column, Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Essay(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
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
