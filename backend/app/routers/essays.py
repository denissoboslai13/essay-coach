from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.ai.provider import AIProvider, get_provider
from app.auth import get_current_user
from app.config import get_settings
from app.db import get_session
from app.models import Essay, Issue, User
from app.schemas import DisputeCreate, EssayCreate, EssayOut, FeedbackOut, IssueOut, RevisionCreate
from app.services import feedback
from app.services.usage import MeteredAI

router = APIRouter(tags=["essays"])


def _metered(kind: str):
    """Dependency: the AI provider wrapped with the limits and usage log of the current user."""

    def dependency(
        session: Session = Depends(get_session),
        user: User = Depends(get_current_user),
        provider: AIProvider = Depends(get_provider),
    ) -> MeteredAI:
        return MeteredAI(provider, session, user, kind)

    return dependency


def _get_essay_or_404(session: Session, essay_id: int, user: User) -> Essay:
    essay = session.get(Essay, essay_id)
    # Someone else's essay looks exactly like a missing one, so ids can't be probed
    if essay is None or essay.user_id != user.id:
        raise HTTPException(status_code=404, detail="Essay not found")
    return essay


@router.post("/essays", response_model=EssayOut, status_code=201)
def create_essay(
    body: EssayCreate, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> Essay:
    essay = Essay(user_id=user.id, topic=body.topic, modifiers=body.modifiers.model_dump())
    session.add(essay)
    session.commit()
    session.refresh(essay)
    return essay


@router.get("/essays", response_model=list[EssayOut])
def list_essays(session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> list[Essay]:
    return list(session.exec(select(Essay).where(Essay.user_id == user.id).order_by(Essay.created_at.desc())))


@router.get("/essays/{essay_id}", response_model=EssayOut)
def get_essay(essay_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> Essay:
    return _get_essay_or_404(session, essay_id, user)


@router.post("/essays/{essay_id}/revisions", response_model=FeedbackOut)
def submit_revision(
    essay_id: int,
    body: RevisionCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
    ai: MeteredAI = Depends(_metered("review")),
) -> FeedbackOut:
    if len(body.text) > get_settings().max_essay_chars:
        raise HTTPException(status_code=413, detail="Essay is too long")
    essay = _get_essay_or_404(session, essay_id, user)
    return feedback.review_revision(session, ai, essay, body.text)


@router.post("/issues/{issue_id}/dispute", response_model=IssueOut)
def dispute_issue(
    issue_id: int,
    body: DisputeCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
    ai: MeteredAI = Depends(_metered("dispute")),
) -> Issue:
    issue = session.get(Issue, issue_id)
    if issue is None or issue.revision.essay.user_id != user.id:
        raise HTTPException(status_code=404, detail="Issue not found")
    return feedback.explain_disputed_issue(session, ai, issue, body.comment)
