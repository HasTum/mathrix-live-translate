"""Armenian -> English translation: NLLB-200 distilled 600M on CTranslate2 (int8).

Chosen by measurement, see DECISIONS.md D7 (chrF 74.5, ~1 s per sentence on this laptop).
License of the model weights: CC-BY-NC-4.0 (non-commercial).
"""
from __future__ import annotations

import ctranslate2
from huggingface_hub import snapshot_download
from transformers import AutoTokenizer

MODEL = "JustFrederik/nllb-200-distilled-600M-ct2-int8"
TOKENIZER = "facebook/nllb-200-distilled-600M"


class ArmenianToEnglish:
    def __init__(self, beam: int = 2, threads: int = 4):
        self._translator = ctranslate2.Translator(snapshot_download(MODEL), device="cpu",
                                                  compute_type="int8", intra_threads=threads)
        self._tok = AutoTokenizer.from_pretrained(TOKENIZER, src_lang="hye_Armn")
        self._beam = beam

    def translate(self, text: str) -> str:
        if not text.strip():
            return ""
        tokens = self._tok.convert_ids_to_tokens(self._tok.encode(text))
        res = self._translator.translate_batch([tokens], target_prefix=[["eng_Latn"]],
                                               beam_size=self._beam, max_decoding_length=128)
        out = res[0].hypotheses[0][1:]           # drop the eng_Latn language token
        return self._tok.decode(self._tok.convert_tokens_to_ids(out), skip_special_tokens=True)
