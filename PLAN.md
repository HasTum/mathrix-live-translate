# PLAN — mathrix-live-translate

## Goal
A local Windows Python app that captures microphone and system audio at the same time,
transcribes Armenian speech, translates it to English, labels speakers, and prints
timestamped lines in the terminal with ≤ 5 s latency. No cloud ASR/translation APIs.

## Requirements (to re-check against the official challenge brief)
- R1 Capture mic + system audio simultaneously
- R2 Transcribe Armenian speech locally
- R3 Translate Armenian → English locally
- R4 Identify speakers
- R5 Print timestamped results in the terminal
- R6 Latency ≤ 5 s (measured: end of utterance → line printed)
- R7 No cloud speech recognition or translation APIs
- R8 Deliverables: README, complete exported chats in `chats/`

## Pipeline and modules
| Module | Input | Output | Status |
|---|---|---|---|
| `audio/devices.py` | WASAPI devices | mic + loopback device info | exists |
| `audio/capture.py` | device stream | 16 kHz mono float32 chunks + timestamps | exists; must fill loopback gaps |
| `vad` | chunks per source | utterance segments (start, end, audio) | todo |
| `asr` | segment audio | Armenian text | todo — model to be chosen by measurement |
| `translate` | Armenian text | English text | todo — model to be chosen by measurement |
| `speakers` | segment audio + source | speaker label | todo — baseline: mic = "Me", system = "Remote"; then split speakers within system audio |
| `output` | labelled segment | terminal line | todo |
| `app` | CLI args | runs everything in threads/queues | todo |

Example output line (draft):
`[00:01:23.4] Remote-2 | HY: Բարև, ինչպե՞ս ես | EN: Hello, how are you? | lat 3.1 s`

## Candidate models (each to be verified in official docs: Armenian support, license, install)
- VAD: Silero VAD
- ASR: Whisper family (e.g. via faster-whisper), plus other local models with Armenian support
- Translation: NLLB-200, MADLAD-400, Whisper's translate mode
- Speaker embeddings: to be researched

## Risks
- Armenian ASR quality may be weak on small models; large models may be too slow on CPU → R6
- Hardware (CPU/GPU/RAM) not yet known — drives model size
- Loopback sends no data during silence (confirmed 2026-10-24) → timeline gaps
- Echo: mic hears speaker output → duplicate lines (use headphones or dedupe)
- Live speaker separation within system audio in < 5 s is hard
- Model licenses may restrict use (e.g. non-commercial)

## Testing strategy
- Unit tests (pytest) for pure logic: gap filling, segmentation, formatting, latency math
- Offline evaluation on recorded Armenian clips with reference text:
  ASR = WER/CER, translation = chrF + manual check, speakers = label accuracy
- Every printed line logs its latency; report median and 95th percentile per session
- Manual end-to-end test: scripted two-person Armenian call

## Milestones
- M0 Environment + capture baseline — done (b0eb262)
- M1 Fix loopback gaps + capture tests
- M2 Offline ASR on WAV files, compare models
- M3 Offline translation, compare models
- M4 Minimal end-to-end live pipeline (speaker = source)
- M5 Measure latency/quality, improve the weakest part
- M6 Speakers within system audio
- M7 README + chat exports
