# 模型提供商配置

Beauty Faces 不捆绑或强制任何模型。文本模型和视觉模型分别配置，可以使用不同的提供商、地址、密钥、模型 ID 和请求参数。

## 支持的接入协议

| Provider | 用途 | 适用情况 |
|---|---|---|
| `ollama` | 文本 + 视觉 | 本机或内网 Ollama |
| `openai_compatible` | 文本 + 视觉 | 任何兼容 Chat Completions 的在线或自托管服务 |
| `custom` | 文本 + 视觉 | 需要自定义 SDK、签名、私有协议或企业网关 |
| `disabled` | 文本 + 视觉 | 临时关闭对应能力 |

`openai_compatible` 不绑定某个品牌。OpenAI、OpenRouter、DeepSeek、vLLM、LM Studio、LocalAI、企业模型网关等，只要接口协议兼容即可。

## Ollama

```dotenv
TEXT_PROVIDER=ollama
TEXT_MODEL=<your-text-model>
TEXT_BASE_URL=http://host.docker.internal:11434
TEXT_PRIVACY_MODE=local

VISION_PROVIDER=ollama
VISION_MODEL=<your-vision-model>
VISION_BASE_URL=http://host.docker.internal:11434
VISION_PRIVACY_MODE=local
```

模型必须提前存在于 Ollama。文本模型如用于自动查商品和知识库，需要支持原生工具调用；不支持时设置：

```dotenv
TEXT_TOOL_CALLING=false
```

关闭后仍可进行普通多轮对话，但不会自动调用商品数据库。

## OpenAI-compatible

```dotenv
TEXT_PROVIDER=openai_compatible
TEXT_MODEL=<provider-model-id>
TEXT_BASE_URL=https://your-provider.example/v1
TEXT_API_KEY=<your-api-key>
TEXT_PRIVACY_MODE=external

VISION_PROVIDER=openai_compatible
VISION_MODEL=<provider-vision-model-id>
VISION_BASE_URL=https://your-provider.example/v1
VISION_API_KEY=<your-api-key>
VISION_PRIVACY_MODE=external
```

`*_BASE_URL` 应指向 API 根路径，程序会追加 `/chat/completions`。如果提供商要求完整地址，可以覆盖：

```dotenv
VISION_ENDPOINT=https://your-provider.example/custom/chat/completions
```

有些提供商使用不同的图片字段、`max_completion_tokens`、reasoning 参数或额外请求体，可通过以下配置适配：

```dotenv
VISION_MAX_TOKENS=
VISION_EXTRA_BODY_JSON={"max_completion_tokens":2048,"reasoning":{"effort":"low"}}
TEXT_EXTRA_BODY_JSON={"top_p":0.9}
TEXT_HEADERS_JSON={"X-Custom-Header":"value"}
VISION_HEADERS_JSON={"HTTP-Referer":"https://your-site.example"}
```

请求体 JSON 会合并到基础请求中，因此可以使用提供商自己的扩展字段。不要在 JSON、Git 或日志中写入真实密钥。

## 自定义文本 Provider

```dotenv
TEXT_PROVIDER=custom
TEXT_PROVIDER_FACTORY=my_package.providers:create_chat_model
TEXT_TOOL_CALLING=true
TEXT_PRIVACY_MODE=external
```

Factory 必须可调用，接收一个设置字典并返回 LangChain ChatModel：

```python
def create_chat_model(settings):
    from langchain_core.language_models.chat_models import BaseChatModel

    # settings includes provider, model, base_url, api_key, headers,
    # extra_body, timeout, privacy, and tool_calling.
    return MyChatModel(...)
```

自定义包需要随部署环境安装。Docker 用户可以在自己的镜像中增加安装步骤，或把模块挂载到 Python 路径。

## 自定义视觉 Provider

```dotenv
VISION_PROVIDER=custom
VISION_PROVIDER_FACTORY=my_package.providers:create_vision_adapter
VISION_PRIVACY_MODE=external
```

Factory 返回一个对象，实现以下任一接口：

```python
def stream(image_b64, prompt):
    yield {"type": "content", "text": "partial text"}
```

或者：

```python
def analyze(image_b64, prompt):
    return "complete text"
```

正式内容使用 `type=content`。内部思考文本不应返回，避免把模型的推理过程暴露给浏览器。

## 隐私标记

程序不会根据 URL 猜测数据是否出域。部署者必须明确设置：

- `local`：模型运行在受信任的本机或内网
- `external`：请求会发送到第三方
- `unknown`：尚未确认

界面会显示该标记。标记为 `local` 不代表自动完成安全审计，仍需检查实际网络地址、代理和日志系统。
