"""SQLite data access for generic customer, product, and knowledge records."""

import json
import sqlite3
import uuid

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
  id          TEXT PRIMARY KEY,
  name        TEXT,
  age         TEXT,
  sex         TEXT,
  segment     TEXT,
  score       TEXT,
  items       TEXT,
  attributes  TEXT,
  analysis    TEXT,
  advice      TEXT,
  avatar      TEXT,
  created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS products (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  brand       TEXT,
  name        TEXT,
  category    TEXT,
  target      TEXT,
  features    TEXT,
  price       TEXT,
  description TEXT,
  image       TEXT,
  attributes  TEXT
);
CREATE TABLE IF NOT EXISTS knowledge_items (
  name        TEXT PRIMARY KEY,
  summary     TEXT,
  caution     TEXT,
  attributes  TEXT
);
"""


def get_conn():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    conn = get_conn()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    _ensure_columns(conn)
    _migrate_legacy_columns(conn)
    conn.commit()
    conn.close()


def _column_names(conn, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _ensure_columns(conn):
    customer_columns = {
        "segment": "TEXT",
        "score": "TEXT",
        "attributes": "TEXT",
    }
    product_columns = {
        "target": "TEXT",
        "features": "TEXT",
        "attributes": "TEXT",
    }
    for table, columns in (
        ("customers", customer_columns),
        ("products", product_columns),
    ):
        existing = _column_names(conn, table)
        for name, column_type in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}")


def _migrate_legacy_columns(conn):
    customer_columns = _column_names(conn, "customers")
    if "nature" in customer_columns:
        conn.execute(
            "UPDATE customers SET segment=nature "
            "WHERE (segment IS NULL OR segment='') AND nature IS NOT NULL"
        )
    if "skin_age" in customer_columns:
        rows = conn.execute("SELECT id,ph,water,skin_age,attributes FROM customers").fetchall()
        for row in rows:
            if row["attributes"]:
                continue
            attributes = {
                key: row[key] for key in ("ph", "water", "skin_age") if row[key] not in (None, "")
            }
            if attributes:
                conn.execute(
                    "UPDATE customers SET attributes=? WHERE id=?",
                    (json.dumps(attributes, ensure_ascii=False), row["id"]),
                )

    product_columns = _column_names(conn, "products")
    if "skin_type" in product_columns:
        conn.execute(
            "UPDATE products SET target=skin_type "
            "WHERE (target IS NULL OR target='') AND skin_type IS NOT NULL"
        )
    if "ingredients" in product_columns:
        conn.execute(
            "UPDATE products SET features=ingredients "
            "WHERE (features IS NULL OR features='') AND ingredients IS NOT NULL"
        )

    tables = {
        row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if "ingredients" in tables:
        conn.execute(
            "INSERT OR IGNORE INTO knowledge_items(name,summary,caution) "
            "SELECT name,effect,caution FROM ingredients"
        )


def _row2dict(row):
    return dict(row) if row is not None else None


def _decode_customer(row):
    data = _row2dict(row)
    if not data:
        return None
    for key in ("items", "attributes", "advice"):
        raw = data.get(key)
        if raw:
            try:
                data[key] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                data[key] = {} if key != "advice" else []
        else:
            data[key] = {} if key != "advice" else []
    return data


def _decode_product(row):
    data = _row2dict(row)
    if not data:
        return None
    raw = data.get("attributes")
    if raw:
        try:
            data["attributes"] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            data["attributes"] = {}
    else:
        data["attributes"] = {}
    return data


def list_customers(keyword="", segment=""):
    conn = get_conn()
    sql = "SELECT id,name,age,sex,segment,score,attributes,avatar FROM customers WHERE 1=1"
    args = []
    if segment:
        sql += " AND segment=?"
        args.append(segment)
    if keyword:
        sql += (
            " AND (name LIKE ? OR age LIKE ? OR score LIKE ? "
            "OR segment LIKE ? OR attributes LIKE ?)"
        )
        pattern = f"%{keyword}%"
        args.extend([pattern] * 5)
    sql += " ORDER BY name"
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [_decode_customer(row) for row in rows]


def get_customer(cid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
    conn.close()
    return _decode_customer(row)


def customer_count():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    conn.close()
    return count


def add_customer(customer):
    cid = f"u-{uuid.uuid4().hex}"
    attributes = customer.get("attributes", {})
    segment = str(attributes.get(config.PROFILE.filter_key, ""))
    age = attributes.get("age", customer.get("age", ""))
    sex = attributes.get("sex", customer.get("sex", ""))
    conn = get_conn()
    conn.execute(
        "INSERT INTO customers "
        "(id,name,age,sex,segment,score,items,attributes,analysis,advice,avatar) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            cid,
            customer.get("name", ""),
            str(age),
            sex,
            segment,
            str(customer.get("score", "")),
            json.dumps(customer.get("items", {}), ensure_ascii=False),
            json.dumps(attributes, ensure_ascii=False),
            customer.get("analysis", ""),
            json.dumps(customer.get("advice", []), ensure_ascii=False),
            customer.get("avatar", ""),
        ),
    )
    conn.commit()
    conn.close()
    return cid


def delete_customer(cid):
    conn = get_conn()
    conn.execute("DELETE FROM customers WHERE id=?", (cid,))
    conn.commit()
    conn.close()


def list_products(category="", keyword=""):
    conn = get_conn()
    sql = "SELECT * FROM products WHERE 1=1"
    args = []
    if category:
        sql += " AND category=?"
        args.append(category)
    if keyword:
        sql += (
            " AND (brand LIKE ? OR name LIKE ? OR target LIKE ? "
            "OR features LIKE ? OR description LIKE ?)"
        )
        pattern = f"%{keyword}%"
        args.extend([pattern] * 5)
    sql += " ORDER BY category, brand, name"
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [_decode_product(row) for row in rows]


def get_product(pid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    conn.close()
    return _decode_product(row)


def add_product(product):
    conn = get_conn()
    cursor = conn.execute(
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
    conn.commit()
    pid = cursor.lastrowid
    conn.close()
    return get_product(pid)


def update_product(pid, product):
    current = get_product(pid)
    if not current:
        return None
    fields = (
        "brand",
        "name",
        "category",
        "target",
        "features",
        "price",
        "description",
        "image",
    )
    values = {
        key: (product.get(key) if product.get(key) is not None else current.get(key, ""))
        for key in fields
    }
    attributes = product.get("attributes")
    if attributes is None:
        attributes = current.get("attributes", {})
    conn = get_conn()
    conn.execute(
        "UPDATE products SET brand=?,name=?,category=?,target=?,features=?,"
        "price=?,description=?,image=?,attributes=? WHERE id=?",
        (
            values["brand"],
            values["name"],
            values["category"],
            values["target"],
            values["features"],
            values["price"],
            values["description"],
            values["image"],
            json.dumps(attributes, ensure_ascii=False),
            pid,
        ),
    )
    conn.commit()
    conn.close()
    return get_product(pid)


def delete_product(pid):
    conn = get_conn()
    conn.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()


def get_knowledge(name):
    conn = get_conn()
    row = conn.execute("SELECT * FROM knowledge_items WHERE name=?", (name,)).fetchone()
    conn.close()
    return _row2dict(row)


def search_knowledge(keyword=""):
    conn = get_conn()
    if keyword:
        pattern = f"%{keyword}%"
        rows = conn.execute(
            "SELECT * FROM knowledge_items WHERE name LIKE ? OR summary LIKE ? ORDER BY name",
            (pattern, pattern),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM knowledge_items ORDER BY name").fetchall()
    conn.close()
    return [_row2dict(row) for row in rows]


def knowledge_count():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM knowledge_items").fetchone()[0]
    conn.close()
    return count
