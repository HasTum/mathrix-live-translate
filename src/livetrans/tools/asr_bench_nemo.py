"""Benchmark NVIDIA's Armenian FastConformer (ONNX export, run with onnx-asr) on the test take.

    python -m livetrans.tools.asr_bench_nemo

Model: nvidia/stt_hy_fastconformer_hybrid_large_pc (CC-BY-4.0); ONNX export
OpenVoiceOS/stt_hy_fastconformer_hybrid_large_pc_onnx (same weights, CTC head).
Prints load time, transcription time, RTF, peak RAM, CER and WER, like asr_bench.
"""
from __future__ import annotations

import argparse
import time

import onnx_asr
import psutil
import soundfile as sf

from livetrans.eval.metrics import cer, wer

MODEL = "OpenVoiceOS/stt_hy_fastconformer_hybrid_large_pc_onnx"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--audio", default="samples/hy_test.wav")
    ap.add_argument("--ref", default="eval/hy_test_reference.txt")
    args = ap.parse_args()

    info = sf.info(args.audio)
    if info.samplerate != 16_000 or info.channels != 1:
        raise SystemExit(f"expected 16 kHz mono, got {info.samplerate} Hz, {info.channels} ch")
    duration = info.frames / info.samplerate
    with open(args.ref, encoding="utf-8") as f:
        reference = f.read()

    t = time.perf_counter()
    model = onnx_asr.load_model(args.model)
    load_s = time.perf_counter() - t

    t = time.perf_counter()
    hypothesis = model.recognize(args.audio)
    asr_s = time.perf_counter() - t

    mem = psutil.Process().memory_info()
    peak_mb = getattr(mem, "peak_wset", mem.rss) / 2**20   # peak_wset exists on Windows

    print(f"\nText:\n  {hypothesis}")
    print(f"\nmodel={args.model}")
    print(f"audio {duration:.1f} s | load {load_s:.1f} s | transcribe {asr_s:.1f} s | "
          f"RTF {asr_s / duration:.2f} | peak RAM {peak_mb:.0f} MB")
    print(f"CER {cer(reference, hypothesis):.3f} | WER {wer(reference, hypothesis):.3f}")


if __name__ == "__main__":
    main()
