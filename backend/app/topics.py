"""Small fixed topic lists. Three random topics are offered per request."""

import random

NORMAL_TOPICS = [
    "Describe a person who has influenced you and explain how.",
    "Is it better to live in a city or in the countryside? Give reasons.",
    "Write about a skill you would like to learn and why.",
    "Should students wear school uniforms? Argue for or against.",
    "Describe a memorable trip and what you learned from it.",
    "What are the advantages and disadvantages of working from home?",
    "Write a report about an event at your school or workplace.",
    "Is social media good or bad for friendships?",
]

HARDER_TOPICS = [
    "To what extent should governments regulate artificial intelligence?",
    "Does economic growth always improve quality of life? Discuss.",
    "Should voting be compulsory? Weigh the arguments on both sides.",
    "Is it ethical to keep animals in zoos? Defend a clear position.",
    "How far should freedom of speech extend online?",
    "Do standardised tests measure what matters in education?",
]


def pick_topics(harder: bool, exclude: set[str] = frozenset(), count: int = 3) -> list[str]:
    """`exclude`: topics already finished, so they are not offered again."""
    pool = [t for t in (HARDER_TOPICS if harder else NORMAL_TOPICS) if t not in exclude]
    return random.sample(pool, k=min(count, len(pool)))
