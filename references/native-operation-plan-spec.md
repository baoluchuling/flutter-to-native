# Native Operation Plan Spec

## 目的

`native_operation_plan.yaml` 描述“原生项目需要做哪些操作”，
重点是操作项，不是类一一映射。

它是 `requirement_sync_contract` 的前置输入。

## 输出时机

- 在 `atlas_planner.py plan` 中生成
- 写入 `.ai/t2n/runs/<run-id>/native_operation_plan.yaml`

## 顶层字段

```yaml
requirement:
operation_policy:
operations:
manual_candidates:
```

## 字段说明

### `requirement`

- `id`
- `name`

### `operation_policy`

- `execution_mode`：建议 `plan_then_confirm_then_apply`
- `auto_apply_confidence`：建议 `high`
- `manual_when`：低置信、高风险、注册点等条件

### `operations`

每条记录表示一个原生改动动作，建议字段：

- `operation_id`
- `action`：`edit_existing`、`create_file`、`manual_review`、`review_candidate`
- `target_path`
- `target_kind`
- `ui_role`
- `confidence`
- `risk`
- `source_screens`
- `intent_links`
- `reason`

### `manual_candidates`

- 需要人工确认或人工实施的目标路径列表

## 生成原则

- 映射对象是”操作”，不是”类对类”
- 每个操作必须带 `reason` 与 `confidence`
- 超过边界或高风险操作默认进入 `manual_candidates`
- 后续 `apply` 仅执行已确认且满足策略的操作项

## 质量门控

### Model 操作

当 `target_kind` 为 model 时，operation 必须附加：

- `field_alignment`：字段对齐表（Flutter 类型 → iOS 类型 + nil 策略）
- 对齐策略必须基于实际读取目标 model 文件后的现有约定

### 入口修改操作

当 `action` 为 `edit_existing` 且涉及入口方法修改时，operation 必须附加：

- `call_chain`：完整的 iOS 侧调用链分析（上游触发 → 目标方法 → 下游调用）
- `architecture_mapping`：Flutter 侧对应位置及架构差异说明

### UI 操作

当 `target_kind` 涉及 UI 时，operation 必须附加：

- `design_reference`：设计稿来源（Figma/截图/无）
- 无设计稿时 `confidence` 不得高于 `medium`，且应进入 `manual_candidates` 或要求用户提供设计稿
