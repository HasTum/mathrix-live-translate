"""Tests for Segmenter: utterance boundaries drive both timestamps (R5) and latency (R6)."""
import numpy as np
import pytest

from livetrans.audio.segmenter import Segmenter

SR = 16_000


def tone(seconds, amp=0.1):            # about -23 dB: clearly "speech" for a -40 dB threshold
    t = np.arange(int(seconds * SR)) / SR
    return (amp * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def silence(seconds):
    return np.zeros(int(seconds * SR), np.float32)


def test_silence_gives_no_utterances():
    assert Segmenter("mic").feed(silence(5)) == []


def test_one_phrase_has_correct_times():
    seg = Segmenter("mic")
    out = seg.feed(np.concatenate([silence(1), tone(1), silence(1)]))
    assert len(out) == 1
    u = out[0]
    assert u.source == "mic"
    assert u.start_s == pytest.approx(0.7, abs=0.05)    # 1.0 s minus 0.3 s pre-roll
    assert u.end_s == pytest.approx(2.0, abs=0.05)


def test_utterance_waits_for_end_silence():
    seg = Segmenter("mic", end_silence_s=0.6)
    assert seg.feed(np.concatenate([tone(1), silence(0.3)])) == []   # pause too short
    assert len(seg.feed(silence(0.4))) == 1                          # now 0.7 s quiet


def test_short_click_is_ignored():
    seg = Segmenter("mic")
    assert seg.feed(np.concatenate([silence(1), tone(0.1), silence(1)])) == []


def test_long_speech_is_cut_to_bound_latency():
    seg = Segmenter("system", max_s=12.0)
    out = seg.feed(np.concatenate([tone(30), silence(1)]))
    assert len(out) == 3
    assert all(len(u.audio) / SR <= 12.0 + 1e-6 for u in out)


def test_two_phrases_are_separated():
    seg = Segmenter("system")
    out = seg.feed(np.concatenate([tone(1), silence(1), tone(1), silence(1)]))
    assert len(out) == 2
    assert out[1].start_s > out[0].end_s


def test_chunk_size_does_not_change_result():
    audio = np.concatenate([silence(1), tone(1), silence(1)])
    whole = Segmenter("mic").feed(audio)
    seg = Segmenter("mic")
    parts = []
    for i in range(0, len(audio), 333):                    # odd size, not a frame multiple
        parts += seg.feed(audio[i:i + 333])
    assert [(u.start_s, u.end_s) for u in parts] == [(u.start_s, u.end_s) for u in whole]
