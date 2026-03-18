# Sync Plan: <requirement-name>

## 1. 需求概览

- Requirement ID: `<requirement-id>`
- Requirement Name: `<requirement-name>`
- Summary: <one-paragraph summary>
- Scope Confidence: `<high|medium|low>`

### 关键用户流程

- <user-flow-1>
- <user-flow-2>

### 关键验收点

- <acceptance-point-1>
- <acceptance-point-2>

## 2. Flutter 证据概览

### 主要代码范围

- <flutter-file-or-dir-1>
- <flutter-file-or-dir-2>

### PR Diff 摘要

- <diff-summary-1>
- <diff-summary-2>

### 测试证据

- <test-file-1>
- <test-file-2>

## 3. 目标原生结果

### 目标行为

- <native-outcome-1>
- <native-outcome-2>

### 期望与 Flutter 保持一致的点

- <parity-point-1>
- <parity-point-2>

## 4. 计划触点

### 需更新的现有文件

- `<file-path>`: <reason> | risk=`<low|medium|high>`

### 计划新建的文件

- `<file-path>`: <reason>

### 可能涉及但暂不自动处理的注册点

- `<file-path>`: <reason>

## 5. 计划动作

### UI

- <ui-action-1>

### 状态与交互

- <state-action-1>

### Networking / Model

- <network-or-model-action-1>

### 路由 / 注册

- <routing-action-1>

## 6. 不支持项与人工处理项

### 当前不支持项

- <unsupported-item-1>

### 需人工处理项

- <manual-item-1>

## 7. 风险摘要

- Overall Risk: `<low|medium|high>`
- Main Risks:
  - <risk-1>

## 8. 确认闸门

- 当前尚未修改任何原生代码
- 如果确认本计划，将进入 `apply` 阶段
- Apply 阶段将依据 `requirement_sync_contract.yaml` 和本计划执行 patch
