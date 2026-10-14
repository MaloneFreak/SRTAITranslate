"""Engines against a local mock server that speaks the OpenAI, Anthropic, DeepL and Ollama APIs."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from srtai import languages
from srtai.core.pipeline import JobOptions, SubtitleTranslator
from srtai.engines import EngineSettings, create_engine, list_models
from srtai.engines.base import AuthError, TranslationRequest
from srtai.engines.deepl import DeepLEngine
from srtai.engines.llm import AnthropicEngine, OllamaEngine, OpenAICompatEngine
from srtai.engines.prompts import parse_translations, split_lines_answer


class MockState:
    def __init__(self):
        self.requests = []
        self.reject_temperature = False
        self.fail_first = 0


def _translate_payload(user_content: str) -> str:
    data = json.loads(user_content)
    return json.dumps({"translations": [{"id": l["id"], "text": "PT:" + l["text"]} for l in data["lines"]]})


def make_handler(state: MockState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, obj, headers=None):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.startswith("/v1/models"):
                return self._send(200, {"data": [{"id": "model-a"}, {"id": "models/model-b"}]})
            if self.path == "/api/tags":
                return self._send(200, {"models": [{"name": "qwen3:8b", "size": 5}]})
            if self.path == "/api/version":
                return self._send(200, {"version": "0.12.0"})
            self._send(404, {"error": "nope"})

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            state.requests.append((self.path, dict(self.headers), body))
            if state.fail_first > 0:
                state.fail_first -= 1
                return self._send(429, {"error": {"message": "slow down"}}, {"Retry-After": "0.1"})
            if self.path == "/v1/chat/completions":
                if self.headers.get("Authorization") != "Bearer good":
                    return self._send(401, {"error": {"message": "bad key"}})
                if state.reject_temperature and "temperature" in body:
                    return self._send(400, {"error": {"message": "Unsupported value: 'temperature'"}})
                content = _translate_payload(body["messages"][-1]["content"])
                return self._send(200, {"choices": [{"message": {"content": "```json\n" + content + "\n```"}}]})
            if self.path == "/v1/messages":
                content = _translate_payload(body["messages"][0]["content"])
                return self._send(200, {"content": [{"type": "text", "text": content}]})
            if self.path == "/v2/translate":
                return self._send(200, {"translations": [{"text": "DE:" + t} for t in body["text"]]})
            if self.path == "/api/chat":
                if body.get("format") == "json":
                    content = _translate_payload(body["messages"][-1]["content"])
                else:  # translategemma style: plain lines
                    text = body["messages"][-1]["content"].split("\n\n\n", 1)[1]
                    content = "\n".join("PT:" + ln for ln in text.split("\n"))
                return self._send(200, {"message": {"role": "assistant", "content": content}})
            self._send(404, {"error": "unknown"})

    return Handler


@pytest.fixture
def server():
    state = MockState()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    state.url = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield state
    httpd.shutdown()


def req(texts):
    return TranslationRequest(texts=texts, source=languages.get("en"), target=languages.get("pt-BR"),
                              context_before=["Earlier line."])


def test_openai_compat_roundtrip_and_temperature_fallback(server):
    server.reject_temperature = True
    engine = OpenAICompatEngine(server.url + "/v1", "good", "model-a")
    assert engine.translate(req(["Hello", "World"])) == ["PT:Hello", "PT:World"]
    path, headers, body = server.requests[-1]
    assert body["response_format"] == {"type": "json_object"}
    assert "temperature" not in body
    assert "Portuguese (Brazil)" in body["messages"][0]["content"]
    assert engine.list_models() == ["model-a", "model-b"]


def test_openai_bad_key(server):
    engine = OpenAICompatEngine(server.url + "/v1", "wrong", "model-a")
    with pytest.raises(AuthError):
        engine.translate(req(["Hello"]))


def test_retry_after_429(server):
    server.fail_first = 2
    engine = OpenAICompatEngine(server.url + "/v1", "good", "model-a")
    assert engine.translate(req(["Hi"])) == ["PT:Hi"]


def test_anthropic(server):
    engine = AnthropicEngine("key", "claude-x", base_url=server.url)
    assert engine.translate(req(["Hello"])) == ["PT:Hello"]
    path, headers, body = server.requests[-1]
    assert headers["x-api-key"] == "key" and body["max_tokens"] > 0 and "system" in body


def test_deepl_uses_free_endpoint_for_fx_keys(server):
    assert DeepLEngine("abc:fx").base_url == "https://api-free.deepl.com"
    engine = DeepLEngine("abc", base_url=server.url)
    out = engine.translate(TranslationRequest(texts=["Hi <i>there</i>"], source=languages.get("en"),
                                              target=languages.get("de"), formality="formal"))
    assert out == ["DE:Hi <i>there</i>"]
    body = server.requests[-1][2]
    assert body["target_lang"] == "DE" and body["source_lang"] == "EN" and body["formality"] == "prefer_more"


def test_ollama_json_and_translategemma(server):
    engine = OllamaEngine("qwen3:8b", base_url=server.url)
    engine.prepare()  # running + model present, nothing to pull
    assert engine.translate(req(["One", "Two"])) == ["PT:One", "PT:Two"]
    gemma = OllamaEngine("translategemma:4b", base_url=server.url)
    assert gemma.translate(req(["One", "Two"])) == ["PT:One", "PT:Two"]
    prompt = server.requests[-1][2]["messages"][-1]["content"]
    assert prompt.startswith("You are a professional English (en) to Portuguese (Brazil) (pt-BR) translator")


def test_full_job_through_http(server, sample_srt):
    cfg = EngineSettings(provider="custom", model="model-a", api_key="good", base_url=server.url + "/v1")
    engine = create_engine(cfg)
    result = SubtitleTranslator(engine, JobOptions(source_lang="en", target_lang="pt-BR")).translate_file(sample_srt)
    assert result.ok, result.error
    text = result.output_path.read_text(encoding="utf-8")
    assert "PT:Where are you going?" in text
    assert list_models(cfg) == ["model-a", "model-b"]


def test_parse_translations_tolerates_formats():
    assert parse_translations('<think>hmm</think>{"translations":[{"id":2,"text":"b"},{"id":1,"text":"a"}]}', 2) == ["a", "b"]
    assert parse_translations('Sure! {"translations": ["a", "b"]} hope it helps', 2) == ["a", "b"]
    assert parse_translations('{"1": "a", "3": "c"}', 3) == ["a", None, "c"]
    assert parse_translations("not json", 2) == [None, None]
    assert split_lines_answer("a\nb\n", 2) == ["a", "b"]
    assert split_lines_answer("a b", 2) == [None, None]


def test_missing_key_is_a_config_error():
    from srtai.engines import ConfigError

    with pytest.raises(ConfigError):
        create_engine(EngineSettings(provider="openai", api_key=""))
