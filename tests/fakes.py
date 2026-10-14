"""Fake engines used by the tests."""
from __future__ import annotations

from srtai.engines.base import Engine, EngineError, TranslationRequest


class UpperEngine(Engine):
    """Behaves like an offline MT model: no context, prefers whole sentences."""

    name = "upper"
    uses_context = False
    supports_tags = False
    prefers_sentences = True
    batch_size = 4

    def __init__(self):
        super().__init__()
        self.calls: list[list[str]] = []

    def translate(self, request: TranslationRequest):
        self.calls.append(list(request.texts))
        return [t.upper() for t in request.texts]


class FlakyLLM(Engine):
    """Behaves like an LLM: uses context, keeps tags, sometimes forgets lines."""

    name = "flaky"
    uses_context = True
    supports_tags = True
    prefers_sentences = False
    batch_size = 5
    max_workers = 3

    def __init__(self, drop_every: int = 3, fail_texts: tuple[str, ...] = ()):
        super().__init__()
        self.drop_every = drop_every
        self.fail_texts = fail_texts
        self.requests: list[TranslationRequest] = []

    def translate(self, request: TranslationRequest):
        self.requests.append(request)
        out = []
        for i, text in enumerate(request.texts):
            if text in self.fail_texts:
                out.append(None)
            elif len(request.texts) > 1 and self.drop_every and i % self.drop_every == 1:
                out.append(None)  # simulate a skipped line in a big batch
            else:
                out.append(f"PT:{text}")
        return out


class BrokenEngine(Engine):
    name = "broken"

    def translate(self, request: TranslationRequest):
        raise EngineError("server exploded", retryable=True, status=503)
