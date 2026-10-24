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
  
## D5 — Microphone level for the internal Conexant mic (2026-10-24)
- Problem: speech was clipped (14.9% and 7.5% of samples at full scale); p90 frame level −3 dB.
- Fix: Windows Sound → Recording → Internal Microphone → Levels: Microphone = 100, Boost = 0.0 dB; enhancements disabled.
- Evidence after fix: 60 s test recording, 0.11% clipped, p10 = −58.6 dB, p90 = −25.5 dB; speech was clear on listening.
- Must be checked again before the interview.


## D6 — ASR model: NVIDIA FastConformer Armenian via ONNX + onnx-asr (2026-10-24)
- Test: 60 s take, 8 Armenian sentences (eval/hy_test_reference.txt), this laptop, CPU only.
  Acceptance criteria set before testing: CER ≤ 0.20, RTF ≤ 0.3, peak RAM ≤ 1 GB.

| Model | CER | WER | RTF | Peak RAM | Result |
|---|---|---|---|---|---|
| Whisper tiny (faster-whisper, int8) | 0.993 | 1.000 | 0.31 | 297 MB | rejected: unrelated English output |
| Whisper base (faster-whisper, int8) | 0.807 | 0.979 | 0.87 | 462 MB | rejected: garbled mixed-language text |
| FastConformer hy (ONNX, fp32) | 0.085 | 0.146 | 0.07 | 917 MB | **chosen** |

- Model: nvidia/stt_hy_fastconformer_hybrid_large_pc (~115M params, trained on ~296 h of
  Armenian; CC-BY-4.0; published WER ~12–13 % FLEURS). Run through the ONNX export
  OpenVoiceOS/stt_hy_fastconformer_hybrid_large_pc_onnx with onnx-asr 0.12.0; no PyTorch needed.
  Load time from cache: 7.2–7.5 s.
- Not chosen: Whisper small (about 3× base's size; base already RTF 0.87, so too slow for live —
  not measured); Armenian fine-tuned Whisper large-v3 (BuzzASR/armenian, CER 3.7 % FLEURS, but
  ~1.5B+ params, GPU-oriented); small Armenian Whisper fine-tunes (no reliable published accuracy,
  need a PyTorch conversion).
- Risks: the ONNX export is a third-party conversion (CTC head only, fp32 only); peak RAM close
  to 1 GB leaves less room for translation; the model card warns it is noise-sensitive and
  non-streaming, so we will feed it one utterance at a time from the VAD.
- Observed errors on our take: "լավ եմ" → "լավավ", "ունենք" → "ունեն", last sentence partly lost.
- Next step: validate the complete live pipeline against the ≤5 s phrase-to-English-output requirement.
