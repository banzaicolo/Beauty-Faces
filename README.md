# Beauty Faces

面部照片皮肤外观观察、结构化皮肤指标分析和护肤产品推荐。

> 仅提供一般护肤信息，不提供医疗诊断。

![Beauty Faces](docs/screenshots/home.png)

## 快速启动

```bash
cp .env.example .env
openssl rand -hex 24   # ADMIN_TOKEN
openssl rand -base64 48 # SESSION_SECRET
docker compose up --build
```

访问 `http://127.0.0.1:8000`。

## 模型配置

文本模型和视觉模型分别配置，支持：

- `ollama`
- `openai_compatible`
- `custom`
- `disabled`

### Ollama

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

### OpenAI-compatible API

```dotenv
TEXT_PROVIDER=openai_compatible
TEXT_MODEL=<your-text-model>
TEXT_BASE_URL=https://your-provider.example/v1
TEXT_API_KEY=<your-api-key>
TEXT_PRIVACY_MODE=external

VISION_PROVIDER=openai_compatible
VISION_MODEL=<your-vision-model>
VISION_BASE_URL=https://your-provider.example/v1
VISION_API_KEY=<your-api-key>
VISION_PRIVACY_MODE=external
```

如果文本模型不支持原生工具调用：

```dotenv
TEXT_TOOL_CALLING=false
```

超时、Token 上限、请求头、扩展请求体、流式设置和自定义 Provider 工厂见 [模型提供商配置](docs/MODEL_PROVIDERS.md)。

## 主要环境变量

| 变量 | 说明 |
|---|---|
| `ADMIN_TOKEN` | 管理口令，至少 16 个字符 |
| `SESSION_SECRET` | Cookie 签名密钥，至少 32 个字符 |
| `APP_PROFILE` | 场景目录，护肤默认 `skin_care` |
| `DATA_DIR` | 数据目录 |
| `SEED_DEMO` | `1` 时导入合成数据 |
| `TEXT_PROVIDER` | 文本模型协议 |
| `TEXT_MODEL` | 文本模型 ID |
| `TEXT_BASE_URL` | 文本模型地址 |
| `TEXT_API_KEY` | 文本 API 密钥 |
| `TEXT_TOOL_CALLING` | 是否启用原生工具调用 |
| `TEXT_PRIVACY_MODE` | `local`、`external` 或 `unknown` |
| `VISION_PROVIDER` | 视觉模型协议 |
| `VISION_MODEL` | 视觉模型 ID |
| `VISION_BASE_URL` | 视觉模型地址 |
| `VISION_API_KEY` | 视觉 API 密钥 |
| `VISION_PRIVACY_MODE` | `local`、`external` 或 `unknown` |
| `COOKIE_SECURE` | HTTPS 部署时设为 `true` |
| `APP_BIND` | Docker 监听地址 |

完整模板见 [.env.example](.env.example)。

## 本地启动

```bash
uv venv
uv pip install -r requirements-dev.txt
export ADMIN_TOKEN="$(openssl rand -hex 24)"
export SESSION_SECRET="$(openssl rand -base64 48)"
export TEXT_PROVIDER=openai_compatible
export TEXT_MODEL="<your-text-model>"
export TEXT_BASE_URL="https://your-provider.example/v1"
export TEXT_API_KEY="<your-api-key>"
export VISION_PROVIDER=openai_compatible
export VISION_MODEL="<your-vision-model>"
export VISION_BASE_URL="https://your-provider.example/v1"
export VISION_API_KEY="<your-api-key>"
export SEED_DEMO=1
python -m app.seed
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 场景数据

护肤场景位于 `app/profiles/skin_care/`。profile 包含客户字段、评分维度、权重、产品分类、知识库、提示词和合成样例。

`app/profiles/hair_care/` 是第二个领域配置示例。场景扩展方法见 [场景配置指南](docs/PROFILE_GUIDE.md)。

## 数据与安全

- 数据库和检查点写入 `DATA_DIR`，默认不入库。
- 每个 profile 使用独立数据库。
- 管理接口和 AI 报告接口要求登录。
- 匿名聊天不能读取客户档案。
- 模型地址、密钥和请求内容由部署者负责审查。
- 仓库不包含真实客户数据、训练数据集或第三方商品图片。

## 测试

```bash
ruff check app tests
APP_PROFILE=skin_care pytest
APP_PROFILE=hair_care pytest
```

## 许可证

[MIT](LICENSE)
