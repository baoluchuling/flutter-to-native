# `touchpoints.md` 固定模板

## 目的

本文档定义 `touchpoints.md` 的固定结构，用于 `Atlas Planner` 输出文件级触点附录。

目标：

- 把本次同步会涉及到的原生文件讲清楚
- 让用户知道哪些文件要改、为什么改、风险是什么
- 为后续 `Atlas Apply` 提供稳定的文件级输入参考

## 模板使用规则

- `touchpoints.md` 是 `sync_plan.md` 的文件级附录
- 任何计划更新的现有原生文件，都必须出现在这里
- 任何高风险触点，都必须在这里单独说明原因
- 这里只记录“文件级触点”，不展开完整 patch 内容

## 固定章节

`touchpoints.md` 固定使用以下章节顺序：

1. 触点概览
2. 现有文件触点
3. 新建文件触点
4. 注册点与全局触点
5. 人工候选触点

## 模板正文

建议正文如下：

```md
# Touchpoints: <requirement-name>

## 1. 触点概览

- Requirement ID: `<requirement-id>`
- Requirement Name: `<requirement-name>`
- Total Touchpoints: `<count>`
- Existing Files: `<count>`
- New Files: `<count>`
- Manual Candidates: `<count>`

## 2. 现有文件触点

### `<file-path>`

- Type: `<feature_screen|feature_flow|feature_service|shared_model|shared_ui|global_router|other>`
- Action: `update`
- Confidence: `<high|medium|low>`
- Risk: `<low|medium|high>`
- Reason: <why this file is involved>
- Expected Change:
  - <change-summary-1>
  - <change-summary-2>

### `<file-path>`

- Type: `<type>`
- Action: `update`
- Confidence: `<high|medium|low>`
- Risk: `<low|medium|high>`
- Reason: <why this file is involved>
- Expected Change:
  - <change-summary-1>

## 3. 新建文件触点

### `<file-path>`

- Type: `<feature_screen|feature_view|feature_component|feature_service|feature_model|other>`
- Action: `create`
- Confidence: `<high|medium|low>`
- Risk: `<low|medium|high>`
- Reason: <why this file should be created>
- Expected Responsibility:
  - <responsibility-1>
  - <responsibility-2>

## 4. 注册点与全局触点

### `<file-path>`

- Type: `<registration_point|global_router|dependency_root|theme_root|other>`
- Action: `<update|manual_candidate>`
- Confidence: `<high|medium|low>`
- Risk: `<low|medium|high>`
- Reason: <why this global file is relevant>
- Note:
  - <note-1>

## 5. 人工候选触点

### `<file-path>`

- Type: `<touchpoint-type>`
- Confidence: `<high|medium|low>`
- Risk: `<low|medium|high>`
- Reason: <why this should not be auto-patched in V1>
- Suggested Manual Action:
  - <manual-action-1>
  - <manual-action-2>
```

## 字段填充规则

### 标题

- 使用 `Touchpoints: <requirement-name>`
- `requirement-name` 必须与 contract 中的 `requirement.name` 一致

### 触点概览

- 只写汇总数字，不写细节
- 数字应与下方章节中的实际条目数一致

### 现有文件触点

- 只放“确实要更新”的现有文件
- 每个文件必须包含：
  - `Type`
  - `Action`
  - `Confidence`
  - `Risk`
  - `Reason`
- `Expected Change` 只写动作摘要，不写完整代码 patch

### 新建文件触点

- 只放计划新建的文件
- `Expected Responsibility` 说明这个文件存在的职责，而不是具体代码

### 注册点与全局触点

- 用来承载路由、依赖注入、全局配置、主题等特殊文件
- 这些文件即使不自动 patch，也应该在这里被显式列出

### 人工候选触点

- 这些文件通常来自：
  - `patch_plan.manual_candidates`
  - 高风险全局文件
  - 低置信度但可能相关的触点

## 类型建议值

触点类型建议值：

- `feature_screen`
- `feature_view`
- `feature_component`
- `feature_flow`
- `feature_service`
- `feature_model`
- `shared_model`
- `shared_ui`
- `registration_point`
- `global_router`
- `dependency_root`
- `theme_root`
- `other`

## 生成要求

- `touchpoints.md` 必须比 `sync_plan.md` 更细，但仍然保持可读
- 一个文件一个区块，不要把多个文件混在同一条 bullet 中
- 触点原因必须是可审阅的，而不是空泛描述
- 高风险文件必须显式带风险等级

## 与其他产物的关系

- `requirement_sync_contract.yaml`：机器主契约
- `sync_plan.md`：面向用户的主计划
- `touchpoints.md`：文件级触点附录
- `risk_report.md`：风险附录
