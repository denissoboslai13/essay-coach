from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db import get_session
from app.models import Essay
from app.schemas import TopicsOut
from app.topics import pick_topics

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_model=TopicsOut)
def get_topics(harder: bool = False, session: Session = Depends(get_session)) -> TopicsOut:
    finished = set(session.exec(select(Essay.topic).where(Essay.completed)))
    return TopicsOut(topics=pick_topics(harder, exclude=finished))
