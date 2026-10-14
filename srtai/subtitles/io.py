"""Reading and writing SRT files with encoding detection."""
from __future__ import annotations

import codecs
import logging
from dataclasses import dataclass
from pathlib import Path

import srt

log = logging.getLogger(__name__)

_BOMS = (
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)


class SubtitleError(Exception):
    """Raised when a subtitle file cannot be read or parsed."""


@dataclass
class SubtitleFile:
    path: Path
    encoding: str
    cues: list[srt.Subtitle]


def detect_encoding(data: bytes) -> str:
    for bom, name in _BOMS:
        if data.startswith(bom):
            return name
    try:
        data.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        from charset_normalizer import from_bytes

        results = from_bytes(data)
        best = results.best()
        if best is not None and best.encoding:
            # Western Windows-1252 is by far the most common legacy encoding for subtitles;
            # prefer it when it explains the bytes as well as the best guess does.
            for match in results:
                if match.encoding == "cp1252" and match.chaos <= best.chaos + 0.01:
                    return "cp1252"
            return best.encoding
    except Exception:  # pragma: no cover - optional dependency problems
        log.debug("charset_normalizer failed", exc_info=True)
    return "cp1252"


def decode(data: bytes) -> tuple[str, str]:
    encoding = detect_encoding(data)
    try:
        text = data.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        encoding = "latin-1"
        text = data.decode(encoding)
    return text.lstrip("﻿"), encoding


def parse(text: str) -> list[srt.Subtitle]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    try:
        cues = list(srt.parse(text, ignore_errors=True))
    except Exception as exc:  # srt raises several error types
        raise SubtitleError(f"Could not parse subtitles: {exc}") from exc
    for cue in cues:
        cue.content = cue.content.strip("\n")
    return cues


def read(path: str | Path) -> SubtitleFile:
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise SubtitleError(f"Could not read {path}: {exc}") from exc
    text, encoding = decode(data)
    cues = parse(text)
    if not cues:
        raise SubtitleError(f"No subtitles found in {path.name}. Is it a valid .srt file?")
    log.info("Read %s: %d cues, encoding %s", path.name, len(cues), encoding)
    return SubtitleFile(path=path, encoding=encoding, cues=cues)


def compose(cues: list[srt.Subtitle]) -> str:
    return srt.compose(cues, reindex=True, strict=False)


def write(path: str | Path, cues: list[srt.Subtitle], encoding: str = "utf-8") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = compose(cues)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding=encoding, errors="replace", newline="\r\n") as f:
        f.write(content)
    tmp.replace(path)
    return path
