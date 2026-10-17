"""Pluggable language-model access for Ollama and DeepSeek."""

import json
import urllib.request

from . import config


def get_chat_model():
    """返回 langchain ChatModel：有 DeepSeek key 走联网，否则走本地 ollama"""
    if config.DEEPSEEK_API_KEY:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=config.DEEPSEEK_MODEL,
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
            temperature=0.6,
        )
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=config.LLM_MODEL,
        base_url=config.OLLAMA_BASE_URL,
        temperature=0.6,
        num_predict=2048,
        reasoning=False,  # 关闭思考模式：qwen3.5 默认思考会吃光输出额度导致正文为空，且慢
    )


def provider_name():
    return "deepseek" if config.DEEPSEEK_API_KEY else f"ollama:{config.LLM_MODEL}"


def privacy_mode():
    if config.DEEPSEEK_API_KEY:
        return "external_llm"
    return "local_llm"


def call_vlm(image_b64: str, prompt: str) -> str:
    """看图分析：直接调 ollama chat 多模态接口（qwen3-vl 等），返回文本"""
    body = {
        "model": config.VLM_MODEL,
        "messages": [{"role": "user", "content": prompt, "images": [image_b64]}],
        "stream": False,
        # qwen3-vl 默认是思考版：思考+正文共用 num_predict 额度，额度必须给足否则正文被截断
        "options": {"temperature": 0.3, "num_predict": 4096},
    }
    url = config.OLLAMA_BASE_URL.rstrip("/") + "/api/chat"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["message"]["content"]


def stream_vlm(image_b64: str, prompt: str):
    """看图分析（流式）：逐段 yield {"type": "thinking"|"content", "text": ...}
    thinking = 模型思考过程（前端灰字实时显示，让用户知道没卡住）
    content  = 正式分析结果"""
    body = {
        "model": config.VLM_MODEL,
        "messages": [{"role": "user", "content": prompt, "images": [image_b64]}],
        "stream": True,
        "options": {"temperature": 0.3, "num_predict": 4096},
    }
    url = config.OLLAMA_BASE_URL.rstrip("/") + "/api/chat"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        for line in r:
            line = line.strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except Exception:
                continue
            msg = chunk.get("message", {})
            thinking = msg.get("thinking")
            if thinking:
                yield {"type": "thinking", "text": thinking}
            content = msg.get("content")
            if content:
                yield {"type": "content", "text": content}
            if chunk.get("done"):
                break
