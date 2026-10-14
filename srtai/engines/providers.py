"""Built-in provider presets shown in the UI."""
from __future__ import annotations

from dataclasses import dataclass, field

CLOUD = "cloud"
LOCAL = "local"
OFFLINE = "offline"


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    category: str                 # cloud | local | offline
    kind: str                     # openai | anthropic | deepl | ollama | ct2
    base_url: str = ""
    default_model: str = ""
    models: tuple[str, ...] = ()  # suggestions; the UI can also fetch the live list
    needs_key: bool = True
    key_url: str = ""
    batch_size: int = 40
    workers: int = 4
    note: str = ""
    extra: dict = field(default_factory=dict, compare=False, hash=False)


PROVIDERS: list[Provider] = [
    Provider(
        "gemini", "Google Gemini", CLOUD, "openai",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        default_model="gemini-flash-latest",
        models=("gemini-flash-latest", "gemini-3.6-flash", "gemini-3.5-flash-lite"),
        key_url="https://aistudio.google.com/apikey",
        note="Has a free tier. Fast and cheap.",
    ),
    Provider(
        "openai", "OpenAI", CLOUD, "openai",
        base_url="https://api.openai.com/v1",
        default_model="gpt-5-mini",
        models=("gpt-5-mini", "gpt-5-nano", "gpt-4.1-mini"),
        key_url="https://platform.openai.com/api-keys",
    ),
    Provider(
        "anthropic", "Anthropic Claude", CLOUD, "anthropic",
        base_url="https://api.anthropic.com",
        default_model="claude-haiku-5-5",
        models=("claude-haiku-5-5", "claude-sonnet-5-5"),
        key_url="https://console.anthropic.com/settings/keys",
    ),
    Provider(
        "deepl", "DeepL", CLOUD, "deepl",
        base_url="",  # chosen from the key: ":fx" keys use the free API
        default_model="",
        key_url="https://www.deepl.com/your-account/keys",
        batch_size=40,
        workers=2,
        note="Free plan: 500,000 characters/month. Translation-only service, no model to choose.",
    ),
    Provider(
        "deepseek", "DeepSeek", CLOUD, "openai",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        models=("deepseek-chat",),
        key_url="https://platform.deepseek.com/api_keys",
    ),
    Provider(
        "openrouter", "OpenRouter", CLOUD, "openai",
        base_url="https://openrouter.ai/api/v1",
        default_model="openrouter/auto",
        models=("openrouter/auto",),
        key_url="https://openrouter.ai/keys",
        note="One key for hundreds of models, including free ones.",
    ),
    Provider(
        "groq", "Groq", CLOUD, "openai",
        base_url="https://api.groq.com/openai/v1",
        default_model="llama-3.3-70b-versatile",
        models=("llama-3.3-70b-versatile",),
        key_url="https://console.groq.com/keys",
        workers=2,
    ),
    Provider(
        "mistral", "Mistral AI", CLOUD, "openai",
        base_url="https://api.mistral.ai/v1",
        default_model="mistral-small-latest",
        models=("mistral-small-latest", "mistral-medium-latest"),
        key_url="https://console.mistral.ai/api-keys",
    ),
    Provider(
        "custom", "Custom (OpenAI-compatible)", CLOUD, "openai",
        base_url="",
        default_model="",
        needs_key=False,
        note="Any server that speaks the OpenAI chat API (vLLM, llama.cpp server, Together...).",
    ),
    Provider(
        "ollama", "Ollama", LOCAL, "ollama",
        base_url="http://localhost:11434",
        default_model="translategemma:4b",
        models=("translategemma:4b", "translategemma:12b", "qwen3:8b", "gemma3:12b"),
        needs_key=False,
        batch_size=12,
        workers=1,
        note="Runs models on your PC. Install Ollama from ollama.com; the app downloads models for you.",
    ),
    Provider(
        "lmstudio", "LM Studio", LOCAL, "openai",
        base_url="http://localhost:1234/v1",
        default_model="",
        needs_key=False,
        batch_size=12,
        workers=1,
        note="Start LM Studio's local server and load a model.",
    ),
    Provider(
        "offline", "Built-in offline (NLLB)", OFFLINE, "ct2",
        default_model="nllb-600m",
        needs_key=False,
        batch_size=16,
        workers=1,
        note="No internet or extra software needed after the model download.",
    ),
]

_BY_ID = {p.id: p for p in PROVIDERS}


def get(provider_id: str) -> Provider:
    try:
        return _BY_ID[provider_id]
    except KeyError:
        raise KeyError(f"Unknown provider: {provider_id}") from None


def by_category(category: str) -> list[Provider]:
    return [p for p in PROVIDERS if p.category == category]
