import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
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
    with TestClient(app) as client:
        response = client.post("/api/ai-report", json={"customer_id": "sample-001"})
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
                "skin_type",
                "ingredients",
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
        payload = {
            "name": "合成测试客户",
            "age": "30",
            "items": {"水分": 35, "油脂": 42},
            "advice": ["这是一条测试建议"],
        }
        created = client.post("/api/customers", json=payload)
        assert created.status_code == 200
        assert created.json()["items"] == payload["items"]
        assert created.json()["advice"] == payload["advice"]


def test_session_and_security_headers():
    with TestClient(app) as client:
        response = client.get("/api/session")
        assert response.status_code == 200
        assert "bf_session" in client.cookies
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["cache-control"] == "no-store"


def test_public_fixtures_are_synthetic():
    root = Path(__file__).resolve().parents[1]
    customers = json.loads((root / "app/configs/customers.sample.json").read_text(encoding="utf-8"))
    products = json.loads((root / "app/configs/products_seed.json").read_text(encoding="utf-8"))
    assert customers
    assert all(item["id"].startswith("sample-") for item in customers)
    assert all(not item.get("avatar") for item in customers)
    assert all(item["image"] == "/product-placeholder.svg" for item in products)


def test_static_frontend_and_placeholder_render():
    with TestClient(app) as client:
        page = client.get("/")
        placeholder = client.get("/product-placeholder.svg")
        assert page.status_code == 200
        assert "Beauty Faces" in page.text
        assert placeholder.status_code == 200
        assert placeholder.headers["content-type"].startswith("image/svg+xml")


def test_original_private_assets_are_not_in_public_release():
    root = Path(__file__).resolve().parents[1]
    forbidden = [
        "archive",
        "客户数据_伊斯佳",
        "demo/data.js",
        "app/configs/customers_seed.json",
        "data/app.db",
        "data/checkpoints.db",
    ]
    assert all(not (root / item).exists() for item in forbidden)


def test_runtime_config_fails_closed(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_TOKEN", "")
    with pytest.raises(RuntimeError, match="ADMIN_TOKEN"):
        config.validate_runtime_config()
