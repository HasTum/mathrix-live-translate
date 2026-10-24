"""Terminal output in the format required by the brief:

    [00:01:12] Speaker 1
    HY: Բարև, ինչպե՞ս ես։
    EN: Hi, how are you?
"""
from __future__ import annotations


def format_time(seconds: float) -> str:
    h, rest = divmod(int(seconds), 3600)
    m, s = divmod(rest, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_segment(t_s: float, speaker: str, hy: str, en: str,
                   latency_s: float | None = None) -> str:
    head = f"[{format_time(t_s)}] {speaker}"
    if latency_s is not None:
        head += f"   (latency {latency_s:.1f} s)"
    return f"{head}\nHY: {hy}\nEN: {en}"
