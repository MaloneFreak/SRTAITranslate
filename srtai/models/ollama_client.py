"""Minimal Ollama client: status, model list, pull with progress, delete."""
from __future__ import annotations

import json
import threading
from typing import Callable, Optional

import requests

from ..engines import http
from ..engines.base import CancelledError, EngineError

OLLAMA_DOWNLOAD_URL = "https://ollama.com/download"


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")

    def version(self) -> Optional[str]:
        try:
            resp = http.session().get(f"{self.base_url}/api/version", timeout=2)
            if resp.ok:
                return resp.json().get("version", "?")
        except (requests.RequestException, ValueError):
            pass
        return None

    def is_running(self) -> bool:
        return self.version() is not None

    def list_models(self) -> list[str]:
        try:
            resp = http.session().get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise EngineError("Could not reach Ollama. Is it installed and running?") from exc
        return sorted(m.get("name", "") for m in resp.json().get("models", []) if m.get("name"))

    def model_sizes(self) -> dict[str, int]:
        try:
            resp = http.session().get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            return {m["name"]: int(m.get("size", 0)) for m in resp.json().get("models", []) if m.get("name")}
        except (requests.RequestException, ValueError, KeyError):
            return {}

    def has_model(self, name: str) -> bool:
        try:
            names = self.list_models()
        except EngineError:
            return False
        wanted = name if ":" in name else f"{name}:latest"
        return wanted in names or name in names

    def pull(self, name: str, progress: Optional[Callable[[str, Optional[float]], None]] = None,
             cancel_event: Optional[threading.Event] = None) -> None:
        layers: dict[str, tuple[int, int]] = {}
        try:
            with http.session().post(f"{self.base_url}/api/pull", json={"model": name, "stream": True},
                                     stream=True, timeout=(10, 600)) as resp:
                if not resp.ok:
                    raise EngineError(f"Ollama could not download {name}: {resp.text[:200]}")
                for raw in resp.iter_lines():
                    if cancel_event is not None and cancel_event.is_set():
                        raise CancelledError()
                    if not raw:
                        continue
                    try:
                        msg = json.loads(raw)
                    except ValueError:
                        continue
                    if msg.get("error"):
                        raise EngineError(f"Ollama: {msg['error']}")
                    status = msg.get("status", "")
                    if msg.get("digest") and msg.get("total"):
                        layers[msg["digest"]] = (int(msg.get("completed", 0)), int(msg["total"]))
                    if progress:
                        done = sum(c for c, _ in layers.values())
                        total = sum(t for _, t in layers.values())
                        progress(f"{name}: {status}", (done / total) if total else None)
                    if status == "success":
                        return
        except requests.RequestException as exc:
            raise EngineError(f"Lost connection to Ollama while downloading {name}.") from exc

    def delete(self, name: str) -> None:
        try:
            resp = http.session().delete(f"{self.base_url}/api/delete", json={"model": name}, timeout=30)
        except requests.RequestException as exc:
            raise EngineError("Could not reach Ollama.") from exc
        if not resp.ok:
            raise EngineError(f"Ollama could not delete {name}: {resp.text[:200]}")
