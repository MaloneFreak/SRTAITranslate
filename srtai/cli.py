"""Command line interface.

Examples:
    python -m srtai translate movie.srt --to pt-BR --provider gemini
    python -m srtai translate ./season1 --to es --provider offline --model nllb-1.3b
    python -m srtai models download nllb-600m
"""
from __future__ import annotations

import argparse
import logging
import sys
import threading
from pathlib import Path

from . import APP_NAME, __version__, app_paths, languages
from .core.cache import TranslationCache
from .core.pipeline import Event, SubtitleTranslator
from .engines import ConfigError, EngineError, create_engine, providers
from .models import catalog, downloader
from .settings import Settings, get_api_key, set_api_key


def collect_files(items: list[str]) -> list[Path]:
    files: list[Path] = []
    for item in items:
        path = Path(item)
        if path.is_dir():
            files.extend(sorted(p for p in path.iterdir() if p.suffix.lower() == ".srt"))
        elif path.suffix.lower() == ".srt" and path.exists():
            files.append(path)
        else:
            print(f"Skipping {item}: not an .srt file or folder", file=sys.stderr)
    return files


def _progress_printer():
    state = {"line": ""}

    def on_event(event: Event) -> None:
        name = Path(event.file).name if event.file else ""
        if event.kind == "status":
            frac = event.data.get("fraction")
            pct = f" {frac * 100:5.1f}%" if isinstance(frac, (int, float)) else ""
            print(f"\r{event.data['message']}{pct}".ljust(80), end="", flush=True)
        elif event.kind == "file_start":
            print(f"\n> {name}")
        elif event.kind == "progress":
            done, total = event.data["done"], event.data["total"]
            print(f"\r  {done}/{total} lines ({done * 100 // max(1, total)}%)".ljust(80), end="", flush=True)
        elif event.kind == "warning":
            print(f"\n  ! {event.data['message']}")
        elif event.kind == "file_done":
            r = event.data["result"]
            print(f"\n  OK -> {r.output_path}  ({r.seconds:.1f}s, {r.from_cache} from cache)")
        elif event.kind == "file_error":
            print(f"\n  FAILED: {event.data['error']}")
    return on_event


def cmd_translate(args: argparse.Namespace) -> int:
    settings = Settings.load()
    files = collect_files(args.inputs)
    if not files:
        print("No .srt files to translate.", file=sys.stderr)
        return 2
    provider_id = args.provider or settings.provider
    cfg = settings.engine_settings(provider_id)
    if args.model:
        cfg.model = args.model
    if args.api_key:
        cfg.api_key = args.api_key
    if args.base_url:
        cfg.base_url = args.base_url
    if args.workers:
        cfg.workers = args.workers
    if args.batch:
        cfg.batch_size = args.batch
    if args.device:
        cfg.device = args.device

    job = settings.job
    job.target_lang = args.to or job.target_lang
    job.source_lang = getattr(args, "from") or job.source_lang
    if args.out_dir is not None:
        job.output_dir = args.out_dir
    if args.pattern:
        job.filename_pattern = args.pattern
    if args.max_line is not None:
        job.max_line_length = args.max_line
    job.bilingual = args.bilingual or job.bilingual
    job.remove_sdh = args.remove_sdh or job.remove_sdh
    job.use_cache = not args.no_cache
    if args.notes:
        job.context_notes = args.notes
    if args.glossary_file:
        job.glossary = Path(args.glossary_file).read_text(encoding="utf-8")
    if args.formality:
        job.formality = args.formality
    for code in (job.target_lang, job.source_lang):
        if code != languages.AUTO and languages.get(code) is None:
            print(f"Unknown language code {code!r}. Run 'python -m srtai languages'.", file=sys.stderr)
            return 2

    try:
        engine = create_engine(cfg)
    except (ConfigError, EngineError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    cache = TranslationCache(app_paths.cache_file()) if job.use_cache else None
    translator = SubtitleTranslator(engine, job, cache, _progress_printer())
    try:
        results = translator.run(files)
    except KeyboardInterrupt:
        translator.cancel()
        print("\nCancelled.")
        return 130
    print()
    failed = [r for r in results if not r.ok]
    print(f"Done: {len(results) - len(failed)} translated, {len(failed)} failed.")
    return 1 if failed else 0


def cmd_models(args: argparse.Namespace) -> int:
    if args.action == "list":
        for m in catalog.OFFLINE_MODELS:
            mark = "installed" if downloader.is_installed(m.id) else "not installed"
            print(f"{m.id:<12} {m.size_label:>8}  {mark:<14} {m.name}")
        print(f"\nModels folder: {app_paths.models_dir()}")
        return 0
    if not args.model_id:
        print("Specify a model id (see 'models list').", file=sys.stderr)
        return 2
    if args.action == "delete":
        downloader.delete_model(args.model_id)
        print(f"Deleted {args.model_id}")
        return 0
    cancel = threading.Event()

    def progress(done: int, total: int, name: str) -> None:
        pct = done * 100 / total if total else 0
        print(f"\r{name}: {done / 1e6:,.0f}/{total / 1e6:,.0f} MB ({pct:.1f}%)".ljust(80), end="", flush=True)

    try:
        path = downloader.install_model(args.model_id, progress, cancel)
    except KeyboardInterrupt:
        cancel.set()
        print("\nPaused. Run the same command again to resume.")
        return 130
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 1
    print(f"\nInstalled to {path}")
    return 0


def cmd_providers(_args) -> int:
    for p in providers.PROVIDERS:
        key = "key saved" if (p.needs_key and get_api_key(p.id)) else ("needs key" if p.needs_key else "no key")
        print(f"{p.id:<11} {p.category:<8} {key:<10} {p.name}  (default model: {p.default_model or '-'})")
    return 0


def cmd_languages(_args) -> int:
    for lang in languages.sorted_for_ui():
        print(f"{lang.code:<8} {lang.name}")
    return 0


def cmd_set_key(args) -> int:
    where = set_api_key(args.provider, args.key)
    print(f"Saved {args.provider} key ({'credential store' if where == 'keyring' else 'local file'}).")
    return 0


def cmd_selftest(args) -> int:
    """Checks that every component works (used by CI on the built .exe)."""
    import importlib
    import tempfile

    report, ok = [], True
    for module in ("customtkinter", "tkinterdnd2", "ctranslate2", "sentencepiece", "py3langid", "keyring",
                   "srt", "requests", "charset_normalizer"):
        try:
            mod = importlib.import_module(module)
            report.append(f"ok   {module} {getattr(mod, '__version__', '')}")
        except Exception as exc:
            ok = False
            report.append(f"FAIL {module}: {exc}")
    try:
        from .core.detect import detect_language
        from .core.pipeline import JobOptions
        from .engines.base import Engine

        class Echo(Engine):
            name = "echo"

            def translate(self, request):
                return [f"[{request.target.code}] {x}" for x in request.texts]

        lang = detect_language(["Where are you going tonight?", "I think we should go home now."])
        report.append(f"{'ok  ' if lang and lang.code == 'en' else 'FAIL'} language detection -> "
                      f"{lang.code if lang else None}")
        ok &= bool(lang and lang.code == "en")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "test.en.srt"
            src.write_text("1\n00:00:01,000 --> 00:00:02,000\n<i>Hello there.</i>\n\n", encoding="utf-8")
            result = SubtitleTranslator(Echo(), JobOptions(target_lang="pt-BR")).translate_file(src)
            out = result.output_path.read_text(encoding="utf-8") if result.ok else str(result.error)
            report.append(f"{'ok  ' if result.ok else 'FAIL'} pipeline -> {out.strip().splitlines()[-1]}")
            ok &= result.ok
        import ctranslate2

        report.append(f"ok   ctranslate2 CUDA devices: {ctranslate2.get_cuda_device_count()}")
        from .gui import theme

        fonts = sorted(p.name for p in theme.app_paths.resource_path("assets", "fonts").glob("*.ttf"))
        report.append(f"{'ok  ' if fonts else 'FAIL'} bundled fonts: {', '.join(fonts)}")
        ok &= bool(fonts)
    except Exception as exc:
        ok = False
        report.append(f"FAIL pipeline: {exc}")
    text = "\n".join(report + [f"RESULT: {'PASS' if ok else 'FAIL'}"])
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="srtai", description=f"{APP_NAME} {__version__}")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command")

    t = sub.add_parser("translate", help="translate .srt files or folders")
    t.add_argument("inputs", nargs="+")
    t.add_argument("--to", help="target language code, e.g. pt-BR (see 'languages')")
    t.add_argument("--from", help="source language code or 'auto'")
    t.add_argument("--provider", choices=[p.id for p in providers.PROVIDERS])
    t.add_argument("--model")
    t.add_argument("--api-key")
    t.add_argument("--base-url")
    t.add_argument("--device", choices=["auto", "cpu", "cuda"], help="offline engine device")
    t.add_argument("--workers", type=int)
    t.add_argument("--batch", type=int, help="lines per request")
    t.add_argument("--out-dir")
    t.add_argument("--pattern", help="output name pattern, default '{name}.{lang}'")
    t.add_argument("--max-line", type=int, help="max characters per line (0 = keep one line)")
    t.add_argument("--bilingual", action="store_true", help="keep the original text under the translation")
    t.add_argument("--remove-sdh", action="store_true", help="remove [sounds] and SPEAKER: labels")
    t.add_argument("--notes", help="context about the video for LLMs")
    t.add_argument("--glossary-file", help="text file with 'term = translation' lines")
    t.add_argument("--formality", choices=["default", "formal", "informal"])
    t.add_argument("--no-cache", action="store_true")
    t.set_defaults(func=cmd_translate)

    m = sub.add_parser("models", help="manage offline models")
    m.add_argument("action", choices=["list", "download", "delete"])
    m.add_argument("model_id", nargs="?")
    m.set_defaults(func=cmd_models)

    sub.add_parser("providers", help="list translation providers").set_defaults(func=cmd_providers)
    sub.add_parser("languages", help="list language codes").set_defaults(func=cmd_languages)
    k = sub.add_parser("set-key", help="save an API key in the system credential store")
    k.add_argument("provider", choices=[p.id for p in providers.PROVIDERS if p.needs_key or p.id == "custom"])
    k.add_argument("key")
    k.set_defaults(func=cmd_set_key)
    st = sub.add_parser("selftest", help="check that all components work")
    st.add_argument("--out", help="also write the report to this file")
    st.set_defaults(func=cmd_selftest)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)
