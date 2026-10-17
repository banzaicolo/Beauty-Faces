"""SQLite data access for customers, products, and ingredients."""

import json
import sqlite3

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
  id         TEXT PRIMARY KEY,
  name       TEXT,
  age        TEXT,
  sex        TEXT,
  nature     TEXT,
  ph         TEXT,
  water      TEXT,
  score      TEXT,
  skin_age   TEXT,
  items      TEXT,        -- 检测项目分数 JSON
  analysis   TEXT,        -- 问题分析文案
  advice     TEXT,        -- 护理建议 JSON 数组
  avatar     TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS products (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  brand       TEXT,
  name        TEXT,
  category    TEXT,
  skin_type   TEXT,
  ingredients TEXT,
  price       TEXT,
  description TEXT,
  image       TEXT
);
CREATE TABLE IF NOT EXISTS ingredients (
  name    TEXT PRIMARY KEY,
  effect  TEXT,
  caution TEXT
);
"""


def get_conn():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    # 并发加固：写锁等待 5 秒（默认 5 秒即抛错），避免多请求同时写直接报 busy
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    conn = get_conn()
    # WAL 模式：读不阻塞写、写不阻塞读，多用户并发时性能与稳定性远好于默认 journal
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    _ensure_columns(conn)
    conn.commit()
    conn.close()


def _ensure_columns(conn):
    """旧库自动迁移：products 缺 image 列就补上（不破坏已有数据）"""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(products)")}
    if "image" not in cols:
        conn.execute("ALTER TABLE products ADD COLUMN image TEXT")


def _row2dict(r):
    return dict(r) if r is not None else None


# ---------- 客户 ----------


def list_customers(keyword="", nature=""):
    conn = get_conn()
    sql = "SELECT id,name,age,sex,nature,ph,water,score,skin_age,avatar FROM customers WHERE 1=1"
    args = []
    if nature:
        sql += " AND nature=?"
        args.append(nature)
    if keyword:
        sql += (
            " AND (name LIKE ? OR age LIKE ? OR skin_age LIKE ? OR score LIKE ? OR nature LIKE ?)"
        )
        kw = f"%{keyword}%"
        args += [kw, kw, kw, kw, kw]
    sql += " ORDER BY score ASC"
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [_row2dict(r) for r in rows]


def get_customer(cid):
    conn = get_conn()
    r = conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
    conn.close()
    d = _row2dict(r)
    if d:
        d["items"] = json.loads(d["items"]) if d.get("items") else {}
        d["advice"] = json.loads(d["advice"]) if d.get("advice") else []
    return d


def customer_count():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    conn.close()
    return n


def add_customer(c):
    """新增客户（自建/拍照测肤保存），items 留空 dict"""
    import time

    cid = f"u-{int(time.time() * 1000)}"
    conn = get_conn()
    conn.execute(
        "INSERT INTO customers "
        "(id,name,age,sex,nature,ph,water,score,skin_age,items,analysis,advice,avatar) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            cid,
            c.get("name", ""),
            str(c.get("age", "")),
            c.get("sex", ""),
            c.get("nature", ""),
            "",
            "",
            "",
            "",
            json.dumps(c.get("items", {}), ensure_ascii=False),
            c.get("analysis", ""),
            json.dumps(c.get("advice", []), ensure_ascii=False),
            "",
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


# ---------- 商品 ----------


def list_products(category="", keyword=""):
    conn = get_conn()
    sql = "SELECT * FROM products WHERE 1=1"
    args = []
    if category:
        sql += " AND category=?"
        args.append(category)
    if keyword:
        sql += " AND (brand LIKE ? OR name LIKE ? OR ingredients LIKE ? OR description LIKE ?)"
        kw = f"%{keyword}%"
        args += [kw, kw, kw, kw]
    sql += " ORDER BY category, brand"
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [_row2dict(r) for r in rows]


def get_product(pid):
    conn = get_conn()
    r = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    conn.close()
    return _row2dict(r)


def add_product(p):
    conn = get_conn()
    cur = conn.execute(
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
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return get_product(pid)


def update_product(pid, p):
    current = get_product(pid)
    if not current:
        return None
    values = {
        key: p.get(key) if p.get(key) is not None else current.get(key, "")
        for key in (
            "brand",
            "name",
            "category",
            "skin_type",
            "ingredients",
            "price",
            "description",
            "image",
        )
    }
    conn = get_conn()
    conn.execute(
        "UPDATE products SET brand=?,name=?,category=?,skin_type=?,"
        "ingredients=?,price=?,description=?,image=? WHERE id=?",
        (
            values["brand"],
            values["name"],
            values["category"],
            values["skin_type"],
            values["ingredients"],
            values["price"],
            values["description"],
            values["image"],
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


# ---------- 成分 ----------


def get_ingredient(name):
    conn = get_conn()
    r = conn.execute("SELECT * FROM ingredients WHERE name=?", (name,)).fetchone()
    conn.close()
    return _row2dict(r)


def search_ingredients(keyword=""):
    conn = get_conn()
    if keyword:
        rows = conn.execute(
            "SELECT * FROM ingredients WHERE name LIKE ? OR effect LIKE ? ORDER BY name",
            (f"%{keyword}%", f"%{keyword}%"),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM ingredients ORDER BY name").fetchall()
    conn.close()
    return [_row2dict(r) for r in rows]


def ingredient_count():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0]
    conn.close()
    return n
