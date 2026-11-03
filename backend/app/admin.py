"""Small admin commands. Run from the backend folder (or inside the container):

    python -m app.admin invite --count 3 --note "classmates"
    python -m app.admin invites
    python -m app.admin usage
    python -m app.admin assign-orphans you@gmail.com
"""

import argparse
import secrets

from sqlalchemy import func, update
from sqlmodel import Session, select

from app.auth import normalize_invite
from app.config import get_settings
from app.db import create_db_and_tables, engine
from app.models import Essay, Invite, UsageLog, User
from app.services.usage import spent_this_month

# No 0/O or 1/I, so codes can be read out or copied by hand
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _new_code() -> str:
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def create_invites(session: Session, count: int, note: str | None) -> list[str]:
    codes = [_new_code() for _ in range(count)]
    session.add_all(Invite(code=normalize_invite(c), note=note) for c in codes)
    session.commit()
    return codes


def cmd_invite(session: Session, args: argparse.Namespace) -> None:
    for code in create_invites(session, args.count, args.note):
        print(code)


def cmd_invites(session: Session, args: argparse.Namespace) -> None:
    rows = session.exec(select(Invite, User).join(User, Invite.used_by_id == User.id, isouter=True))
    for invite, user in rows:
        status = f"used by {user.email}" if user else "unused"
        print(f"{invite.code}  {status:40}  {invite.note or ''}")


def cmd_usage(session: Session, args: argparse.Namespace) -> None:
    budget = get_settings().monthly_budget_usd
    print(f"This month: ${spent_this_month(session):.4f} of ${budget:.2f}")
    per_user = session.exec(
        select(User.email, func.count(func.distinct(UsageLog.request_id)), func.sum(UsageLog.cost_usd))
        .join(UsageLog, UsageLog.user_id == User.id)
        .group_by(User.id)
        .order_by(func.sum(UsageLog.cost_usd).desc())
    )
    for email, actions, cost in per_user:
        print(f"  {email:40} {actions:5} actions  ${cost:.4f}  (all time)")


def cmd_assign_orphans(session: Session, args: argparse.Namespace) -> None:
    """Essays written before login existed have no owner. Give them to one account."""
    user = session.exec(select(User).where(User.email == args.email.lower())).first()
    if user is None:
        raise SystemExit(f"No user with email {args.email}. Sign in once first.")
    result = session.exec(update(Essay).where(Essay.user_id.is_(None)).values(user_id=user.id))
    session.commit()
    print(f"Assigned {result.rowcount} essays to {user.email}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.admin")
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("invite", help="create invite codes")
    p.add_argument("--count", type=int, default=1)
    p.add_argument("--note", help="who the codes are for")
    p.set_defaults(func=cmd_invite)

    sub.add_parser("invites", help="list invite codes").set_defaults(func=cmd_invites)
    sub.add_parser("usage", help="AI spend this month and per user").set_defaults(func=cmd_usage)

    p = sub.add_parser("assign-orphans", help="give essays without an owner to a user")
    p.add_argument("email")
    p.set_defaults(func=cmd_assign_orphans)

    args = parser.parse_args()
    create_db_and_tables()
    with Session(engine) as session:
        args.func(session, args)


if __name__ == "__main__":
    main()
