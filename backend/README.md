# Essay Coach – backend

FastAPI + SQLite (SQLModel) + Anthropic SDK. Google sign-in, invite-only registration, daily and monthly cost limits.

## Setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # then put your key into ANTHROPIC_API_KEY
```

`LOCAL_MODE=true` (the default in `.env.example`): no login, one built-in local account, no daily limits.
To try the hosted sign-in locally, set `LOCAL_MODE=false`, `GOOGLE_CLIENT_ID` and `ADMIN_EMAILS`
(see `../deploy/README.md`). Docker always runs with `LOCAL_MODE=false`.

## Run

```powershell
uvicorn app.main:app --reload
```

Interactive API docs: http://localhost:8000/docs

## Tests

```powershell
pytest                       # fast tests with a fake AI, no key needed
pytest tests/test_live.py -s # real AI on the fixture essay (needs key, costs a few calls)
```

## Layout

```
app/
  main.py            FastAPI app, CORS, error handlers
  site.py            production entry: API under /api + built frontend (Docker)
  auth.py            Google sign-in, invites, cookie sessions, current user
  admin.py           CLI: invite codes, usage, assign old essays
  config.py          settings from environment / .env
  db.py              SQLite engine and session
  models.py          tables: User -> Essay -> Revision -> Issue, LoginSession, Invite, UsageLog
  schemas.py         API shapes, modifiers, AI output schema
  topics.py          fixed topic lists
  routers/           HTTP endpoints
  services/feedback.py  the write -> feedback -> revise loop
  services/usage.py  prices, usage log, daily and monthly limits
  ai/provider.py     the only module that calls the AI vendor
  ai/prompts.py      prompt text (normal vs strict, modifiers)
tests/
  fixtures/film_evening.json  test essay with 15 known errors + key
```

## Endpoints

All endpoints except `/auth/config`, `/auth/google` and `/health` need a signed-in user,
and only return that user's own data.

| Method | Path | Purpose |
|---|---|---|
| GET | `/auth/config` | Google client id, whether dev login is on |
| POST | `/auth/google` | `{credential, invite_code?}` -> session cookie |
| POST | `/auth/logout` | end the session |
| GET | `/auth/me` | email, admin flag, checks left today |
| GET | `/topics?harder=false` | 3 random topics |
| POST | `/essays` | start an essay: `{topic, modifiers}` |
| GET | `/essays`, `/essays/{id}` | essays with all revisions and issues |
| POST | `/essays/{id}/revisions` | submit text, get up to 5 issues |
| POST | `/issues/{id}/dispute` | "I don't think that is an error" -> rule explanation |

Reviews and disputes return 429 when the daily limit or the monthly budget is used up.
