"""User settings (JSON) and API keys (OS credential store)."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field, fields

from . import APP_ID, app_paths
from .core.pipeline import JobOptions
from .engines import EngineSettings, providers

log = logging.getLogger(__name__)

KEY_ENV_VARS = {
    "openai": ("OPENAI_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "deepl": ("DEEPL_API_KEY", "DEEPL_AUTH_KEY"),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "groq": ("GROQ_API_KEY",),
    "mistral": ("MISTRAL_API_KEY",),
    "custom": ("SRTAI_CUSTOM_API_KEY",),
}


@dataclass
class Settings:
    ui_language: str = ""                 # "" = follow the system, "en", "pt-BR"
    appearance: str = "system"            # system | dark | light
    provider: str = "gemini"
    models: dict = field(default_factory=dict)       # provider id -> model
    base_urls: dict = field(default_factory=dict)    # provider id -> URL override
    workers: dict = field(default_factory=dict)      # provider id -> parallel requests
    batch_sizes: dict = field(default_factory=dict)  # provider id -> lines per request
    temperature: float = 0.2
    offline_device: str = "auto"
    job: JobOptions = field(default_factory=JobOptions)
    last_dir: str = ""
    geometry: str = ""

    # -- persistence ------------------------------------------------------
    @classmethod
    def load(cls) -> "Settings":
        path = app_paths.settings_file()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError):
            log.warning("Settings file unreadable; using defaults", exc_info=True)
            return cls()
        known = {f.name for f in fields(cls)}
        job_known = {f.name for f in fields(JobOptions)}
        job = JobOptions(**{k: v for k, v in (data.get("job") or {}).items() if k in job_known})
        kwargs = {k: v for k, v in data.items() if k in known and k != "job"}
        settings = cls(**kwargs, job=job)
        if settings.provider not in {p.id for p in providers.PROVIDERS}:
            settings.provider = "gemini"
        return settings

    def save(self) -> None:
        path = app_paths.settings_file()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    # -- helpers ----------------------------------------------------------
    def model_for(self, provider_id: str) -> str:
        return self.models.get(provider_id) or providers.get(provider_id).default_model

    def base_url_for(self, provider_id: str) -> str:
        return self.base_urls.get(provider_id) or providers.get(provider_id).base_url

    def engine_settings(self, provider_id: str | None = None) -> EngineSettings:
        pid = provider_id or self.provider
        cloud = providers.get(pid).category == providers.CLOUD
        batch = self.batch_sizes.get(pid) or (self.batch_sizes.get("*") if cloud else 0)
        workers = self.workers.get(pid) or (self.workers.get("*") if cloud else 0)
        return EngineSettings(
            provider=pid,
            model=self.model_for(pid),
            api_key=get_api_key(pid),
            base_url=self.base_urls.get(pid, ""),
            batch_size=int(batch or 0),
            workers=int(workers or 0),
            temperature=self.temperature,
            device=self.offline_device,
        )


# -- API keys -------------------------------------------------------------
def _keyring():
    try:
        import keyring
        from keyring.errors import NoKeyringError  # noqa: F401

        backend = keyring.get_keyring()
        if "fail" in type(backend).__module__.lower():
            return None
        return keyring
    except Exception:
        return None


def _fallback_file():
    return app_paths.data_dir() / "keys.json"


def get_api_key(provider_id: str) -> str:
    kr = _keyring()
    if kr is not None:
        try:
            value = kr.get_password(APP_ID, provider_id)
            if value:
                return value
        except Exception:
            log.debug("keyring read failed", exc_info=True)
    try:
        data = json.loads(_fallback_file().read_text(encoding="utf-8"))
        if data.get(provider_id):
            return data[provider_id]
    except (OSError, ValueError):
        pass
    for var in KEY_ENV_VARS.get(provider_id, ()):
        if os.environ.get(var):
            return os.environ[var]
    return ""


def set_api_key(provider_id: str, value: str) -> str:
    """Store a key. Returns "keyring" or "file" depending on where it went."""
    value = (value or "").strip()
    kr = _keyring()
    if kr is not None:
        try:
            if value:
                kr.set_password(APP_ID, provider_id, value)
            else:
                try:
                    kr.delete_password(APP_ID, provider_id)
                except Exception:
                    pass
            _remove_from_file(provider_id)
            return "keyring"
        except Exception:
            log.warning("keyring write failed; using local file", exc_info=True)
    path = _fallback_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if value:
        data[provider_id] = value
    else:
        data.pop(provider_id, None)
    path.write_text(json.dumps(data), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return "file"


def _remove_from_file(provider_id: str) -> None:
    path = _fallback_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if data.pop(provider_id, None) is not None:
        path.write_text(json.dumps(data), encoding="utf-8")
