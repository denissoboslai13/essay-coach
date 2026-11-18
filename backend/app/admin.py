"""Small admin commands. Run from the backend folder (or inside the container):

    python -m app.admin invite --count 3 --note "classmates"
    python -m app.admin invites
    python -m app.admin usage
    python -m app.admin assign-orphans you@gmail.com
    python -m app.admin delete-user someone@gmail.com
    python -m app.admin backup
"""

import argparse
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, update
from sqlmodel import Session, select

from app.auth import normalize_invite
from app.config import get_settings
from app.db import create_db_and_tables, engine
from app.models import Essay, Invite, UsageLog, User
from app.services.account import delete_account
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
        status = f"used by {user.email}" if user else "used (account deleted)" if invite.used_at else "unused"
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


def cmd_delete_user(session: Session, args: argparse.Namespace) -> None:
    """For deletion requests that come by email. Same as the "Delete account" button."""
    user = session.exec(select(User).where(User.email == args.email.lower())).first()
    if user is None:
        raise SystemExit(f"No user with email {args.email}.")
    essays = len(session.exec(select(Essay.id).where(Essay.user_id == user.id)).all())
    if not args.yes and input(f"Delete {user.email} and {essays} essays? Type 'yes': ").strip() != "yes":
        raise SystemExit("Cancelled.")
    delete_account(session, user)
    print(f"Deleted {args.email} and {essays} essays")


def backup_database(target_dir: Path, keep: int) -> Path:
    """Consistent copy of the SQLite database (safe while the app is running), checked for
    corruption. Keeps the newest `keep` copies in `target_dir` and deletes older ones."""
    source_path = engine.url.database
    if engine.url.get_backend_name() != "sqlite" or not source_path or source_path == ":memory:":
        raise SystemExit("Backups only work for a SQLite database file.")
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = target_dir / f"essay_coach-{stamp}.db"

    source = sqlite3.connect(source_path)
    copy = sqlite3.connect(target)
    try:
        source.backup(copy)
        result = copy.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        copy.close()
        source.close()
    if result != "ok":
        target.unlink()
        raise SystemExit(f"Backup failed the integrity check: {result}")

    for old in sorted(target_dir.glob("essay_coach-*.db"))[:-keep]:
        old.unlink()
    return target


def cmd_backup(session: Session, args: argparse.Namespace) -> None:
    settings = get_settings()
    target = backup_database(Path(args.dir or settings.backup_dir), args.keep or settings.backup_keep)
    print(f"Backup written to {target}")


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

    p = sub.add_parser("delete-user", help="delete an account and all its essays")
    p.add_argument("email")
    p.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    p.set_defaults(func=cmd_delete_user)

    p = sub.add_parser("backup", help="copy the database to BACKUP_DIR, keep the newest BACKUP_KEEP copies")
    p.add_argument("--dir", help="overrides BACKUP_DIR")
    p.add_argument("--keep", type=int, help="overrides BACKUP_KEEP")
    p.set_defaults(func=cmd_backup)

    args = parser.parse_args()
    create_db_and_tables()
    with Session(engine) as session:
        args.func(session, args)


if __name__ == "__main__":
    main()
