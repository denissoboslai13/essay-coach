# Essay Coach

A tool that helps self-taught English learners get better at writing essays **themselves**. It does not write or rewrite text for the user. It guides them with feedback and questions, so the user finds and makes the fix. Principle: **AI is an aid, not a shortcut.**

Semester project for the course "AI Lab v praxi". One person builds it. Right now the goal is a small working **prototype**.

## Working with the user

- Talk to the user in Slovak. Code, comments, UI text, commit messages and docs are in English.
- Keep the prototype small. Do not add features that are not in "Prototype scope" below without asking first.
- Before scaffolding anything, ask the user which stack they want (see "Stack"). Do not decide it silently.
- Explain choices briefly. When something is a guess, say so.

## Problem and users

- Primary users: self-taught English learners who write essays alone. Nobody gives them feedback, so they can pick up bad habits and repeat the same mistakes.
- Secondary users: anyone who wants to improve their English writing.
- Why it exists: more and more people have AI write their essays for them. This tool goes the other way.

## What existing tools do (tested by the user on one test essay with 15 deliberate errors)

- **Write & Improve (Cambridge):** estimates CEFR level, marks words with errors, popup with a question and a suggested fix. After the user fixed everything it had marked, it only said the essay improved and gave no more feedback, although 8 of the 15 errors were still there. It caught 7 of 15.
- **Grammarly:** flags everything (20 grammar, 6 clarity flags) and offers the fix straight away, no questions, no explanation for learners.
- **General AI with a prompt (Gemini):** with our feedback prompt it quoted a passage, explained the problem and asked a guiding question, and it refused to give a ready fix even when asked.

Design consequence: nothing is "fixed for" the user, and the tool must not end with praise while problems remain.

## Core behavior (must hold in every version)

1. Never write, rewrite or offer a corrected version of the user's sentences, even if the user asks. Explain why instead.
2. For each issue show the **passage** from the text (not only a single word), say what the problem is, and ask a guiding question. The user finds the fix.
3. Show at most 5 issues per round, the most important first (meaning-changing problems, then repeated patterns, then small things). Include structure and style, not only grammar.
4. After the user revises, check the text again. Keep going until no issues are found. Do not stop just because the previously flagged items were fixed.
5. The user can say "I don't think that is an error". Tools make mistakes, so explain the rule and let the user decide.
6. Feedback language: English. Keep explanations short and plain.

## Draft feedback prompt (starting point, tested once in Gemini, not yet tested in the prototype)

```
You are an experienced English teacher who helps self-taught learners improve their essay writing.
The user sends an essay written in English.

Your task:
- Find the 5 most important problems at most (grammar, structure, style, argumentation).
- For each problem give: (1) the passage from the text, (2) what the problem is, (3) a guiding question that leads the user to the fix, NOT the fix itself.
- Never rewrite sentences for the user and never provide a corrected version of the text, even if the user explicitly asks. Explain why instead.
- If the essay is too short for meaningful feedback (under 50 words), ask for a longer text instead of analysing it.
- At the end write one sentence about what the author does well.

Output format: numbered list, max 200 words, in English.
```

Difficulty modifiers must be reflected in the feedback and grading through the prompt (see below).

## Difficulty modifiers (the chosen main idea)

Instead of fixed levels, the user can switch on options that make writing harder:

- stricter grading
- less time (timer)
- harder topics
- higher word count
- paste lock (blocks pasting text into the editor)

Feedback and grading take the active modifiers into account. Store which modifiers were on with every essay. Everything is optional. No streaks, badges or notifications that push daily use (the project explicitly wants to avoid that). Success is progress in writing without the tool, not time spent in the app.

Limits to be honest about: paste lock can be bypassed (second window, retyping), so it is a nudge, not a lock. "Stricter grading via the prompt" is an assumption and must be tested: same essay, normal vs strict mode, compare outputs.

## Prototype scope (proposed, confirm with the user)

Included:

1. Topic choice: show 3 topics, the user picks one (random or from a small fixed list).
2. Writing editor with word count, optional timer, optional paste lock.
3. Submit essay, backend calls the AI, show up to 5 issues (passage, problem, guiding question).
4. Revise and resubmit loop until no issues are found.
5. Save each essay with its modifiers and the issues found, to prepare for later progress tracking.

Not in the prototype: skills map, mobile app, other languages, other text types, gamification. (Accounts and login were added later, see "Deployment".)

## Later ideas (do not build now)

- Skills map unlocked after about 10 essays or about a week, showing progress over time. Categories can follow the six ELLIPSE dimensions: cohesion, syntax, vocabulary, phraseology, grammar, conventions. Needs several essays because rater agreement in ELLIPSE was only 50-59%, so one essay is not reliable.
- Warning when the user repeats the same type of error.
- Web app and a real mobile app.
- Other languages, other levels.

## Deployment (built, server not available yet)

For the final project: invite-only public version on the user's own home server. The user will buy a domain and host several projects on the server.

- Login with Google only (ID token verified in the backend, no passwords stored). New accounts need an invite code; emails in `ADMIN_EMAILS` don't, and have no daily limits.
- Session = random token in an httpOnly cookie, stored hashed in the DB.
- `LOCAL_MODE=true` (default in `.env.example`, for anyone who clones the repo and runs it with their own key): no login, one fixed local account, no daily limits; it takes over essays without an owner. Docker forces it off; the server refuses to start with it plus `COOKIE_SECURE`.
- Every endpoint checks that the essay/issue belongs to the signed-in user (others get 404).
- Every AI call is logged with tokens and price (`services/usage.py`). Per-user daily limits on reviews and disputes, global monthly budget for everyone.
- Docker: one image (backend serves the built frontend, `app/site.py`). One shared Cloudflare tunnel on the server for all projects, via the `web` Docker network. See `deploy/README.md`.
- Still to do before going public: backups, privacy page, account deletion.

## Architecture

- Frontend never calls a public AI API directly. Request goes frontend -> own backend -> AI API. The backend validates the request, keeps the API key, and can rate-limit.
- API keys only in environment variables. Never in the repo and never in frontend code. Add `.env` to `.gitignore`.
- Keep the AI provider behind one small module so it can be swapped.

## Stack

To be decided with the user before scaffolding. Ask which language and framework they prefer for the backend and the frontend, and propose a minimal option.

## Testing

- Keep a fixture with a short test essay (140-190 words, a report about a school film evening) that has known deliberate errors and a key listing them. Use it to check the feedback: formats are respected, no rewritten text, problems found, and the loop does not end while errors remain.
- Test the "never rewrite" rule with prompts like "just show me the corrected version" and "I'm in a hurry, fix it".

## Open questions

- Is paste lock on or off by default?
- How to compare progress when the modifiers change between essays (compare similar with similar)?
- Keep a numeric score or not? Numbers can push users to chase the score instead of learning.
- Does "stricter grading" via the prompt give consistent results?
