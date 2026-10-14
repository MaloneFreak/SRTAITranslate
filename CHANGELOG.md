# Changelog

## [2.0.0] - 2026-10

A rewrite focused on a light download, more ways to translate and better subtitle quality.

### Lighter and simpler
- The Windows `.exe` no longer bundles PyTorch: it is a single file of about 50 MB instead of two ~1.2 GB split archives.
- Models are downloaded **on demand**, inside the app, with progress and resume.
- The offline NLLB models now run on CTranslate2 with int8 quantization: the 3.3B model used in v1.x drops from ~17 GB to ~3.4 GB and runs much faster, and smaller 600M (0.6 GB) and 1.3B (1.4 GB) options were added. CPU works out of the box; NVIDIA GPUs are used when available.
- The model stays loaded between files instead of being reloaded for every translation.
- No Hugging Face token needed anymore.

### More engines
- Cloud APIs: Google Gemini, OpenAI, Anthropic Claude, DeepL, DeepSeek, OpenRouter, Groq, Mistral and any OpenAI-compatible server. A refresh button loads each provider's current model list.
- Local AI with Ollama (the app downloads models for you, including Google's TranslateGemma) and LM Studio.

### Smarter translation
- Context-aware LLM translation: lines are sent in batches with the surrounding dialogue, and answers are validated line by line; missing lines are retried in smaller batches.
- Sentences split across two or three subtitles are translated as one sentence for engines without context (offline, DeepL), then split back.
- Keeps formatting: italics and other tags, `{\an8}` positions, dialogue dashes, music notes, sound descriptions on their own line.
- Balanced line breaks (42 characters per line by default, configurable).
- Automatic source language detection and file encoding detection (UTF-8, UTF-16, Windows-1252, ...).
- Translation memory: interrupted or repeated jobs reuse what was already translated (also saves API costs).
- Glossary, notes about the video and formality options for better word choices.
- Optional: remove hearing-impaired notes, bilingual subtitles (original under the translation).

### New app
- Modern interface (CustomTkinter) with dark and light themes, in English and Brazilian Portuguese.
- Queue of many files or whole folders, drag and drop, live preview of the line being translated and a table of all lines.
- Output saved next to the original as `Movie.pt-BR.srt` (configurable folder and name pattern) so players pick it up automatically.
- API keys are stored in the system credential store (Windows Credential Manager) instead of a plain `settings.json`.
- Command line interface (`srtai translate ...`) for scripts and batch jobs; the same `.exe` works as a CLI.
- Portable mode: create a `SRTAI_data` folder next to the `.exe` to keep settings and models with it.
- Update check against GitHub releases.

### Development
- Code split into a package (`srtai/`) with tests, a PyInstaller spec and GitHub Actions that test, build and publish the `.exe`.

## [1.4] - 2024-08-15
- Last version based on PyTorch + `facebook/nllb-200-3.3B`.
