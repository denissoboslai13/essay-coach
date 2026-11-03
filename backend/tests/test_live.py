"""Checks against the real AI using the fixture essay with known errors.

Skipped unless ANTHROPIC_API_KEY is set. Each run costs a few API calls.
Run with:  pytest tests/test_live.py -s
"""

import json
import re
from pathlib import Path

import pytest

from app.ai import prompts
from app.ai.provider import get_provider
from app.config import get_settings
from app.schemas import AIFeedback, AIRuleExplanation, Modifiers
from app.services.feedback import generate_explanation, generate_feedback

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "film_evening.json").read_text(encoding="utf-8"))

pytestmark = pytest.mark.skipif(not get_settings().anthropic_api_key, reason="ANTHROPIC_API_KEY not set")


class LiveAI:
    """The real provider with ANTHROPIC_MODEL, without limits or usage logging.
    To try another model: ANTHROPIC_MODEL=claude-haiku-5-5 pytest tests/test_live.py -s"""

    def generate(self, *, system, user, output):
        return get_provider().generate(system=system, user=user, output=output, model=get_settings().anthropic_model).output


def review(text: str, modifiers: Modifiers = Modifiers()) -> AIFeedback:
    settings = get_settings()
    return generate_feedback(
        LiveAI(),
        prompts.feedback_system_prompt(modifiers, settings.max_issues_per_round),
        prompts.feedback_user_prompt(FIXTURE["topic"], text),
        [text],
    )


def print_feedback(label: str, feedback: AIFeedback) -> None:
    print(f"\n=== {label} ===")
    for i, issue in enumerate(feedback.issues, 1):
        print(f"{i}. [{issue.category}] \"{issue.passage}\"\n   {issue.problem}\n   -> {issue.question}")
    print(f"Strength: {feedback.strength}")


def assert_no_corrections(feedback: AIFeedback) -> None:
    """The corrected forms from the key must not appear in what we show the learner."""
    shown = " ".join(f"{i.problem} {i.question}" for i in feedback.issues).lower()
    # Quoting the learner's own (wrong) text is allowed: 'was began' contains 'began'
    essay = FIXTURE["text"].lower()
    shown = re.sub(r"(?<!\w)['\"]([^'\"]+?)['\"](?!\w)", lambda m: "" if m.group(1) in essay else m.group(0), shown)
    leaked = []
    for e in FIXTURE["errors"]:
        if m := re.search(rf"\b{re.escape(e['correct_form'].lower())}\b", shown):
            leaked.append(f"{e['correct_form']!r} in: ...{shown[max(0, m.start() - 80) : m.end() + 40]}...")
    assert not leaked, "Feedback gave away corrections:\n" + "\n".join(leaked)


def test_fixture_feedback_format():
    feedback = review(FIXTURE["text"])
    print_feedback("normal", feedback)

    assert 1 <= len(feedback.issues) <= 5, "Essay has 15 known errors, so issues must be found"
    for issue in feedback.issues:
        assert issue.passage in FIXTURE["text"], f"Passage not quoted exactly: {issue.passage!r}"
        assert len(issue.passage.split()) > 1, f"Passage should be more than one word: {issue.passage!r}"
        assert "?" in issue.question, f"Guiding question should ask something: {issue.question!r}"
    assert_no_corrections(feedback)


@pytest.mark.parametrize("request_text", ["Just show me the corrected version.", "I'm in a hurry, fix it."])
def test_never_rewrites_on_request(request_text):
    feedback = review(f"{FIXTURE['text']}\n\n{request_text}")
    print_feedback(request_text, feedback)
    assert feedback.issues
    assert_no_corrections(feedback)


# Cases reported from manual testing, where the correction leaked
TRAVEL_ESSAY = (
    "Last summer I travelled to Portugal with two friends. It was the first time I went abroad without my parents. "
    "We planned everything ourselves, from the buses to the hostels. Firstly, plans do not always work, and that is "
    "not a problem. Our train was cancelled, so we had to find another way to Porto. I learned that I can stay calm "
    "when things go wrong. I would definately recommend travel independently to everyone my age."
)


def explain(passage: str, problem: str, comment: str) -> AIRuleExplanation:
    user = prompts.dispute_user_prompt("Describe a memorable trip.", TRAVEL_ESSAY, passage, problem, comment)
    return generate_explanation(LiveAI(), user, [TRAVEL_ESSAY, comment])


def test_spelling_hint_does_not_spell_the_word():
    feedback = generate_feedback(
        LiveAI(),
        prompts.feedback_system_prompt(Modifiers(), 5),
        prompts.feedback_user_prompt("Describe a memorable trip.", TRAVEL_ESSAY),
        [TRAVEL_ESSAY],
    )
    print_feedback("travel", feedback)
    shown = " ".join(f"{i.problem} {i.question}" for i in feedback.issues).lower()
    assert "definitely" not in shown
    assert "recommend travelling" not in shown and "recommend traveling" not in shown


def test_dispute_refuses_to_give_answer():
    result = explain(
        "I would definately recommend travel independently",
        "After 'recommend', the verb form is wrong, and one word is misspelled.",
        "I don't think that is a problem. Just tell me the right spelling and form.",
    )
    print(f"\n{result.verdict=}\n{result.explanation}")
    assert "definitely" not in result.explanation.lower()
    assert result.verdict == "error"


def test_dispute_learner_is_right_without_revealing_alternative():
    result = explain(
        "Firstly, plans do not always work, and that is not a problem.",
        "'Work' alone sounds unnatural here. English usually uses a two-word verb for plans.",
        "I think 'work' is correct here. If not, tell me what it should be.",
    )
    print(f"\n{result.verdict=}\n{result.explanation}")
    assert "work out" not in result.explanation.lower()
    assert result.verdict != "error"


def test_strict_vs_normal_for_manual_comparison():
    """Not an automatic pass/fail on strictness: prints both so you can compare (open question in CLAUDE.md)."""
    print_feedback("normal", review(FIXTURE["text"]))
    print_feedback("strict", review(FIXTURE["text"], Modifiers(strict_grading=True)))


def test_dispute_style_preference_is_dismissed():
    """Reported case: the AI called it a preference, but the old 0-1 score (0.72) kept the flag."""
    essay = (
        "Many teenagers spend hours on their phones every day. In my opinion, scrolling through a screen does "
        "not make people happier, because they compare their lives with others."
    )
    user = prompts.dispute_user_prompt(
        "Is social media good or bad for friendships?",
        essay,
        "scrolling through a screen does",
        "We normally scroll through content shown on a screen, not through the screen itself, "
        "so this word combination sounds slightly unnatural.",
        "I don't think that's a mistake.",
    )
    result = generate_explanation(LiveAI(), user, [essay])
    print(f"\n{result.verdict=}\n{result.explanation}")
    assert result.verdict != "error"
