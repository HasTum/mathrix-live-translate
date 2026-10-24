"""Run the full pipeline (Segmenter -> ASR -> translation) on a recorded WAV file.

    python -m livetrans.tools.run_file
    python -m livetrans.tools.run_file --audio samples/hy_test.wav --threshold-db -40

Checks on real speech, without live audio: how the Segmenter splits the take,
ASR on in-memory audio, and processing time per utterance (the main part of latency).
"""
from __future__ import annotations

import argparse
import statistics
import time

import numpy as np
import soundfile as sf

from livetrans.asr import ArmenianASR
from livetrans.audio.segmenter import Segmenter
from livetrans.eval.metrics import cer
from livetrans.output import format_segment
from livetrans.translate import ArmenianToEnglish


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", default="samples/hy_test.wav")
    ap.add_argument("--ref", default="eval/hy_test_reference.txt")
    ap.add_argument("--threshold-db", type=float, default=-40.0)
    args = ap.parse_args()

    audio, sr = sf.read(args.audio, dtype="float32")
    if sr != 16_000 or audio.ndim != 1:
        raise SystemExit("expected 16 kHz mono audio")

    print("loading models ...")
    asr, mt = ArmenianASR(), ArmenianToEnglish()

    seg = Segmenter("mic", threshold_db=args.threshold_db)
    utts = seg.feed(np.concatenate([audio, np.zeros(sr, np.float32)]))   # 1 s silence flushes the end
    print(f"{len(utts)} utterances found\n")

    texts, proc = [], []
    for u in utts:
        t = time.perf_counter()
        hy = asr.transcribe(u.audio)
        t_asr = time.perf_counter() - t
        en = mt.translate(hy)
        dt = time.perf_counter() - t
        texts.append(hy)
        proc.append(dt)
        print(format_segment(u.start_s, "Me", hy, en))
        print(f"   ({u.end_s - u.start_s:.1f} s audio | ASR {t_asr:.2f} s | total {dt:.2f} s)\n")

    if proc:
        with open(args.ref, encoding="utf-8") as f:
            reference = f.read()
        print(f"processing per utterance: median {statistics.median(proc):.2f} s, max {max(proc):.2f} s")
        print(f"estimated latency = end-of-phrase wait {seg.end_silence * seg.frame / sr:.1f} s "
              f"+ processing -> max {seg.end_silence * seg.frame / sr + max(proc):.1f} s")
        print(f"CER of all utterances joined: {cer(reference, ' '.join(texts)):.3f}")


if __name__ == "__main__":
    main()
