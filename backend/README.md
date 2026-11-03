# Essay Coach – backend

FastAPI + SQLite (SQLModel) + Anthropic SDK.

## Setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # then put your key into ANTHROPIC_API_KEY
```

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
  main.py            FastAPI app, CORS, error handler
  config.py          settings from environment / .env
  db.py              SQLite engine and session
  models.py          tables: Essay -> Revision -> Issue
  schemas.py         API shapes, modifiers, AI output schema
  topics.py          fixed topic lists
  routers/           HTTP endpoints
  services/feedback.py  the write -> feedback -> revise loop
  ai/provider.py     the only module that calls the AI vendor
  ai/prompts.py      prompt text (normal vs strict, modifiers)
tests/
  fixtures/film_evening.json  test essay with 15 known errors + key
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/topics?harder=false` | 3 random topics |
| POST | `/essays` | start an essay: `{topic, modifiers}` |
| GET | `/essays`, `/essays/{id}` | essays with all revisions and issues |
| POST | `/essays/{id}/revisions` | submit text, get up to 5 issues |
| POST | `/issues/{id}/dispute` | "I don't think that is an error" -> rule explanation |
