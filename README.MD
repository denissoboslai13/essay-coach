# Essay Coach

**An aid, not a shortcut.** Essay Coach helps self-taught English learners get better at writing essays _themselves_. It never writes or rewrites your text. It points to a passage, says what the problem is, and asks a guiding question, so **you** find and make the fix.

> **Status: prototype.** Semester project for the course _AI Lab v praxi_, built by one person.
> The prototype is **BYOK (bring your own key)**: it runs locally and uses an Anthropic API key
> that you put into `backend/.env`. There is no public hosted version yet (see [Roadmap](#roadmap)).

---

## Who it is for

- **Primary:** self-taught English learners who write essays alone and get no feedback, so they repeat the same mistakes without noticing.
- **Secondary:** anyone who wants to improve their English writing.

Why it exists: more and more people let AI write their essays for them. Essay Coach goes the other way. AI only gives feedback, and the learner does the writing.

## What it does

1. **Pick a topic.** You get 3 topics (normal or harder) and choose one. Topics you have finished are not offered again.
2. **Write.** The editor shows a word count. You can turn on a timer and a paste lock. Browser spellcheck is off on purpose.
3. **Get feedback.** You get at most **5 issues** per round, most important first: meaning-changing problems, then repeated patterns, then small things. Each issue has:
   - the **passage** from your text (highlighted in the editor on hover),
   - **what the problem is**, in short plain English,
   - a **guiding question**, never the fix.
4. **Revise and resubmit.** Every round checks the whole text again and shows which earlier issues you fixed. The loop ends only when no issues are found, not just because the flagged items were fixed.
5. **Disagree.** "I don't think that is an error" asks for the rule behind the flag and a verdict. If you were right, or it is a style choice, the passage is not flagged again.

### Difficulty modifiers (all optional)

Instead of fixed levels, you switch on what makes writing harder:

| Modifier         | Effect                                                                           |
| ---------------- | -------------------------------------------------------------------------------- |
| Stricter grading | The prompt also reports minor issues (word choice, transitions, punctuation)     |
| Timer            | Countdown until the first submission                                             |
| Harder topics    | Argumentative / abstract topic list                                              |
| Word target      | Below it: flagged as underdeveloped. More than 10 % above it: submission refused |
| Paste lock       | Blocks pasting into the editor (a nudge, not a real lock)                        |

The active modifiers are stored with every essay, so progress can later be compared like with like.

### Design rules that always hold

- No rewritten or corrected sentences, **even when the user asks** ("just fix it", "I'm in a hurry").
- A code-level **leak guard** backs up the prompt. If a feedback text contains something that looks like a corrected form of the learner's words, the AI is asked again, and anything still leaking is replaced with a neutral hint.
- Never ends with praise while problems remain. There is one honest sentence about what the author does well.
- No streaks, badges or notifications. Success is writing better _without_ the tool, not time spent in the app.

---

## Tech stack

| Part     | Technology                                                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Backend  | Python 3.14, **FastAPI**, **SQLModel** (SQLAlchemy + Pydantic), SQLite, pydantic-settings                                             |
| AI       | **Anthropic Claude** via the official `anthropic` Python SDK, structured outputs (Pydantic schemas). Default model: Claude Sonnet 5.5 |
| Frontend | **React 19**, **Vite 8**, plain CSS (Courier Prime + IBM Plex Sans)                                                                   |
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
main.py FastAPI app
ai/provider.py the only module that calls the AI vendor
ai/prompts.py prompt text (normal vs strict, modifiers)
services/feedback.py write -> feedback -> revise loop
services/leak_guard.py "never reveal the correction" backstop
routers/ HTTP endpoints
tests/ pytest, fixtures/film_evening.json
frontend/
src/ React components, styles.css

```

---

## Running it locally (BYOK)

You need Python 3.14+, Node 22+ and your own Anthropic API key.

**Backend**

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # put your key into ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

**Frontend** (second terminal)

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to the backend on port 8000.

**Tests**

```powershell
cd backend
pytest --ignore=tests/test_live.py   # fast, fake AI, no key, no cost
pytest tests/test_live.py -s         # real AI on the fixture essay (costs a few calls)
```

> Every submission costs real API tokens on **your** key. The backend refuses texts under
> 50 words before any AI call.

---

## Roadmap

### In progress: invite-only public version

Goal: by the final project deadline, run Essay Coach on a home server so invited people can try it without their own key.

- **Google sign-in** (no passwords stored) with **invite codes** for registration
- **Ownership checks:** every user sees only their own essays
- **Cost control:** every AI call logged with its price, a **daily limit** per user and a **monthly budget cap** for the whole app
- **Cheaper model for public users** (e.g. Claude Haiku 5.5), only after it passes the fixture tests
- **Docker Compose** deployment, exposed through **Cloudflare Tunnel** on an own domain (no open ports, automatic HTTPS)
- Admin commands for invites and usage

### Planned

- Privacy page and "delete my account" (GDPR), nightly database backups
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
- **"Stricter grading via the prompt" is an assumption.** It needs testing on the same essay in normal and strict mode.
- The AI can be wrong. That is why every flag can be disputed and the user decides.

## Open questions

- Paste lock on or off by default?
- How to compare progress when modifiers change between essays?
- Keep a numeric score at all, or would it make users chase the number?
