"""Known-truth evaluation of speaker labelling (offline, repeatable).

    python -m livetrans.tools.speakers_eval
    python -m livetrans.tools.speakers_eval --thresholds 0.25 0.35

Builds test sequences with a known speaker for every piece from clean single-speaker
recordings, then runs the speaker labelling on them. Identical input every run, so a
labelling change can be compared against the baseline.
Clips: "path" or "path:start:end" (seconds) to use only a clean part of a recording.

Scenarios:
  turns        clean pieces only, speakers take turns: A B C D A B C D ...
  mixed-start  first piece mixes A then B (like two people greeting), then clean turns
  handovers    clean turns plus a mixed piece at every second change of speaker
A mixed piece = last 3 s of one speaker's piece + first 4 s of the next speaker's piece,
like a quick handover without the 0.6 s pause that would end an utterance.

Accuracy, splits and merges use clean pieces only (a mixed piece has no single true
speaker). Mixed pieces are reported separately:
  found     number of labels used in the whole sequence
  splits    extra labels given to the same person (should be 0)
  merges    extra people sharing one label (should be 0)
  ghosts    labels used only by mixed pieces, i.e. a "speaker" who is no real person (should be 0)
  accuracy  clean pieces labelled correctly with the best one-to-one label<->person matching
  mixed     how many mixed pieces got the label of one of the two people in them
"""
from __future__ import annotations

import argparse
from itertools import permutations

import numpy as np
import soundfile as sf

from livetrans.audio.segmenter import Segmenter
from livetrans.speakers import DEFAULT_MODEL, DEFAULT_THRESHOLD, SpeakerClusterer, SpeakerEmbedder

SR = 16_000
DEFAULT_CLIPS = ["samples/meet_a.wav:0:40", "samples/meet_b.wav",
                 "samples/speaker_a.wav", "samples/speaker_b.wav"]
SCENARIOS = ["turns", "mixed-start", "handovers"]


def parse_clip(spec: str) -> tuple[str, float, float | None]:
    """'path' or 'path:start:end' -> (path, start_s, end_s or None)."""
    parts = spec.rsplit(":", 2)
    if len(parts) == 3:
        try:
            return parts[0], float(parts[1]), float(parts[2])
        except ValueError:
            pass
    return spec, 0.0, None


def load_pieces(spec: str, threshold_db: float, max_s: float) -> list[np.ndarray]:
    """Cut a clean recording into pieces like the live system side; keep pieces >= 2 s."""
    path, start, end = parse_clip(spec)
    audio, sr = sf.read(path, dtype="float32")
    if sr != SR or audio.ndim != 1:
        raise SystemExit(f"{path}: expected 16 kHz mono audio")
    audio = audio[int(start * SR): None if end is None else int(end * SR)]
    seg = Segmenter("system", threshold_db=threshold_db, max_s=max_s)
    utts = seg.feed(np.concatenate([audio, np.zeros(SR, np.float32)]))
    return [u.audio for u in utts if len(u.audio) >= 2 * SR]


def build_scenario(name: str, pieces: dict[str, list[np.ndarray]],
                   rounds: int) -> tuple[list[tuple[np.ndarray, str]], int]:
    """Returns ([(audio, truth), ...], number of reused pieces). Truth 'A+B' = mixed."""
    names = list(pieces)
    used = {n: 0 for n in names}

    def take(n: str) -> np.ndarray:
        p = pieces[n][used[n] % len(pieces[n])]
        used[n] += 1
        return p

    def mixed(a: str, b: str) -> tuple[np.ndarray, str]:
        return np.concatenate([take(a)[-3 * SR:], take(b)[:4 * SR]]), f"{a}+{b}"

    seq: list[tuple[np.ndarray, str]] = []
    if name == "mixed-start":
        seq.append(mixed(names[0], names[1]))
    change = 0
    for _ in range(rounds):
        for n in names:
            if name == "handovers" and seq:
                change += 1
                if change % 2 == 0:
                    seq.append(mixed(seq[-1][1].split("+")[-1], n))
            seq.append((take(n), n))
    reused = sum(max(0, used[n] - len(pieces[n])) for n in names)
    return seq, reused


def score(labels: list[int], truth: list[str]) -> dict:
    """Scores clean pieces only; mixed pieces ('A+B') are reported separately.

    found     labels used anywhere in the sequence
    splits    extra labels given to one person (clean pieces)
    merges    extra people sharing one label (clean pieces)
    ghosts    labels used only by mixed pieces: a "speaker" who is not a real person
    accuracy  clean pieces labelled correctly under the best one-to-one label<->person match
    mixed_ok  mixed pieces that got the label of one of the two people in them
    """
    clean = [(lab, t) for lab, t in zip(labels, truth) if "+" not in t]
    mixed = [(lab, t) for lab, t in zip(labels, truth) if "+" in t]
    people = sorted({t for _, t in clean})
    labs = sorted({lab for lab, _ in clean})
    splits = sum(len({lab for lab, t in clean if t == p}) - 1 for p in people)
    merges = sum(len({t for lab, t in clean if lab == x}) - 1 for x in labs)
    ghosts = len(set(labels) - set(labs))
    candidates = labs + [None] * max(0, len(people) - len(labs))
    best, best_match = -1, {}
    for perm in permutations(candidates, len(people)):
        match = dict(zip(people, perm))
        hits = sum(match[t] == lab for lab, t in clean)
        if hits > best:
            best, best_match = hits, match
    mixed_ok = sum(lab in {best_match.get(p) for p in t.split("+")} for lab, t in mixed)
    return {"found": len(set(labels)), "splits": splits, "merges": merges, "ghosts": ghosts,
            "accuracy": best / len(clean) if clean else 0.0,
            "mixed_ok": mixed_ok, "mixed": len(mixed)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", nargs="+", default=DEFAULT_CLIPS)
    ap.add_argument("--thresholds", type=float, nargs="+", default=[DEFAULT_THRESHOLD])
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--threshold-db", type=float, default=-45.0)
    ap.add_argument("--max-utterance-s", type=float, default=7.0)
    args = ap.parse_args()

    names = [chr(ord("A") + i) for i in range(len(args.clips))]
    pieces = {}
    for n, spec in zip(names, args.clips):
        pieces[n] = load_pieces(spec, args.threshold_db, args.max_utterance_s)
        print(f"{n} = {spec}: {len(pieces[n])} clean pieces")
        if not pieces[n]:
            raise SystemExit(f"{spec}: no pieces of at least 2 s")

    emb = SpeakerEmbedder(args.model)
    for scen in SCENARIOS:
        seq, reused = build_scenario(scen, pieces, args.rounds)
        n_mixed = sum("+" in t for _, t in seq)
        vecs = [emb.embed(a) for a, _ in seq]
        truth = [t for _, t in seq]
        note = f", {reused} pieces reused" if reused else ""
        print(f"\nscenario {scen}: {len(seq)} pieces ({n_mixed} mixed{note}), "
              f"truth {len(names)} speakers")
        print("  truth   " + " ".join(f"{t:>3}" for t in truth))
        for th in args.thresholds:
            c = SpeakerClusterer(threshold=th)
            labels = [c.assign(v, len(a) / SR)[0] for v, (a, _) in zip(vecs, seq)]
            s = score(labels, truth)
            print(f"  t={th:.2f}  " + " ".join(f"{x:>3}" for x in labels))
            print(f"          found {s['found']}, splits {s['splits']}, merges {s['merges']}, "
                  f"ghosts {s['ghosts']}, accuracy {s['accuracy']:.0%} (clean pieces)"
                  + (f", mixed pieces given one of their speakers: {s['mixed_ok']}/{s['mixed']}"
                     if s["mixed"] else ""))


if __name__ == "__main__":
    main()
