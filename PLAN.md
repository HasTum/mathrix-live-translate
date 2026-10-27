# PLAN — mathrix-live-translate

## Goal
A local Python app (Windows 10, this laptop) that captures microphone and system audio
at the same time, transcribes Armenian speech, translates it to English, labels speakers,
and prints timestamped lines in the terminal within 5 s. No cloud speech/translation APIs.
Source of truth: "Coding Challenge: Live Armenian Transcription → English Translation" (Oct 21, 2026).
Deadline: ~2026-10-30, ~20 h total.

## Requirements (from the brief)
- R1 Capture mic + system audio simultaneously; user picks devices (device list / CLI flags)
- R2 Transcribe spoken Armenian to Armenian text
- R3 Translate each segment to English
- R4 Speakers: mic = "Me"; system side = "Speaker 1", "Speaker 2"…, stable for the whole session
- R5 Live terminal output per segment: time, speaker, HY original, EN translation
- R6 Latency ≤ 5 s from end of phrase to its English line
- R7 Transcription, translation and speaker identification run locally
- R8 Runs on the laptop brought to the interview (i5-4200M, 2 cores, 5.9 GB RAM, no GPU)
- R9 Deliverables: Git repo, README (setup, audio setup, model choices + alternatives,
  architecture, limitations), complete unedited chat exports in `chats/` (one .md per session)
- R10 Never commit model weights, audio recordings or API keys

Out of scope: GUI, installer, echo handling, naming speakers, saving transcripts, other languages.

## Output format
    [00:01:12] Speaker 1
    HY: Բարև, ինչպե՞ս ես։
    EN: Hi, how are you?

## Pipeline and modules
| Module | Input | Output | Status |
|---|---|---|---|
| `audio/devices.py` | WASAPI devices | mic + loopback device info | done |
| `audio/capture.py` | device stream | 16 kHz mono chunks + timestamps | done |
| `audio/timeline.py` | chunks | gap-free stream per source | done (M1) |
| `vad` | stream per source | utterance segments (start, end, audio) | todo |
| `asr` | segment audio | Armenian text | todo — chosen by measurement |
| `translate` | Armenian text | English text | todo — chosen by measurement |
| `speakers` | system-side segment audio | Speaker N (stable) | todo |
| `output` | labelled segment | terminal lines | todo |
| `app` | CLI flags | runs everything in threads/queues | todo |

## Candidate models (verify each in official docs: Armenian support, license, size, install)
- VAD: Silero VAD
- ASR: Whisper family via faster-whisper (small sizes first), other local models with Armenian
- Translation: NLLB-200 distilled, MADLAD-400, Whisper translate mode
- Speaker embeddings: small local speaker-embedding model (to research)

## Risks
- Hardware: 2-core 2013 CPU, ~1.7 GB free RAM, no GPU → small models only; ASR + MT + speaker
  model must fit in memory together; close Chrome when running
- Armenian is low-resource: small ASR models may be inaccurate → measure CER/WER
- Telling call-side speakers apart from short segments, live, on CPU
- Model licenses (e.g. non-commercial)

## Testing strategy
- Unit tests (pytest) for pure logic: gap filling, segmentation, speaker clustering, formatting
- Offline evaluation on my own Armenian recordings with reference text (not committed):
  ASR = CER/WER, translation = manual check, speakers = label accuracy
- Every line's latency is logged; report median and 95th percentile per session
- Rehearsal of the interview: live call with 2+ Armenian speakers on the system side

## Milestones
- M0 Environment + capture baseline — done (b0eb262)
- M1 Fill loopback silence gaps + tests — done (9b7bc32)
- M2 Offline ASR on WAV files, compare models (speed + CER)
- M3 Offline translation, compare models
- M4 Minimal end-to-end live pipeline (mic = Me, system = one speaker)
- M5 Measure latency/quality, improve the weakest part
- M6 Speaker 1 / Speaker 2 on the system side
- M7 README + chat exports + interview rehearsal
