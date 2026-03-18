# Profile Assets Spec

## 目的

定义 `T2N Atlas` 前置扫描阶段的可复用资产格式。该资产用于后续多个需求同步复用，不是一次性 run 产物。

## 目录约定

```text
.ai/t2n/
  flutter-profile/
  native-profile/
  shared/
    capability_map.yaml
```

## 通用约束

- 所有记录必须包含 `stable_id`
- 所有记录必须包含 `source_refs`
- 所有记录必须包含 `last_seen_commit`
- 所有 profile 必须包含 `scan_meta.yaml`
- 支持增量刷新：允许更新记录，不允许无原因删除历史记录

## flutter-profile / native-profile 最小文件集

### 1. `repo_architecture.yaml`

最小字段：

- `repo_root`
- `architecture.label`
- `architecture.confidence`
- `layering`
- `entry_points`
- `global_constraints`

### 2. `feature_catalog.yaml`

最小字段：

- `features[]`
- `features[].stable_id`
- `features[].name`
- `features[].owned_files`
- `features[].screens`
- `features[].state_units`
- `features[].api_units`
- `features[].tests`

### 3. `symbol_index.jsonl`

每行一条 symbol，最小字段：

- `stable_id`
- `symbol_name`
- `symbol_kind`
- `file_path`
- `signature`
- `source_refs`
- `last_seen_commit`

### 4. `navigation_registry.yaml`

最小字段：

- `entry_points`
- `route_definitions`
- `registration_points`
- `transition_calls`

### 5. `data_contracts.yaml`

最小字段：

- `apis[]`
- `apis[].name`
- `apis[].endpoint`
- `apis[].models`
- `models[]`
- `models[].name`
- `models[].fields`

### 6. `risk_zones.yaml`

最小字段：

- `risk_files[]`
- `risk_files[].path`
- `risk_files[].level`
- `risk_files[].reason`
- `auto_apply_policy`

### 7. `scan_meta.yaml`

最小字段：

- `schema_version`
- `generated_at`
- `repo_root`
- `scan_scope`
- `head_commit`
- `incremental_from`

## native-profile-v2（推荐上游资产）

当仓库级画像能力拆分为独立模块（`repo-profile-core`）时，`flutter-to-native` 推荐直接消费以下上游资产：

- `feature_registry.json`
- `host_mapping.json`

可选增强资产：

- `symbol_graph.jsonl`
- `relation_graph.jsonl`
- `scan_meta.yaml`

### `feature_registry.json` 最小字段

- `feature_id`
- `name`
- `description`
- `aliases`（选填）
- `related_features`（选填）

### `host_mapping.json` 最小字段

- `feature_id`
- `page_hosts`
- `action_hosts`
- `state_hosts`
- `data_hosts`
- `code_entities`（用于将 feature 直接定位到可修改文件）

## shared/capability_map.yaml

用途：

- 描述 Flutter 能力语义到 Native 候选触点的映射。

最小字段：

- `capabilities[]`
- `capabilities[].capability_id`
- `capabilities[].intent_summary`
- `capabilities[].flutter_refs`
- `capabilities[].native_candidates[]`
- `capabilities[].native_candidates[].path`
- `capabilities[].native_candidates[].confidence`
- `capabilities[].native_candidates[].risk`
- `capabilities[].native_candidates[].reason`
- `capabilities[].native_candidates[].evidence`

## 复用规则

- 需求级流程只读 profile 与 capability 资产，不直接从零全仓扫描
- 当输入 commit 变化较小时，优先增量刷新对应 feature 区域
- `confidence=low` 或 `risk=high` 的候选，默认流入 `manual_candidates`
