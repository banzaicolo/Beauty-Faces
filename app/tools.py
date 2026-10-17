"""Profile-agnostic read-only tools for the consultation agent."""

import json

from langchain_core.tools import tool

from . import config, db, rules


@tool
def search_products(category: str = "", keyword: str = "") -> str:
    """Search the active product catalog by category or free-text keyword."""
    rows = db.list_products(category=category, keyword=keyword)
    if not rows:
        return "No matching products found."
    copy = config.PUBLIC_PROFILE["copy"]
    lines = []
    for product in rows:
        lines.append(
            f"[{product['id']}] {product['brand']} {product['name']} "
            f"({product['category']} | {copy['product_target_label']}: "
            f"{product['target']} | {product['price']}) "
            f"{copy['product_features_label']}: {product['features']} "
            f"Description: {product['description']}"
        )
    return "\n".join(lines)


@tool
def get_knowledge_info(name: str) -> str:
    """Look up a knowledge entry, ingredient, or feature in the active profile."""
    row = db.get_knowledge(name.strip())
    if not row:
        return f"Knowledge entry not found: {name}"
    caution = f" Caution: {row['caution']}" if row.get("caution") else ""
    return f"{row['name']}: {row['summary']}.{caution}".strip()


@tool
def recommend_products(measurements_json: str) -> str:
    """Rank profile dimensions and recommend matching products from measurement JSON."""
    try:
        items = json.loads(measurements_json)
        items = {key: float(value) if value is not None else None for key, value in items.items()}
    except (TypeError, ValueError, json.JSONDecodeError):
        return "Invalid measurement data. Pass a JSON object."

    recommendations = rules.recommend(items)
    if not recommendations:
        return "No recommendations available."
    lines = []
    for recommendation in recommendations:
        products = " ; ".join(
            f"{product['brand']} {product['name']} ({product['features']}, {product['price']})"
            for product in recommendation["products"]
        )
        lines.append(f"{recommendation['label']} (score {recommendation['score']}): {products}")
    return "\n".join(lines)


ALL_TOOLS = [search_products, get_knowledge_info, recommend_products]
