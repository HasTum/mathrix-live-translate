
"""Live Armenian -> English transcription and translation with speaker labels.

    python -m livetrans.app --list
    python -m livetrans.app
    python -m livetrans.app --mic 9 --loopback 10 --timing
    python -m livetrans.app --max-utterance-s 7 --mt-beam 1 --timing

Captures the microphone ("Me") and system audio (the call) at the same time and cuts
each into utterances. One worker thread runs ASR and translation and prints every
segment with its latency (end of phrase -> printed). Ctrl+C stops and prints latency
statistics. --timing also shows where the time goes and reports skipped utterances.
M4: all system audio is labelled "Speaker 1"; separating call speakers is M6.
"""
from __future__ import annotations

import argparse
import queue
import statistics
import sys
import threading
import time

import pyaudiowpatch as pyaudio

from livetrans.asr import ArmenianASR
from livetrans.audio.capture import TARGET_SR, AudioSource
from livetrans.audio.devices import default_loopback, default_mic, get_device, print_devices
from livetrans.audio.segmenter import Segmenter
from livetrans.audio.timeline import Timeline
from livetrans.output import format_segment
from livetrans.translate import ArmenianToEnglish

LABELS = {"mic": "Me", "system": "Speaker 1"}


def worker(jobs: queue.Queue, t0: float, asr: ArmenianASR, mt: ArmenianToEnglish,
           stats: list[dict], skipped: list[float], show_timing: bool) -> None:
    """Process utterances one at a time (2 CPU cores: parallel models would only compete)."""
    while True:
        u = jobs.get()
        if u is None:                         # stop signal
            return
        t_start = time.monotonic()
        hy = asr.transcribe(u.audio)
        t_asr = time.monotonic()
        audio_s = len(u.audio) / TARGET_SR
        if not hy:                            # report it: never drop speech silently
            skipped.append(audio_s)
            if show_timing:
                print(f"   [skipped: ASR found no words in {audio_s:.1f} s of "
                      f"{LABELS[u.source]} audio at {u.start_s:.1f} s]\n", flush=True)
            continue
        en = mt.translate(hy)
        t_end = time.monotonic()
        rec = {"source": u.source,
               "latency": t_end - (t0 + u.end_s),       # end of phrase -> printed
               "audio": audio_s,
               "wait": t_start - (t0 + u.end_s),        # end-of-phrase detection + queue
               "asr": t_asr - t_start,
               "mt": t_end - t_asr}
        stats.append(rec)
        print(format_segment(u.start_s, LABELS[u.source], hy, en, rec["latency"]), flush=True)
        if show_timing:
            print(f"   [audio {rec['audio']:.1f} s | waited {rec['wait']:.1f} s | "
                  f"ASR {rec['asr']:.2f} s | MT {rec['mt']:.2f} s]", flush=True)
        print(flush=True)


def report(stats: list[dict], skipped: list[float]) -> None:
    if not stats:
        print(f"\nno segments were processed ({len(skipped)} skipped)")
        return
    lat = sorted(r["latency"] for r in stats)
    p95 = lat[round(0.95 * (len(lat) - 1))]
    over = sum(x > 5.0 for x in lat)
    n_me = sum(r["source"] == "mic" for r in stats)
    med = {k: statistics.median(r[k] for r in stats) for k in ("audio", "wait", "asr", "mt")}
    print(f"\n{len(lat)} segments ({n_me} Me, {len(lat) - n_me} system), {len(skipped)} skipped "
          f"| latency median {statistics.median(lat):.1f} s, p95 {p95:.1f} s, "
          f"max {lat[-1]:.1f} s | over 5 s: {over}")
    print(f"medians: audio {med['audio']:.1f} s | waited {med['wait']:.1f} s | "
          f"ASR {med['asr']:.2f} s | MT {med['mt']:.2f} s (max MT {max(r['mt'] for r in stats):.2f} s)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Live Armenian -> English transcription")
    ap.add_argument("--list", action="store_true", help="print audio devices and exit")
    ap.add_argument("--mic", type=int, help="microphone device index (default: system default)")
    ap.add_argument("--loopback", type=int, help="loopback device index (default: default speakers)")
    ap.add_argument("--threshold-db", type=float, default=-40.0,
                    help="mic loudness that counts as speech (default -40)")
    ap.add_argument("--system-threshold-db", type=float, default=-45.0,
                    help="system-audio loudness that counts as speech (default -45)")
    ap.add_argument("--end-silence-s", type=float, default=0.6,
                    help="pause that ends a phrase (default 0.6)")
    ap.add_argument("--max-utterance-s", type=float, default=7.0,
                    help="cut longer speech into pieces of this length (default 7)")
    ap.add_argument("--mt-beam", type=int, default=2, help="translation beam size (default 2)")
    ap.add_argument("--timing", action="store_true", help="show waiting/ASR/translation times")
    args = ap.parse_args()

    pa = pyaudio.PyAudio()
    try:
        if args.list:
            print_devices(pa)
            return
        mic = get_device(pa, args.mic) if args.mic is not None else default_mic(pa)
        loop = get_device(pa, args.loopback) if args.loopback is not None else default_loopback(pa)
        print(f"mic:    [{mic.index}] {mic.name}")
        print(f"system: [{loop.index}] {loop.name}")
        print(f"settings: end-silence {args.end_silence_s} s, max utterance "
              f"{args.max_utterance_s} s, MT beam {args.mt_beam}")
        print("loading models ...", flush=True)
        asr, mt = ArmenianASR(), ArmenianToEnglish(beam=args.mt_beam)

        chunks: queue.Queue = queue.Queue()
        jobs: queue.Queue = queue.Queue()
        stats: list[dict] = []
        skipped: list[float] = []
        sources = [AudioSource(pa, mic, "mic", chunks), AudioSource(pa, loop, "system", chunks)]
        seg_args = dict(end_silence_s=args.end_silence_s, max_s=args.max_utterance_s)
        segmenters = {"mic": Segmenter("mic", threshold_db=args.threshold_db, **seg_args),
                      "system": Segmenter("system", threshold_db=args.system_threshold_db,
                                          **seg_args)}

        t0 = time.monotonic()                 # shared clock for timestamps and latency
        timelines = {s.source: Timeline(t0, TARGET_SR) for s in sources}
        th = threading.Thread(target=worker,
                              args=(jobs, t0, asr, mt, stats, skipped, args.timing), daemon=True)
        th.start()
        for s in sources:
            s.start()
        print("listening - speak Armenian. Ctrl+C to stop.\n", flush=True)

        def push(name: str, parts: list) -> None:
            for part in parts:
                for u in segmenters[name].feed(part):
                    jobs.put(u)
                    if jobs.qsize() > 2:
                        print(f"[warning] {jobs.qsize()} utterances waiting: processing is "
                              f"falling behind", file=sys.stderr, flush=True)

        try:
            while True:
                try:
                    c = chunks.get(timeout=0.05)
                    push(c.source, timelines[c.source].on_chunk(c.t, c.samples))
                except queue.Empty:
                    pass
                now = time.monotonic()
                for name, tl in timelines.items():   # keep quiet sources moving (see D4)
                    part = tl.on_tick(now)
                    if part is not None:
                        push(name, [part])
        except KeyboardInterrupt:
            print("\nstopping ...", flush=True)
        finally:
            for s in sources:
                s.stop()
        jobs.put(None)                        # let the worker finish what is queued
        th.join(timeout=30)
        report(stats, skipped)
    finally:
        pa.terminate()


if __name__ == "__main__":
    main()
