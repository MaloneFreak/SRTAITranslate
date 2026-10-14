"""Offline models the app can download on demand.

The models are Meta's NLLB-200 converted to CTranslate2 with int8 quantization,
which makes them 4-6x smaller and much faster than the original PyTorch weights
(v1.x shipped PyTorch + the 3.3B model in float32, ~17 GB).
Each entry lists mirrors in order; the first one that responds is used.
"""
from __future__ import annotations

from dataclasses import dataclass

NLLB_TOKENIZER_REPO = "facebook/nllb-200-distilled-600M"
NLLB_TOKENIZER_FILE = "sentencepiece.bpe.model"


@dataclass(frozen=True)
class OfflineModel:
    id: str
    name: str
    repos: tuple[str, ...]
    size_mb: int
    ram_gb: float
    quality: int      # 1..3
    speed: int        # 1..3
    description: str
    description_pt: str
    family: str = "nllb"
    license: str = "CC-BY-NC-4.0 (non-commercial use)"

    @property
    def size_label(self) -> str:
        return f"{self.size_mb / 1024:.1f} GB" if self.size_mb >= 1024 else f"{self.size_mb} MB"


OFFLINE_MODELS: list[OfflineModel] = [
    OfflineModel(
        id="nllb-600m",
        name="NLLB-200 600M (fast)",
        repos=(
            "osa911/nllb-200-distilled-600M-ct2-int8",
            "mijuanlo/nllb-200-distilled-600M-ct2-int8",
            "luigi000/nllb-200-distilled-600M-ct2-int8",
        ),
        size_mb=620,
        ram_gb=1.5,
        quality=1,
        speed=3,
        description="Smallest and fastest. Runs well on any PC (CPU). Good for a quick translation.",
        description_pt="Menor e mais rápido. Roda bem em qualquer PC (CPU). Bom para traduções rápidas.",
    ),
    OfflineModel(
        id="nllb-1.3b",
        name="NLLB-200 1.3B (balanced)",
        repos=(
            "OpenNMT/nllb-200-distilled-1.3B-ct2-int8",
            "mijuanlo/nllb-200-distilled-1.3B-int8-ct2",
        ),
        size_mb=1320,
        ram_gb=3,
        quality=2,
        speed=2,
        description="Noticeably better quality. Recommended for most people.",
        description_pt="Qualidade bem melhor. Recomendado para a maioria das pessoas.",
    ),
    OfflineModel(
        id="nllb-3.3b",
        name="NLLB-200 3.3B (best)",
        repos=(
            "OpenNMT/nllb-200-3.3B-ct2-int8",
            "mijuanlo/nllb-200-3.3B-ct2-int8",
        ),
        size_mb=3210,
        ram_gb=6,
        quality=3,
        speed=1,
        description="Same model as v1.x, but 5x smaller. Best offline quality; an NVIDIA GPU helps a lot.",
        description_pt="Mesmo modelo da v1.x, mas 5x menor. Melhor qualidade offline; uma GPU NVIDIA ajuda muito.",
    ),
]

_BY_ID = {m.id: m for m in OFFLINE_MODELS}


def get(model_id: str) -> OfflineModel:
    try:
        return _BY_ID[model_id]
    except KeyError:
        raise KeyError(f"Unknown offline model: {model_id}") from None


# Ollama models suggested in the Models page.
@dataclass(frozen=True)
class OllamaSuggestion:
    tag: str
    size_label: str
    description: str
    description_pt: str


OLLAMA_SUGGESTIONS: list[OllamaSuggestion] = [
    OllamaSuggestion("translategemma:4b", "3.3 GB",
                     "Google's translation model. Great quality for its size; runs on most PCs.",
                     "Modelo de tradução do Google. Ótima qualidade para o tamanho; roda na maioria dos PCs."),
    OllamaSuggestion("translategemma:12b", "8.1 GB",
                     "Larger TranslateGemma. Excellent quality; needs a GPU with ~10 GB or lots of RAM.",
                     "TranslateGemma maior. Qualidade excelente; precisa de GPU com ~10 GB ou bastante RAM."),
    OllamaSuggestion("qwen3:8b", "5.2 GB",
                     "General LLM that follows the subtitle context well (uses the context-aware mode).",
                     "LLM geral que acompanha bem o contexto das falas (usa o modo com contexto)."),
    OllamaSuggestion("gemma3:12b", "8.1 GB",
                     "Strong multilingual general model (context-aware mode).",
                     "Modelo geral multilíngue forte (modo com contexto)."),
]
