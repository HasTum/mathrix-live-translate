"""Tell system-side speakers apart: voiceprints (speaker embeddings) + online clustering.

SpeakerEmbedder: sherpa-onnx with NVIDIA's TitaNet-small ONNX model (trained on VoxCeleb,
Fisher, Switchboard and LibriSpeech; NeMo license), downloaded from
csukuangfj/speaker-embedding-models. Chosen by measurement, see DECISIONS.md D9.
SpeakerClusterer: compares each new voiceprint with the speakers seen so far (cosine
similarity to each speaker's average). Labels never change once given, so the same
person keeps the same "Speaker N" for the whole session (brief requirement).
"""
from __future__ import annotations

import numpy as np

REPO = "csukuangfj/speaker-embedding-models"
DEFAULT_MODEL = "nemo_en_titanet_small.onnx"
DEFAULT_THRESHOLD = 0.25        # A/B test: 0.20-0.30 gave 2 speakers, 100 % correct (D9)


class SpeakerEmbedder:
    def __init__(self, model: str = DEFAULT_MODEL, threads: int = 2):
        import sherpa_onnx                                  # imported here: tests don't need it
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(REPO, model)
        config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=path, num_threads=threads)
        if not config.validate():
            raise RuntimeError(f"invalid speaker model config for {path}")
        self._ex = sherpa_onnx.SpeakerEmbeddingExtractor(config)

    def embed(self, audio: np.ndarray) -> np.ndarray:
        """audio: float32, 16 kHz, mono. Returns the voiceprint vector."""
        stream = self._ex.create_stream()
        stream.accept_waveform(sample_rate=16_000, waveform=audio)
        stream.input_finished()
        if not self._ex.is_ready(stream):
            raise RuntimeError(f"audio too short for a voiceprint ({len(audio) / 16_000:.2f} s)")
        return np.asarray(self._ex.compute(stream), dtype=np.float32)


class SpeakerClusterer:
    """Online assignment of voiceprints to Speaker 1, 2, ...

    - similarity >= threshold to the closest speaker -> that speaker
    - otherwise a new speaker, but only from an utterance of at least min_new_s seconds;
      shorter ones give unreliable voiceprints and go to the closest existing speaker
    - only long-enough utterances update a speaker's average, keeping it clean
    """

    def __init__(self, threshold: float = DEFAULT_THRESHOLD, min_new_s: float = 1.5):
        self.threshold, self.min_new_s = threshold, min_new_s
        self._sums: list[np.ndarray] = []                   # sum of unit voiceprints per speaker

    @property
    def n_speakers(self) -> int:
        return len(self._sums)

    def assign(self, emb: np.ndarray, duration_s: float) -> tuple[int, float]:
        """Returns (speaker number starting at 1, similarity to the chosen speaker)."""
        e = emb / (np.linalg.norm(emb) + 1e-9)
        if not self._sums:                                  # first voice ever: Speaker 1
            self._sums.append(e.copy())
            return 1, 1.0
        sims = [float(e @ (s / np.linalg.norm(s))) for s in self._sums]
        best = int(np.argmax(sims))
        long_enough = duration_s >= self.min_new_s
        if sims[best] >= self.threshold or not long_enough:
            if long_enough:
                self._sums[best] += e
            return best + 1, sims[best]
        self._sums.append(e.copy())                         # a new, distinct voice
        return len(self._sums), 1.0
