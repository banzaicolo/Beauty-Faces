"""规则引擎：短板维度计算 + 商品推荐匹配（精确判断交给规则，语言组织交给大模型）"""

from . import config, db


def _avg(a):
    a = [x for x in a if x is not None]
    return round(sum(a) / len(a)) if a else None


def weak_dims(items):
    """算短板维度，返回按严重度升序（分数越低越需关注）"""
    out = []
    for dim in config.DIMS:
        names = dim["items"]
        vals = [items.get(n) for n in names if items.get(n) is not None]
        sc = _avg(vals)
        if sc is not None:
            out.append(
                {
                    "cat": dim["cat"],
                    "label": dim["label"],
                    "score": sc,
                    "names": names,
                    "detail": {n: items.get(n) for n in names if items.get(n) is not None},
                }
            )
    out.sort(key=lambda x: x["score"])
    return out


def recommend(items, top_n=3):
    """根据检测数据推荐商品，返回 [{cat,label,score,products}]"""
    result = []
    for w in weak_dims(items)[:3]:
        prods = db.list_products(category=w["cat"])[:top_n]
        if prods:
            result.append(
                {"cat": w["cat"], "label": w["label"], "score": w["score"], "products": prods}
            )
    return result


def build_report_prompt(d):
    """拼报告生成 prompt（结论先算好，让大模型只组织语言）"""
    wd = weak_dims(d.get("items", {}))[:3]
    concl = "\n".join(
        f"{i + 1}. {x['cat']}不足（{x['score']}分）——相关指标："
        + "、".join(f"{k}{v}分" for k, v in x["detail"].items())
        for i, x in enumerate(wd)
    )
    info = (
        f"肤质：{d.get('nature', '')}，pH {d.get('ph', '')}，"
        f"肤龄{d.get('skin_age', '')}岁（实际{d.get('age', '')}岁），"
        f"综合分{d.get('score', '')}"
    )
    template = config.load_text("report_prompt.txt")
    return template.replace("{info}", info).replace("{concl}", concl), wd
