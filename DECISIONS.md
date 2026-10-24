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


## D7 — Translation: NLLB-200 distilled 600M, CTranslate2 int8 (2026-10-24)
- Test: the 8 test sentences, one sentence per call (as in the live app), beam 2, 4 threads.
  Acceptance criteria set before testing: ≥ 6/8 understandable, median ≤ 1.0 s/sentence,
  peak RAM ≤ 1.2 GB.

| Source text | chrF | Understandable | Median / max time | Peak RAM |
|---|---|---|---|---|
| Correct Armenian (eval/hy_test_reference.txt) | 74.5 | 8/8 | 0.96 s / 1.06 s | 1051 MB |
| Real ASR output (eval/hy_test_asr.txt) | 69.1 | 7/8 | 0.92 s / 1.28 s | 1037 MB |

- Model: JustFrederik/nllb-200-distilled-600M-ct2-int8 (third-party int8 conversion with the
  official ct2-transformers-converter); tokenizer from facebook/nllb-200-distilled-600M.
  Runs on CTranslate2; transformers is used only for the tokenizer (no PyTorch).
- License: CC-BY-NC-4.0 (non-commercial). Acceptable for this challenge; must be stated in README.
- Alternatives: M2M100 418M (MIT license, generally weaker on low-resource languages, kept as
  fallback); OPUS-MT mul→en (Apache-2.0, no published Armenian scores; no dedicated hy→en
  model found); NLLB 1.3B and local LLMs (rejected: RAM).
- Observation: remaining errors come mostly from ASR (sentence 4 "ունեն" → "they have";
  sentence 8 lost words), so ASR is the weaker link.
- Memory: ASR ~0.9 GB + translation ~1.0 GB ≈ 2 GB → close Chrome during live use.

## D8 — Latency: cut utterances at 7 s, translation beam 2 (2026-10-24)
- Requirement R6: ≤ 5 s from end of phrase to printed line.
- Mic test (read sentences, 2–5 s each): median 1.6–1.8 s, max 2.0 s. Breakdown: end-of-phrase
  wait 0.6 s + ASR ~0.25 s + translation ~0.8–1.0 s.
- System test (Armenian podcast, continuous speech, ~60 s per run, `--timing`):

| Run | Settings | Segments | Median | p95 | Max | Over 5 s | Max MT |
|---|---|---|---|---|---|---|---|
| 1 | beam 2, max 12 s | 3 | 4.5 s | 5.9 s | 5.9 s | 1 | 5.08 s |
| 2 | beam 1, max 12 s | 3 | 4.7 s | 5.5 s | 5.5 s | 1 | 4.56 s |
| 3 | beam 2, max 7 s | 12 | 2.9 s | 4.0 s | 4.3 s | 0 | 3.77 s |

- Cause: continuous speech has no 0.6 s pauses, so utterances hit the maximum length;
  translation time grows with text length (up to ~5 s for 12 s of speech). Beam 1 did not help.
- Decision: default max utterance 7 s (`--max-utterance-s`), beam 2. Shorter input also
  gave more coherent translations; cost: some sentences are cut mid-thought.
- Risks: margin ~0.7 s; one segment waited 1.4 s in the queue; the video player (and at the
  interview, the call app) competes for the 2 CPU cores → re-measure during the rehearsal;
  6 s is the next lever. Echo: the mic hears the speakers → use headphones.
- Also fixed: utterances where ASR finds no words were dropped silently; they are now
  counted in the summary and shown with `--timing`.

