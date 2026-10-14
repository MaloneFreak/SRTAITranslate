"""Common interface for every translation engine."""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..languages import Language


class EngineError(Exception):
    """A translation engine failed. ``user_message`` is safe to show in the UI."""

    def __init__(self, message: str, *, retryable: bool = False, status: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status = status

    @property
    def user_message(self) -> str:
        return str(self)


class AuthError(EngineError):
    pass


class ConfigError(EngineError):
    pass


class CancelledError(Exception):
    pass


@dataclass
class TranslationRequest:
    texts: list[str]
    source: Optional[Language]          # None when unknown
    target: Language
    context_before: list[str] = field(default_factory=list)
    context_after: list[str] = field(default_factory=list)
    notes: str = ""                     # free text about the video (LLMs)
    glossary: list[tuple[str, str]] = field(default_factory=list)
    formality: str = "default"          # default | formal | informal


ProgressFn = Callable[[str, float | None], None]  # (message, fraction 0..1 or None)


class Engine(ABC):
    """Translate lists of short texts.

    ``translate`` returns one item per input text. An item may be ``None`` when the
    engine could not produce it (e.g. an LLM skipped a line); the pipeline retries
    those with smaller batches.
    """

    name: str = "engine"
    uses_context: bool = False        # sends neighbouring lines (LLMs)
    supports_tags: bool = False       # keeps <i> tags inside text
    prefers_sentences: bool = True    # benefits from merging broken sentences
    needs_source_language: bool = False
    batch_size: int = 16
    max_workers: int = 1

    def __init__(self) -> None:
        self.cancel_event = threading.Event()

    def signature(self) -> str:
        """Identifies engine+model for the translation cache."""
        return self.name

    def prepare(self, progress: ProgressFn | None = None) -> None:
        """Load models / check connectivity before a job starts."""

    @abstractmethod
    def translate(self, request: TranslationRequest) -> list[Optional[str]]:
        ...

    def close(self) -> None:
        pass

    def check_cancel(self) -> None:
        if self.cancel_event.is_set():
            raise CancelledError()
