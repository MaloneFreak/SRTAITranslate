"""Source language detection for subtitle files."""
from __future__ import annotations

import logging
from typing import Optional

from .. import languages
from ..subtitles.text import strip_tags

log = logging.getLogger(__name__)


def detect_language(texts: list[str], max_chars: int = 6000) -> Optional[languages.Language]:
    sample: list[str] = []
    size = 0
    for text in texts:
        clean = strip_tags(text).strip()
        if clean:
            sample.append(clean)
            size += len(clean)
            if size > max_chars:
                break
    if not sample:
        return None
    try:
        import py3langid as langid
    except ImportError:  # pragma: no cover
        log.warning("py3langid not installed; cannot detect language")
        return None
    try:
        code, _score = langid.classify("\n".join(sample))
    except Exception:  # pragma: no cover
        log.warning("Language detection failed", exc_info=True)
        return None
    lang = languages.get(code)
    log.info("Detected source language: %s -> %s", code, lang.code if lang else None)
    return lang
