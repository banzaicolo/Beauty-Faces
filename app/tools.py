"""Read-only tools available to the anonymous consultation agent."""

import json

from langchain_core.tools import tool

from . import db, rules


@tool
def search_products(category: str = "", keyword: str = "") -> str:
    """查询商品库，返回匹配的护肤产品。
    category 可选：控油祛痘 / 舒缓修护 / 美白淡斑 / 抗皱紧致 / 补水保湿；
    keyword 可选：按品牌 / 名称 / 成分模糊搜索。"""
    rows = db.list_products(category=category, keyword=keyword)
    if not rows:
        return "没有找到匹配的产品。"
    lines = []
    for p in rows:
        lines.append(
            f"[{p['id']}] {p['brand']} {p['name']}"
            f"（{p['category']}｜适合{p['skin_type']}｜{p['price']}）"
            f" 成分：{p['ingredients']} 说明：{p['description']}"
        )
    return "\n".join(lines)


@tool
def get_ingredient_info(name: str) -> str:
    """查询某个护肤成分的功效和注意事项。"""
    r = db.get_ingredient(name.strip())
    if not r:
        return f"成分库中暂未收录「{name}」。"
    caution = f" 注意：{r['caution']}" if r.get("caution") else ""
    return f"{r['name']}：{r['effect']}。{caution}".strip()


@tool
def recommend_products(skin_items_json: str) -> str:
    """根据检测 JSON 计算短板维度，并推荐对应功效产品。

    输入示例：{"水分": 30, "油脂": 33}
    """
    try:
        items = json.loads(skin_items_json)
    except Exception:
        return "检测数据格式有误，请传入 JSON 对象。"
    items = {k: (float(v) if v is not None else None) for k, v in items.items()}
    recos = rules.recommend(items)
    if not recos:
        return "暂无推荐。"
    out = []
    for r in recos:
        pl = "；".join(
            f"{p['brand']} {p['name']}（{p['ingredients']}，{p['price']}）" for p in r["products"]
        )
        out.append(f"【{r['cat']}】（该维度 {r['score']} 分，需关注）：{pl}")
    return "\n".join(out)


ALL_TOOLS = [search_products, get_ingredient_info, recommend_products]
