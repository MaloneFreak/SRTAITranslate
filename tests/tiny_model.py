"""Builds a tiny random NLLB-like CTranslate2 model so the offline engine can be tested
without downloading gigabytes. Its translations are gibberish; the test only checks the
plumbing (tokenization, language tokens, decoding, batching)."""
from __future__ import annotations

import os

import numpy as np


def build_tiny_nllb(out: str) -> str:
    import sentencepiece as spm
    from ctranslate2.specs import transformer_spec as ts

    os.makedirs(out, exist_ok=True)
    corpus = ("Hello world. How are you today? I think we should go home before it starts raining. "
              "Where are you going? To the store. Thank you very much. Previously on the show. ") * 50
    spm.SentencePieceTrainer.train(
        sentence_iterator=iter(corpus.split(". ")), model_prefix=f"{out}/sentencepiece.bpe",
        vocab_size=120, user_defined_symbols=["eng_Latn", "por_Latn", "deu_Latn"],
        bos_id=-1, eos_id=1, unk_id=0, pad_id=2, model_type="bpe", minloglevel=2,
    )
    sp = spm.SentencePieceProcessor(model_file=f"{out}/sentencepiece.bpe.model")
    specials = ["<s>", "<pad>", "</s>", "<unk>"]
    vocab = specials + [sp.id_to_piece(i) for i in range(sp.get_piece_size()) if sp.id_to_piece(i) not in specials]
    d, ffn, n_vocab = 32, 64, len(vocab)
    spec = ts.TransformerSpec.from_config(num_layers=1, num_heads=2)
    rng = np.random.default_rng(0)

    lookup = {}

    def visit(layer, prefix=""):
        for attr, val in list(layer.__dict__.items()):
            if attr.startswith("_"):
                continue
            path = f"{prefix}/{attr}" if prefix else attr
            if isinstance(val, list):
                for i, item in enumerate(val):
                    if hasattr(item, "_visit"):
                        visit(item, f"{path}_{i}")
            elif hasattr(val, "_visit"):
                visit(val, path)
            else:
                lookup[path] = (layer, attr)

    visit(spec)

    def rand(*shape):
        return rng.normal(0, 0.1, shape).astype(np.float32)

    for full, value in spec.variables(ordered=True):
        if value is not None:
            continue
        layer, attr = lookup[full]
        if attr == "gamma":
            arr = np.ones(d, np.float32)
        elif attr == "beta":
            arr = np.zeros(d, np.float32)
        elif "embeddings" in full or "projection" in full:
            arr = rand(n_vocab, d)
        elif "self_attention/linear_0" in full:
            arr = rand(3 * d, d)
        elif "attention/linear_1" in full and "self_attention" not in full:
            arr = rand(2 * d, d)
        elif "ffn/linear_0" in full:
            arr = rand(ffn, d)
        elif "ffn/linear_1" in full:
            arr = rand(d, ffn)
        elif "linear" in full:
            arr = rand(d, d)
        else:
            raise ValueError(f"unexpected variable {full}")
        setattr(layer, attr, arr)
    spec.register_source_vocabulary(vocab)
    spec.register_target_vocabulary(vocab)
    spec.validate()
    spec.optimize(quantization="int8")
    spec.save(out)
    return out
