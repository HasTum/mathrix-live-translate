"""Tests for Timeline. Requirement R5: timestamps must stay correct
even when a source is silent (bug found 2026-10-24)."""
import numpy as np
import pytest

from livetrans.audio.timeline import Timeline

SR = 16_000


def chunk(seconds):
    return np.ones(int(seconds * SR), dtype=np.float32)


def test_continuous_chunks_get_no_padding():
    tl = Timeline(t0=0.0)
    for i in range(1, 101):                    # 100 chunks of 30 ms, on time
        out = tl.on_chunk(i * 0.03, chunk(0.03))
        assert len(out) == 1
    assert tl.padded == 0
    assert tl.position_s() == pytest.approx(3.0, abs=0.01)


def test_gap_between_chunks_is_filled_with_silence():
    tl = Timeline(t0=0.0)
    tl.on_chunk(1.0, chunk(1.0))               # audio 0..1 s
    out = tl.on_chunk(3.0, chunk(1.0))         # audio 2..3 s, nothing in 1..2 s
    assert len(out) == 2
    assert out[0].size == pytest.approx(SR, abs=1)
    assert not out[0].any()                    # the padding is real silence
    assert tl.position_s() == pytest.approx(3.0, abs=0.01)


def test_completely_silent_source_still_advances():
    """Reproduces the real bug: no playback for 20 s gave a 0.0 s system file."""
    tl = Timeline(t0=0.0, hold_s=0.3)
    total = 0
    for t in np.arange(0.1, 20.01, 0.1):
        part = tl.on_tick(t)
        if part is not None:
            total += part.size
    assert total / SR == pytest.approx(20.0 - 0.3, abs=0.11)


def test_tick_then_chunk_does_not_double_count():
    tl = Timeline(t0=0.0, hold_s=0.3)
    tl.on_tick(2.0)                            # silence up to 1.7 s
    tl.on_chunk(2.03, chunk(0.03))             # real audio 2.00..2.03 s
    assert tl.position_s() == pytest.approx(2.03, abs=0.01)


def test_small_jitter_is_not_padded():
    tl = Timeline(t0=0.0, tolerance_s=0.1)
    tl.on_chunk(0.03, chunk(0.03))
    tl.on_chunk(0.11, chunk(0.03))             # 50 ms late: jitter, not a gap
    assert tl.padded == 0
