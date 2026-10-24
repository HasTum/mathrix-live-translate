## D5 — Microphone level for the internal Conexant mic (2026-10-24)
- Problem: speech was clipped (14.9 % and 7.5 % of samples at full scale); p90 frame level −3 dB.
- Fix: Windows Sound → Recording → Internal Microphone → Levels: Microphone = __, Boost = __;
  enhancements disabled.
- Evidence after fix: 60 s test take, 0.11 % clipped, p10 −58.6 dB, p90 −25.5 dB; speech clear on listening.
- Must be checked again before the interview.

## D6 — ASR model: NVIDIA FastConformer Armenian via ONNX + onnx-asr (2026-10-24)
- Test: 60 s take, 8 Armenian sentences (eval/hy_test_reference.txt), this laptop, CPU only.
  Acceptance criteria set before testing: CER ≤ 0.20, RTF ≤ 0.3, peak RAM ≤ 1 GB.

| Model | CER | WER | RTF | Peak RAM | Result |
|---|---|---|---|---|---|
| Whisper tiny (faster-whisper, int8) | 0.993 | 1.000 | 0.31 | 297 MB | rejected: unrelated English output |
| Whisper base (faster-whisper, int8) | 0.807 | 0.979 | 0.87 | 462 MB | rejected: garbled mixed-language text |
| FastConformer hy (ONNX, fp32) | 0.085 | 0.146 | 0.07 | __ MB | **chosen** |

- Model: nvidia/stt_hy_fastconformer_hybrid_large_pc (~115M params, trained on ~296 h of
  Armenian; CC-BY-4.0; published WER ~12–13 % FLEURS). Run through the ONNX export
  OpenVoiceOS/stt_hy_fastconformer_hybrid_large_pc_onnx with onnx-asr 0.12.0; no PyTorch needed.
  Load time from cache: __ s.
- Not chosen: Whisper small (about 3× base's size; base already RTF 0.87, so too slow for live —
  not measured); Armenian fine-tuned Whisper large-v3 (BuzzASR/armenian, CER 3.7 % FLEURS, but
  ~1.5B+ params, GPU-oriented); small Armenian Whisper fine-tunes (no reliable published accuracy,
  need a PyTorch conversion).
- Risks: the ONNX export is a third-party conversion (CTC head only, fp32 only); peak RAM close
  to 1 GB leaves less room for translation; the model card warns it is noise-sensitive and
  non-streaming, so we will feed it one utterance at a time from the VAD.
- Observed errors on our take: "լավ եմ" → "լավավ", "ունենք" → "ունեն", last sentence partly lost.
