"""Benchmark one faster-whisper model on a recording with a known transcript.

    python -m livetrans.tools.asr_bench --model tiny
    python -m livetrans.tools.asr_bench --model small --beam 5
    python -m livetrans.tools.asr_bench --model tiny --no-vad

Prints load time, transcription time, real-time factor (RTF = processing time /
audio length; below 1.0 means faster than real time), peak memory, how much audio
the voice detector (VAD) kept, CER and WER.
Run one model per process so the memory figure belongs to that model alone.
"""
from __future__ import annotations

import argparse
import time

import psutil
import soundfile as sf
from faster_whisper import WhisperModel

from livetrans.eval.metrics import cer, wer


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="tiny", help="tiny, base, small, ... or a local CTranslate2 folder")
    ap.add_argument("--audio", default="samples/hy_test.wav")
    ap.add_argument("--ref", default="eval/hy_test_reference.txt")
    ap.add_argument("--compute", default="int8")
    ap.add_argument("--beam", type=int, default=1)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--no-vad", action="store_true", help="give the model all audio, skip voice detection")
    args = ap.parse_args()

    audio, sr = sf.read(args.audio, dtype="float32")
    if sr != 16_000:
        raise SystemExit(f"expected 16 kHz audio, got {sr} Hz")
    duration = len(audio) / sr
    with open(args.ref, encoding="utf-8") as f:
        reference = f.read()

    t = time.perf_counter()
    model = WhisperModel(args.model, device="cpu", compute_type=args.compute, cpu_threads=args.threads)
    load_s = time.perf_counter() - t

    t = time.perf_counter()
    segments, info = model.transcribe(audio, language="hy", beam_size=args.beam,
                                      vad_filter=not args.no_vad)
    segments = list(segments)                  # decoding actually happens here (lazy generator)
    asr_s = time.perf_counter() - t

    hypothesis = " ".join(s.text.strip() for s in segments)
    mem = psutil.Process().memory_info()
    peak_mb = getattr(mem, "peak_wset", mem.rss) / 2**20   # peak_wset exists on Windows

    print("\nSegments:")
    for s in segments:
        print(f"  [{s.start:6.2f} -> {s.end:6.2f}] {s.text.strip()}")
    vad = "off" if args.no_vad else "on"
    print(f"\nmodel={args.model} compute={args.compute} beam={args.beam} threads={args.threads} vad={vad}")
    print(f"audio {duration:.1f} s | speech kept by VAD {info.duration_after_vad:.1f} s")
    print(f"load {load_s:.1f} s | transcribe {asr_s:.1f} s | "
          f"RTF {asr_s / duration:.2f} | peak RAM {peak_mb:.0f} MB")
    print(f"CER {cer(reference, hypothesis):.3f} | WER {wer(reference, hypothesis):.3f}")


if __name__ == "__main__":
    main()
