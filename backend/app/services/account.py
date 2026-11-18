"""Deleting an account (GDPR "right to erasure").

Deleted: the user, their essays with all revisions and issues, and their login sessions.
Kept without a link to the person: the usage log (tokens and price), so the monthly budget
stays correct, and the invite code they used, so it can't be used a second time.
"""

from sqlalchemy import delete, update
from sqlmodel import Session, select

from app.models import Essay, Invite, Issue, LoginSession, Revision, UsageLog, User


def delete_account(session: Session, user: User) -> None:
    essay_ids = select(Essay.id).where(Essay.user_id == user.id)
    revision_ids = select(Revision.id).where(Revision.essay_id.in_(essay_ids))

    session.exec(delete(Issue).where(Issue.revision_id.in_(revision_ids)))
    session.exec(delete(Revision).where(Revision.essay_id.in_(essay_ids)))
    session.exec(delete(Essay).where(Essay.user_id == user.id))
    session.exec(delete(LoginSession).where(LoginSession.user_id == user.id))
    session.exec(update(UsageLog).where(UsageLog.user_id == user.id).values(user_id=None))
    session.exec(update(Invite).where(Invite.used_by_id == user.id).values(used_by_id=None))
    session.delete(user)
    session.commit()
