"""Offline translation with NLLB-200 running on CTranslate2 (CPU or NVIDIA GPU)."""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Optional

from .base import ConfigError, Engine, EngineError, TranslationRequest

log = logging.getLogger(__name__)

# Loaded translators are kept between jobs so a second file starts instantly.
_LOADED: dict[tuple[str, str], tuple[object, object]] = {}
_LOAD_LOCK = threading.Lock()


def cuda_available() -> bool:
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def _find_tokenizer(model_dir: Path) -> Path:
    for name in ("sentencepiece.bpe.model", "spm.model", "sentencepiece.model"):
        if (model_dir / name).is_file():
            return model_dir / name
    found = sorted(model_dir.glob("*.model"))
    if not found:
        raise ConfigError(f"No SentencePiece tokenizer found in {model_dir}. Re-download the model.")
    return found[0]


class OfflineEngine(Engine):
    name = "offline"
    uses_context = False
    supports_tags = False
    prefers_sentences = True
    needs_source_language = True
    max_workers = 1

    def __init__(self, model_id: str, model_dir: str | Path | None = None, device: str = "auto",
                 beam_size: int = 4, batch_size: int = 16):
        super().__init__()
        self.model_id = model_id
        self.model_dir = Path(model_dir) if model_dir else None
        self.device = device
        self.beam_size = beam_size
        self.batch_size = batch_size
        self._translator = None
        self._sp = None
        self.active_device = "cpu"

    def signature(self) -> str:
        return f"offline:{self.model_id}"

    def prepare(self, progress=None) -> None:
        from ..models import downloader

        model_dir = self.model_dir or downloader.model_path(self.model_id)
        if not downloader.is_installed(self.model_id) and not (model_dir / "model.bin").is_file():
            if progress:
                progress("Downloading the offline model (first time only)...", 0.0)

            def on_progress(done: int, total: int, name: str) -> None:
                if progress:
                    mb_done, mb_total = done / 1e6, total / 1e6
                    progress(f"Downloading model: {mb_done:,.0f} / {mb_total:,.0f} MB", done / total if total else None)

            model_dir = downloader.install_model(self.model_id, on_progress, self.cancel_event)
        if progress:
            progress("Loading the offline model...", None)
        self._load(model_dir)

    def _load(self, model_dir: Path) -> None:
        try:
            import ctranslate2
            import sentencepiece as spm
        except ImportError as exc:  # pragma: no cover - packaging problem
            raise ConfigError("The offline engine is not available in this build.") from exc

        want_gpu = self.device in ("auto", "cuda") and cuda_available()
        key = (str(model_dir), "cuda" if want_gpu else "cpu")
        with _LOAD_LOCK:
            if key in _LOADED:
                self._translator, self._sp = _LOADED[key]
                self.active_device = key[1]
                return
            sp = spm.SentencePieceProcessor()
            sp.Load(str(_find_tokenizer(model_dir)))
            threads = max(1, (os.cpu_count() or 4) - 1)
            translator = None
            if want_gpu:
                try:
                    translator = ctranslate2.Translator(str(model_dir), device="cuda", compute_type="int8_float16")
                    self.active_device = "cuda"
                except Exception as exc:  # missing CUDA/cuDNN DLLs, not enough VRAM...
                    log.warning("GPU not usable, falling back to CPU: %s", exc)
            if translator is None:
                try:
                    translator = ctranslate2.Translator(str(model_dir), device="cpu", compute_type="int8",
                                                        intra_threads=threads)
                except Exception as exc:
                    raise EngineError(f"Could not load the offline model: {exc}") from exc
                self.active_device = "cpu"
                key = (str(model_dir), "cpu")
            _LOADED.clear()  # keep only one model in memory
            _LOADED[key] = (translator, sp)
            self._translator, self._sp = translator, sp
        log.info("Offline model %s loaded on %s", self.model_id, self.active_device)

    def translate(self, request: TranslationRequest) -> list[Optional[str]]:
        self.check_cancel()
        if self._translator is None:
            self.prepare()
        if request.source is None or not request.source.nllb:
            raise ConfigError("Choose the source language (the offline model cannot detect it here).")
        if not request.target.nllb:
            raise ConfigError(f"The offline model does not support {request.target.name}.")
        src, tgt = request.source.nllb, request.target.nllb
        sp = self._sp
        tokens = [[src] + sp.EncodeAsPieces(text)[:400] + ["</s>"] for text in request.texts]
        results = self._translator.translate_batch(
            tokens,
            target_prefix=[[tgt]] * len(tokens),
            beam_size=self.beam_size,
            max_batch_size=self.batch_size,
            max_decoding_length=512,
            repetition_penalty=1.05,
            no_repeat_ngram_size=0,
        )
        out: list[Optional[str]] = []
        for text, res in zip(request.texts, results):
            hyp = res.hypotheses[0]
            if hyp and hyp[0] == tgt:
                hyp = hyp[1:]
            translated = sp.DecodePieces(hyp).strip()
            if len(translated) > 4 * len(text) + 40:  # runaway repetition
                retry = self._translator.translate_batch(
                    [[src] + sp.EncodeAsPieces(text) + ["</s>"]], target_prefix=[[tgt]],
                    beam_size=2, repetition_penalty=1.4, max_decoding_length=2 * len(text) + 32,
                )
                hyp = retry[0].hypotheses[0]
                translated = sp.DecodePieces(hyp[1:] if hyp and hyp[0] == tgt else hyp).strip()
            out.append(translated or None)
        return out
