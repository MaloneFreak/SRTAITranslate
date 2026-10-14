"""DeepL API engine (Free and Pro)."""
from __future__ import annotations

from typing import Optional

from . import http
from .base import ConfigError, Engine, EngineError, TranslationRequest

FREE_URL = "https://api-free.deepl.com"
PRO_URL = "https://api.deepl.com"


class DeepLEngine(Engine):
    name = "deepl"
    supports_tags = True
    prefers_sentences = True
    batch_size = 40
    max_workers = 2

    def __init__(self, api_key: str, base_url: str = ""):
        super().__init__()
        if not api_key:
            raise ConfigError("Enter your DeepL API key.")
        self.api_key = api_key.strip()
        self.base_url = (base_url or (FREE_URL if self.api_key.endswith(":fx") else PRO_URL)).rstrip("/")
        self._target_overrides: dict[str, str] = {}

    def _headers(self) -> dict:
        return {"Authorization": f"DeepL-Auth-Key {self.api_key}", "Content-Type": "application/json"}

    def translate(self, request: TranslationRequest) -> list[Optional[str]]:
        self.check_cancel()
        target = request.target.deepl
        if not target:
            raise EngineError(f"DeepL does not support {request.target.name}. Choose another engine.")
        target = self._target_overrides.get(target, target)
        payload: dict = {
            "text": request.texts,
            "target_lang": target,
            "tag_handling": "html",
            "preserve_formatting": True,
        }
        if request.source and request.source.deepl_source:
            payload["source_lang"] = request.source.deepl_source
        context = " ".join(filter(None, [request.notes.strip()] + request.context_before[-3:]))
        if context:
            payload["context"] = context[:2000]
        if request.formality == "formal":
            payload["formality"] = "prefer_more"
        elif request.formality == "informal":
            payload["formality"] = "prefer_less"
        try:
            data = http.request_json("POST", f"{self.base_url}/v2/translate", headers=self._headers(),
                                     payload=payload, cancel_event=self.cancel_event)
        except EngineError as exc:
            base = target.split("-")[0]
            if exc.status == 400 and "target_lang" in str(exc) and base != target:
                self._target_overrides[request.target.deepl] = base  # e.g. ES-419 -> ES
                return self.translate(request)
            raise
        items = data.get("translations", []) if isinstance(data, dict) else []
        result: list[Optional[str]] = [None] * len(request.texts)
        for i, item in enumerate(items[: len(result)]):
            result[i] = item.get("text")
        return result

    def usage(self) -> tuple[int, int]:
        data = http.request_json("GET", f"{self.base_url}/v2/usage", headers=self._headers(), retries=1, timeout=20)
        return int(data.get("character_count", 0)), int(data.get("character_limit", 0))
