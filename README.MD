# Essay Coach

**An aid, not a shortcut.** Essay Coach helps self-taught English learners get better at writing essays _themselves_. It never writes or rewrites your text. It points to a passage, says what the problem is, and asks a guiding question, so **you** find and make the fix.

> **Status: prototype finished (2026-11-25).** Semester project for the course _AI Lab v praxi_, built by one person.
> All features in scope are built and tested. The only step left is running it on a home server with an own domain (see [Roadmap](#roadmap)).
> You can run it on your own computer with your own Anthropic API key (**BYOK**, no login needed).
> An invite-only hosted version with Google sign-in is built and will run on a home server (see [Hosting](#hosting-it-for-others)).

---

## Who it is for

- **Primary:** self-taught English learners who write essays alone and get no feedback, so they repeat the same mistakes without noticing.
- **Secondary:** anyone who wants to improve their English writing.

Why it exists: more and more people let AI write their essays for them. Essay Coach goes the other way. AI only gives feedback, and the learner does the writing.

## What it does

1. **Pick a topic.** You get 3 topics (normal or harder), each of a different essay type, and choose one. There are 76 topics in six types (opinion, both views, advantages and disadvantages, problem and solution, report, narrative). They were drafted by AI once and reviewed by hand; no AI call is made to pick them. Topics you have finished are not offered again.
2. **Write.** The editor shows a word count. You can turn on a timer and a paste lock. Browser spellcheck is off on purpose.
3. **Get feedback.** You get at most **5 errors** per round (7 with stricter grading), most important first: meaning-changing problems, then repeated patterns, then small things. Each issue has:
   - the **passage** from your text (highlighted in the editor on hover),
   - **what the problem is**, in short plain English,
   - a **guiding question**, never the fix.
4. **Revise and resubmit.** Every round checks the whole text again and shows which earlier errors you fixed. The loop ends only when no errors are found, not just because the flagged items were fixed.
5. **Disagree.** "I don't think that is an error" asks for the rule behind the flag and a verdict. If you were right, or it is a style choice, the passage is not flagged again.

### Errors vs suggestions

An **error** is something wrong: grammar, a wrong word, spelling, punctuation, an unclear sentence, a contradiction, or a text that misses the task (off topic, no conclusion). A **suggestion** is about text that is already correct but could be better (more formal, more precise, more detail).

- Normal grading shows **errors only**.
- Stricter grading also shows up to **3 optional suggestions**, but only once all errors fit in one round.
- Suggestions **never keep the loop going**. Without this split the loop never ended in testing, because the AI always finds something to improve.

### Difficulty modifiers (all optional)

Instead of fixed levels, you switch on what makes writing harder:

| Modifier         | Effect                                                                           |
| ---------------- | -------------------------------------------------------------------------------- |
| Stricter grading | Up to 7 errors per round instead of 5, minor ones included, plus up to 3 optional style suggestions |
| Timer            | Countdown until the first submission                                             |
| Harder topics    | Argumentative / abstract topic list                                              |
| Word target      | Clearly below it: flagged as a structure error. More than 10 % above it: submission refused |
| Paste lock       | Blocks pasting into the editor (a nudge, not a real lock)                        |

The active modifiers are stored with every essay, so progress can later be compared like with like.

### Design rules that always hold

- No rewritten or corrected sentences, **even when the user asks** ("just fix it", "I'm in a hurry").
- A code-level **leak guard** backs up the prompt. If a feedback text contains something that looks like a corrected form of the learner's words, the AI is asked again, and anything still leaking is replaced with a neutral hint.
- Never ends with praise while problems remain. There is one honest sentence about what the author does well.
- No streaks, badges or notifications. Success is writing better _without_ the tool, not time spent in the app.

---

## Running it locally (BYOK)

You need Python 3.14+, Node 22+ and your own [Anthropic API key](https://console.anthropic.com/). Every AI call is billed to **your** key. There is no login: the app runs in **local mode** with one built-in account and no daily limits.

**Backend**

```powershell
git clone https://github.com/denissoboslai13/essay-coach.git
cd essay-coach/backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env
# open .env and put your key after ANTHROPIC_API_KEY=  (that's the only thing you need to fill in)
uvicorn app.main:app --reload
```

**Frontend** (second terminal)

```powershell
cd essay-coach/frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to the backend on port 8000.

**Tests**

```powershell
cd backend
pytest --ignore=tests/test_live.py --ignore=tests/test_live_loop.py   # fast, fake AI, no cost
pytest tests/test_live.py -s         # real AI on the fixture essay (costs a few calls)
pytest tests/test_live_loop.py -s    # real AI, the whole revise loop through the API (~15 calls)
```

> The backend refuses texts under 50 words before any AI call, so short tests cost nothing.

---

## Hosting it for others

The same code runs as an **invite-only** web app, so invited people can use it without their own key. Local mode is then always off.

- **Google sign-in** only. The backend verifies Google's ID token; no passwords are stored. Sessions are httpOnly cookies, stored hashed.
- **Invite codes:** a new account needs a one-time code. Admin accounts (`ADMIN_EMAILS`) don't.
- **Ownership checks:** every user sees only their own essays. Someone else's essay looks like a missing one (404).
- **Cost control:** every AI call is logged with its tokens and price. A **daily limit** per user (checks and rule explanations) and a **monthly budget cap** for the whole app.
- **Docker:** one image, where the backend also serves the built frontend. On the server it sits behind a **Cloudflare Tunnel** on an own domain (no open ports, automatic HTTPS), shared with other projects.
- **Privacy:** a privacy page (`/#privacy`), and users can delete their account and all their essays themselves.
- **Backups:** a daily, integrity-checked copy of the database, the newest 14 are kept.
- **Admin commands:** `python -m app.admin invite | invites | usage | assign-orphans | delete-user | backup`.

Try the hosted setup locally:

```powershell
docker compose up --build      # http://localhost:8000, needs GOOGLE_CLIENT_ID and ADMIN_EMAILS in backend/.env
```

Step-by-step setup (Google Cloud, server, tunnel): [`deploy/README.md`](deploy/README.md).

---

## Tech stack

| Part     | Technology                                                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Backend  | Python 3.14, **FastAPI**, **SQLModel** (SQLAlchemy + Pydantic), SQLite, pydantic-settings                                             |
| AI       | **Anthropic Claude** via the official `anthropic` Python SDK, structured outputs (Pydantic schemas). Default model: Claude Sonnet 5.5 |
| Login    | Google Identity Services + `google-auth` (ID token verification), invite codes, cookie sessions                                       |
| Frontend | **React 19**, **Vite 8**, plain CSS (Courier Prime + IBM Plex Sans)                                                                   |
| Hosting  | Docker Compose, Cloudflare Tunnel                                                                                                      |
| Tests    | pytest with a fake AI provider. Optional live tests against the real API with a fixture essay that has 15 known errors                |

### Architecture

```
browser (React) -> own backend (FastAPI) -> Anthropic API
                         |
                       SQLite
```

- The frontend **never** calls the AI directly. The backend validates requests, holds the API key and enforces limits.
- The API key lives only in environment variables (`backend/.env`, git-ignored).
- The AI vendor sits behind one small module (`backend/app/ai/provider.py`), so it can be swapped (for example for a local model).

```
backend/
  app/
    main.py                 FastAPI app (API)
    site.py                 production entry: API under /api + built frontend
    auth.py                 Google sign-in, invites, sessions, local mode
    admin.py                CLI: invite codes, usage, delete a user, backup
    ai/provider.py          the only module that calls the AI vendor
    ai/prompts.py           prompt text (normal vs strict, modifiers)
    services/feedback.py    write -> feedback -> revise loop
    services/leak_guard.py  "never reveal the correction" backstop
    services/usage.py       prices, usage log, daily and monthly limits
    services/account.py     account deletion
    routers/                HTTP endpoints
  tests/                    pytest, fixtures/film_evening.json
frontend/
  src/                      React components, styles.css
deploy/                     hosting guide, shared Cloudflare tunnel
Dockerfile, docker-compose*.yml
```

More on the API and the code: [`backend/README.md`](backend/README.md).

---

## Roadmap

### Done

- Prototype: topics, editor, feedback loop, disputes, difficulty modifiers, leak guard
- Local BYOK mode without login
- Invite-only hosted version: Google sign-in, invite codes, ownership checks, usage log, daily limits, monthly budget, Docker, admin commands
- Privacy page, account deletion (GDPR), daily database backups
- Errors vs optional suggestions (strict grading: 7 errors + up to 3 suggestions)
- 76 reviewed topics in six essay types
- Final test run (2026-11-25): all fast and live tests pass. The live loop test fixes only what was flagged and resubmits: on the fixture essay it took 5 rounds, found all 15 known errors and never ended early. A corrected essay finishes, instructions hidden in the essay are ignored, an off-topic essay is flagged. Docker image builds and starts.

### Next (the only step left for the semester project)

Deploy on the home server with an own domain, following [`deploy/README.md`](deploy/README.md):

1. Buy the domain and add it to Cloudflare.
2. Google sign-in: add the production URL to the OAuth client.
3. On the server: `backend/.env` (key, `GOOGLE_CLIENT_ID`, `ADMIN_EMAILS`, `PRIVACY_CONTACT`, limits), the shared `web` network and Cloudflare tunnel, then `docker compose -f docker-compose.yml -f docker-compose.server.yml up -d --build`.
4. Set a spend limit in the Anthropic Console as a second line of defence behind `MONTHLY_BUDGET_USD`.
5. Set up an off-server copy of the backups.
6. Sign in as admin, create invite codes, and test the whole flow once on the real domain.

After that:

- **Cheaper model for public users** (e.g. Claude Haiku 5.5), only after it passes the fixture tests

### Planned

- Essay history: see your past essays and revisions
- **Skills map** after about 10 essays or a week, along the six ELLIPSE dimensions (cohesion, syntax, vocabulary, phraseology, grammar, conventions). It needs several essays because one essay is not a reliable measure.
- Warning when the same type of error keeps coming back
- Experiment: **local LLM** on the home server (e.g. via Ollama), compared against Claude on the fixture essay before any switch

### Later ideas

- Mobile app
- Other languages and other text types

---

## Known limits (honest list)

- **Paste lock can be bypassed** (second window, retyping). It is a nudge.
- **Stricter grading via the prompt alone did not work.** In testing (same essay, normal vs strict) the difference between two runs of one mode was bigger than between the modes. So strict now also changes the code path: 7 errors instead of 5, plus optional suggestions.
- **Error vs suggestion is decided by the AI** and is not fully consistent: a borderline point can be an error in one run and a suggestion in the next. Disputing a flag is the way out.
- **The leak guard is tuned to be strict.** It sometimes asks the AI again (one extra call) or replaces a hint with a more general one, and it is a backstop, not a guarantee.
- **An essay written by another AI passes as error-free.** The tool can't tell who wrote a text. It is built for people who want to improve.
- The AI can be wrong. That is why every flag can be disputed and the user decides.
- Daily limits and the budget are counted in UTC, and the price per call is an estimate from token counts.

## Open questions

- Paste lock on or off by default?
- How to compare progress when modifiers change between essays?
- Keep a numeric score at all, or would it make users chase the number?
