from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.models import Essay, User
from app.schemas import TopicsOut
from app.topics import pick_topics

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_model=TopicsOut)
def get_topics(
    harder: bool = False, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> TopicsOut:
    finished = set(session.exec(select(Essay.topic).where(Essay.completed, Essay.user_id == user.id)))
    return TopicsOut(topics=pick_topics(harder, exclude=finished))
