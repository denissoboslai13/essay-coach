"""Leak detector cases, taken from real model outputs during manual testing."""

import pytest

from app.services.leak_guard import find_leaks

FILM = "The evening was organised last friday. The film was began at half past six. Students could choosed a film."
TRAVEL = "Plans do not always work. I would definately recommend travel independently to everyone my age."


@pytest.mark.parametrize(
    "field, source, leak",
    [
        ("Does 'the film began' need a passive at all?", FILM, "the film began"),
        ("Which tense describes something that happened last Friday?", FILM, "Friday"),
        ("How is definitely spelled?", TRAVEL, "definitely"),
    ],
)
def test_detects_corrections(field, source, leak):
    assert leak in find_leaks(field, [source])


@pytest.mark.parametrize(
    "field, source",
    [
        ("Is 'was began' active or passive? See also 'could choosed'.", FILM),
        ("Also check the capital letter in 'last friday'.", FILM),
        ("Look up 'recommend' in a learner's dictionary. Which verb patterns follow it?", TRAVEL),
        ("Which of the words that sound like 'to' means 'more than is good'?", FILM),
        ("Is each subject (students, plans, everybody) singular or plural? Don't guess.", TRAVEL),
        ("English often uses a different tense after this phrase.", TRAVEL),
    ],
)
def test_allows_quotes_and_hints(field, source):
    assert find_leaks(field, [source]) == []
