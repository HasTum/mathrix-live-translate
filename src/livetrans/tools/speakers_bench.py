"""Compare speaker labelling settings on recorded system-audio clips.

    python -m livetrans.tools.speakers_bench --asr
    python -m livetrans.tools.speakers_bench --audio samples/speaker_a.wav --audio2 samples/speaker_b.wav --model nemo_en_titanet_small.onnx

Cuts each clip into utterances (same Segmenter settings as the live system side), computes
one voiceprint per utterance and assigns labels at several thresholds.
With --audio2 (a different person) it also reports similarity between the clips and runs
an interleaved test: utterances alternate A, B, A, B... (truth known) and each threshold
is scored for the number of speakers found and labelling accuracy.
"""
from __future__ import annotations

import argparse
import statistics
import time
from collections import Counter

import numpy as np
import psutil
import soundfile as sf

from livetrans.audio.segmenter import Segmenter
from livetrans.output import format_time
from livetrans.speakers import DEFAULT_MODEL, SpeakerClusterer, SpeakerEmbedder


def load_utterances(path: str, args: argparse.Namespace) -> list:
    audio, sr = sf.read(path, dtype="float32")
    if sr != 16_000 or audio.ndim != 1:
        raise SystemExit(f"{path}: expected 16 kHz mono audio")
    seg = Segmenter("system", threshold_db=args.threshold_db, max_s=args.max_utterance_s)
    return seg.feed(np.concatenate([audio, np.zeros(sr, np.float32)]))


def unit(v: np.ndarray) -> np.ndarray:
    return v / (np.linalg.norm(v) + 1e-9)


def accuracy(pred: list[int], truth: list[str]) -> float:
    """Each predicted label counts as the true speaker most often behind it."""
    correct = 0
    for label in set(pred):
        behind = Counter(t for p, t in zip(pred, truth) if p == label)
        correct += behind.most_common(1)[0][1]
    return correct / len(pred)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", default="samples/speakers_test.wav")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--thresholds", type=float, nargs="+",
                    default=[0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6])
    ap.add_argument("--min-new-s", type=float, default=1.5)
    ap.add_argument("--threshold-db", type=float, default=-45.0)
    ap.add_argument("--max-utterance-s", type=float, default=7.0)
    ap.add_argument("--ref-utt", type=int, default=1, help="show similarity to this utterance")
    ap.add_argument("--audio2", help="recording of a different person (enables the A/B test)")
    ap.add_argument("--center", action="store_true", help="subtract the average voiceprint")
    ap.add_argument("--scale", type=float, default=1.0, help="multiply audio before the voiceprint")
    ap.add_argument("--asr", action="store_true", help="also print the Armenian text")
    args = ap.parse_args()

    utts = load_utterances(args.audio, args)
    print(f"{len(utts)} utterances in {args.audio}")

    rss0 = psutil.Process().memory_info().rss / 2**20
    t = time.perf_counter()
    emb = SpeakerEmbedder(args.model)
    print(f"model {args.model} loaded in {time.perf_counter() - t:.1f} s")
    raw, times = [], []
    for u in utts:
        t = time.perf_counter()
        raw.append(unit(emb.embed(u.audio * args.scale)))
        times.append(time.perf_counter() - t)
    rss1 = psutil.Process().memory_info().rss / 2**20
    print(f"voiceprint time per utterance: median {statistics.median(times):.3f} s, "
          f"max {max(times):.3f} s | extra RAM ~{rss1 - rss0:.0f} MB")

    utts2, raw2 = [], []
    if args.audio2:
        utts2 = load_utterances(args.audio2, args)
        raw2 = [unit(emb.embed(u.audio * args.scale)) for u in utts2]

    if args.center:                                      # remove the component all voices share
        mu = np.mean(np.stack(raw + raw2), axis=0)
        raw = [unit(v - mu) for v in raw]
        raw2 = [unit(v - mu) for v in raw2]
        print("centered: average voiceprint subtracted")

    U = np.stack(raw)
    S = U @ U.T                                          # cosine similarity of every pair
    pairs = S[np.triu_indices(len(U), 1)]
    print(f"pairwise similarity within the clip: min {pairs.min():.2f}, "
          f"median {np.median(pairs):.2f}, max {pairs.max():.2f}")

    if raw2:
        V = np.stack(raw2)
        X = U @ V.T
        within2 = (V @ V.T)[np.triu_indices(len(V), 1)]
        print(f"similarity clip vs {args.audio2} ({len(V)} utterances): "
              f"median {np.median(X):.2f}, max {X.max():.2f}  "
              f"[within {args.audio2}: median {np.median(within2):.2f}, min {within2.min():.2f}]")

        # Interleaved test: A1 B1 A2 B2 ... - the truth is known, so score it.
        seq, truth = [], []
        for i in range(max(len(raw), len(raw2))):
            for vecs, us, name in ((raw, utts, "A"), (raw2, utts2, "B")):
                if i < len(vecs):
                    seq.append((vecs[i], len(us[i].audio) / 16_000))
                    truth.append(name)
        print(f"\ninterleaved A/B test ({len(seq)} utterances, truth: 2 speakers):")
        for th in args.thresholds:
            c = SpeakerClusterer(threshold=th, min_new_s=args.min_new_s)
            pred = [c.assign(v, d)[0] for v, d in seq]
            print(f"  threshold {th:.2f}: {c.n_speakers} speakers, "
                  f"accuracy {accuracy(pred, truth):.0%}  labels {''.join(map(str, pred))}")

    print()
    labels = {}
    for th in args.thresholds:
        c = SpeakerClusterer(threshold=th, min_new_s=args.min_new_s)
        labels[th] = [c.assign(v, len(u.audio) / 16_000)[0] for v, u in zip(raw, utts)]
        print(f"{args.audio} alone, threshold {th:.2f}: {c.n_speakers} speakers")

    asr = None
    if args.asr:
        from livetrans.asr import ArmenianASR
        asr = ArmenianASR()

    ref = args.ref_utt - 1
    head = (f"  #  time      dur  sim#{args.ref_utt:<2} "
            + " ".join(f"t{th:.2f}" for th in args.thresholds))
    print("\n" + head)
    for i, u in enumerate(utts):
        cols = " ".join(f"{labels[th][i]:>5}" for th in args.thresholds)
        line = (f"{i + 1:3}  {format_time(u.start_s)}  {len(u.audio) / 16_000:4.1f}  "
                f"{S[i, ref]:5.2f}  {cols}")
        if asr:
            line += "  " + asr.transcribe(u.audio)[:60]
        print(line)


if __name__ == "__main__":
    main()
