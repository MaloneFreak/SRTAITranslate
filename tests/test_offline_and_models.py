import json

import pytest

from srtai import app_paths, languages
from srtai.core.pipeline import JobOptions, SubtitleTranslator
from srtai.engines.base import TranslationRequest
from srtai.models import catalog, downloader

ctranslate2 = pytest.importorskip("ctranslate2")
pytest.importorskip("sentencepiece")


@pytest.fixture
def tiny_installed(tmp_path):
    from tiny_model import build_tiny_nllb

    target = downloader.model_path("nllb-600m")
    build_tiny_nllb(str(target))
    (target / downloader.MANIFEST).write_text(json.dumps({"id": "nllb-600m"}))
    return target


def test_offline_engine_plumbing(tiny_installed, sample_srt):
    from srtai.engines.offline import OfflineEngine

    engine = OfflineEngine("nllb-600m", device="cpu", beam_size=1)
    statuses = []
    engine.prepare(lambda msg, frac: statuses.append(msg))
    assert engine.active_device == "cpu"
    out = engine.translate(TranslationRequest(texts=["Hello world.", "Thank you."],
                                              source=languages.get("en"), target=languages.get("pt-BR")))
    assert len(out) == 2 and all(isinstance(t, str) for t in out)
    assert not any("por_Latn" in t for t in out)  # language token is stripped

    result = SubtitleTranslator(engine, JobOptions(source_lang="en", target_lang="pt-BR")).translate_file(sample_srt)
    assert result.ok, result.error
    assert result.cues == 9


def test_offline_requires_known_source_language(tiny_installed):
    from srtai.engines.base import ConfigError
    from srtai.engines.offline import OfflineEngine

    engine = OfflineEngine("nllb-600m", device="cpu")
    with pytest.raises(ConfigError):
        engine.translate(TranslationRequest(texts=["x"], source=None, target=languages.get("pt-BR")))


def test_catalog_and_install_state(tiny_installed):
    assert downloader.is_installed("nllb-600m")
    assert not downloader.is_installed("nllb-3.3b")
    assert downloader.installed_size("nllb-600m") > 0
    assert catalog.get("nllb-1.3b").size_label.endswith("GB")
    downloader.delete_model("nllb-600m")
    assert not downloader.is_installed("nllb-600m")


def test_download_resumes_and_installs(monkeypatch, tmp_path):
    """Simulate Hugging Face with a fake session: listing + ranged downloads."""
    files = {"model.bin": b"x" * 3000, "config.json": b"{}", "shared_vocabulary.json": b"[]",
             "sentencepiece.bpe.model": b"spm"}

    class Resp:
        def __init__(self, status, body=b"", js=None):
            self.status_code, self._body, self._js = status, body, js
            self.ok = status < 400

        def json(self):
            return self._js

        def raise_for_status(self):
            if not self.ok:
                raise RuntimeError(self.status_code)

        def iter_content(self, chunk_size):
            for i in range(0, len(self._body), 1000):
                yield self._body[i: i + 1000]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Session:
        def get(self, url, headers=None, stream=False, timeout=None, allow_redirects=True):
            if "/api/models/" in url:
                if "osa911" in url:
                    return Resp(404)
                return Resp(200, js=[{"type": "file", "path": k, "size": len(v)} for k, v in files.items()]
                            + [{"type": "file", "path": "README.md", "size": 5}])
            name = url.rsplit("/", 1)[1]
            body = files[name]
            start = int(headers["Range"].split("=")[1].split("-")[0]) if headers else 0
            return Resp(206 if start else 200, body[start:])

    monkeypatch.setattr(downloader.http, "session", lambda: Session())
    # A partial file from an interrupted download is resumed, not restarted.
    partial = app_paths.models_dir() / "nllb-600m.partial"
    partial.mkdir(parents=True)
    (partial / "model.bin.part").write_bytes(b"x" * 1000)
    seen = []
    path = downloader.install_model("nllb-600m", lambda d, t, n: seen.append((d, t)))
    assert (path / "model.bin").read_bytes() == files["model.bin"]
    assert not (path / "README.md").exists()
    assert downloader.is_installed("nllb-600m")
    assert seen[-1][0] == seen[-1][1]
