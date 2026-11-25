"""Fixed topic lists, grouped by essay type. Three random topics are offered per request,
each of a different type when possible.

Drafted by AI once and reviewed by a human; there is no AI call at runtime.
Keep the old topic strings unchanged: stored essays refer to them (finished topics are not offered again).
"""

import random

NORMAL_GROUPS: dict[str, list[str]] = {
    "opinion": [
        "Should students wear school uniforms? Argue for or against.",
        "Is social media good or bad for friendships?",
        "Is it better to live in a city or in the countryside? Give reasons.",
        "Should homework be banned in primary schools? Give your opinion.",
        "Is it better to travel alone or with friends? Explain your view.",
        "Should children have their own mobile phone before the age of twelve?",
        "Are video games a waste of time? Give your opinion with examples.",
        "Should fast food advertising be banned on television?",
    ],
    "both_views": [
        "Some people prefer to read books, others prefer to watch films. Discuss both views and give your opinion.",
        "Some people think university should be free for everyone, others think students should pay. Discuss both views.",
        "Some people prefer one close friend, others prefer many friends. Discuss both views and give your opinion.",
        "Some people think pets should not be kept in flats, others disagree. Discuss both views.",
        "Some people learn best alone, others in a group. Discuss both views and give your opinion.",
        "Some people think tourists help their town, others think they cause problems. Discuss both views.",
    ],
    "advantages": [
        "What are the advantages and disadvantages of working from home?",
        "What are the advantages and disadvantages of learning a language online?",
        "What are the advantages and disadvantages of living with your parents as a young adult?",
        "What are the advantages and disadvantages of having a part-time job while studying?",
        "What are the advantages and disadvantages of shopping online instead of in shops?",
        "What are the advantages and disadvantages of owning a car in a big city?",
        "What are the advantages and disadvantages of taking a gap year before university?",
    ],
    "problem_solution": [
        "Many young people spend too much time on their phones. What problems does this cause, and how can it be solved?",
        "Many towns have too much traffic. Explain the causes and suggest practical solutions.",
        "A lot of food is thrown away every day. Why does this happen, and what can people do about it?",
        "Many students feel stressed before exams. What are the reasons, and how can schools help?",
        "Many people do not get enough exercise. Why, and what could encourage them to move more?",
        "Plastic waste is a growing problem. What can individuals and shops do to reduce it?",
    ],
    "report": [
        "Write a report about an event at your school or workplace.",
        "Write a report for your manager about a training course you attended, with recommendations.",
        "Write a report for your town council about the sports facilities in your area and how to improve them.",
        "Write a report about a new café or restaurant in your town for a local website.",
        "Write a report for your school about how students travel to school and how it could be made greener.",
        "Write a report about a trip you took part in, saying what went well and what could be better.",
    ],
    "narrative": [
        "Describe a person who has influenced you and explain how.",
        "Describe a memorable trip and what you learned from it.",
        "Write about a skill you would like to learn and why.",
        "Describe a day when everything went wrong, and how it ended.",
        "Describe a place that is special to you and explain why.",
        "Write about a mistake you made and what you learned from it.",
        "Describe a tradition from your country or family and what it means to you.",
        "Write about a time you helped someone, or someone helped you.",
    ],
}

HARDER_GROUPS: dict[str, list[str]] = {
    "opinion": [
        "To what extent should governments regulate artificial intelligence?",
        "Is it ethical to keep animals in zoos? Defend a clear position.",
        "How far should freedom of speech extend online?",
        "Do standardised tests measure what matters in education?",
        "To what extent are individuals, rather than governments, responsible for tackling climate change?",
        "Should parents be held legally responsible for crimes committed by their children?",
        "Is it ever right to break the law in order to protest? Defend a clear position.",
    ],
    "both_views": [
        "Should voting be compulsory? Weigh the arguments on both sides.",
        "Does economic growth always improve quality of life? Discuss.",
        "Some argue that the arts should be funded by the state, others that they should survive on the market. Discuss both views.",
        "Some believe schools should focus on national history, others on world history. Discuss both views.",
        "Some say success is mainly the result of talent and effort, others of luck and background. Discuss both views.",
        "Some think space exploration is worth its cost, others that the money is needed on Earth. Discuss both views.",
    ],
    "advantages": [
        "What are the advantages and disadvantages of a four-day working week for employees and employers?",
        "Discuss the advantages and disadvantages of replacing cash entirely with digital payments.",
        "What are the benefits and risks of using genetic testing to predict people's health?",
        "Weigh the advantages and disadvantages of hosting a large international sporting event.",
        "What are the advantages and disadvantages of letting AI tools mark students' work?",
        "Discuss the benefits and drawbacks of widespread video surveillance in public places.",
    ],
    "problem_solution": [
        "Housing in many large cities has become unaffordable for young people. Analyse the causes and propose solutions.",
        "Misinformation spreads quickly online. Who should be responsible for limiting it, and how?",
        "Many rural areas are losing their young people. Why is this happening, and what could reverse it?",
        "Loneliness is increasing among elderly people. What are the causes, and what should society do?",
        "Many jobs may be automated in the next twenty years. How should education systems respond?",
        "Fast fashion harms the environment. What measures would be both effective and fair?",
    ],
    "report": [
        "Write a report for your city council evaluating the public transport system and recommending changes.",
        "Write a report for your company's management analysing why staff leave and proposing ways to keep them.",
        "Write a report for a university committee assessing how well it supports international students.",
        "Write a report evaluating a local environmental project and whether it should receive more funding.",
        "Write a report for a youth organisation on how young people in your area spend their free time, with recommendations.",
    ],
    "narrative": [
        "Describe a decision that changed the direction of your life and reflect on whether it was the right one.",
        "Write about a belief you once held strongly and later changed. What made you change your mind?",
        "Describe a book, film or work of art that challenged the way you see the world.",
        "Reflect on a conflict you were part of and what it taught you about other people.",
        "Describe how your hometown has changed during your lifetime and evaluate whether the changes were positive.",
    ],
}

NORMAL_TOPICS = [t for group in NORMAL_GROUPS.values() for t in group]
HARDER_TOPICS = [t for group in HARDER_GROUPS.values() for t in group]


def pick_topics(harder: bool, exclude: set[str] = frozenset(), count: int = 3) -> list[str]:
    """`exclude`: topics already finished, so they are not offered again.
    Each topic comes from a different essay type, as long as enough types have topics left."""
    groups = HARDER_GROUPS if harder else NORMAL_GROUPS
    pools = [left for group in groups.values() if (left := [t for t in group if t not in exclude])]
    random.shuffle(pools)
    picked = [random.choice(pool) for pool in pools[:count]]
    rest = [t for pool in pools for t in pool if t not in picked]
    return picked + random.sample(rest, k=min(count - len(picked), len(rest)))
