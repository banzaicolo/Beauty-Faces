# Beauty Faces

面向门店演示场景的本地优先 AI 护肤内容助手。项目把多模态模型、规则化推荐、商品/成分检索、LangGraph 工具调用和客户管理界面组合成一个可运行的 MVP。

> 本项目用于护肤内容展示与工程演示，不是医疗器械，不提供疾病诊断，也不能替代皮肤科医生。项目不包含真实客户数据、训练数据集或第三方商品图片。

![Beauty Faces 首页](docs/screenshots/home.png)

## 功能

- 本地 Ollama 文本模型与视觉模型，支持 DeepSeek 作为可选文本模型
- LangGraph 多轮对话、工具调用与 SQLite 会话记忆
- 规则引擎按检测分数计算重点维度并匹配商品
- 合成商品库、成分库和 4 份完全虚构的客户样例
- 拍照外观观察、客户档案、商品库管理
- 管理端使用签名 HttpOnly Cookie，不再把口令保存在浏览器存储中
- 匿名聊天按签名会话隔离，不能跨会话读取检查点
- 请求体大小限制、基础速率限制、安全响应头
- 本地默认绑定 `127.0.0.1`，Docker 使用非 root 用户

## 快速启动

### 1. 准备模型

先安装 [Ollama](https://ollama.com/)，然后拉取默认模型：

```bash
ollama pull qwen3.5:4b
ollama pull qwen3-vl:8b
```

模型标签可能随时间变化。如标签不可用，请修改 `.env` 中的 `LLM_MODEL` 和 `VLM_MODEL`。

### 2. 配置密钥

```bash
cp .env.example .env
```

将 `.env` 中的两个占位值替换为随机值：

```bash
openssl rand -hex 24
openssl rand -base64 48
```

`ADMIN_TOKEN` 少于 16 个字符或 `SESSION_SECRET` 少于 32 个字符时，应用会拒绝启动。

### 3. Docker 启动

```bash
docker compose up --build
```

打开 <http://127.0.0.1:8000>。

Docker 使用命名卷 `beauty-faces-data` 保存 SQLite 数据库，不会把运行数据写进 Git 工作区。需要连接宿主机 Ollama 时，默认地址是 `http://host.docker.internal:11434`。

### 4. 本地 Python 启动

```bash
uv venv
uv pip install -r requirements-dev.txt
export ADMIN_TOKEN="$(openssl rand -hex 24)"
export SESSION_SECRET="$(openssl rand -base64 48)"
export SEED_DEMO=1
export DATA_DIR="./data"
python -m app.seed
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 配置

| 变量 | 必填 | 默认值 | 说明 |
|---|---:|---|---|
| `ADMIN_TOKEN` | 是 | 无 | 门店管理口令，至少 16 个字符 |
| `SESSION_SECRET` | 是 | 无 | Cookie 签名密钥，至少 32 个字符 |
| `DATA_DIR` | 否 | `./data` | 数据库与检查点目录 |
| `SEED_DEMO` | 否 | `0` | 为 `1` 时导入合成客户样例 |
| `OLLAMA_URL` | 否 | `http://localhost:11434` | Ollama 地址；容器中通常为宿主机地址 |
| `LLM_MODEL` | 否 | `qwen3.5:4b` | 文本与工具调用模型 |
| `VLM_MODEL` | 否 | `qwen3-vl:8b` | 图片观察模型 |
| `DEEPSEEK_API_KEY` | 否 | 空 | 设置后，文本请求改走外部 DeepSeek |
| `COOKIE_SECURE` | 否 | `false` | HTTPS 部署时设为 `true` |
| `APP_BIND` | 否 | `127.0.0.1` | Docker 映射地址 |

`OLLAMA_URL` 指向远程主机时，图片和文本同样会离开本机。只有确认服务受信任后，界面上的“本地模型模式”才有实际意义。

## 数据与仓库隔离

公开版本采用“代码 + 合成样例”的发布边界：

- 不包含原项目中的 `客户数据_伊斯佳/`、`app/configs/customers_seed.json`、`demo/data.js`、SQLite 数据库和 LangGraph 检查点。
- 不包含 `archive/` 中的研究数据与 3.8 GB 图像，也不包含 `data/products/` 中的品牌商品图。
- 不包含 `.workbuddy/`、`.DS_Store`、日志和本地密钥。
- 客户样例已替换为 4 份完全虚构的数据，ID 使用 `sample-*`，头像字段为空。
- 商品库已替换为 15 个虚构商品，图片统一使用仓库内生成的 [通用占位图](app/static/product-placeholder.svg)。
- `data/` 中只保留 `.gitkeep`；数据库、WAL、检查点、私有客户资料和第三方图片均被 `.gitignore` 排除。

如果要在本地保存真实数据，请继续使用不进入 Git 的 `data/app.db` 或独立的 `private/` 目录，并在部署层面做好备份、访问控制和删除策略。

## 安全设计

- 管理口令和会话密钥缺失或过短时直接拒绝启动，不再提供公开默认口令。
- 管理登录成功后只下发签名 HttpOnly Cookie，不在 `localStorage` 保存口令。
- `/api/customers*`、`/api/products*` 和 `/api/ai-report` 均要求管理会话。
- 匿名智能体不再挂载客户档案查询工具。
- 匿名聊天的检查点 ID 使用“匿名会话作用域 + 客户端 UUID”，不能仅靠猜另一个 UUID 读取其他会话。
- 图片请求默认上限 16 MB，聊天消息默认上限 4,000 字符。
- AI 接口带有单进程滑动窗口限流，仅适合单节点演示。生产环境应换用网关、Redis 或共享限流组件。
- 所有 API 响应禁止缓存，并附带 CSP、`nosniff`、`DENY` 和权限策略响应头。
- 视觉接口不向浏览器转发模型的内部思考文本，只显示通用处理状态和最终内容。

## 本次发布改造记录

以下改动针对公开 GitHub 发布，原始 Beauty-Faces 工作目录保持不变：

1. 新建独立发布副本，避免真实客户资料、数据库、检查点和研究素材进入首次 Git 提交。
2. 删除公开默认管理口令，加入启动时的安全配置校验。
3. 用签名 HttpOnly Cookie 替换 `localStorage` 管理口令。
4. 为 AI 报告接口增加管理权限，移除匿名智能体读取客户档案的能力。
5. 为匿名聊天加入签名会话作用域，客户端会话 ID 改为随机 UUID。
6. 修复编辑商品时图片被空字符串覆盖的问题。
7. 修复结构化客户检测项无法通过 API 保存的问题，并新增客户删除接口。
8. 增强 HTML 转义，补充请求大小限制、基础限流、安全头和无缓存策略。
9. 将真实客户种子替换为合成样例，将品牌商品图和商品种子替换为通用虚构数据。
10. 增加 `.gitignore`、`.dockerignore`、环境变量模板、直接依赖固定与 `uv.lock`、MIT 许可证和医疗免责声明。
11. 增加认证、权限、会话、商品图片、客户数据和合成数据测试，以及 GitHub Actions CI。
12. Docker 默认使用官方 PyPI、非 root 用户、健康检查和本地回环端口映射。

## 项目结构

```text
app/
  agent.py             LangGraph 智能体
  auth.py              签名 Cookie 与会话校验
  config.py            环境配置
  db.py                SQLite 数据访问
  main.py              FastAPI 入口和 API
  middleware.py        请求大小与安全响应头
  rate_limit.py        单进程限流
  static/              Web 前端与通用商品占位图
  configs/             合成样例、维度、成分和提示词
tests/                 API 与发布边界测试
.github/workflows/     CI
```

## 测试

```bash
pip install -r requirements-dev.txt
ruff check app tests
pytest
```

测试使用临时数据目录和合成数据，不会读取原始客户文件。

## 已知限制

- 这是单门店、单节点演示，不是多租户 SaaS。
- 管理端仍使用共享口令，没有个人账号、审计日志和细粒度角色。
- 匿名 Cookie 和检查点不会自动到期删除，生产环境需要配置数据保留策略。
- SQLite 适合单实例演示；多实例部署需要外部数据库和共享会话存储。
- 视觉模型输出不可作为医学判断，也没有临床验证结论。
- 当前登录 Cookie、限流和安全机制应配合 HTTPS 反向代理使用。

## 许可证

代码使用 [MIT License](LICENSE)。仓库中不包含原项目的真实客户数据、研究数据集或品牌商品图片；如另行下载第三方数据集，请遵守各自许可证。
