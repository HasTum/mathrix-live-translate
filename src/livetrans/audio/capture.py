"""Capture one audio device and deliver 16 kHz mono float32 chunks to a queue.

Every downstream model (VAD, ASR, speaker embeddings) expects 16 kHz mono,
so we convert once, here, as early as possible.
"""
from __future__ import annotations

import queue
import time
from dataclasses import dataclass

import numpy as np
import pyaudiowpatch as pyaudio
import soxr

from .devices import Device

TARGET_SR = 16_000


@dataclass
class AudioChunk:
    source: str          # "mic" or "system"
    t: float             # time.monotonic() when the chunk arrived
    samples: np.ndarray  # float32, mono, 16 kHz, range [-1, 1]


class AudioSource:
    def __init__(self, pa: pyaudio.PyAudio, device: Device, source: str,
                 out: "queue.Queue[AudioChunk]", block_ms: int = 30):
        self.pa, self.device, self.source, self.out = pa, device, source, out
        self.frames_per_buffer = int(device.sample_rate * block_ms / 1000)
        # Streaming resampler keeps state between chunks -> no clicks at chunk edges.
        self._resampler = soxr.ResampleStream(device.sample_rate, TARGET_SR, 1, dtype="float32")
        self._stream = None

    def _callback(self, in_data, frame_count, time_info, status):
        x = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
        if self.device.channels > 1:
            x = x.reshape(-1, self.device.channels).mean(axis=1)
        y = self._resampler.resample_chunk(x)
        if y.size:
            self.out.put(AudioChunk(self.source, time.monotonic(), y))
        return (None, pyaudio.paContinue)

    def start(self) -> None:
        self._stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=self.device.channels,
            rate=self.device.sample_rate,
            input=True,
            input_device_index=self.device.index,
            frames_per_buffer=self.frames_per_buffer,
            stream_callback=self._callback,
        )
        self._stream.start_stream()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
