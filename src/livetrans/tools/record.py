"""Step-1 test tool: list devices, record mic + system audio, show live levels, save WAVs.

    python -m livetrans.tools.record --list
    python -m livetrans.tools.record --seconds 20
    python -m livetrans.tools.record --mic 3 --loopback 12 --seconds 20

The saved WAVs (16 kHz mono) are also our test material for comparing ASR models.
"""
from __future__ import annotations

import argparse
import queue
import time
from pathlib import Path

import numpy as np
import pyaudiowpatch as pyaudio
import soundfile as sf

from livetrans.audio.capture import TARGET_SR, AudioSource
from livetrans.audio.devices import default_loopback, default_mic, get_device, print_devices


def bar(rms: float, width: int = 20) -> str:
    db = 20 * np.log10(max(rms, 1e-6))          # -120 .. 0 dBFS
    n = int(np.clip((db + 60) / 60, 0, 1) * width)
    return "#" * n + "." * (width - n) + f" {db:6.1f} dB"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="print devices and exit")
    ap.add_argument("--mic", type=int, help="microphone device index (default: system default)")
    ap.add_argument("--loopback", type=int, help="loopback device index (default: default speakers)")
    ap.add_argument("--seconds", type=float, default=15)
    ap.add_argument("--out", default="samples")
    args = ap.parse_args()

    pa = pyaudio.PyAudio()
    try:
        if args.list:
            print_devices(pa)
            return

        mic = get_device(pa, args.mic) if args.mic is not None else default_mic(pa)
        loop = get_device(pa, args.loopback) if args.loopback is not None else default_loopback(pa)
        print(f"mic:    [{mic.index}] {mic.name} ({mic.sample_rate} Hz)")
        print(f"system: [{loop.index}] {loop.name} ({loop.sample_rate} Hz)\n")

        q: queue.Queue = queue.Queue()
        sources = [AudioSource(pa, mic, "mic", q), AudioSource(pa, loop, "system", q)]
        for s in sources:
            s.start()

        buf = {"mic": [], "system": []}
        last = {"mic": 0.0, "system": 0.0}
        t0 = t_print = time.monotonic()
        while time.monotonic() - t0 < args.seconds:
            try:
                c = q.get(timeout=0.1)
                buf[c.source].append(c.samples)
                last[c.source] = max(last[c.source], float(np.sqrt(np.mean(c.samples ** 2))))
            except queue.Empty:
                pass
            if time.monotonic() - t_print >= 0.5:
                print(f"\rmic {bar(last['mic'])} | system {bar(last['system'])}", end="", flush=True)
                last = {"mic": 0.0, "system": 0.0}
                t_print = time.monotonic()
        print()
        for s in sources:
            s.stop()

        out = Path(args.out)
        out.mkdir(exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for name, chunks in buf.items():
            audio = np.concatenate(chunks) if chunks else np.zeros(0, np.float32)
            path = out / f"{stamp}_{name}.wav"
            sf.write(path, audio, TARGET_SR)
            print(f"saved {path}  ({len(audio) / TARGET_SR:.1f} s)")
    finally:
        pa.terminate()


if __name__ == "__main__":
    main()
