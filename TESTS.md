# TESTS — mathrix-live-translate

Requirement → test map. Every number below is copied from a measurement recorded in
DECISIONS.md (D1–D9) or from a test run in the project chat; nothing is estimated.
Measurements were made on the interview laptop (Windows 10 21H2, i5-4200M, 2 cores,
5.9 GB RAM, no GPU), 2026-10-24.

## 1. Automated tests

Command (from the project folder):

    C:\ProgramData\anaconda3\envs\livetrans\python.exe -m pytest -q

Latest verified result: **29 passed** (2026-10-24, at commit f5e73db).

| File | Tests | Covers |
|---|---|---|
| tests/test_timeline.py | 5 | R1, R5: silence gaps in loopback audio are filled, so timestamps stay correct |
| tests/test_segmenter.py | 7 | R5, R6: phrase boundaries, pre-roll, end-of-phrase wait, 7 s / 12 s cuts, chunk-size independence |
| tests/test_metrics.py | 8 | R2: CER/WER used to choose models (Armenian punctuation, "և" = "եւ") |
| tests/test_output.py | 3 | R5: time, speaker, HY and EN lines in the brief's format |
| tests/test_speakers.py | 6 | R4: new voice → new label, same voice keeps its label, short clips cannot create speakers |

The automated tests cover pure logic only. Audio devices and models are covered by the
measurement tools and manual checks below.

## 2. Measurement tools (re-runnable, need audio files in samples/ — not committed)

| Tool | Measures |
|---|---|
| `python -m livetrans.tools.record` | capture of both sources, length, inserted silence |
| `python -m livetrans.tools.asr_bench` | Whisper models: CER, WER, RTF, RAM |
| `python -m livetrans.tools.asr_bench_nemo` | chosen ASR: CER, WER, RTF, RAM |
| `python -m livetrans.tools.mt_bench` | translation: chrF, time per sentence, RAM |
| `python -m livetrans.tools.run_file` | full pipeline on a WAV file: utterances, CER, processing time |
| `python -m livetrans.tools.speakers_bench` | voiceprint similarity, interleaved A/B labelling test |
| `python -m livetrans.app --timing` | live run: per-segment latency breakdown and summary |

Reference texts: eval/hy_test_reference.txt (8 Armenian sentences),
eval/hy_test_reference_en.txt (English), eval/hy_test_asr.txt (real ASR output).

## 3. Requirement map with results

### R1 — Mic and system audio at the same time; user picks devices
- Automated: tests/test_timeline.py (5).
- Manual, done: `record --list` shows the mic [9] and the speakers' loopback [10];
  `--mic` / `--loopback` select devices (D3).
- Manual, done: 20 s recording with no playback gave a 0.0 s system file before the fix;
  after the fix both files were 20.0 s (system: 4.6 s silence inserted) (D4).

### R2 — Armenian transcription
- Automated: tests/test_metrics.py (8).
- Measured on a 60 s take of 8 read sentences (D6):

| Model | CER | WER | RTF | Peak RAM | Result |
|---|---|---|---|---|---|
| Whisper tiny | 0.993 | 1.000 | 0.31 | 297 MB | rejected |
| Whisper base | 0.807 | 0.979 | 0.87 | 462 MB | rejected |
| FastConformer hy (ONNX) | 0.085 | 0.146 | 0.06–0.07 | 917 MB | chosen |

- Full pipeline on the same take (`run_file`): 9 utterances for 8 sentences (one sentence
  split at a pause), CER 0.072.
- Known errors: "լավ եմ" → "լավավ", "ունենք" → "ունեն", last sentence partly lost.

### R3 — English translation
- Measured on the 8 sentences, one call per sentence, beam 2 (D7):

| Source text | chrF | Understandable | Median / max time | Peak RAM |
|---|---|---|---|---|
| Correct Armenian | 74.5 | 8/8 | 0.96 s / 1.06 s | 1051 MB |
| Real ASR output | 69.1 | 7/8 | 0.92 s / 1.28 s | 1037 MB |

- The "understandable" counts are the assessment recorded in D7; the developer's own
  count is still to be confirmed.

### R4 — Speakers: mic = "Me", call side = "Speaker 1", "Speaker 2", stable for the session
- Automated: tests/test_speakers.py (6).
- Measured, two single-speaker clips A and B recorded through system audio (D9):
  TitaNet-small, A vs B similarity 0.12 (max 0.25), within A 0.80, within B 0.50;
  interleaved A/B test (18 utterances): thresholds 0.20–0.30 → 2 speakers, all labels
  correct; >= 0.35 → B split into two speakers. Chosen threshold: 0.25.
- Live, done: two-person Armenian podcast (host + guest): 9 segments, host → Speaker 1,
  guest → Speaker 2, host returning → Speaker 1 again (similarity 0.80) (D9).
- Known limitation: one 7 s cut contained the end of the host and the start of the guest.

### R5 — Live terminal output with time, speaker, Armenian and English
- Automated: tests/test_output.py (3), tests/test_timeline.py (5), tests/test_segmenter.py (7).
- Manual, done: live runs print the format from the brief.

### R6 — Latency at most 5 s (end of phrase → English line printed)
- Mic, read sentences: median 1.6–1.8 s, max 2.0 s (D8).
- System audio, continuous podcast speech (D8):

| Settings | Segments | Median | p95 | Max | Over 5 s |
|---|---|---|---|---|---|
| beam 2, max 12 s | 3 | 4.5 s | 5.9 s | 5.9 s | 1 |
| beam 1, max 12 s | 3 | 4.7 s | 5.5 s | 5.5 s | 1 |
| beam 2, max 7 s (chosen) | 12 | 2.9 s | 4.0 s | 4.3 s | 0 |

- With speaker identification (D9): 9 segments, median 3.1 s, max 4.4 s, 0 over 5 s;
  speaker step median 0.17 s.
- Margin is about 0.6–0.7 s; must be re-measured under real call conditions (see M1).

### R7 — Local models only
- Manual, done: all models run on the CPU of this laptop through onnx-asr, CTranslate2
  and sherpa-onnx; no cloud speech or translation API is called in the code.
- Note: models are downloaded once from Hugging Face into the user cache.
- Pending: run once with the network disconnected (see M2).

### R8 — Runs on the interview laptop
- Manual, done: every measurement above was made on this laptop.
- Memory: ASR ~0.9 GB + translation ~1.0 GB + speakers ~0.2 GB ≈ 2.1 GB → close Chrome.

### R9 — Deliverables
- README: pending. Chat exports in chats/ (one .md per session): pending.

### R10 — No model weights, audio recordings or API keys in Git
- .gitignore excludes .venv, samples/*, models/, *.wav, *.bin, *.safetensors, *.pt, .env.
- Pending: final check before submission (see M4).

## 4. Pending manual tests

| ID | Test | Pass criteria | Status |
|---|---|---|---|
| M1 | Interview rehearsal: real video call with **at least two Armenian-speaking participants** on the call side, headphones on my side, `python -m livetrans.app --timing` | each caller keeps one "Speaker N" label; "Me" only for my voice; 0 segments over 5 s; English understandable | **PENDING** |
| M2 | Offline run: disconnect the network, start the app, speak and play audio | app loads cached models and works without network | PENDING |
| M3 | Mic level check before the interview (Windows Sound → Recording → Levels, see D5) | `record` take: clipped < 0.1 %, speech p90 between −25 and −12 dB | PENDING (re-check on the day) |
| M4 | Repository check: `git ls-files` contains no .wav, .onnx, .bin or other model/audio files | no such files listed | PENDING |
