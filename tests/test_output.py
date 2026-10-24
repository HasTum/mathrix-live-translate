"""Tests for the terminal format (R5: time, speaker, Armenian, English)."""
from livetrans.output import format_segment, format_time


def test_time_format_matches_brief():
    assert format_time(72.9) == "00:01:12"
    assert format_time(3725) == "01:02:05"


def test_segment_has_all_four_parts():
    text = format_segment(72.4, "Speaker 1", "Բարև, ինչպե՞ս ես։", "Hi, how are you?")
    assert text == "[00:01:12] Speaker 1\nHY: Բարև, ինչպե՞ս ես։\nEN: Hi, how are you?"


def test_latency_is_shown_when_given():
    assert "(latency 2.3 s)" in format_segment(5, "Me", "a", "b", latency_s=2.34)
