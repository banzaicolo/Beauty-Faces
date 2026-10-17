"""数据导入：把 configs/ 下的种子数据灌入 SQLite。
用法：python3 -m app.seed  （在项目根目录，幂等可重复执行）
- 商品：表为空时导入
- 成分：幂等覆盖
- 演示客户：默认不导入；设 SEED_DEMO=1 时才灌入完全虚构的 4 份样例"""

import json
import os
import sys

from . import config, db


def seed():
    db.init_db()
    conn = db.get_conn()

    # 1. 完全虚构的演示客户 —— 仅在 SEED_DEMO=1 时导入
    n_c = 0
    if (
        os.environ.get("SEED_DEMO") == "1"
        and conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 0
    ):
        customers = config.load_json("customers.sample.json")
        for c in customers:
            conn.execute(
                "INSERT OR REPLACE INTO customers "
                "(id,name,age,sex,nature,ph,water,score,skin_age,items,analysis,advice,avatar) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    str(c.get("id")),
                    c.get("name", ""),
                    str(c.get("age", "")),
                    c.get("sex", ""),
                    c.get("nature", ""),
                    str(c.get("ph", "")),
                    str(c.get("water", "")),
                    str(c.get("score", "")),
                    str(c.get("skinAge", "")),
                    json.dumps(c.get("items", {}), ensure_ascii=False),
                    c.get("analysis", ""),
                    json.dumps(c.get("advice", []), ensure_ascii=False),
                    c.get("avatar", ""),
                ),
            )
            n_c += 1

    # 2. 商品 —— 仅当商品表为空时导入，避免容器重启重复累积
    n_p = 0
    if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        products = config.load_json("products_seed.json")
        for p in products:
            conn.execute(
                "INSERT INTO products "
                "(brand,name,category,skin_type,ingredients,price,description,image) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    p.get("brand", ""),
                    p.get("name", ""),
                    p.get("category", ""),
                    p.get("skin_type", ""),
                    p.get("ingredients", ""),
                    p.get("price", ""),
                    p.get("description", ""),
                    p.get("image", ""),
                ),
            )
            n_p += 1

    # 3. 成分库 —— 主键 name 幂等
    n_i = 0
    ingredients = config.load_json("ingredients.json")
    for ing in ingredients:
        conn.execute(
            "INSERT OR REPLACE INTO ingredients (name,effect,caution) VALUES (?,?,?)",
            (ing["name"], ing.get("effect", ""), ing.get("caution", "")),
        )
        n_i += 1

    conn.commit()
    conn.close()
    print(f"导入完成：客户 {n_c}，商品 {n_p}，成分 {n_i}")
    print(f"数据库：{config.DB_PATH}")


if __name__ == "__main__":
    sys.path.insert(0, str(config.BASE_DIR.parent))
    seed()
