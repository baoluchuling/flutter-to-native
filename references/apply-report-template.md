# `apply_report.md` 固定模板

## 目的

本文档定义 `apply_report.md` 的固定结构，用于 `Atlas Apply` 输出执行结果报告。

目标：

- 记录本次实际执行了什么
- 对照计划说明哪些已执行、哪些未执行
- 显式暴露执行偏差和中止原因

## 模板使用规则

- `apply_report.md` 是 apply 阶段的事实报告
- 它只记录实际执行情况，不重复做需求规划
- 它必须与 `sync_plan.md`、`touchpoints.md` 对照一致
- 一旦存在执行偏差，必须明确写出

## 固定章节

`apply_report.md` 固定使用以下章节顺序：

1. 执行概览
2. 已执行创建项
3. 已执行更新项
4. 未执行项
5. 人工保留项
6. 执行偏差与异常
7. 后续建议

## 模板正文

建议正文如下：

```md
# Apply Report: <requirement-name>

## 1. 执行概览

- Requirement ID: `<requirement-id>`
- Requirement Name: `<requirement-name>`
- Apply Status: `<completed|partial|aborted>`
- Planned Creates: `<count>`
- Planned Updates: `<count>`
- Actual Creates: `<count>`
- Actual Updates: `<count>`

## 2. 已执行创建项

### `<file-path>`

- Action: `create`
- Status: `<completed|partial>`
- Planned: `yes`
- Notes:
  - <note-1>

## 3. 已执行更新项

### `<file-path>`

- Action: `update`
- Status: `<completed|partial>`
- Planned: `yes`
- Notes:
  - <note-1>

## 4. 未执行项

### `<file-path-or-item>`

- Planned Action: `<create|update>`
- Reason Not Applied:
  - <reason-1>

## 5. 人工保留项

### `<file-path-or-item>`

- Reason:
  - <reason-1>
- Suggested Follow-up:
  - <manual-action-1>

## 6. 执行偏差与异常

- <deviation-or-error-1>
- <deviation-or-error-2>

## 7. 后续建议

- <next-step-1>
- <next-step-2>
```

## 字段填充规则

### 执行概览

- `Apply Status` 建议值：
  - `completed`
  - `partial`
  - `aborted`
- 如果中途终止，必须使用 `aborted`

### 已执行创建项 / 已执行更新项

- 只列实际执行成功或部分执行的项
- 每个文件都必须带 `Planned: yes`
- 如果某文件存在偏差，不要藏在这里，要同步写入“执行偏差与异常”

### 未执行项

- 只放计划内但未落地的项
- 原因必须具体，不能只写“失败”

### 人工保留项

- 与 `patch_plan.manual_candidates` 和执行中转人工的项保持一致

### 执行偏差与异常

- 记录计划与实际不一致的地方
- 记录中止原因
- 记录执行时发现但计划阶段未暴露的问题

### 后续建议

- 如果 apply 成功但 verify 仍需重点关注，就在这里提示
- 如果 apply 被中止，就明确建议回到 planner 或人工处理

## 生成要求

- `apply_report.md` 必须基于真实执行结果生成
- 不得把未执行项写成已执行
- 不得省略中止原因
- 不做风险分析扩写，风险解释交给 `risk_report.md`

## 与其他产物的关系

- `sync_plan.md`：计划做什么
- `touchpoints.md`：涉及哪些文件
- `apply_report.md`：实际做了什么
- `verify_report.md`：做完之后够不够
