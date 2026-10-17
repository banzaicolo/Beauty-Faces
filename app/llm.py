"""Provider-neutral text and vision model adapters.

Supported deployment protocols:
- Ollama native
- OpenAI-compatible chat completions
- Custom factories loaded from a Python module path
"""

import importlib
import json
import urllib.request
from collections.abc import Generator

from . import config


def _resolve_factory(path_value: str):
    module_name, separator, attribute = path_value.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError("Provider factory must use module.path:function syntax")
    module = importlib.import_module(module_name)
    factory = getattr(module, attribute)
    if not callable(factory):
        raise TypeError(f"Provider factory is not callable: {path_value}")
    return factory


def _settings(prefix: str) -> dict:
    return {
        "provider": getattr(config, f"{prefix}_PROVIDER"),
        "model": getattr(config, f"{prefix}_MODEL"),
        "base_url": getattr(config, f"{prefix}_BASE_URL"),
        "api_key": getattr(config, f"{prefix}_API_KEY"),
        "factory": getattr(config, f"{prefix}_PROVIDER_FACTORY"),
        "temperature": getattr(config, f"{prefix}_TEMPERATURE"),
        "max_tokens": getattr(config, f"{prefix}_MAX_TOKENS"),
        "headers": getattr(config, f"{prefix}_HEADERS"),
        "extra_body": getattr(config, f"{prefix}_EXTRA_BODY"),
        "timeout": getattr(config, f"{prefix}_TIMEOUT_SECONDS"),
        "privacy": getattr(config, f"{prefix}_PRIVACY_MODE"),
    }


def get_chat_model():
    """Build a LangChain chat model from TEXT_* environment settings."""
    settings = _settings("TEXT")
    provider = settings["provider"]
    if provider == "custom":
        factory = _resolve_factory(settings["factory"])
        settings["tool_calling"] = config.TEXT_TOOL_CALLING
        return factory(settings)
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        client_kwargs = {}
        if settings["headers"]:
            client_kwargs["headers"] = settings["headers"]
        if settings["timeout"]:
            client_kwargs["timeout"] = settings["timeout"]
        options = {
            "model": settings["model"],
            "base_url": settings["base_url"],
            "temperature": settings["temperature"],
            "client_kwargs": client_kwargs,
        }
        if settings["max_tokens"] is not None:
            options["num_predict"] = settings["max_tokens"]
        options.update(settings["extra_body"])
        return ChatOllama(**options)
    if provider == "openai_compatible":
        from langchain_openai import ChatOpenAI

        options = {
            "model": settings["model"],
            "api_key": settings["api_key"] or "not-required",
            "temperature": settings["temperature"],
            "timeout": settings["timeout"],
            "default_headers": settings["headers"] or None,
        }
        if settings["base_url"]:
            options["base_url"] = settings["base_url"]
        if settings["max_tokens"] is not None:
            options["max_completion_tokens"] = settings["max_tokens"]
        if settings["extra_body"]:
            options["extra_body"] = settings["extra_body"]
        return ChatOpenAI(**options)
    raise RuntimeError(f"Unsupported text provider: {provider}")


def validate_provider_configuration() -> None:
    """Instantiate configured adapters without making a network request."""
    if config.TEXT_PROVIDER != "disabled":
        from langchain_core.language_models.chat_models import BaseChatModel

        model = get_chat_model()
        if not isinstance(model, BaseChatModel):
            raise TypeError("Text provider factory must return a LangChain BaseChatModel")
    if config.VISION_PROVIDER != "disabled":
        adapter = _vision_adapter()
        if not hasattr(adapter, "stream"):
            raise TypeError("Vision provider must expose stream(image_b64, prompt)")


def provider_name() -> str:
    if config.TEXT_PROVIDER == "custom":
        return f"custom:{config.TEXT_PROVIDER_FACTORY}"
    return f"{config.TEXT_PROVIDER}:{config.TEXT_MODEL}"


def text_privacy_mode() -> str:
    return config.TEXT_PRIVACY_MODE


def vision_privacy_mode() -> str:
    return config.VISION_PRIVACY_MODE


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", ""))
        return "".join(parts)
    return ""


def _completion_url(base_url: str) -> str:
    if base_url.endswith("/chat/completions"):
        return base_url
    return base_url.rstrip("/") + "/chat/completions"


def _ollama_chat_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/api/chat"):
        return base
    if base.endswith("/api"):
        return base + "/chat"
    return base + "/api/chat"


class OllamaVisionAdapter:
    def __init__(self, settings: dict):
        self.settings = settings

    def stream(self, image_b64: str, prompt: str) -> Generator[dict, None, None]:
        body = {
            "model": self.settings["model"],
            "messages": [{"role": "user", "content": prompt, "images": [image_b64]}],
            "stream": True,
            "options": {
                "temperature": self.settings["temperature"],
            },
        }
        if self.settings["max_tokens"] is not None:
            body["options"]["num_predict"] = self.settings["max_tokens"]
        body.update(self.settings["extra_body"])
        endpoint = _ollama_chat_url(self.settings["base_url"])
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.settings["timeout"]) as response:
            for raw_line in response:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = chunk.get("message", {})
                thinking = message.get("thinking")
                if thinking:
                    yield {"type": "thinking", "text": thinking}
                content = message.get("content")
                if content:
                    yield {"type": "content", "text": content}
                if chunk.get("done"):
                    break


class OpenAICompatibleVisionAdapter:
    def __init__(self, settings: dict):
        self.settings = settings

    def _endpoint_and_headers(self):
        endpoint = config.VISION_ENDPOINT or _completion_url(self.settings["base_url"])
        headers = {"Content-Type": "application/json"}
        headers.update(self.settings["headers"])
        if self.settings["api_key"]:
            headers.setdefault("Authorization", f"Bearer {self.settings['api_key']}")
        return endpoint, headers

    def _body(self, image_b64: str, prompt: str, stream: bool) -> dict:
        body = {
            "model": self.settings["model"],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}",
                                "detail": "auto",
                            },
                        },
                    ],
                }
            ],
            "stream": stream,
            "temperature": self.settings["temperature"],
        }
        if self.settings["max_tokens"] is not None:
            body["max_tokens"] = self.settings["max_tokens"]
        body.update(self.settings["extra_body"])
        return body

    def stream(self, image_b64: str, prompt: str) -> Generator[dict, None, None]:
        endpoint, headers = self._endpoint_and_headers()
        stream = config.VISION_STREAM
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(self._body(image_b64, prompt, stream)).encode("utf-8"),
            headers=headers,
        )
        if not stream:
            with urllib.request.urlopen(request, timeout=self.settings["timeout"]) as response:
                payload = json.loads(response.read())
            content = _content_text(
                payload.get("choices", [{}])[0].get("message", {}).get("content")
            )
            if content:
                yield {"type": "content", "text": content}
            return

        with urllib.request.urlopen(request, timeout=self.settings["timeout"]) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                payload_text = line[5:].strip()
                if payload_text == "[DONE]":
                    break
                try:
                    payload = json.loads(payload_text)
                except json.JSONDecodeError:
                    continue
                delta = payload.get("choices", [{}])[0].get("delta", {})
                content = _content_text(delta.get("content"))
                if content:
                    yield {"type": "content", "text": content}


class CustomVisionAdapter:
    def __init__(self, adapter):
        self.adapter = adapter

    def stream(self, image_b64: str, prompt: str):
        method = getattr(self.adapter, "stream", None)
        if method:
            yield from method(image_b64, prompt)
            return
        method = getattr(self.adapter, "analyze", None)
        if method:
            result = method(image_b64, prompt)
            if isinstance(result, str):
                yield {"type": "content", "text": result}
            else:
                yield from result
            return
        raise TypeError(
            "Custom vision provider must implement stream(image_b64, prompt) "
            "or analyze(image_b64, prompt)"
        )


def _vision_adapter():
    settings = _settings("VISION")
    provider = settings["provider"]
    if provider == "custom":
        factory = _resolve_factory(settings["factory"])
        settings["stream"] = config.VISION_STREAM
        return CustomVisionAdapter(factory(settings))
    if provider == "ollama":
        return OllamaVisionAdapter(settings)
    if provider == "openai_compatible":
        return OpenAICompatibleVisionAdapter(settings)
    if provider == "disabled":
        raise RuntimeError("Vision provider is disabled")
    raise RuntimeError(f"Unsupported vision provider: {provider}")


def stream_vlm(image_b64: str, prompt: str):
    yield from _vision_adapter().stream(image_b64, prompt)


def call_vlm(image_b64: str, prompt: str) -> str:
    return "".join(
        piece["text"] for piece in stream_vlm(image_b64, prompt) if piece.get("type") == "content"
    )
