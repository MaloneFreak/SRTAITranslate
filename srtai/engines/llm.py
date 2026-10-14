"""Chat-based LLM engines: OpenAI-compatible APIs, Anthropic Claude and Ollama."""
from __future__ import annotations

import logging
from typing import Optional

from . import http, prompts
from .base import ConfigError, Engine, EngineError, TranslationRequest

log = logging.getLogger(__name__)


class LLMEngine(Engine):
    uses_context = True
    supports_tags = True
    prefers_sentences = False

    def __init__(self, model: str, temperature: float = 0.2, batch_size: int = 40, workers: int = 4):
        super().__init__()
        if not model:
            raise ConfigError("Choose a model for this provider.")
        self.model = model
        self.temperature = temperature
        self.batch_size = batch_size
        self.max_workers = workers

    def signature(self) -> str:
        return f"{self.name}:{self.model}"

    def translate(self, request: TranslationRequest) -> list[Optional[str]]:
        self.check_cancel()
        if prompts.is_translategemma(self.model):
            text = "\n".join(request.texts)
            answer = self.chat(None, prompts.translategemma_prompt(text, request.source, request.target), json_mode=False)
            return prompts.split_lines_answer(answer, len(request.texts))
        answer = self.chat(prompts.build_system_prompt(request), prompts.build_user_payload(request), json_mode=True)
        return prompts.parse_translations(answer, len(request.texts))

    def chat(self, system: Optional[str], user: str, json_mode: bool) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    def list_models(self) -> list[str]:  # pragma: no cover - overridden
        return []


class OpenAICompatEngine(LLMEngine):
    """OpenAI, Gemini, DeepSeek, OpenRouter, Groq, Mistral, LM Studio, custom servers."""

    def __init__(self, base_url: str, api_key: str, model: str, *, provider_id: str = "openai", **kwargs):
        super().__init__(model, **kwargs)
        if not base_url:
            raise ConfigError("Enter the server URL (e.g. http://localhost:8000/v1).")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.name = provider_id
        self._send_temperature = True
        self._send_json_mode = True

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if "openrouter.ai" in self.base_url:
            headers["HTTP-Referer"] = "https://github.com/MaloneFreak/SRTAITranslate"
            headers["X-Title"] = "SRT AI Translator"
        return headers

    def chat(self, system: Optional[str], user: str, json_mode: bool) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        while True:
            payload: dict = {"model": self.model, "messages": messages}
            if self._send_temperature:
                payload["temperature"] = self.temperature
            if json_mode and self._send_json_mode:
                payload["response_format"] = {"type": "json_object"}
            try:
                data = http.request_json(
                    "POST", f"{self.base_url}/chat/completions", headers=self._headers(),
                    payload=payload, cancel_event=self.cancel_event, timeout=300,
                )
            except EngineError as exc:
                text = str(exc).lower()
                # Some models reject optional parameters; drop them once and retry.
                if self._send_temperature and "temperature" in text:
                    self._send_temperature = False
                    continue
                if self._send_json_mode and exc.status in (400, 422) and ("response_format" in text or "json" in text):
                    self._send_json_mode = False
                    continue
                raise
            try:
                choice = data["choices"][0]
                content = choice["message"].get("content") or ""
            except (KeyError, IndexError, TypeError) as exc:
                raise EngineError(f"Unexpected answer from {self.name}: {str(data)[:200]}") from exc
            if isinstance(content, list):  # some servers return content parts
                content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
            return content

    def list_models(self) -> list[str]:
        data = http.request_json("GET", f"{self.base_url}/models", headers=self._headers(), retries=1, timeout=20)
        items = data.get("data", data.get("models", [])) if isinstance(data, dict) else data
        names = []
        for item in items or []:
            if isinstance(item, dict):
                name = item.get("id") or item.get("name")
                if name:
                    names.append(str(name).removeprefix("models/"))
        return sorted(set(names))


class AnthropicEngine(LLMEngine):
    API_VERSION = "2023-06-01"

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.anthropic.com", **kwargs):
        super().__init__(model, **kwargs)
        if not api_key:
            raise ConfigError("Enter your Anthropic API key.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.name = "anthropic"
        self._send_temperature = True

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
        }

    def chat(self, system: Optional[str], user: str, json_mode: bool) -> str:
        while True:
            payload: dict = {
                "model": self.model,
                "max_tokens": 8192,
                "messages": [{"role": "user", "content": user}],
            }
            if system:
                payload["system"] = system
            if self._send_temperature:
                payload["temperature"] = self.temperature
            try:
                data = http.request_json(
                    "POST", f"{self.base_url}/v1/messages", headers=self._headers(),
                    payload=payload, cancel_event=self.cancel_event, timeout=300,
                )
            except EngineError as exc:
                if self._send_temperature and "temperature" in str(exc).lower():
                    self._send_temperature = False
                    continue
                raise
            parts = data.get("content", []) if isinstance(data, dict) else []
            return "".join(p.get("text", "") for p in parts if isinstance(p, dict) and p.get("type") == "text")

    def list_models(self) -> list[str]:
        data = http.request_json("GET", f"{self.base_url}/v1/models", headers=self._headers(),
                                 params={"limit": 100}, retries=1, timeout=20)
        return [m["id"] for m in data.get("data", []) if isinstance(m, dict) and m.get("id")]


class OllamaEngine(LLMEngine):
    """Ollama's native API (supports JSON mode and pulling models on demand)."""

    def __init__(self, model: str, base_url: str = "http://localhost:11434", **kwargs):
        kwargs.setdefault("batch_size", 12)
        kwargs.setdefault("workers", 1)
        super().__init__(model, **kwargs)
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self.name = "ollama"

    def prepare(self, progress=None) -> None:
        from ..models import ollama_client

        client = ollama_client.OllamaClient(self.base_url)
        if not client.is_running():
            raise EngineError(
                "Ollama is not running. Install it from https://ollama.com and open it, "
                "or choose another engine."
            )
        if not client.has_model(self.model):
            if progress:
                progress(f"Downloading {self.model} with Ollama...", 0.0)
            client.pull(self.model, progress=progress, cancel_event=self.cancel_event)

    def chat(self, system: Optional[str], user: str, json_mode: bool) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature, "num_ctx": 8192},
            "keep_alive": "10m",
        }
        if json_mode:
            payload["format"] = "json"
        data = http.request_json("POST", f"{self.base_url}/api/chat", payload=payload,
                                 cancel_event=self.cancel_event, timeout=600, retries=2)
        return (data.get("message") or {}).get("content", "") if isinstance(data, dict) else ""

    def list_models(self) -> list[str]:
        from ..models import ollama_client

        return ollama_client.OllamaClient(self.base_url).list_models()
