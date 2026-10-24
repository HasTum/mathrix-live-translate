"""Armenian speech recognition: NVIDIA FastConformer (ONNX export) via onnx-asr.

Chosen by measurement, see DECISIONS.md D6 (CER 0.085, RTF 0.07 on this laptop).
"""
from __future__ import annotations

import numpy as np
import onnx_asr

MODEL = "OpenVoiceOS/stt_hy_fastconformer_hybrid_large_pc_onnx"


class ArmenianASR:
    def __init__(self, model: str = MODEL):
        self._model = onnx_asr.load_model(model)

    def transcribe(self, audio: np.ndarray) -> str:
        """audio: float32, 16 kHz, mono. Returns Armenian text ('' if nothing recognized)."""
        return str(self._model.recognize(audio)).strip()
