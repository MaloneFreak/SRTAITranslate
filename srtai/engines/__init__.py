"""Engine factory: turns saved settings into a ready-to-use Engine."""
from __future__ import annotations

from dataclasses import dataclass

from . import providers
from .base import AuthError, CancelledError, ConfigError, Engine, EngineError, TranslationRequest


@dataclass
class EngineSettings:
    provider: str = "gemini"
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    batch_size: int = 0      # 0 = provider default
    workers: int = 0         # 0 = provider default
    temperature: float = 0.2
    device: str = "auto"     # offline engine: auto | cpu | cuda


def create_engine(cfg: EngineSettings) -> Engine:
    provider = providers.get(cfg.provider)
    model = (cfg.model or provider.default_model).strip()
    base_url = (cfg.base_url or provider.base_url).strip()
    batch = cfg.batch_size or provider.batch_size
    workers = cfg.workers or provider.workers
    if provider.needs_key and not cfg.api_key.strip():
        raise ConfigError(f"Add your {provider.name} API key in Settings (or in the field next to the provider).")

    if provider.kind == "openai":
        from .llm import OpenAICompatEngine

        return OpenAICompatEngine(base_url, cfg.api_key.strip(), model, provider_id=provider.id,
                                  temperature=cfg.temperature, batch_size=batch, workers=workers)
    if provider.kind == "anthropic":
        from .llm import AnthropicEngine

        return AnthropicEngine(cfg.api_key.strip(), model, base_url=base_url,
                               temperature=cfg.temperature, batch_size=batch, workers=workers)
    if provider.kind == "ollama":
        from .llm import OllamaEngine

        return OllamaEngine(model, base_url=base_url, temperature=cfg.temperature,
                            batch_size=batch, workers=workers)
    if provider.kind == "deepl":
        from .deepl import DeepLEngine

        engine = DeepLEngine(cfg.api_key, base_url=cfg.base_url)
        engine.batch_size = min(50, batch)
        engine.max_workers = workers
        return engine
    if provider.kind == "ct2":
        from .offline import OfflineEngine

        return OfflineEngine(model, device=cfg.device, batch_size=batch)
    raise ConfigError(f"Unsupported provider type: {provider.kind}")


def list_models(cfg: EngineSettings) -> list[str]:
    """Ask the provider which models are available (for the model dropdown)."""
    provider = providers.get(cfg.provider)
    if provider.kind == "ct2":
        from ..models import catalog

        return [m.id for m in catalog.OFFLINE_MODELS]
    if provider.kind == "deepl":
        return []
    engine = create_engine(EngineSettings(**{**cfg.__dict__, "model": cfg.model or provider.default_model or "x"}))
    return engine.list_models()  # type: ignore[attr-defined]


__all__ = [
    "AuthError", "CancelledError", "ConfigError", "Engine", "EngineError", "EngineSettings",
    "TranslationRequest", "create_engine", "list_models", "providers",
]
