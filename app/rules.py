"""Profile-driven weighted scoring and deterministic product matching."""

from . import config, db


def _weighted_average(values):
    weighted = [
        (float(value), float(weight))
        for value, weight in values
        if value is not None and weight > 0
    ]
    total_weight = sum(weight for _value, weight in weighted)
    if not weighted or total_weight == 0:
        return None
    return round(sum(value * weight for value, weight in weighted) / total_weight)


def ranked_dimensions(items):
    """Return dimensions ordered from most to least concerning."""
    result = []
    for dimension in config.PROFILE.data["dimensions"]:
        detail = {}
        values = []
        for item in dimension["items"]:
            value = items.get(item["key"])
            if value is None:
                continue
            detail[item["key"]] = value
            values.append((value, item.get("weight", 1)))
        score = _weighted_average(values)
        if score is None:
            continue
        result.append(
            {
                "id": dimension["id"],
                "cat": dimension["category"],
                "label": dimension["label"],
                "score": score,
                "names": [item["key"] for item in dimension["items"]],
                "detail": detail,
            }
        )

    higher_is_better = config.PROFILE.data.get("higher_is_better", True)
    result.sort(key=lambda row: row["score"], reverse=not higher_is_better)
    return result


def recommend(items):
    settings = config.PROFILE.data["recommendation"]
    top_dimensions = int(settings["top_dimensions"])
    products_per_dimension = int(settings["products_per_dimension"])
    recommendations = []
    for dimension in ranked_dimensions(items)[:top_dimensions]:
        products = db.list_products(category=dimension["cat"])
        if not products:
            continue
        recommendations.append(
            {
                **dimension,
                "products": products[:products_per_dimension],
            }
        )
    return recommendations


def _customer_info(customer):
    fields = config.PROFILE.data["customer_fields"]
    attributes = customer.get("attributes", {})
    labels = {field["key"]: field["label"] for field in fields}
    parts = []
    for key, value in attributes.items():
        if value not in (None, ""):
            parts.append(f"{labels.get(key, key)} {value}")
    if customer.get("score"):
        parts.append(f"综合评分 {customer['score']}")
    return "；".join(parts)


def build_report_prompt(customer):
    dimensions = ranked_dimensions(customer.get("items", {}))
    dimensions = dimensions[: config.PROFILE.data["recommendation"]["top_dimensions"]]
    conclusions = "\n".join(
        f"{index + 1}. {row['label']}（{row['score']} 分）："
        + "、".join(
            f"{config.PUBLIC_PROFILE['item_labels'].get(key, key)}={value}"
            for key, value in row["detail"].items()
        )
        for index, row in enumerate(dimensions)
    )
    template = config.load_text("report_prompt.txt")
    prompt = template.replace("{info}", _customer_info(customer))
    prompt = prompt.replace("{concl}", conclusions)
    prompt = prompt.replace("{conclusions}", conclusions)
    return prompt, dimensions


def active_alerts(items):
    alerts = []
    for alert in config.PROFILE.data.get("alerts", []):
        value = items.get(alert.get("item"))
        if value is None:
            continue
        threshold = float(alert.get("threshold", 0))
        operator = alert.get("operator", "lt")
        triggered = {
            "lt": float(value) < threshold,
            "lte": float(value) <= threshold,
            "gt": float(value) > threshold,
            "gte": float(value) >= threshold,
            "eq": float(value) == threshold,
        }.get(operator, False)
        if triggered:
            alerts.append({"message": alert.get("message", "")})
    return alerts
