"""Text metrics for Armenian transcription: CER and WER.

Both compare a model's output (hypothesis) with what was really said (reference)
after identical normalization, so punctuation, letter case and the two spellings
of "և" are not counted as errors.
"""
from __future__ import annotations

import re
import unicodedata


def normalize(text: str) -> str:
    """NFKC (turns the ligature "և" into "եւ"), lowercase, remove punctuation, collapse spaces.

    Punctuation is removed, not replaced by a space, because Armenian marks such as
    the question mark "՞" sit inside words: "ինչպե՞ս" must become "ինչպես".
    """
    text = unicodedata.normalize("NFKC", text).lower()
    text = "".join(ch for ch in text if not unicodedata.category(ch).startswith("P"))
    return re.sub(r"\s+", " ", text).strip()


def edit_distance(ref: list, hyp: list) -> int:
    """Minimum number of substitutions, insertions and deletions turning ref into hyp."""
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1,              # deletion
                         cur[j - 1] + 1,           # insertion
                         prev[j - 1] + (r != h))   # substitution (or match)
        prev = cur
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    """Character error rate (spaces count as characters)."""
    ref, hyp = normalize(reference), normalize(hypothesis)
    if not ref:
        raise ValueError("reference is empty after normalization")
    return edit_distance(list(ref), list(hyp)) / len(ref)


def wer(reference: str, hypothesis: str) -> float:
    """Word error rate."""
    ref, hyp = normalize(reference).split(), normalize(hypothesis).split()
    if not ref:
        raise ValueError("reference is empty after normalization")
    return edit_distance(ref, hyp) / len(ref)
