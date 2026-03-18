# Requirement Sync Contract 字段级 Schema

## 目的

本文档定义 `requirement_sync_contract.yaml` 的字段级 schema，作为 `Atlas Planner`、`Atlas Apply`、`Atlas Verify` 的统一契约。

使用原则：

- 先保证 V1 可落地
- 优先定义稳定字段
- 对高风险、不确定、人工处理项显式建模

## 文件级规则

- 文件名固定为 `requirement_sync_contract.yaml`
- 格式使用 YAML
- 顶层字段顺序尽量保持稳定，便于 diff 和审阅
- 未知字段不要随意追加到顶层，应优先放入现有结构中的 `notes`、`manual_candidates`、`unsupported` 等位置

## 顶层字段

顶层字段顺序建议如下：

```yaml
requirement:
mode:
sync_strategy:
source:
target:
behavior:
flutter_evidence:
native_impact:
patch_plan:
unsupported:
notes:
```

## 字段定义

### `requirement`

类型：

- object

必填：

- 是

字段：

- `id`: string，必填
- `name`: string，必填，推荐使用稳定 slug
- `summary`: string，必填
- `acceptance_criteria`: string[]，选填

说明：

- `id` 对应 PRD、工单或需求唯一标识
- `name` 是 contract 内部使用的需求名
- `summary` 应简洁描述本次要同步的功能

### `mode`

类型：

- string

必填：

- 是

允许值：

- `feature_sync`

### `sync_strategy`

类型：

- string

必填：

- 是

允许值：

- `scoped_patch`

### `source`

类型：

- object

必填：

- 是

字段：

- `flutter_paths`: string[]，选填
- `change_basis`: string[]，必填
- `change_ref`: string，选填
- `prd_path`: string，选填
- `pr_diff_path`: string，选填
- `tests_paths`: string[]，选填
- `notes`: string[]，选填

`change_basis` 允许值：

- `prd`
- `flutter_digest`
- `flutter_code`
- `flutter_pr_diff`
- `flutter_tests`

约束：

- `change_basis` 至少包含 1 项
- 如果 `flutter_paths` 为空，必须至少有 `pr_diff_path` 或 `tests_paths`

### `target`

类型：

- object

必填：

- 是

字段：

- `platform`: string，必填，V1 固定为 `ios`
- `language`: string，必填，V1 固定为 `swift`
- `ui_framework`: string，必填，V1 固定为 `uikit`
- `repo_root`: string，必填
- `profile_path`: string，必填
- `module_hint`: string，选填
- `write_mode`: string，选填

`write_mode` 建议值：

- `plan_only`
- `apply_after_approval`

### `behavior`

类型：

- object

必填：

- 是

字段：

- `user_flows`: string[]，必填
- `acceptance_points`: string[]，必填
- `states`: object[]，选填
- `interactions`: string[]，选填
- `strings`: string[]，选填
- `assets`: string[]，选填

`states` 子项建议字段：

- `name`: string，必填
- `kind`: string，必填
- `notes`: string[]，选填

`kind` 建议值：

- `loading`
- `success`
- `error`
- `empty`
- `retry`
- `partial`

### `flutter_evidence`

类型：

- object

必填：

- 是

字段：

- `screens`: string[]，选填
- `representative_screens`: object[]，选填
- `state_holders`: string[]，选填
- `api_calls`: string[]，选填
- `models`: string[]，选填
- `tests`: string[]，选填
- `key_files`: string[]，选填

`representative_screens` 子项建议字段：

- `name`: string，必填
- `path`: string，选填
- `role`: string，必填，建议值为 `primary_screen`、`auxiliary_dialog`、`auxiliary_overlay`、`component_view`
- `confidence`: number，选填

约束：

- 该对象至少应包含 1 个非空字段

### `native_impact`

类型：

- object

必填：

- 是

字段：

- `existing_files`: string[]，选填
- `new_files`: string[]，选填
- `registration_points`: string[]，选填
- `risk_files`: object[]，选填
- `selected_touchpoints`: object[]，选填

`risk_files` 子项字段：

- `path`: string，必填
- `risk`: string，必填
- `reason`: string，必填

`selected_touchpoints` 子项字段：

- `path`: string，必填
- `kind`: string，必填
- `confidence`: string，必填
- `reason`: string，必填
- `risk`: string，选填
- `ui_role`: string，选填
- `source_screens`: string[]，选填

`confidence` 建议值：

- `high`
- `medium`
- `low`

`risk` 建议值：

- `low`
- `medium`
- `high`

`ui_role` 建议值：

- `primary_screen`
- `auxiliary_dialog`
- `auxiliary_overlay`
- `component_view`
- `non_ui`
- `registration_point`

约束：

- `existing_files` 与 `new_files` 可以同时为空，但这时 `registration_points` 或 `selected_touchpoints` 至少要有内容

### `patch_plan`

类型：

- object

必填：

- 是

字段：

- `create`: string[]，选填
- `update`: string[]，选填
- `manual_candidates`: string[]，选填
- `deferred_items`: string[]，选填

约束：

- `create`、`update`、`manual_candidates` 三者至少要有一项非空

### `unsupported`

类型：

- string[]

必填：

- 是

说明：

- 如果当前没有不支持项，也建议显式写为 `[]`

### `notes`

类型：

- string[]

必填：

- 否

说明：

- 放置不适合单独建模但又需要保留的附加说明

## 最小有效 Contract

下面是 V1 允许的最小有效示例：

```yaml
requirement:
  id: PRD-001
  name: sample_feature
  summary: Sync sample feature from Flutter into iOS

mode: feature_sync
sync_strategy: scoped_patch

source:
  flutter_paths:
    - lib/features/sample_feature/
  change_basis:
    - prd
    - flutter_code

target:
  platform: ios
  language: swift
  ui_framework: uikit
  repo_root: ../native-ios
  profile_path: .ai/t2n/native-profile-v2

behavior:
  user_flows:
    - open_sample
  acceptance_points:
    - sample screen opens

flutter_evidence:
  key_files:
    - lib/features/sample_feature/sample_page.dart

native_impact:
  existing_files:
    - SampleViewController.swift

patch_plan:
  update:
    - SampleViewController.swift

unsupported: []
```

## 设计约束

- contract 必须既能给机器消费，也能给人审阅
- contract 必须显式表达高风险点
- contract 不负责承载完整 patch 内容，只负责描述 patch 范围和意图
- contract 不应隐藏关键假设

## 与后续阶段的关系

- `Atlas Planner` 负责生成该 contract
- `Atlas Apply` 依据该 contract 和 `sync_plan.md` 执行 patch
- `Atlas Verify` 依据该 contract 检查最终结果是否覆盖目标行为
