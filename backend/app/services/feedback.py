"""Business logic for the write -> feedback -> revise loop."""

from sqlmodel import Session

from app.ai import prompts
from app.ai.provider import AIProvider
from app.config import get_settings
from app.models import Essay, Issue, Revision
from app.schemas import AIFeedback, AIRuleExplanation, FeedbackOut, IssueOut, Modifiers, RevisionOut
from app.services.leak_guard import find_leaks

GENERIC_QUESTION = "Read this passage again slowly. What looks wrong to you, and why?"


def count_words(text: str) -> int:
    return len(text.split())


def _leak_retry_note(leaks: list[str]) -> str:
    listed = ", ".join(f"'{leak}'" for leak in sorted(set(leaks)))
    return (
        "\n\n<review_note>\nA previous draft of your answer revealed corrections: "
        f"{listed}. Write your answer again from scratch. Do not use these or any other corrected forms anywhere.\n</review_note>"
    )


def _feedback_leaks(feedback: AIFeedback, sources: list[str]) -> list[str]:
    fields = [f for i in feedback.issues for f in (i.problem, i.question)]
    fields += [c.comment for c in feedback.previous_issues] + [feedback.strength]
    return [leak for f in fields for leak in find_leaks(f, sources)]


def _scrub_feedback(feedback: AIFeedback, sources: list[str]) -> None:
    """Last resort after a retry: replace any field that still leaks with a neutral text."""
    for issue in feedback.issues:
        if find_leaks(issue.problem, sources):
            issue.problem = f"There is a {issue.category} problem in this passage."
        if find_leaks(issue.question, sources):
            issue.question = GENERIC_QUESTION
    for check in feedback.previous_issues:
        if find_leaks(check.comment, sources):
            check.comment = "Well done, this is correct now." if check.status == "fixed" else "This still needs work."
    if find_leaks(feedback.strength, sources):
        feedback.strength = ""


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def generate_feedback(provider: AIProvider, system: str, user: str, sources: list[str]) -> AIFeedback:
    """AI feedback that has passed the leak check (one retry, then scrub)."""
    feedback = provider.generate(system=system, user=user, output=AIFeedback)
    if leaks := _feedback_leaks(feedback, sources):
        feedback = provider.generate(system=system, user=user + _leak_retry_note(leaks), output=AIFeedback)
        _scrub_feedback(feedback, sources)
    return feedback


def generate_explanation(provider: AIProvider, user: str, sources: list[str]) -> AIRuleExplanation:
    """Dispute explanation that has passed the leak check (one retry, then a neutral text)."""
    result = provider.generate(system=prompts.DISPUTE_SYSTEM, user=user, output=AIRuleExplanation)
    if leaks := find_leaks(result.explanation, sources):
        result = provider.generate(
            system=prompts.DISPUTE_SYSTEM, user=user + _leak_retry_note(leaks), output=AIRuleExplanation
        )
    if find_leaks(result.explanation, sources):
        result.explanation = (
            "The flag stands. Look up the rule for this kind of problem in a grammar reference and compare it with your passage."
            if result.verdict == "error"
            else "You are right: this is fine here, so it won't be flagged again."
        )
    return result


def _overlaps_dismissed(passage: str, dismissed: list[Issue]) -> bool:
    """True if a new passage is the same as, or contains / is contained in, a dismissed one."""
    p = _normalize(passage)
    return any((d := _normalize(i.passage)) in p or p in d for i in dismissed)


def review_revision(session: Session, provider: AIProvider, essay: Essay, text: str) -> FeedbackOut:
    """Check a new version of the essay. Every submission is reviewed from scratch."""
    settings = get_settings()
    words = count_words(text)

    if words < settings.min_words_for_feedback:
        # Not worth an AI call; nothing is stored
        return FeedbackOut(
            status="too_short",
            message=f"Write at least {settings.min_words_for_feedback} words to get useful feedback (you have {words}).",
        )

    modifiers = Modifiers.model_validate(essay.modifiers)
    if modifiers.max_words and words > modifiers.max_words:
        # Staying within the length is part of the task, so this is checked before any AI call
        return FeedbackOut(
            status="too_long",
            message=f"Your target is {modifiers.min_words} words, at most {modifiers.max_words}. "
            f"You have {words}. Cut {words - modifiers.max_words} words before submitting.",
        )

    previous = [i for i in essay.revisions[-1].issues if not i.dismissed] if essay.revisions else []
    dismissed = [i for rev in essay.revisions for i in rev.issues if i.dismissed]

    system = prompts.feedback_system_prompt(modifiers, settings.max_issues_per_round)
    user = prompts.feedback_user_prompt(
        essay.topic,
        text,
        previous_issues=[(i.passage, i.problem) for i in previous],
        dismissed=[(i.passage, i.problem) for i in dismissed],
    )
    # Quoting the previous version is fine too ("you changed X")
    sources = [text] + ([essay.revisions[-1].text] if essay.revisions else [])

    feedback = generate_feedback(provider, system, user, sources)

    # Mark which issues from the previous round were fixed
    for check in feedback.previous_issues:
        if 1 <= check.number <= len(previous):
            issue = previous[check.number - 1]
            issue.resolution = check.status
            issue.resolution_comment = check.comment
            session.add(issue)

    revision = Revision(
        essay_id=essay.id,
        round=len(essay.revisions) + 1,
        text=text,
        word_count=words,
        # Judged once in the first round, then kept, so it doesn't change with every revision
        strength=essay.revisions[0].strength if essay.revisions else feedback.strength,
    )
    # Backstop for the prompt: never re-flag something the learner was right about
    new_issues = [i for i in feedback.issues if not _overlaps_dismissed(i.passage, dismissed)]
    # The schema can't enforce a max length, so cap it here
    for rank, ai_issue in enumerate(new_issues[: settings.max_issues_per_round], start=1):
        revision.issues.append(
            Issue(
                rank=rank,
                category=ai_issue.category,
                passage=ai_issue.passage,
                problem=ai_issue.problem,
                question=ai_issue.question,
            )
        )

    essay.completed = not revision.issues
    session.add(revision)
    session.add(essay)
    session.commit()
    session.refresh(revision)
    for issue in previous:
        session.refresh(issue)

    return FeedbackOut(
        status="issues_found" if revision.issues else "no_issues",
        revision=RevisionOut.model_validate(revision, from_attributes=True),
        previous_issues=[IssueOut.model_validate(i, from_attributes=True) for i in previous],
    )


def explain_disputed_issue(session: Session, provider: AIProvider, issue: Issue, comment: str | None) -> Issue:
    """User says "I don't think that is an error": explain the rule and judge who is right."""
    revision = issue.revision
    user = prompts.dispute_user_prompt(revision.essay.topic, revision.text, issue.passage, issue.problem, comment)
    sources = [revision.text] + ([comment] if comment else [])
    result = generate_explanation(provider, user, sources)
    issue.disputed = True
    issue.dispute_comment = comment
    issue.rule_explanation = result.explanation
    issue.dispute_verdict = result.verdict
    # A style preference is the learner's choice, so it is dismissed like a correct passage
    issue.dismissed = result.verdict != "error"
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue
