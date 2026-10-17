# 场景配置指南

这份指南说明如何在不修改应用代码的情况下增加一个垂直推荐场景。

## 1. 复制模板

```bash
cp -R app/profiles/skin_care app/profiles/my_scene
```

把 `app/profiles/my_scene/profile.json` 中的 `id` 改为 `my_scene`，它必须与目录名一致。

然后启动：

```bash
APP_PROFILE=my_scene
SEED_DEMO=1
DATA_DIR=./data
```

数据库会写成 `data/my_scene.db` 和 `data/my_scene-checkpoints.db`。

## 2. `profile.json` 的最小结构

```json
{
  "schema_version": 1,
  "id": "my_scene",
  "version": "0.1.0",
  "branding": {
    "name": "My Assistant",
    "tagline": "垂直场景推荐助手"
  },
  "copy": {
    "assistant_name": "小助手",
    "chat_title": "推荐顾问",
    "customer_nav": "客户档案",
    "product_nav": "产品库"
  },
  "higher_is_better": true,
  "customer_fields": [
    {
      "key": "segment",
      "label": "客户类型",
      "type": "select",
      "options": ["类型 A", "类型 B"],
      "filterable": true
    }
  ],
  "dimensions": [
    {
      "id": "comfort",
      "label": "舒适度",
      "category": "舒适产品",
      "items": [
        {"key": "舒适评分", "label": "舒适评分", "weight": 1}
      ]
    }
  ],
  "recommendation": {
    "top_dimensions": 3,
    "products_per_dimension": 3
  },
  "assessment": {
    "enabled": false,
    "prompt_file": "vlm_prompt.txt"
  },
  "alerts": []
}
```

`copy` 中未填写的键会使用 `app/profile.py` 的通用默认文案。

## 3. 必填资源

- `system_prompt.txt`
- `report_prompt.txt`
- `customers.sample.json`
- `products.sample.json`
- `knowledge.json`
- `vlm_prompt.txt`，仅在 `assessment.enabled=true` 时需要

报告模板支持：

- `{info}`：客户年龄、性别、属性和综合评分
- `{conclusions}` 或 `{concl}`：计算后的重点维度与指标

## 4. 数据约束

客户样例：

```json
{
  "id": "my-scene-sample-001",
  "name": "示例客户",
  "age": "30",
  "sex": "女",
  "score": "70",
  "attributes": {"segment": "类型 A"},
  "items": {"舒适评分": 55},
  "analysis": "合成记录",
  "advice": ["合成建议"],
  "avatar": ""
}
```

产品样例：

```json
{
  "brand": "示例品牌",
  "name": "示例产品",
  "category": "舒适产品",
  "target": "类型 A",
  "features": "特点 A、特点 B",
  "price": "示例价",
  "description": "合成说明",
  "image": "/product-placeholder.svg"
}
```

知识样例：

```json
{
  "name": "知识条目",
  "summary": "通用说明",
  "caution": "注意事项"
}
```

启动校验会检查：

- 维度 ID 和评分项是否唯一
- 客户字段是否唯一，且恰好一个字段可筛选
- 客户样例是否只引用已声明字段和指标
- 产品分类是否对应已声明维度
- 警示规则是否引用已声明指标
- prompt 和样例资源是否存在
- 推荐数量是否合法

## 5. 扩展规则

当前通用引擎适合：

- 产品选品与服务推荐
- 多指标评分和加权排序
- 关键词检索与结构化知识查询
- 单门店客户或设备记录管理

如果业务需要复杂审批流、库存同步、订单、租户权限、医疗工作流或多种实体关系，应增加专门的数据模型和连接器，而不是继续把全部逻辑塞进 `profile.json`。配置驱动解决领域差异，不替代真正的业务系统设计。
