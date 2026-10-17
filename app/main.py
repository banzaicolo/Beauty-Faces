"""FastAPI entry point for a profile-driven consultation assistant."""

import hashlib
import json
import logging
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from . import auth, config, db, llm, rate_limit, rules
from .agent import get_agent
from .middleware import RequestSizeLimitMiddleware, SecurityHeadersMiddleware

logger = logging.getLogger(__name__)

FRIENDLY_ERR = "AI 服务暂时不可用，请稍后重试"
RECORD_LABEL = config.PUBLIC_PROFILE["copy"]["customer_nav"]
PRODUCT_LABEL = config.PUBLIC_PROFILE["copy"]["product_nav"]


@asynccontextmanager
async def lifespan(_app):
    config.validate_runtime_config()
    db.init_db()
    yield


app = FastAPI(
    title=config.PUBLIC_PROFILE["branding"]["name"],
    description=config.PUBLIC_PROFILE["branding"].get(
        "tagline", "Profile-driven consultation assistant"
    ),
    lifespan=lifespan,
)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


class ChatRequest(BaseModel):
    thread_id: str = Field(min_length=36, max_length=36)
    message: str = Field(min_length=1, max_length=config.MAX_CHAT_CHARS)


class ReportRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=128)


class ImageRequest(BaseModel):
    image: str = Field(
        min_length=1,
        max_length=config.MAX_IMAGE_B64_CHARS,
        description="Base64 encoded image or a data URL",
    )


class CustomerBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    age: str = Field(default="", max_length=8)
    sex: str = Field(default="女", max_length=12)
    analysis: str = Field(default="", max_length=4000)
    items: dict[str, float | None] = Field(default_factory=dict)
    attributes: dict[str, str | float | int | None] = Field(default_factory=dict)
    advice: list[str] = Field(default_factory=list, max_length=10)
    score: str = Field(default="", max_length=20)
    avatar: str = Field(default="", max_length=500)


class LoginBody(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class ProductBody(BaseModel):
    brand: str = Field(default="", max_length=100)
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(default="", max_length=40)
    target: str = Field(default="", max_length=120)
    features: str = Field(default="", max_length=1000)
    price: str = Field(default="", max_length=40)
    description: str = Field(default="", max_length=2000)
    image: str = Field(default="/product-placeholder.svg", max_length=500)
    attributes: dict[str, str | float | int | None] = Field(default_factory=dict)


class ProductUpdateBody(ProductBody):
    image: str | None = Field(default=None, max_length=500)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "provider": llm.provider_name(),
        "privacy": llm.privacy_mode(),
        "llm": config.LLM_MODEL,
        "vlm": config.VLM_MODEL,
        "profile": config.PUBLIC_PROFILE["id"],
        "customers": db.customer_count(),
        "products": len(db.list_products()),
        "knowledge": db.knowledge_count(),
    }


@app.get("/api/session")
def create_session(request: Request, response: Response):
    if not auth.anonymous_session(request):
        auth.create_anonymous_session(response)
    return {"ok": True}


@app.post("/api/login")
def login(body: LoginBody, request: Request, response: Response):
    rate_limit.enforce("login", request)
    if auth.check_admin_password(body.password):
        auth.create_admin_session(response)
        return {"ok": True}
    raise HTTPException(401, "口令错误")


@app.get("/api/admin/session", dependencies=[Depends(auth.require_admin)])
def admin_session():
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response):
    auth.clear_sessions(response)
    return {"ok": True}


@app.get("/api/customers", dependencies=[Depends(auth.require_admin)])
def customers(keyword: str = "", segment: str = ""):
    return db.list_customers(keyword=keyword, segment=segment)


@app.get("/api/customers/{cid}", dependencies=[Depends(auth.require_admin)])
def customer(cid: str):
    result = db.get_customer(cid)
    if not result:
        raise HTTPException(404, f"{RECORD_LABEL}不存在")
    return result


@app.post("/api/customers", dependencies=[Depends(auth.require_admin)])
def create_customer(body: CustomerBody):
    cid = db.add_customer(body.model_dump())
    return db.get_customer(cid)


@app.delete("/api/customers/{cid}", dependencies=[Depends(auth.require_admin)])
def remove_customer(cid: str):
    if not db.get_customer(cid):
        raise HTTPException(404, f"{RECORD_LABEL}不存在")
    db.delete_customer(cid)
    return {"ok": True}


@app.get("/api/products", dependencies=[Depends(auth.require_admin)])
def products(category: str = "", keyword: str = ""):
    return db.list_products(category=category, keyword=keyword)


@app.post("/api/products", dependencies=[Depends(auth.require_admin)])
def create_product(body: ProductBody):
    return db.add_product(body.model_dump())


@app.put("/api/products/{pid}", dependencies=[Depends(auth.require_admin)])
def edit_product(pid: int, body: ProductUpdateBody):
    if not db.get_product(pid):
        raise HTTPException(404, f"{PRODUCT_LABEL}不存在")
    return db.update_product(pid, body.model_dump(exclude_unset=True))


@app.delete("/api/products/{pid}", dependencies=[Depends(auth.require_admin)])
def remove_product(pid: int):
    if not db.get_product(pid):
        raise HTTPException(404, f"{PRODUCT_LABEL}不存在")
    db.delete_product(pid)
    return {"ok": True}


@app.get("/api/knowledge")
def knowledge(keyword: str = ""):
    return db.search_knowledge(keyword=keyword)


@app.get("/api/ingredients", include_in_schema=False)
def ingredients_compat(keyword: str = ""):
    """Backward-compatible alias for the former domain-specific knowledge route."""
    return db.search_knowledge(keyword=keyword)


@app.get("/api/meta")
def meta():
    return config.PUBLIC_PROFILE


@app.post("/api/recommend")
def recommend_api(body: dict):
    return rules.recommend(body.get("items", {}))


@app.post("/api/ai-report", dependencies=[Depends(auth.require_admin)])
def ai_report(req: ReportRequest, request: Request):
    rate_limit.enforce("ai-report", request)
    result = db.get_customer(req.customer_id)
    if not result:
        raise HTTPException(404, f"{RECORD_LABEL}不存在")
    prompt, weak_dims = rules.build_report_prompt(result)
    try:
        model = llm.get_chat_model()
        response = model.invoke([HumanMessage(content=prompt)])
        report = response.content
    except Exception:
        logger.exception("AI report generation failed")
        raise HTTPException(500, FRIENDLY_ERR) from None
    return {
        "report": report,
        "provider": llm.provider_name(),
        "weak_dims": [
            {
                "id": item["id"],
                "cat": item["cat"],
                "label": item["label"],
                "score": item["score"],
            }
            for item in weak_dims
        ],
        "alerts": rules.active_alerts(result.get("items", {})),
    }


@app.post("/api/vlm-analyze")
def vlm_analyze(req: ImageRequest, request: Request):
    rate_limit.enforce("vlm", request)
    if not config.PUBLIC_PROFILE["assessment"]["enabled"]:
        raise HTTPException(404, "This profile does not enable visual assessment")
    image = req.image
    if image.strip().startswith("data:"):
        try:
            image = image.split(",", 1)[1]
        except IndexError:
            raise HTTPException(400, "图片数据格式有误") from None

    def generate():
        emitted = False
        status = {"type": "thinking", "text": "正在调用本地视觉模型…\n"}
        yield f"data: {json.dumps(status, ensure_ascii=False)}\n\n"
        for attempt in range(2):
            try:
                prompt = config.load_text(config.PUBLIC_PROFILE["assessment"]["prompt_file"])
                for piece in llm.stream_vlm(image, prompt):
                    if piece.get("type") != "content":
                        continue
                    emitted = True
                    yield f"data: {json.dumps(piece, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return
            except Exception:
                logger.exception("VLM request failed on attempt %s", attempt + 1)
                if emitted or attempt == 1:
                    break
        yield f"data: {json.dumps({'error': FRIENDLY_ERR}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/chat")
def chat(req: ChatRequest, request: Request, response: Response):
    rate_limit.enforce("chat", request)
    try:
        conversation_id = str(UUID(req.thread_id))
    except ValueError:
        raise HTTPException(400, "thread_id 必须是 UUID") from None

    session = auth.anonymous_session(request)
    if not session:
        session = auth.create_anonymous_session(response)
    scope = hashlib.sha256(session.encode("utf-8")).hexdigest()[:24]
    checkpoint_thread_id = f"{scope}:{conversation_id}"

    agent = get_agent()
    run_config = {"configurable": {"thread_id": checkpoint_thread_id}}

    def generate():
        try:
            for msg_chunk, metadata in agent.stream(
                {"messages": [HumanMessage(content=req.message)]},
                config=run_config,
                stream_mode="messages",
            ):
                if metadata.get("langgraph_node") == "tools":
                    continue
                content = getattr(msg_chunk, "content", "")
                if content:
                    yield f"data: {json.dumps({'token': content}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception:
            logger.exception("Chat request failed")
            yield f"data: {json.dumps({'error': FRIENDLY_ERR}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


static_dir = config.BASE_DIR / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
