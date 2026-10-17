from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app import config, llm, rules
from app.main import app


def login(client: TestClient) -> None:
    response = client.post("/api/login", json={"password": config.ADMIN_TOKEN})
    assert response.status_code == 200


def test_admin_routes_use_http_only_cookie():
    with TestClient(app) as client:
        assert client.get("/api/customers").status_code == 401
        login_response = client.post("/api/login", json={"password": config.ADMIN_TOKEN})
        cookie = login_response.headers["set-cookie"].lower()
        assert "httponly" in cookie
        assert "samesite=strict" in cookie
        assert client.get("/api/customers").status_code == 200


def test_customer_report_is_admin_only():
    customer_id = config.PROFILE.read_json("customers.sample.json")[0]["id"]
    with TestClient(app) as client:
        response = client.post("/api/ai-report", json={"customer_id": customer_id})
        assert response.status_code == 401


def test_product_edit_preserves_existing_image():
    with TestClient(app) as client:
        login(client)
        products = client.get("/api/products").json()
        product = next(item for item in products if item.get("image"))
        body = {
            key: product.get(key, "")
            for key in (
                "brand",
                "name",
                "category",
                "target",
                "features",
                "price",
                "description",
            )
        }
        response = client.put(f"/api/products/{product['id']}", json=body)
        assert response.status_code == 200
        assert response.json()["image"] == product["image"]


def test_structured_customer_items_round_trip():
    with TestClient(app) as client:
        login(client)
        dimension = config.PUBLIC_PROFILE["dimensions"][0]
        item_key = dimension["items"][0]["key"]
        filter_field = next(
            field for field in config.PUBLIC_PROFILE["customer_fields"] if field["filterable"]
        )
        payload = {
            "name": "合成测试客户",
            "age": "30",
            "items": {item_key: 35},
            "attributes": {filter_field["key"]: filter_field.get("options", ["测试"])[0]},
            "advice": ["这是一条测试建议"],
        }
        created = client.post("/api/customers", json=payload)
        assert created.status_code == 200
        assert created.json()["items"] == payload["items"]
        assert created.json()["attributes"] == payload["attributes"]
        assert created.json()["advice"] == payload["advice"]


def test_session_and_security_headers():
    with TestClient(app) as client:
        response = client.get("/api/session")
        assert response.status_code == 200
        assert "bf_session" in client.cookies
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["cache-control"] == "no-store"


def test_public_fixtures_are_synthetic():
    customers = config.PROFILE.read_json("customers.sample.json")
    products = config.PROFILE.read_json("products.sample.json")
    assert customers
    assert all("-sample-" in item["id"] for item in customers)
    assert all(not item.get("avatar") for item in customers)
    assert all(item["image"] == "/product-placeholder.svg" for item in products)


def test_static_frontend_and_placeholder_render():
    with TestClient(app) as client:
        page = client.get("/")
        placeholder = client.get("/product-placeholder.svg")
        assert page.status_code == 200
        assert config.PUBLIC_PROFILE["branding"]["name"]
        assert placeholder.status_code == 200
        assert placeholder.headers["content-type"].startswith("image/svg+xml")


def test_original_private_assets_are_not_in_public_release():
    root = Path(__file__).resolve().parents[1]
    forbidden = [
        "archive",
        "客户数据_伊斯佳",
        "demo/data.js",
        "app/configs",
        "app/configs/customers_seed.json",
        "data/app.db",
        "data/checkpoints.db",
    ]
    assert all(not (root / item).exists() for item in forbidden)


def test_runtime_config_fails_closed(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_TOKEN", "")
    with pytest.raises(RuntimeError, match="ADMIN_TOKEN"):
        config.validate_runtime_config()


def test_runtime_config_requires_a_model(monkeypatch):
    monkeypatch.setattr(config, "TEXT_MODEL", "")
    with pytest.raises(RuntimeError, match="TEXT_MODEL"):
        config.validate_runtime_config()


def test_chat_thread_is_scoped_to_signed_session(monkeypatch):
    class Chunk:
        content = "ok"

    thread_ids = []

    class FakeAgent:
        def stream(self, _messages, config, stream_mode):
            thread_ids.append(config["configurable"]["thread_id"])
            yield Chunk(), {"langgraph_node": "agent"}

    monkeypatch.setattr(main_module, "get_agent", lambda: FakeAgent())
    conversation_id = "2a3f3f56-9dbf-4eb1-b3d4-fc1b04f990de"
    payload = {"thread_id": conversation_id, "message": "你好"}

    with TestClient(app) as first:
        first.get("/api/session")
        assert first.post("/api/chat", json=payload).status_code == 200
    with TestClient(app) as second:
        second.get("/api/session")
        assert second.post("/api/chat", json=payload).status_code == 200

    assert len(thread_ids) == 2
    assert thread_ids[0] != thread_ids[1]
    assert all(thread_id.endswith(conversation_id) for thread_id in thread_ids)


def test_profile_meta_drives_dimensions_and_categories():
    with TestClient(app) as client:
        meta = client.get("/api/meta")
        assert meta.status_code == 200
        payload = meta.json()
        assert payload["id"] == config.PROFILE.id
        assert payload["dimensions"]
        assert payload["categories"] == [
            dimension["category"] for dimension in payload["dimensions"]
        ]
        assert payload["filter_key"] in {field["key"] for field in payload["customer_fields"]}


def test_recommendation_respects_profile_limits():
    customer = config.PROFILE.read_json("customers.sample.json")[0]
    recommendations = rules.recommend(customer["items"])
    settings = config.PUBLIC_PROFILE["recommendation"]
    assert len(recommendations) <= settings["top_dimensions"]
    assert all(
        len(recommendation["products"]) <= settings["products_per_dimension"]
        for recommendation in recommendations
    )
    assert all(recommendation["products"] for recommendation in recommendations)


def test_openai_compatible_text_provider_uses_deployment_settings(monkeypatch):
    monkeypatch.setattr(config, "TEXT_PROVIDER", "openai_compatible")
    monkeypatch.setattr(config, "TEXT_MODEL", "customer-selected-model")
    monkeypatch.setattr(config, "TEXT_BASE_URL", "https://models.example/v1")
    monkeypatch.setattr(config, "TEXT_API_KEY", "test-key")
    monkeypatch.setattr(config, "TEXT_TIMEOUT_SECONDS", 42)
    model = llm.get_chat_model()
    assert model.model_name == "customer-selected-model"
    assert str(model.openai_api_base).rstrip("/") == "https://models.example/v1"
