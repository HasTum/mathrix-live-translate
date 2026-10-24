"""Keep each audio source on a continuous timeline.

WASAPI loopback delivers no data at all while nothing is playing
(confirmed 2026-10-24: a 20 s recording with no playback produced a 0.0 s file).
Without correction, silent stretches vanish and every later timestamp is wrong.

Timeline turns irregular chunk arrivals into a gap-free sample stream:
- on_chunk(): inserts silence before a chunk that arrives after a gap
- on_tick():  emits silence while a source is completely quiet

Pure logic, no audio devices -> fully unit-testable.
"""
from __future__ import annotations

import numpy as np


class Timeline:
    def __init__(self, t0: float, sr: int = 16_000,
                 tolerance_s: float = 0.1, hold_s: float = 0.3):
        self.t0 = t0                            # time.monotonic() when capture started
        self.sr = sr
        self.tolerance = int(tolerance_s * sr)  # ignore timing jitter below this
        self.hold_s = hold_s                    # on_tick waits this long for late real data
        self.emitted = 0                        # samples output so far
        self.padded = 0                         # silence samples inserted (diagnostics)

    def _expected(self, t: float) -> int:
        """Samples that should exist at wall-clock time t."""
        return max(0, int(round((t - self.t0) * self.sr)))

    def _silence(self, n: int) -> np.ndarray:
        self.emitted += n
        self.padded += n
        return np.zeros(n, dtype=np.float32)

    def on_chunk(self, t_arrival: float, samples: np.ndarray) -> list[np.ndarray]:
        """A chunk that ended at t_arrival. Returns [silence?, samples]."""
        out = []
        gap = (self._expected(t_arrival) - samples.size) - self.emitted
        if gap > self.tolerance:
            out.append(self._silence(gap))
        out.append(samples)
        self.emitted += samples.size
        return out

    def on_tick(self, now: float) -> np.ndarray | None:
        """Call regularly. Returns silence up to (now - hold_s) if the source is quiet."""
        gap = self._expected(now - self.hold_s) - self.emitted
        if gap > self.tolerance:
            return self._silence(gap)
        return None

    def position_s(self) -> float:
        """Seconds of audio emitted so far."""
        return self.emitted / self.sr
