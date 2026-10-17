"""Seed the active scenario profile's synthetic fixtures into SQLite."""

import json
import os
import sys

from . import config, db


def seed():
    db.init_db()
    conn = db.get_conn()
    profile = config.PROFILE

    customer_count = 0
    if (
        os.environ.get("SEED_DEMO") == "1"
        and conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 0
    ):
        for customer in profile.read_json("customers.sample.json"):
            attributes = customer.get("attributes", {})
            conn.execute(
                "INSERT OR REPLACE INTO customers "
                "(id,name,age,sex,segment,score,items,attributes,analysis,advice,avatar) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    str(customer.get("id")),
                    customer.get("name", ""),
                    str(customer.get("age", "")),
                    customer.get("sex", ""),
                    str(attributes.get(profile.filter_key, "")),
                    str(customer.get("score", "")),
                    json.dumps(customer.get("items", {}), ensure_ascii=False),
                    json.dumps(attributes, ensure_ascii=False),
                    customer.get("analysis", ""),
                    json.dumps(customer.get("advice", []), ensure_ascii=False),
                    customer.get("avatar", ""),
                ),
            )
            customer_count += 1

    product_count = 0
    if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        for product in profile.read_json("products.sample.json"):
            conn.execute(
                "INSERT INTO products "
                "(brand,name,category,target,features,price,description,image,attributes) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    product.get("brand", ""),
                    product.get("name", ""),
                    product.get("category", ""),
                    product.get("target", ""),
                    product.get("features", ""),
                    product.get("price", ""),
                    product.get("description", ""),
                    product.get("image", ""),
                    json.dumps(product.get("attributes", {}), ensure_ascii=False),
                ),
            )
            product_count += 1

    knowledge_count = 0
    for item in profile.read_json("knowledge.json"):
        conn.execute(
            "INSERT OR REPLACE INTO knowledge_items "
            "(name,summary,caution,attributes) VALUES (?,?,?,?)",
            (
                item["name"],
                item.get("summary", ""),
                item.get("caution", ""),
                json.dumps(item.get("attributes", {}), ensure_ascii=False),
            ),
        )
        knowledge_count += 1

    conn.commit()
    conn.close()
    print(
        f"[{profile.id}] seeded customers={customer_count}, "
        f"products={product_count}, knowledge={knowledge_count}"
    )
    print(f"database={config.DB_PATH}")


if __name__ == "__main__":
    sys.path.insert(0, str(config.BASE_DIR.parent))
    seed()
