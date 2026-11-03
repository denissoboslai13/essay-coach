"""Login with Google, invite-only registration and cookie sessions.

Flow: the frontend shows Google's sign-in button and gets an ID token (a JWT signed by Google).
The backend verifies it, finds or registers the user, and sets an httpOnly session cookie.
No passwords are stored anywhere.

LOCAL_MODE (running it on your own machine) skips all of this: every request belongs to one local account.
"""

import hashlib
import ipaddress
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import delete, update
from sqlmodel import Session, select

from app.config import get_settings
from app.db import get_session
from app.models import Essay, Invite, LoginSession, User, utcnow
from app.schemas import AuthConfigOut, GoogleLogin, MeOut, QuotaOut
from app.services import usage

SESSION_COOKIE = "ec_session"
# Sent as `detail` when an unknown account signs in without a code, so the frontend asks for one
INVITE_REQUIRED = "invite_required"
# The single account used in LOCAL_MODE ("local" can never be a real Google id)
LOCAL_SUB = "local"
LOCAL_EMAIL = "local@localhost"
LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_invite(code: str) -> str:
    """Codes look like ABCD-EFGH. Accept lower case and missing or extra spaces."""
    return "".join(code.split()).upper()


def verify_google_token(credential: str) -> dict:
    """Checks Google's signature, expiry, audience (our client id) and issuer.
    Returns the token's claims. Raises ValueError if the token is not valid."""
    client_id = get_settings().google_client_id
    if not client_id:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured (GOOGLE_CLIENT_ID)")
    return id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)


def create_login_session(session: Session, user: User) -> str:
    """Stores a new session and returns the token for the cookie."""
    token = secrets.token_urlsafe(32)
    session.add(
        LoginSession(
            user_id=user.id,
            token_hash=_hash(token),
            expires_at=utcnow() + timedelta(days=get_settings().session_days),
        )
    )
    # Housekeeping: drop everyone's expired sessions
    session.exec(delete(LoginSession).where(LoginSession.expires_at <= utcnow()))
    session.commit()
    return token


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 24 * 3600,
        httponly=True,  # not readable from JavaScript
        secure=settings.cookie_secure,
        samesite="lax",  # not sent with cross-site POSTs, which blocks CSRF
        path="/",
    )


def local_user(session: Session) -> User:
    """LOCAL_MODE: one fixed account for whoever runs the app on their own machine with their own key.
    Created on first use, admin (no daily limits). It also takes over essays without an owner."""
    user = session.exec(select(User).where(User.google_sub == LOCAL_SUB)).first()
    if user is None:
        user = User(google_sub=LOCAL_SUB, email=LOCAL_EMAIL, is_admin=True)
        session.add(user)
        session.flush()
        session.exec(update(Essay).where(Essay.user_id.is_(None)).values(user_id=user.id))
        session.commit()
        session.refresh(user)
    return user


def is_local_request(request: Request) -> bool:
    """True only for a browser on this machine. A tunnel or a public server sends another Host,
    and a direct connection from outside has a non-loopback client address."""
    if request.url.hostname not in LOCAL_HOSTNAMES or request.client is None:
        return False
    try:
        return ipaddress.ip_address(request.client.host).is_loopback
    except ValueError:
        return False


def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    """FastAPI dependency for every endpoint that needs a signed-in user."""
    if get_settings().local_mode:
        # Local mode means no login and no limits on the owner's key, so it must never be reachable from outside
        if not is_local_request(request):
            raise HTTPException(status_code=403, detail="Local mode only works on localhost.")
        return local_user(session)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        query = select(LoginSession).where(LoginSession.token_hash == _hash(token), LoginSession.expires_at > utcnow())
        login = session.exec(query).first()
        if login and (user := session.get(User, login.user_id)):
            return user
    raise HTTPException(status_code=401, detail="Please sign in")


def _register_with_invite(session: Session, user: User, code: str | None) -> None:
    if not code:
        raise HTTPException(status_code=403, detail=INVITE_REQUIRED)
    session.add(user)
    session.flush()
    # Conditional update, so two people can't use the same code at the same moment
    claimed = session.exec(
        update(Invite)
        .where(Invite.code == normalize_invite(code), Invite.used_by_id.is_(None))
        .values(used_by_id=user.id, used_at=utcnow())
    )
    if claimed.rowcount != 1:
        session.rollback()
        raise HTTPException(status_code=403, detail="This invite code is not valid or has already been used.")


def find_or_register(session: Session, *, sub: str, email: str, name: str | None, invite_code: str | None) -> User:
    email = email.lower()
    is_admin = email in get_settings().admin_email_set
    user = session.exec(select(User).where(User.google_sub == sub)).first()
    if user:
        # Keep the profile and the admin flag in sync with Google and the settings
        user.email, user.name, user.is_admin = email, name, is_admin
    else:
        user = User(google_sub=sub, email=email, name=name, is_admin=is_admin)
        if not is_admin:
            _register_with_invite(session, user, invite_code)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def me_out(session: Session, user: User) -> MeOut:
    settings = get_settings()
    return MeOut(
        email=user.email,
        name=user.name,
        is_admin=user.is_admin,
        local_mode=settings.local_mode,
        quota=QuotaOut(
            reviews_left=usage.remaining_today(session, user, "review"),
            daily_reviews=settings.daily_reviews_per_user,
            disputes_left=usage.remaining_today(session, user, "dispute"),
            daily_disputes=settings.daily_disputes_per_user,
            budget_reached=usage.budget_reached(session),
        ),
    )


@router.get("/config", response_model=AuthConfigOut)
def auth_config() -> AuthConfigOut:
    return AuthConfigOut(google_client_id=get_settings().google_client_id)


@router.post("/google", response_model=MeOut)
def google_login(body: GoogleLogin, response: Response, session: Session = Depends(get_session)) -> MeOut:
    try:
        claims = verify_google_token(body.credential)
    except ValueError:
        raise HTTPException(status_code=401, detail="Google sign-in failed. Please try again.")
    if not claims.get("email_verified"):
        raise HTTPException(status_code=401, detail="The email address of your Google account is not verified.")
    user = find_or_register(
        session, sub=claims["sub"], email=claims["email"], name=claims.get("name"), invite_code=body.invite_code
    )
    _set_session_cookie(response, create_login_session(session, user))
    return me_out(session, user)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, session: Session = Depends(get_session)) -> None:
    if token := request.cookies.get(SESSION_COOKIE):
        session.exec(delete(LoginSession).where(LoginSession.token_hash == _hash(token)))
        session.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> MeOut:
    return me_out(session, user)
