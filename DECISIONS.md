# DECISIONS

Each entry: decision, why, evidence, alternatives.

## D1 — Python 3.11 in a dedicated conda env `livetrans` (2026-10-24)
- Why: the old `.venv` was created from conda's `tf_env` (Python 3.10.16) and would
  break if `tf_env` changes. Anaconda stops new Python 3.10 builds after 2026-10-31.
  3.11 is inside the project's `requires-python` range.
- Evidence: all dependencies installed as prebuilt cp311 wheels; capture works on 3.11.
- Alternative rejected: keep the 3.10 `.venv`.

## D2 — Tooling: cmd.exe and IDLE (2026-10-24)
- Machine is Windows 10 21H2 (build 19044), not Windows 11.
- Notepad does not open on this machine; VS Code is not installed.
  IDLE (from the project env) is used to edit files for now.

## D3 — System audio via WASAPI loopback with PyAudioWPatch
- Why: captures what the speakers play without a virtual cable driver;
  the user still hears the call normally.
- Evidence: 20 s recordings at 48 kHz from "Speakers [Loopback]" alongside the mic.

## D4 — Fill silence gaps with a per-source Timeline (2026-10-24)
- Problem: WASAPI loopback delivers no data while nothing plays.
  Evidence: 20 s recording with no playback produced a 0.0 s system file.
  Without a fix, quiet periods vanish and later timestamps are wrong (breaks R5).
- Decision: `audio/timeline.py` tracks expected samples from the shared clock
  and inserts silence. Inserted amount is reported, not hidden.
- Evidence after fix: 5/5 unit tests pass; live 20 s run gave mic 20.0 s
  (0.3 s inserted) and system 20.0 s (4.6 s inserted).
- Trade-offs: silence is declared only after 0.3 s (`hold_s`), which does not
  delay speech. Drift between the sound-card clock and the system clock is not
  corrected yet; revisit if long sessions show misalignment.
