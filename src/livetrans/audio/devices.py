"""Discover Windows WASAPI input devices: microphones and loopback (system output) devices.

We use PyAudioWPatch, a PyAudio fork that exposes WASAPI loopback capture.
Loopback lets us record what the speakers play (the other side of a call)
without a virtual cable driver, and the user keeps hearing the call normally.
"""
from __future__ import annotations

from dataclasses import dataclass

import pyaudiowpatch as pyaudio


@dataclass
class Device:
    index: int
    name: str
    channels: int
    sample_rate: int
    is_loopback: bool


def _to_device(info: dict) -> Device:
    return Device(
        index=int(info["index"]),
        name=str(info["name"]),
        channels=int(info["maxInputChannels"]),
        sample_rate=int(info["defaultSampleRate"]),
        is_loopback=bool(info.get("isLoopbackDevice", False)),
    )


def list_devices(pa: pyaudio.PyAudio) -> tuple[list[Device], list[Device]]:
    """Return (microphones, loopback_devices), WASAPI only."""
    wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
    mics, loops = [], []
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info["hostApi"] != wasapi["index"] or info["maxInputChannels"] < 1:
            continue
        dev = _to_device(info)
        (loops if dev.is_loopback else mics).append(dev)
    return mics, loops


def default_mic(pa: pyaudio.PyAudio) -> Device:
    wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
    return _to_device(pa.get_device_info_by_index(wasapi["defaultInputDevice"]))


def default_loopback(pa: pyaudio.PyAudio) -> Device:
    """Loopback twin of the current default speakers/headphones."""
    wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
    speakers = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
    for lb in pa.get_loopback_device_info_generator():
        if speakers["name"] in lb["name"]:
            return _to_device(lb)
    raise RuntimeError(f"No loopback device found for default output '{speakers['name']}'")


def get_device(pa: pyaudio.PyAudio, index: int) -> Device:
    return _to_device(pa.get_device_info_by_index(index))


def print_devices(pa: pyaudio.PyAudio) -> None:
    mics, loops = list_devices(pa)
    dm, dl = default_mic(pa), None
    try:
        dl = default_loopback(pa)
    except RuntimeError:
        pass
    print("Microphones (use with --mic):")
    for d in mics:
        mark = "*" if d.index == dm.index else " "
        print(f" {mark} [{d.index:>2}] {d.name}  ({d.channels}ch, {d.sample_rate} Hz)")
    print("\nSystem audio / loopback (use with --loopback):")
    for d in loops:
        mark = "*" if dl and d.index == dl.index else " "
        print(f" {mark} [{d.index:>2}] {d.name}  ({d.channels}ch, {d.sample_rate} Hz)")
    print("\n* = default")
