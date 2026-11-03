"""Cost control: every AI call is logged with its price, and limits are checked before calling.

Limits:
- per user and day: number of reviews and of disputes (admins are exempt)
- for the whole app and month: total spend in USD (applies to everyone, admins too)
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import TypeVar
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from app.ai.provider import AIProvider
from app.config import get_settings
from app.models import UsageLog, User, utcnow

T = TypeVar("T", bound=BaseModel)

# USD per million tokens (input, output), from Anthropic's price list (checked 2026-11).
# Haiku costs more above 100K input tokens, which essays here never reach.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-fable-5-1": (10.00, 50.00),
}
# Unknown model: assume the most expensive one, so the budget errs on the safe side
FALLBACK_PRICE = max(PRICES.values())

ACTION_NOUNS = {"review": "checks", "dispute": "rule explanations"}


class QuotaExceeded(Exception):
    """A daily or monthly limit is reached. Shown to the user as is."""


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = next((p for m, p in PRICES.items() if model.startswith(m)), FALLBACK_PRICE)
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def model_for(user: User) -> str:
    settings = get_settings()
    return (settings.anthropic_admin_model if user.is_admin else "") or settings.anthropic_model


def daily_limit(kind: str) -> int:
    settings = get_settings()
    return settings.daily_reviews_per_user if kind == "review" else settings.daily_disputes_per_user


def _start_of_day() -> datetime:
    return utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_month() -> datetime:
    return _start_of_day().replace(day=1)


def actions_today(session: Session, user_id: int, kind: str) -> int:
    """Counts user actions, not AI calls: a leak retry is part of the same action."""
    query = select(func.count(func.distinct(UsageLog.request_id))).where(
        UsageLog.user_id == user_id, UsageLog.kind == kind, UsageLog.created_at >= _start_of_day()
    )
    return session.exec(query).one()


def spent_this_month(session: Session) -> float:
    query = select(func.coalesce(func.sum(UsageLog.cost_usd), 0.0)).where(UsageLog.created_at >= _start_of_month())
    return session.exec(query).one()


def budget_reached(session: Session) -> bool:
    return spent_this_month(session) >= get_settings().monthly_budget_usd


def check_quota(session: Session, user: User, kind: str) -> None:
    if budget_reached(session):
        raise QuotaExceeded("Essay Coach has used up its AI budget for this month. Please come back next month.")
    limit = daily_limit(kind)
    if not user.is_admin and actions_today(session, user.id, kind) >= limit:
        raise QuotaExceeded(f"You have used all {limit} {ACTION_NOUNS[kind]} for today. Come back tomorrow.")


_busy_users: set[int] = set()
_busy_lock = threading.Lock()


@contextmanager
def one_action_at_a_time(user_id: int) -> Iterator[None]:
    """Without this, many requests sent at once would all pass the daily limit check before
    the first one is logged. Works within one process (the Docker image runs one)."""
    with _busy_lock:
        if user_id in _busy_users:
            raise QuotaExceeded("Another check is still running. Wait for it to finish, then try again.")
        _busy_users.add(user_id)
    try:
        yield
    finally:
        with _busy_lock:
            _busy_users.discard(user_id)


def remaining_today(session: Session, user: User, kind: str) -> int | None:
    """None = no daily limit (admin)."""
    if user.is_admin:
        return None
    return max(0, daily_limit(kind) - actions_today(session, user.id, kind))


class MeteredAI:
    """The provider as seen by one user action (one review or one dispute).

    Checks the limits before the first AI call and logs the tokens of every call.
    Its `generate` returns the parsed output only, so the feedback services don't deal with costs.
    """

    def __init__(self, provider: AIProvider, session: Session, user: User, kind: str) -> None:
        self._provider = provider
        self._session = session
        self._user = user
        self._kind = kind
        self._request_id = uuid4().hex
        self._checked = False

    def generate(self, *, system: str, user: str, output: type[T]) -> T:
        if not self._checked:
            check_quota(self._session, self._user, self._kind)
            self._checked = True
        result = self._provider.generate(system=system, user=user, output=output, model=model_for(self._user))
        self._session.add(
            UsageLog(
                user_id=self._user.id,
                request_id=self._request_id,
                kind=self._kind,
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost_usd=cost_usd(result.model, result.input_tokens, result.output_tokens),
            )
        )
        # Committed right away, so the cost is recorded even if a later step of the action fails
        self._session.commit()
        return result.output
