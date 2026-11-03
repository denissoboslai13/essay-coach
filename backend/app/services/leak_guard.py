"""Code-level backstop for "never reveal the correction".

The prompt forbids corrections, but models still slip sometimes (e.g. a question
that quotes 'the film began' when the essay says 'the film was began'). A text
fragment counts as a leak when it is NOT in the learner's text but is very
similar to something that is: that is what a corrected version looks like.
"""

import re
from difflib import SequenceMatcher

# 'quoted' / "quoted" / “quoted” fragments. Apostrophes inside words (don't, learner's) are not quote marks.
_QUOTE_RE = re.compile(r"(?<!\w)['\"‘“]([^\"“”]+?)['\"’”](?!\w)")
_WORD_RE = re.compile(r"[A-Za-z]+")

QUOTE_SIMILARITY = 0.75
WORD_SIMILARITY = 0.85


def _clean(text: str) -> str:
    """Drop punctuation (keep apostrophes) and collapse whitespace."""
    return " ".join(re.sub(r"[^\w\s']", " ", text).split())


def _similar(a: str, b: str, threshold: float) -> bool:
    m = SequenceMatcher(None, a, b)
    return m.real_quick_ratio() >= threshold and m.quick_ratio() >= threshold and m.ratio() >= threshold


def _quote_leaks(field: str, sources: list[str]) -> list[str]:
    leaks = []
    for raw in _QUOTE_RE.findall(field):
        quote = _clean(raw)
        if len(quote) < 3 or any(quote in s for s in sources):
            continue
        # Same letters but different capitals (friday -> Friday) is a correction too
        n = len(quote.split())
        q = quote.lower()
        for s in sources:
            words = s.lower().split()
            windows = (" ".join(words[i : i + size]) for size in {max(1, n - 1), n, n + 1} for i in range(len(words)))
            if any(w == q or _similar(q, w, QUOTE_SIMILARITY) for w in windows):
                leaks.append(raw)
                break
    return leaks


def _word_leaks(field: str, vocab: set[str]) -> list[str]:
    """Unquoted words that look like a spelling fix of a word in the text (definately -> definitely)."""
    leaks = []
    for word in {w.lower() for w in _WORD_RE.findall(field) if len(w) >= 5}:
        if word in vocab:
            continue
        for original in vocab:
            # Prefix pairs are inflections (student/students), not spelling fixes
            if abs(len(original) - len(word)) > 1 or word.startswith(original) or original.startswith(word):
                continue
            if _similar(word, original, WORD_SIMILARITY):
                leaks.append(word)
                break
    return leaks


def _capital_leaks(field: str, cased_vocab: set[str]) -> list[str]:
    """Mid-sentence capitalised words the learner wrote in lower case (friday -> Friday)."""
    lower_vocab = {w.lower() for w in cased_vocab}
    leaks = []
    for m in re.finditer(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-z]+)\b", field):
        word = m.group(1)
        if word not in cased_vocab and word.lower() in lower_vocab:
            leaks.append(word)
    return leaks


def find_leaks(field: str, source_texts: list[str]) -> list[str]:
    """Fragments in `field` that look like corrections of `source_texts` (the learner's own text)."""
    sources = [_clean(s) for s in source_texts]
    cased_vocab = {w for s in source_texts for w in _WORD_RE.findall(s)}
    vocab = {w.lower() for w in cased_vocab}
    return _quote_leaks(field, sources) + _word_leaks(field, vocab) + _capital_leaks(field, cased_vocab)
