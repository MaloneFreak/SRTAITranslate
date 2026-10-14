import json

from srtai import app_paths, settings
from srtai.cli import main as cli_main
from srtai.settings import Settings


def test_settings_roundtrip_and_unknown_keys():
    s = Settings.load()
    s.provider = "deepl"
    s.models["openai"] = "gpt-x"
    s.job.target_lang = "es"
    s.save()
    data = json.loads(app_paths.settings_file().read_text(encoding="utf-8"))
    data["something_new"] = 1
    data["job"]["removed_option"] = True
    app_paths.settings_file().write_text(json.dumps(data), encoding="utf-8")
    loaded = Settings.load()
    assert loaded.provider == "deepl" and loaded.model_for("openai") == "gpt-x" and loaded.job.target_lang == "es"


def test_api_key_fallback_and_env(monkeypatch):
    monkeypatch.setattr(settings, "_keyring", lambda: None)
    assert settings.set_api_key("openai", "sk-test") == "file"
    assert settings.get_api_key("openai") == "sk-test"
    settings.set_api_key("openai", "")
    assert settings.get_api_key("openai") == ""
    monkeypatch.setenv("GEMINI_API_KEY", "from-env")
    assert settings.get_api_key("gemini") == "from-env"


def test_cloud_overrides_apply_only_to_cloud():
    s = Settings()
    s.workers["*"] = 7
    assert s.engine_settings("openai").workers == 7
    assert s.engine_settings("ollama").workers == 0


def test_cli_translate_with_custom_server(sample_srt, monkeypatch, capsys):
    from srtai.engines.base import Engine

    class Echo(Engine):
        name = "echo"

        def translate(self, request):
            return ["ES:" + t for t in request.texts]

    monkeypatch.setattr("srtai.cli.create_engine", lambda cfg: Echo())
    code = cli_main(["translate", str(sample_srt), "--to", "es", "--from", "en", "--provider", "custom",
                     "--no-cache"])
    assert code == 0
    out = sample_srt.with_name("Movie.es.srt")
    assert "ES:Where are you going?" in out.read_text(encoding="utf-8")
    assert "1 translated, 0 failed" in capsys.readouterr().out


def test_cli_rejects_unknown_language(sample_srt):
    assert cli_main(["translate", str(sample_srt), "--to", "xx-YY"]) == 2


def test_selftest_passes(tmp_path):
    report = tmp_path / "report.txt"
    assert cli_main(["selftest", "--out", str(report)]) == 0
    assert "RESULT: PASS" in report.read_text(encoding="utf-8")
