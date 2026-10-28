# mathrix-live-translate

Live Armenian speech → Armenian text → English translation in the terminal, with speaker
labels. The program captures the microphone ("Me") and the computer's audio output (the
other side of a call: "Speaker 1", "Speaker 2", …) at the same time. Speech recognition,
translation and speaker identification all run locally on the CPU.

```
[00:01:12] Speaker 1   (latency 3.1 s)
HY: Բարև, ինչպե՞ս ես։
EN: Hi, how are you?
```

## Features

- Microphone and system audio captured simultaneously (WASAPI loopback, no virtual cable).
- Armenian speech recognition, English translation, timestamped output per phrase.
- Speaker labels: everything from the microphone is "Me"; voices on the call side are told
  apart and keep their label for the whole session.
- Per-segment latency, an end-of-session summary (median / p95 / max, segments over 5 s),
  and an optional timing breakdown (`--timing`).

## Requirements

- **Windows 10 or 11** (system audio via WASAPI loopback with PyAudioWPatch).
- Python 3.10–3.12; developed and measured with **Python 3.11** in a conda environment.
- About **2.1 GB free RAM** while running (estimate from separate measurements: speech
  recognition ~0.9 GB, translation ~1.0 GB, speaker model ~0.2 GB).
- **Internet on the first run**: the models (~1.1 GB) are downloaded from Hugging Face into
  the user cache, not into the project.
- Development and all measurements: Intel i5-4200M (2 cores, 4 threads), 5.9 GB RAM, no GPU.

## Setup

```
conda create -n livetrans python=3.11 -y
conda activate livetrans
git clone https://github.com/HasTum/mathrix-live-translate.git
cd mathrix-live-translate
pip install -e .          # application
pip install -e .[dev]     # optional: tests and benchmark tools
```

Dependencies (see `pyproject.toml`): numpy, PyAudioWPatch, soxr, soundfile, onnx-asr,
ctranslate2, transformers (tokenizer only, no PyTorch), sentencepiece, huggingface-hub,
sherpa-onnx. Development extras: pytest, psutil, sacrebleu, faster-whisper (only for the
Whisper comparison benchmark).

### Audio setup

1. **Use headphones.** Without them the microphone also hears the call from the speakers
   and prints it a second time as "Me" (echo handling is out of scope).
2. Plug in the headphones **before** starting: the default loopback device follows the
   default Windows output device.
3. List devices (`*` = default) and choose others if needed:
   ```
   python -m livetrans.app --list
   python -m livetrans.app --mic 9 --loopback 10
   ```
4. Microphone level: Windows Sound settings → Recording → microphone → Levels. Aim for speech
   peaks around −25 to −12 dBFS and under 0.1 % clipped samples. Check with
   `python -m livetrans.tools.record --seconds 20` (live levels; WAVs saved to `samples/`).
   On the development laptop the default level clipped about 15 % of samples (DECISIONS.md D5).

## Run

```
python -m livetrans.app            # speak Armenian; Ctrl+C to stop
python -m livetrans.app --timing   # also show waiting / ASR / speaker / translation times
```

| Option | Default | Meaning |
|---|---|---|
| `--list` | | print audio devices and exit |
| `--mic N`, `--loopback N` | system defaults | choose devices |
| `--threshold-db` | −40 | microphone loudness that counts as speech |
| `--system-threshold-db` | −45 | system-audio loudness that counts as speech |
| `--end-silence-s` | 0.6 | pause that ends a phrase |
| `--max-utterance-s` | 7 | longer speech is cut into pieces of this length |
| `--mt-beam` | 2 | translation beam size |
| `--speaker-threshold` | 0.40 | voice similarity needed to match a known caller |
| `--timing` | off | per-segment timing breakdown |

## Models

Armenian is a low-resource language, so each choice was measured on the development laptop.
Full numbers and reasoning: `DECISIONS.md`.

| Task | Chosen | Alternatives considered |
|---|---|---|
| Speech recognition | NVIDIA FastConformer Armenian (`nvidia/stt_hy_fastconformer_hybrid_large_pc`, ~115M parameters, CC-BY-4.0); ONNX export `OpenVoiceOS/stt_hy_fastconformer_hybrid_large_pc_onnx` run with `onnx-asr` | Whisper tiny (CER 0.99) and base (CER 0.81, real-time factor 0.87) measured and rejected; Whisper small not measured (base already too slow); Armenian fine-tuned Whisper large-v3 too large for this CPU |
| Translation | NLLB-200 distilled 600M, int8 CTranslate2 conversion `JustFrederik/nllb-200-distilled-600M-ct2-int8`; tokenizer `facebook/nllb-200-distilled-600M` (weights CC-BY-NC-4.0, non-commercial) | M2M100 418M (fallback), OPUS-MT (no published Armenian scores), larger NLLB or local LLMs (RAM) |
| Speaker identification | NVIDIA TitaNet-small voiceprints (`nemo_en_titanet_small.onnx` from `csukuangfj/speaker-embedding-models`) via `sherpa-onnx`, plus online clustering | WeSpeaker ResNet34 (did not separate two voices), CAM++, ERes2Net, TitaNet-large (slower, not better); PyTorch-based tools (too heavy) |

## Architecture

```
microphone ─► capture ─┐                            ┌─► speech recognition
                       ├─► Timeline ─► Segmenter ─► │   speaker voiceprint (call side only)
loopback   ─► capture ─┘   (per source)             └─► translation ─► terminal
```

- `audio/capture.py`: one WASAPI stream per source, converted to 16 kHz mono.
- `audio/timeline.py`: keeps each source on a gap-free clock; loopback sends no data while
  nothing plays, so silence is inserted (D4).
- `audio/segmenter.py`: cuts each source into phrases with a loudness threshold (phrase ends
  after a 0.6 s pause; at most 7 s per piece).
- `asr.py`, `translate.py`, `speakers.py`: model wrappers. One worker thread processes
  phrases in order (with 2 CPU cores, parallel models would only compete).
- `output.py`: terminal format. `app.py`: command line, threads, shutdown summary.
- `tools/`: recorder and the benchmarks behind each decision; `eval/`: reference texts.

## Tests and measured performance

```
python -m pytest -q        # 43 passed (unit tests of the pure logic)
```

`TESTS.md` maps every requirement to tests and manual checks. Results (all on the development
laptop; sources in `DECISIONS.md`):

| Measurement | Result |
|---|---|
| Speech recognition, 60 s take of 8 read sentences | CER 0.085, WER 0.146, real-time factor 0.06–0.07 (D6); full pipeline on the same take: CER 0.072 |
| Translation of the same 8 sentences | chrF 74.5 from correct text, 69.1 from recognition output; ~1 s per sentence (D7) |
| Speakers, known-truth evaluation (3 verified single voices; clean turns, mixed first piece, quick handovers) | threshold 0.40: 100 % in all scenarios, no merged, split or invented speakers; 0.25–0.30 merged people after a mixed piece (D10) |
| Latency, microphone, read sentences | median 1.6–1.8 s, max 2.0 s, 0 over 5 s (D8) |
| Latency, continuous podcast speech, 7 s pieces | median 2.9 s, max 4.3 s, 0 over 5 s (D8) |
| Latency with speaker identification, podcast | median 3.1 s, max 4.4 s, 0 over 5 s (D9) |
| Latency, Google Meet call, one remote speaker | median 1.9 s, max 3.1 s, 0 over 5 s |
| Latency, two YouTube videos including a page switch | 1 to 3 segments over 5 s (max 5.9–6.3 s) |

Latency is measured from the end of a phrase to its English line.

## Verification status

| Requirement | Status |
|---|---|
| Microphone and system audio together, device choice | verified |
| Armenian transcription, English translation, output format | verified |
| ≤ 5 s latency | verified at normal load; **exceeded under CPU load** (see limitations) |
| Speaker labels on the call side | verified on recorded test data and with a podcast (two speakers, earlier threshold 0.25). **A live call with at least two remote speakers at the current threshold 0.40 has not been verified.** |
| Local models only | inference runs locally. **Fully offline operation after the first download has not been verified.** |

## Known limitations

- **Latency under CPU load.** On 2 cores the models use the whole CPU for about 3 s per 7 s
  piece. Loading a web page or other heavy work slowed translation about 2× and pushed
  segments over 5 s; in one overloaded run phrases queued up and latency grew far beyond 5 s.
  Raising the process priority showed no improvement. During a call, run nothing else.
- **Reported latency can be too low under heavy load.** When audio waits in the capture
  queue, the timeline inserts silence for it and then runs ahead of the clock (diagnosed,
  not fixed; not seen at normal load).
- **Translation sometimes repeats itself** ("I give examples, I give examples, …"), which also
  makes that segment slow.
- **Speakers:** a piece containing two voices (quick handover or overlap) gets one label; two
  people sharing one device in a call were merged at the earlier threshold 0.25.
- Very short utterances (single words) are often misrecognised; names are often mistranslated.
- The speech model is noise-sensitive (model card); translation weights are non-commercial.

## What I would improve with more time

- Fix the timeline drift; keep mixed pieces from shaping a speaker's voiceprint.
- Reduce load per piece when the queue grows (shorter pieces, beam 1); stop translation
  repetition loops.
- A voice-activity detector instead of the loudness threshold; more voices in the speaker
  evaluation.

## Project files

`PLAN.md` (plan and milestones), `DECISIONS.md` (decisions with measurements),
`TESTS.md` (requirement-to-test map), `chats/` (complete, unedited AI chat exports).
