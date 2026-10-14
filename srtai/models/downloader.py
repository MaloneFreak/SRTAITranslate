"""Resumable model downloads from Hugging Face (no huggingface_hub needed)."""
from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import requests

from .. import app_paths
from ..engines import http
from ..engines.base import CancelledError
from . import catalog

log = logging.getLogger(__name__)

# (bytes_done, bytes_total, message)
DownloadProgress = Callable[[int, int, str], None]

_SKIP_FILES = {".gitattributes", "README.md", "tokenizer.json", "tokenizer_config.json",
               "special_tokens_map.json", "generation_config.json", "pytorch_model.bin"}
MANIFEST = "srtai_manifest.json"


class DownloadError(Exception):
    pass


def hf_endpoint() -> str:
    return os.environ.get("HF_ENDPOINT", "https://huggingface.co").rstrip("/")


@dataclass
class RemoteFile:
    path: str
    size: int


def list_repo_files(repo: str, timeout: float = 20) -> list[RemoteFile]:
    url = f"{hf_endpoint()}/api/models/{repo}/tree/main"
    resp = http.session().get(url, timeout=timeout)
    if resp.status_code == 404:
        raise DownloadError(f"Repository not found: {repo}")
    resp.raise_for_status()
    files = []
    for item in resp.json():
        if item.get("type") == "file":
            size = (item.get("lfs") or {}).get("size", item.get("size", 0))
            files.append(RemoteFile(item["path"], int(size or 0)))
    return files


def model_path(model_id: str) -> Path:
    return app_paths.models_dir() / model_id


def is_installed(model_id: str) -> bool:
    path = model_path(model_id)
    return (path / "model.bin").is_file() and (path / MANIFEST).is_file()


def installed_size(model_id: str) -> int:
    path = model_path(model_id)
    if not path.is_dir():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def delete_model(model_id: str) -> None:
    for path in (model_path(model_id), app_paths.models_dir() / f"{model_id}.partial"):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


def _download_file(url: str, dest: Path, on_bytes: Callable[[int], None],
                   cancel: Optional[threading.Event], expected: int = 0) -> None:
    part = dest.with_name(dest.name + ".part")
    existing = part.stat().st_size if part.exists() else 0
    if expected and existing == expected:
        part.replace(dest)
        on_bytes(existing)
        return
    headers = {"Range": f"bytes={existing}-"} if existing else {}
    for attempt in range(6):
        try:
            with http.session().get(url, headers=headers, stream=True, timeout=(15, 60),
                                    allow_redirects=True) as resp:
                if resp.status_code == 416:  # already complete
                    break
                if resp.status_code not in (200, 206):
                    raise DownloadError(f"Download failed ({resp.status_code}) for {dest.name}")
                if resp.status_code == 200 and existing:
                    existing = 0  # server ignored Range; start over
                    part.unlink(missing_ok=True)
                on_bytes(existing)
                with open(part, "ab") as f:
                    for chunk in resp.iter_content(chunk_size=1 << 20):
                        if cancel is not None and cancel.is_set():
                            raise CancelledError()
                        if chunk:
                            f.write(chunk)
                            on_bytes(len(chunk))
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError,
                requests.exceptions.Timeout) as exc:
            if attempt == 5:
                raise DownloadError(f"Connection lost while downloading {dest.name}. Try again; "
                                    "the download will resume.") from exc
            log.warning("Download interrupted (%s), resuming", exc)
            time.sleep(2 + attempt * 2)
            existing = part.stat().st_size if part.exists() else 0
            on_bytes(-1)  # reset marker handled by the caller
            headers = {"Range": f"bytes={existing}-"} if existing else {}
    part.replace(dest)


def install_model(model_id: str, progress: Optional[DownloadProgress] = None,
                  cancel: Optional[threading.Event] = None) -> Path:
    """Download an offline model (resuming partial downloads) and return its folder."""
    model = catalog.get(model_id)
    final_dir = model_path(model_id)
    if is_installed(model_id):
        return final_dir
    work_dir = app_paths.models_dir() / f"{model_id}.partial"
    work_dir.mkdir(parents=True, exist_ok=True)

    repo, files, last_error = None, [], None
    for candidate in model.repos:
        try:
            files = [f for f in list_repo_files(candidate)
                     if f.path not in _SKIP_FILES and "/" not in f.path and not f.path.endswith(".safetensors")]
            if any(f.path == "model.bin" for f in files):
                repo = candidate
                break
        except (DownloadError, requests.RequestException) as exc:
            last_error = exc
            log.warning("Mirror %s unavailable: %s", candidate, exc)
    if repo is None:
        raise DownloadError(f"Could not reach any download source for {model.name}. "
                            f"Check your internet connection. ({last_error})")

    jobs: list[tuple[str, RemoteFile]] = [(repo, f) for f in files]
    if model.family == "nllb" and not any(f.path.endswith(".model") for f in files):
        try:
            tok = [f for f in list_repo_files(catalog.NLLB_TOKENIZER_REPO) if f.path == catalog.NLLB_TOKENIZER_FILE]
        except requests.RequestException as exc:
            raise DownloadError(f"Could not download the tokenizer: {exc}") from exc
        jobs += [(catalog.NLLB_TOKENIZER_REPO, f) for f in tok]

    total = sum(f.size for _, f in jobs)
    done_before = 0
    lock = threading.Lock()
    state = {"current": 0, "last": 0.0}

    for repo_id, remote in jobs:
        dest = work_dir / remote.path
        if dest.exists() and (not remote.size or dest.stat().st_size == remote.size):
            done_before += dest.stat().st_size
            continue
        state["current"] = 0

        def on_bytes(n: int, _name=remote.path) -> None:
            with lock:
                if n == -1:
                    state["current"] = 0
                    return
                state["current"] += n
                now = time.monotonic()
                if progress and (now - state["last"] > 0.2):
                    state["last"] = now
                    progress(done_before + state["current"], total, _name)

        url = f"{hf_endpoint()}/{repo_id}/resolve/main/{remote.path}"
        _download_file(url, dest, on_bytes, cancel, remote.size)
        done_before += dest.stat().st_size

    (work_dir / MANIFEST).write_text(json.dumps({
        "id": model_id, "repo": repo, "files": [f.path for _, f in jobs], "installed_at": time.time(),
    }, indent=2), encoding="utf-8")
    if final_dir.exists():
        shutil.rmtree(final_dir, ignore_errors=True)
    work_dir.replace(final_dir)
    if progress:
        progress(total, total, "done")
    return final_dir
