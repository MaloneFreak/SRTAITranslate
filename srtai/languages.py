"""Language table shared by every engine.

Each entry maps one user-facing language to the codes each backend expects:
BCP-47 for LLMs and file names, FLORES-200 for NLLB, and DeepL's codes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Language:
    code: str            # BCP-47, also used in output file names (e.g. "pt-BR")
    name: str            # English name, also used in LLM prompts
    name_pt: str         # Portuguese name, shown when the UI is in PT-BR
    nllb: Optional[str]  # FLORES-200 code used by NLLB models
    deepl: Optional[str] = None  # DeepL target code (source uses the part before "-")

    @property
    def base(self) -> str:
        return self.code.split("-")[0].lower()

    def display(self, ui_lang: str = "en") -> str:
        return self.name_pt if ui_lang.startswith("pt") else self.name

    @property
    def deepl_source(self) -> Optional[str]:
        return self.deepl.split("-")[0] if self.deepl else None


AUTO = "auto"

LANGUAGES: list[Language] = [
    Language("en", "English", "Inglês", "eng_Latn", "EN-US"),
    Language("en-GB", "English (UK)", "Inglês (Reino Unido)", "eng_Latn", "EN-GB"),
    Language("pt-BR", "Portuguese (Brazil)", "Português (Brasil)", "por_Latn", "PT-BR"),
    Language("pt-PT", "Portuguese (Portugal)", "Português (Portugal)", "por_Latn", "PT-PT"),
    Language("es", "Spanish", "Espanhol", "spa_Latn", "ES"),
    Language("es-419", "Spanish (Latin America)", "Espanhol (América Latina)", "spa_Latn", "ES-419"),
    Language("fr", "French", "Francês", "fra_Latn", "FR"),
    Language("de", "German", "Alemão", "deu_Latn", "DE"),
    Language("it", "Italian", "Italiano", "ita_Latn", "IT"),
    Language("nl", "Dutch", "Holandês", "nld_Latn", "NL"),
    Language("pl", "Polish", "Polonês", "pol_Latn", "PL"),
    Language("ru", "Russian", "Russo", "rus_Cyrl", "RU"),
    Language("uk", "Ukrainian", "Ucraniano", "ukr_Cyrl", "UK"),
    Language("cs", "Czech", "Tcheco", "ces_Latn", "CS"),
    Language("sk", "Slovak", "Eslovaco", "slk_Latn", "SK"),
    Language("sl", "Slovenian", "Esloveno", "slv_Latn", "SL"),
    Language("hr", "Croatian", "Croata", "hrv_Latn", None),
    Language("sr", "Serbian", "Sérvio", "srp_Cyrl", None),
    Language("bs", "Bosnian", "Bósnio", "bos_Latn", None),
    Language("bg", "Bulgarian", "Búlgaro", "bul_Cyrl", "BG"),
    Language("ro", "Romanian", "Romeno", "ron_Latn", "RO"),
    Language("hu", "Hungarian", "Húngaro", "hun_Latn", "HU"),
    Language("el", "Greek", "Grego", "ell_Grek", "EL"),
    Language("tr", "Turkish", "Turco", "tur_Latn", "TR"),
    Language("sv", "Swedish", "Sueco", "swe_Latn", "SV"),
    Language("nb", "Norwegian (Bokmål)", "Norueguês (Bokmål)", "nob_Latn", "NB"),
    Language("da", "Danish", "Dinamarquês", "dan_Latn", "DA"),
    Language("fi", "Finnish", "Finlandês", "fin_Latn", "FI"),
    Language("et", "Estonian", "Estoniano", "est_Latn", "ET"),
    Language("lv", "Latvian", "Letão", "lvs_Latn", "LV"),
    Language("lt", "Lithuanian", "Lituano", "lit_Latn", "LT"),
    Language("is", "Icelandic", "Islandês", "isl_Latn", None),
    Language("ga", "Irish", "Irlandês", "gle_Latn", None),
    Language("ca", "Catalan", "Catalão", "cat_Latn", None),
    Language("gl", "Galician", "Galego", "glg_Latn", None),
    Language("eu", "Basque", "Basco", "eus_Latn", None),
    Language("sq", "Albanian", "Albanês", "als_Latn", None),
    Language("mk", "Macedonian", "Macedônio", "mkd_Cyrl", None),
    Language("be", "Belarusian", "Bielorrusso", "bel_Cyrl", None),
    Language("cy", "Welsh", "Galês", "cym_Latn", None),
    Language("eo", "Esperanto", "Esperanto", "epo_Latn", None),
    Language("ar", "Arabic", "Árabe", "arb_Arab", "AR"),
    Language("he", "Hebrew", "Hebraico", "heb_Hebr", "HE"),
    Language("fa", "Persian", "Persa", "pes_Arab", None),
    Language("ur", "Urdu", "Urdu", "urd_Arab", None),
    Language("hi", "Hindi", "Hindi", "hin_Deva", None),
    Language("bn", "Bengali", "Bengali", "ben_Beng", None),
    Language("pa", "Punjabi", "Punjabi", "pan_Guru", None),
    Language("gu", "Gujarati", "Guzerate", "guj_Gujr", None),
    Language("mr", "Marathi", "Marathi", "mar_Deva", None),
    Language("ta", "Tamil", "Tâmil", "tam_Taml", None),
    Language("te", "Telugu", "Telugo", "tel_Telu", None),
    Language("kn", "Kannada", "Canarês", "kan_Knda", None),
    Language("ml", "Malayalam", "Malaiala", "mal_Mlym", None),
    Language("ne", "Nepali", "Nepalês", "npi_Deva", None),
    Language("si", "Sinhala", "Cingalês", "sin_Sinh", None),
    Language("th", "Thai", "Tailandês", "tha_Thai", "TH"),
    Language("vi", "Vietnamese", "Vietnamita", "vie_Latn", "VI"),
    Language("id", "Indonesian", "Indonésio", "ind_Latn", "ID"),
    Language("ms", "Malay", "Malaio", "zsm_Latn", None),
    Language("tl", "Filipino (Tagalog)", "Filipino (Tagalo)", "tgl_Latn", None),
    Language("zh-Hans", "Chinese (Simplified)", "Chinês (Simplificado)", "zho_Hans", "ZH-HANS"),
    Language("zh-Hant", "Chinese (Traditional)", "Chinês (Tradicional)", "zho_Hant", "ZH-HANT"),
    Language("yue", "Cantonese", "Cantonês", "yue_Hant", None),
    Language("ja", "Japanese", "Japonês", "jpn_Jpan", "JA"),
    Language("ko", "Korean", "Coreano", "kor_Hang", "KO"),
    Language("km", "Khmer", "Khmer", "khm_Khmr", None),
    Language("lo", "Lao", "Laosiano", "lao_Laoo", None),
    Language("my", "Burmese", "Birmanês", "mya_Mymr", None),
    Language("ka", "Georgian", "Georgiano", "kat_Geor", None),
    Language("hy", "Armenian", "Armênio", "hye_Armn", None),
    Language("az", "Azerbaijani", "Azerbaijano", "azj_Latn", None),
    Language("kk", "Kazakh", "Cazaque", "kaz_Cyrl", None),
    Language("uz", "Uzbek", "Uzbeque", "uzn_Latn", None),
    Language("mn", "Mongolian", "Mongol", "khk_Cyrl", None),
    Language("sw", "Swahili", "Suaíli", "swh_Latn", None),
    Language("am", "Amharic", "Amárico", "amh_Ethi", None),
    Language("af", "Afrikaans", "Africâner", "afr_Latn", None),
    Language("zu", "Zulu", "Zulu", "zul_Latn", None),
    Language("yo", "Yoruba", "Iorubá", "yor_Latn", None),
    Language("ha", "Hausa", "Hauçá", "hau_Latn", None),
    Language("so", "Somali", "Somali", "som_Latn", None),
]

_BY_CODE = {lang.code.lower(): lang for lang in LANGUAGES}

# ISO 639-1 codes returned by language detection that need a specific variant.
_DETECTION_ALIASES = {
    "pt": "pt-BR",
    "zh": "zh-Hans",
    "no": "nb",
    "nn": "nb",
    "iw": "he",
}


def get(code: Optional[str]) -> Optional[Language]:
    """Return the language for a BCP-47 code (case-insensitive), or None."""
    if not code or code == AUTO:
        return None
    key = code.strip().lower()
    if key in _BY_CODE:
        return _BY_CODE[key]
    key = _DETECTION_ALIASES.get(key, key).lower()
    if key in _BY_CODE:
        return _BY_CODE[key]
    base = key.split("-")[0]
    return _BY_CODE.get(_DETECTION_ALIASES.get(base, base).lower())


def require(code: str) -> Language:
    lang = get(code)
    if lang is None:
        raise ValueError(f"Unknown language code: {code!r}")
    return lang


def sorted_for_ui(ui_lang: str = "en") -> list[Language]:
    return sorted(LANGUAGES, key=lambda lang: lang.display(ui_lang).casefold())
