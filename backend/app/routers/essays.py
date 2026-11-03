from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.ai.provider import AIProvider, get_provider
from app.config import get_settings
from app.db import get_session
from app.models import Essay, Issue
from app.schemas import DisputeCreate, EssayCreate, EssayOut, FeedbackOut, IssueOut, RevisionCreate
from app.services import feedback

router = APIRouter(tags=["essays"])


def _get_essay_or_404(session: Session, essay_id: int) -> Essay:
    essay = session.get(Essay, essay_id)
    if essay is None:
        raise HTTPException(status_code=404, detail="Essay not found")
    return essay


@router.post("/essays", response_model=EssayOut, status_code=201)
def create_essay(body: EssayCreate, session: Session = Depends(get_session)) -> Essay:
    essay = Essay(topic=body.topic, modifiers=body.modifiers.model_dump())
    session.add(essay)
    session.commit()
    session.refresh(essay)
    return essay


@router.get("/essays", response_model=list[EssayOut])
def list_essays(session: Session = Depends(get_session)) -> list[Essay]:
    return list(session.exec(select(Essay).order_by(Essay.created_at.desc())))


@router.get("/essays/{essay_id}", response_model=EssayOut)
def get_essay(essay_id: int, session: Session = Depends(get_session)) -> Essay:
    return _get_essay_or_404(session, essay_id)


@router.post("/essays/{essay_id}/revisions", response_model=FeedbackOut)
def submit_revision(
    essay_id: int,
    body: RevisionCreate,
    session: Session = Depends(get_session),
    provider: AIProvider = Depends(get_provider),
) -> FeedbackOut:
    if len(body.text) > get_settings().max_essay_chars:
        raise HTTPException(status_code=413, detail="Essay is too long")
    essay = _get_essay_or_404(session, essay_id)
    return feedback.review_revision(session, provider, essay, body.text)


@router.post("/issues/{issue_id}/dispute", response_model=IssueOut)
def dispute_issue(
    issue_id: int,
    body: DisputeCreate,
    session: Session = Depends(get_session),
    provider: AIProvider = Depends(get_provider),
) -> Issue:
    issue = session.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return feedback.explain_disputed_issue(session, provider, issue, body.comment)
