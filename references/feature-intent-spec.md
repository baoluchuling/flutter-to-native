# Feature Intent Spec

## 目的

`feature_intent_spec.yaml` 用于描述“Flutter 需求到底改了什么功能语义”，
不描述原生改哪里，只描述功能意图本身。

它是 `native_operation_plan` 的输入前置。

## 输出时机

- 在 `atlas_planner.py plan` 中生成
- 写入 `.ai/t2n/runs/<run-id>/feature_intent_spec.yaml`

## 顶层字段

```yaml
requirement:
intent_scope:
intent_units:
behavior_contract:
```

## 字段说明

### `requirement`

- `id`
- `name`
- `summary`

### `intent_scope`

- `primary_features`
- `supporting_features`
- `flutter_paths`
- `change_basis`
- `change_ref`

### `intent_units`

每个单元对应一个功能意图片段，建议字段：

- `intent_id`
- `intent_type`：`ui_flow` 或 `data_flow`
- `screen_name`
- `screen_path`
- `screen_role`
- `interactions`
- `trigger_mode` — 新增：`user_action`（用户点击触发）、`auto`（自动触发，如翻到特定页面）、`conditional`（条件满足后自动触发）。必须标注触发的 Flutter 方法名和调用链
- `states`
- `acceptance_points`
- `api_calls`
- `models` — 当类型为 `data_flow` 时，每个 model 字段必须标注 nullable 信息
- `model_fields` — 新增：Flutter model 的字段清单，含类型和 `?` 标注，为后续字段对齐表提供输入

### `behavior_contract`

- `user_flows`
- `acceptance_points`
- `strings`
- `assets`

## 生成原则

- 先语义，后代码；不做 Flutter class 到 native class 的一一映射
- 优先保留能驱动原生重写的行为信息（流程、状态、交互、数据）
- 保持字段稳定，便于 `native_operation_plan` 和 `contract` 复用
- **Model 字段必须保留完整的 nullable 信息**，为后续字段对齐表提供准确输入
- **UI 描述用行为语言**（"底部弹出面板，71% 高度，包含产品卡片列表"），不用 Flutter Widget 语言（"Stack + Positioned + Container"）
- **UI 微调不得单独排除**：间距、颜色、圆角、字体等视觉参数变更必须合并到对应功能的 intent 中，列出具体的变更值（如 `cornerRadius: 100 → 200`），这些参数直接影响最终 UI 还原度
