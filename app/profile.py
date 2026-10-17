"""Scenario profile loading and validation.

A profile owns domain vocabulary, dimensions, prompts, fixtures, and UI labels.
Application code remains profile-agnostic.
"""

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path

PROFILE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")

DEFAULT_COPY = {
    "assistant_name": "顾问",
    "chat_title": "智能顾问",
    "chat_subtitle": "多轮对话 · 自动查库",
    "chat_placeholder": "输入你的问题…",
    "chat_examples": ["推荐一款产品", "有哪些知识条目？"],
    "service_group": "顾问服务",
    "admin_group": "管理",
    "chat_nav": "智能顾问",
    "assessment_nav": "照片分析",
    "customer_nav": "客户管理",
    "product_nav": "产品库",
    "customers_title": "客户管理",
    "add_customer": "＋ 新增客户",
    "customer_search_placeholder": "搜索姓名或标签…",
    "assessment_title": "照片分析",
    "assessment_subtitle": "一般性外观观察，不提供专业诊断",
    "assessment_upload": "选择照片 / 拍照",
    "assessment_start": "开始分析",
    "assessment_hint": (
        "照片会发送到所配置的视觉模型服务。请先取得被拍摄者同意；"
        "如情况严重、持续加重或需要诊断，请咨询专业人士。"
    ),
    "products_title": "产品库",
    "add_product": "＋ 新增产品",
    "product_search_placeholder": "搜索品牌 / 名称 / 特点…",
    "customer_detail_title": "客户记录",
    "analysis_title": "记录摘要",
    "advice_title": "建议",
    "dimension_heading": "关注维度",
    "item_heading": "指标",
    "recommendation_heading": "匹配产品",
    "report_button": "生成 AI 建议",
    "save_customer": "保存为客户",
    "send_to_advisor": "发给智能顾问",
    "new_chat": "＋ 新对话",
    "login_title": "管理登录",
    "logout": "退出登录",
    "disclaimer": "本工具提供一般信息，不能替代专业意见。",
    "privacy_local": "本地模型模式",
    "privacy_external": "外部模型模式",
    "product_target_label": "适用对象",
    "product_features_label": "主要特点",
    "product_category_label": "分类",
    "knowledge_entity": "知识条目",
}

REQUIRED_RESOURCES = (
    "system_prompt.txt",
    "report_prompt.txt",
    "customers.sample.json",
    "products.sample.json",
    "knowledge.json",
)


@dataclass(frozen=True)
class Profile:
    root: Path
    data: dict

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def filter_key(self) -> str:
        for field in self.data["customer_fields"]:
            if field.get("filterable"):
                return field["key"]
        return self.data["customer_fields"][0]["key"]

    def read_json(self, name: str):
        with open(self.root / name, encoding="utf-8") as handle:
            return json.load(handle)

    def read_text(self, name: str) -> str:
        with open(self.root / name, encoding="utf-8") as handle:
            return handle.read()

    def public_meta(self) -> dict:
        public = copy.deepcopy(self.data)
        public.pop("resources", None)
        public["filter_key"] = self.filter_key
        public["categories"] = [dimension["category"] for dimension in public["dimensions"]]
        public["item_labels"] = {
            item["key"]: item["label"]
            for dimension in public["dimensions"]
            for item in dimension["items"]
        }
        return public


def _require_keys(value: dict, keys: tuple[str, ...], location: str) -> None:
    missing = [key for key in keys if key not in value]
    if missing:
        raise ValueError(f"{location} is missing: {', '.join(missing)}")


def load_profile(profile_root: Path) -> Profile:
    if not PROFILE_ID_PATTERN.fullmatch(profile_root.name):
        raise ValueError(f"Invalid profile id: {profile_root.name}")
    profile_file = profile_root / "profile.json"
    if not profile_file.exists():
        raise ValueError(f"Profile not found: {profile_file}")

    with open(profile_file, encoding="utf-8") as handle:
        data = json.load(handle)

    _require_keys(
        data,
        (
            "schema_version",
            "id",
            "version",
            "branding",
            "copy",
            "dimensions",
            "recommendation",
            "assessment",
            "customer_fields",
        ),
        str(profile_file),
    )
    if data["id"] != profile_root.name:
        raise ValueError("Profile id must match its directory name")
    if data["schema_version"] != 1:
        raise ValueError("Unsupported profile schema_version")

    data["copy"] = {**DEFAULT_COPY, **data.get("copy", {})}
    _require_keys(data["branding"], ("name",), f"{profile_file}: branding")
    _require_keys(
        data["recommendation"],
        ("top_dimensions", "products_per_dimension"),
        f"{profile_file}: recommendation",
    )
    _require_keys(
        data["assessment"],
        ("enabled", "prompt_file"),
        f"{profile_file}: assessment",
    )

    if not data["dimensions"]:
        raise ValueError(f"{profile_file}: at least one dimension is required")
    dimension_ids = set()
    item_keys = set()
    for dimension in data["dimensions"]:
        _require_keys(
            dimension,
            ("id", "label", "category", "items"),
            f"{profile_file}: dimension",
        )
        if dimension["id"] in dimension_ids:
            raise ValueError(f"Duplicate dimension id: {dimension['id']}")
        dimension_ids.add(dimension["id"])
        if not dimension["items"]:
            raise ValueError(f"Dimension {dimension['id']} has no items")
        for item in dimension["items"]:
            _require_keys(item, ("key", "label"), f"{profile_file}: dimension item")
            if item["key"] in item_keys:
                raise ValueError(f"Duplicate measurement key: {item['key']}")
            item_keys.add(item["key"])
            item.setdefault("weight", 1.0)

    fields = data["customer_fields"]
    if not fields:
        raise ValueError(f"{profile_file}: customer_fields cannot be empty")
    field_keys = set()
    filter_count = 0
    for field in fields:
        _require_keys(field, ("key", "label", "type"), f"{profile_file}: customer field")
        if field["key"] in field_keys:
            raise ValueError(f"Duplicate customer field key: {field['key']}")
        field_keys.add(field["key"])
        if field["type"] not in {"text", "number", "select"}:
            raise ValueError(f"Unsupported customer field type: {field['type']}")
        if field.get("filterable"):
            filter_count += 1
    if filter_count != 1:
        raise ValueError("Exactly one customer field must be filterable")

    for name in REQUIRED_RESOURCES:
        if not (profile_root / name).exists():
            raise ValueError(f"Profile resource missing: {name}")
    prompt_file = data["assessment"]["prompt_file"]
    if data["assessment"]["enabled"] and not (profile_root / prompt_file).exists():
        raise ValueError(f"Assessment prompt missing: {prompt_file}")

    categories = {dimension["category"] for dimension in data["dimensions"]}
    customers = json.loads((profile_root / "customers.sample.json").read_text(encoding="utf-8"))
    products = json.loads((profile_root / "products.sample.json").read_text(encoding="utf-8"))
    knowledge = json.loads((profile_root / "knowledge.json").read_text(encoding="utf-8"))
    if not customers:
        raise ValueError(f"{profile_file}: customers.sample.json cannot be empty")
    if not products:
        raise ValueError(f"{profile_file}: products.sample.json cannot be empty")
    if not knowledge:
        raise ValueError(f"{profile_file}: knowledge.json cannot be empty")

    for customer in customers:
        _require_keys(customer, ("id", "name", "items", "attributes"), "customer sample")
        unknown_items = set(customer.get("items", {})) - item_keys
        if unknown_items:
            raise ValueError(f"Customer sample uses undeclared items: {sorted(unknown_items)}")
        unknown_fields = set(customer.get("attributes", {})) - field_keys
        if unknown_fields:
            raise ValueError(f"Customer sample uses undeclared fields: {sorted(unknown_fields)}")

    for product in products:
        _require_keys(product, ("name", "category"), "product sample")
        if product["category"] not in categories:
            raise ValueError(
                f"Product category is not declared as a dimension: {product['category']}"
            )
    for item in knowledge:
        _require_keys(item, ("name", "summary"), "knowledge sample")

    data.setdefault("alerts", [])
    data.setdefault("higher_is_better", True)
    if not isinstance(data["higher_is_better"], bool):
        raise ValueError("higher_is_better must be a boolean")
    if int(data["recommendation"]["top_dimensions"]) < 1:
        raise ValueError("recommendation.top_dimensions must be at least 1")
    if int(data["recommendation"]["products_per_dimension"]) < 1:
        raise ValueError("recommendation.products_per_dimension must be at least 1")
    declared_measurements = item_keys | set(data["assessment"].get("extra_items", []))
    for alert in data["alerts"]:
        if alert.get("item") not in declared_measurements:
            raise ValueError(f"Alert references undeclared item: {alert.get('item')}")
    data["resources"] = {
        "customers": "customers.sample.json",
        "products": "products.sample.json",
        "knowledge": "knowledge.json",
    }
    return Profile(root=profile_root, data=data)
