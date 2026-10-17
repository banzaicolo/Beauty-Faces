# 模型提供商配置

## Provider 类型

| 值 | 接口 |
|---|---|
| `ollama` | Ollama `/api/chat` |
| `openai_compatible` | OpenAI Chat Completions |
| `custom` | Python 工厂 |
| `disabled` | 关闭对应能力 |

`openai_compatible` 可用于 OpenAI、OpenRouter、DeepSeek、vLLM、LM Studio、LocalAI 和其他兼容接口。

## Ollama

```dotenv
TEXT_PROVIDER=ollama
TEXT_MODEL=<text-model>
TEXT_BASE_URL=http://host.docker.internal:11434
TEXT_PRIVACY_MODE=local

VISION_PROVIDER=ollama
VISION_MODEL=<vision-model>
VISION_BASE_URL=http://host.docker.internal:11434
VISION_PRIVACY_MODE=local
```

模型需提前存在于 Ollama。自动查商品和知识库需要文本模型支持工具调用；否则设置：

```dotenv
TEXT_TOOL_CALLING=false
```

## OpenAI-compatible

```dotenv
TEXT_PROVIDER=openai_compatible
TEXT_MODEL=<text-model>
TEXT_BASE_URL=https://provider.example/v1
TEXT_API_KEY=<api-key>
TEXT_PRIVACY_MODE=external

VISION_PROVIDER=openai_compatible
VISION_MODEL=<vision-model>
VISION_BASE_URL=https://provider.example/v1
VISION_API_KEY=<api-key>
VISION_PRIVACY_MODE=external
```

`*_BASE_URL` 填 API 根路径，程序追加 `/chat/completions`。完整视觉端点可直接指定：

```dotenv
VISION_ENDPOINT=https://provider.example/custom/chat/completions
```

## 请求参数

```dotenv
TEXT_TEMPERATURE=0.6
TEXT_MAX_TOKENS=
TEXT_TIMEOUT_SECONDS=180
TEXT_HEADERS_JSON={"X-Custom-Header":"value"}
TEXT_EXTRA_BODY_JSON={"top_p":0.9}

VISION_TEMPERATURE=0.3
VISION_MAX_TOKENS=
VISION_TIMEOUT_SECONDS=300
VISION_STREAM=true
VISION_HEADERS_JSON={"HTTP-Referer":"https://your-site.example"}
VISION_EXTRA_BODY_JSON={"max_completion_tokens":2048}
```

`*_EXTRA_BODY_JSON` 会合并到请求体，可传提供商私有参数。

## 自定义文本 Provider

```dotenv
TEXT_PROVIDER=custom
TEXT_PROVIDER_FACTORY=my_package.providers:create_chat_model
TEXT_TOOL_CALLING=true
```

工厂接收 settings 字典，返回 LangChain ChatModel：

```python
def create_chat_model(settings):
    return MyChatModel(
        model=settings["model"],
        api_key=settings["api_key"],
    )
```

可用设置包括 `provider`、`model`、`base_url`、`api_key`、`headers`、`extra_body`、`timeout`、`privacy` 和 `tool_calling`。

## 自定义视觉 Provider

```dotenv
VISION_PROVIDER=custom
VISION_PROVIDER_FACTORY=my_package.providers:create_vision_adapter
```

工厂返回对象，实现 `stream(image_b64, prompt)` 或 `analyze(image_b64, prompt)`：

```python
def stream(image_b64, prompt):
    yield {"type": "content", "text": "partial result"}
```

```python
def analyze(image_b64, prompt):
    return "complete result"
```

自定义包需安装到运行环境。自定义工厂会执行 Python 代码，只加载可信模块。

## 隐私标记

- `local`：本机或内网模型
- `external`：第三方 API
- `unknown`：未确认

该标记只用于界面显示，不会改变实际网络路径。
