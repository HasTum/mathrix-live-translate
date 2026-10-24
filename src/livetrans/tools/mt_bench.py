"""Benchmark Armenian -> English translation: NLLB-200 distilled 600M (CTranslate2, int8).

    python -m livetrans.tools.mt_bench
    python -m livetrans.tools.mt_bench --source eval/hy_test_asr.txt

Translates one sentence per line, as the live app will (one utterance at a time).
Prints each translation with its time, then median/max time, peak RAM and chrF
against the English references.
"""
from __future__ import annotations

import argparse
import statistics
import time

import ctranslate2
import psutil
import sacrebleu
from huggingface_hub import snapshot_download
from transformers import AutoTokenizer

MODEL = "JustFrederik/nllb-200-distilled-600M-ct2-int8"   # third-party int8 conversion (CC-BY-NC-4.0)
TOKENIZER = "facebook/nllb-200-distilled-600M"             # Meta's official tokenizer


def read_lines(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="eval/hy_test_reference.txt")
    ap.add_argument("--ref", default="eval/hy_test_reference_en.txt")
    ap.add_argument("--beam", type=int, default=2)
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()

    src, ref = read_lines(args.source), read_lines(args.ref)
    if len(src) != len(ref):
        raise SystemExit(f"{args.source} has {len(src)} lines but {args.ref} has {len(ref)}")

    t = time.perf_counter()
    model_dir = snapshot_download(MODEL)
    translator = ctranslate2.Translator(model_dir, device="cpu", compute_type="int8",
                                        intra_threads=args.threads)
    tok = AutoTokenizer.from_pretrained(TOKENIZER, src_lang="hye_Armn")
    load_s = time.perf_counter() - t

    def translate(text: str) -> str:
        tokens = tok.convert_ids_to_tokens(tok.encode(text))
        res = translator.translate_batch([tokens], target_prefix=[["eng_Latn"]],
                                         beam_size=args.beam, max_decoding_length=128)
        out = res[0].hypotheses[0][1:]           # drop the eng_Latn language token
        return tok.decode(tok.convert_tokens_to_ids(out), skip_special_tokens=True)

    translate("Բարև")                            # warm-up, not timed

    hyps, times = [], []
    for i, (s, r) in enumerate(zip(src, ref), 1):
        t = time.perf_counter()
        en = translate(s)
        dt = time.perf_counter() - t
        hyps.append(en)
        times.append(dt)
        print(f"{i}. [{dt:.2f} s] HY:  {s}\n            EN:  {en}\n            REF: {r}")

    mem = psutil.Process().memory_info()
    peak_mb = getattr(mem, "peak_wset", mem.rss) / 2**20   # peak_wset exists on Windows
    chrf = sacrebleu.corpus_chrf(hyps, [ref]).score

    print(f"\nsource={args.source} beam={args.beam} threads={args.threads}")
    print(f"load {load_s:.1f} s | per sentence: median {statistics.median(times):.2f} s, "
          f"max {max(times):.2f} s | peak RAM {peak_mb:.0f} MB | chrF {chrf:.1f}")


if __name__ == "__main__":
    main()
