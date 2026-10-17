import json

from app import llm


class FakeStreamingResponse:
    def __init__(self, lines):
        self.lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __iter__(self):
        yield from self.lines


def test_openai_compatible_vision_adapter_streams_without_vendor_names(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        chunk = {
            "choices": [{"delta": {"content": "visible result"}}],
        }
        return FakeStreamingResponse([f"data: {json.dumps(chunk)}\n".encode(), b"data: [DONE]\n"])

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    adapter = llm.OpenAICompatibleVisionAdapter(
        {
            "model": "deployment-model",
            "base_url": "https://provider.example/v1",
            "api_key": "test-key",
            "headers": {"X-Provider": "custom"},
            "extra_body": {"vendor_option": True},
            "temperature": 0.2,
            "max_tokens": 512,
            "timeout": 12,
        }
    )
    pieces = list(adapter.stream("aW1hZ2U=", "inspect"))

    assert captured["url"] == "https://provider.example/v1/chat/completions"
    assert captured["body"]["model"] == "deployment-model"
    assert captured["body"]["vendor_option"] is True
    assert captured["body"]["messages"][0]["content"][1]["type"] == "image_url"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert pieces == [{"type": "content", "text": "visible result"}]


def test_custom_factory_path_resolves_callable():
    factory = llm._resolve_factory("builtins:dict")
    assert callable(factory)


def test_ollama_url_accepts_root_and_api_paths():
    assert llm._ollama_chat_url("http://localhost:11434") == ("http://localhost:11434/api/chat")
    assert llm._ollama_chat_url("http://localhost:11434/api") == ("http://localhost:11434/api/chat")
