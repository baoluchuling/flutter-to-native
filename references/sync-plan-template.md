# `sync_plan.md` 固定模板

## 目的

本文档定义 `sync_plan.md` 的固定结构，用于 `Atlas Planner` 生成供用户审阅的同步计划。

目标：

- 让每次计划输出结构一致
- 让用户快速判断是否可以进入 apply
- 让 `Atlas Apply` 能稳定读取计划中的关键结论

## 模板使用规则

- `sync_plan.md` 是给人看的主计划文档，不是机器主契约
- 机器主契约仍然是 `requirement_sync_contract.yaml`
- `sync_plan.md` 负责总结、解释、列出触点和下一步动作
- 所有已计划修改但高风险的点，必须在 `sync_plan.md` 中可见

## 固定章节

`sync_plan.md` 固定使用以下章节顺序：

1. 需求概览
2. Flutter 证据概览
3. 目标原生结果
4. 计划触点
5. 计划动作
6. 不支持项与人工处理项
7. 风险摘要
8. 确认闸门

## 模板正文

建议正文如下：

```md
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
- `<file-path>`: <reason> | risk=`<low|medium|high>`

### 计划新建的文件

- `<file-path>`: <reason>
- `<file-path>`: <reason>

### 可能涉及但暂不自动处理的注册点

- `<file-path>`: <reason>

## 5. 计划动作

### UI

- <ui-action-1>
- <ui-action-2>

### 状态与交互

- <state-action-1>
- <state-action-2>

### Networking / Model

- <network-or-model-action-1>
- <network-or-model-action-2>

### 路由 / 注册

- <routing-action-1>

## 6. 不支持项与人工处理项

### 当前不支持项

- <unsupported-item-1>
- <unsupported-item-2>

### 需人工处理项

- <manual-item-1>
- <manual-item-2>

## 7. 风险摘要

- Overall Risk: `<low|medium|high>`
- Main Risks:
  - <risk-1>
  - <risk-2>

## 8. 确认闸门

- 当前尚未修改任何原生代码
- 如果确认本计划，将进入 `apply` 阶段
- Apply 阶段将依据 `requirement_sync_contract.yaml` 和本计划执行 patch
```

## 字段填充规则

### 标题

- 使用 `Sync Plan: <requirement-name>`
- `requirement-name` 应与 contract 中的 `requirement.name` 一致

### 需求概览

- `Requirement ID` 和 `Requirement Name` 直接来自 contract
- `Summary` 来自 `requirement.summary`
- `Scope Confidence` 来自 planner 对业务范围的置信度

### Flutter 证据概览

- 只列“最关键”的代码、diff 和测试，不列全量清单
- 全量详情可以在 `touchpoints.md` 或其他附录中展开

### 目标原生结果

- 用业务语言描述目标结果
- 不写成实现细节清单

### 计划触点

- 每个文件都要带原因
- 高风险文件必须标风险级别
- 如果某文件只作为人工候选，也必须写出来

### 计划动作

- 按职责域分组，不按文件分组
- 让用户先看懂“要做什么”，再看“改哪些文件”

### 不支持项与人工处理项

- `unsupported` 来自 contract
- 人工处理项来自 `patch_plan.manual_candidates` 及风险判断

### 风险摘要

- `Overall Risk` 是本次计划总风险等级
- `Main Risks` 不应超过 3 到 5 条

### 确认闸门

- 必须明确写出“尚未改代码”
- 必须明确写出“确认后才进入 apply”

## 生成要求

- `sync_plan.md` 应简洁可读，优先让用户快速批准或驳回
- 不要把它写成巨长变更清单
- 不要把所有技术细节都塞进主文档
- 细节留给 `touchpoints.md` 和 `risk_report.md`

## 与其他产物的关系

- `requirement_sync_contract.yaml`：机器主契约
- `sync_plan.md`：用户主审阅文档
- `touchpoints.md`：文件级附录
- `risk_report.md`：风险附录
