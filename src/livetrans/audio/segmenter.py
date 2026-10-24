"""Split one audio source into utterances with a simple loudness threshold.

Minimal first version (PLAN rule: end-to-end first, then improve the weakest part).
It runs on the gap-free 16 kHz stream from Timeline, so silence on the system side
(WASAPI loopback sends nothing) still closes an utterance.

An utterance starts at the first loud frame (plus a short pre-roll so the first
syllable is not cut) and ends after `end_silence_s` of quiet frames, or when it
reaches `max_s` (keeps latency bounded during long monologues).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Utterance:
    source: str           # "mic" or "system"
    start_s: float        # seconds since session start (timeline position), incl. pre-roll
    end_s: float          # end of the last loud frame
    audio: np.ndarray     # float32, 16 kHz, mono


class Segmenter:
    def __init__(self, source: str, sr: int = 16_000, frame_ms: int = 30,
                 threshold_db: float = -40.0, end_silence_s: float = 0.6,
                 min_speech_s: float = 0.3, max_s: float = 12.0, preroll_s: float = 0.3):
        self.source, self.sr = source, sr
        self.frame = int(sr * frame_ms / 1000)                  # samples per frame
        self.threshold_db = threshold_db
        self.end_silence = round(end_silence_s * 1000 / frame_ms)   # all counts in frames
        self.min_speech = round(min_speech_s * 1000 / frame_ms)
        self.max_frames = round(max_s * 1000 / frame_ms)
        self.preroll = round(preroll_s * 1000 / frame_ms)
        self._pending = np.zeros(0, np.float32)   # leftover samples, less than one frame
        self._idx = 0                             # timeline index of the next frame
        self._history: list[np.ndarray] = []      # recent quiet frames (pre-roll)
        self._frames: list[np.ndarray] = []       # frames of the current utterance
        self._start: int | None = None            # frame index where the utterance starts
        self._speech = 0                          # loud frames in the current utterance
        self._silence = 0                         # consecutive quiet frames at the end
        self._last_loud = 0

    def feed(self, samples: np.ndarray) -> list[Utterance]:
        """Add samples; return any utterances that just finished."""
        x = np.concatenate([self._pending, samples.astype(np.float32, copy=False)])
        n = len(x) // self.frame
        self._pending = x[n * self.frame:]
        out = []
        for k in range(n):
            u = self._process(x[k * self.frame:(k + 1) * self.frame])
            if u is not None:
                out.append(u)
        return out

    def _process(self, f: np.ndarray) -> Utterance | None:
        idx = self._idx
        self._idx += 1
        loud = 20 * np.log10(np.sqrt(np.mean(f ** 2)) + 1e-12) > self.threshold_db

        if self._start is None:                   # waiting for speech
            if loud:
                self._frames = self._history + [f]
                self._start = idx - len(self._history)
                self._history = []
                self._speech, self._silence, self._last_loud = 1, 0, idx
            else:
                self._history.append(f)
                if len(self._history) > self.preroll:
                    self._history.pop(0)
            return None

        self._frames.append(f)                    # inside an utterance
        if loud:
            self._speech += 1
            self._silence = 0
            self._last_loud = idx
        else:
            self._silence += 1
        if self._silence >= self.end_silence or len(self._frames) >= self.max_frames:
            return self._close()
        return None

    def _close(self) -> Utterance | None:
        frames, start, last, speech = self._frames, self._start, self._last_loud, self._speech
        self._frames, self._start, self._speech, self._silence = [], None, 0, 0
        if speech < self.min_speech:              # a click or cough, not speech
            return None
        sec = self.frame / self.sr
        return Utterance(self.source, start * sec, (last + 1) * sec, np.concatenate(frames))
