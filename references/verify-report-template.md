# `verify_report.md` 固定模板

## 目的

本文档定义 `verify_report.md` 的固定结构，用于 `Atlas Verify` 输出验证结论报告。

目标：

- 说明本次 apply 后哪些目标已经覆盖
- 说明哪些目标未覆盖、部分覆盖或无法确认
- 为下一步继续 apply、回到 planner 或转人工处理提供依据

## 模板使用规则

- `verify_report.md` 是验证结论，不是执行日志
- 它必须基于 `apply_report.md` 和 contract 进行判断
- 它必须显式区分：已验证、部分验证、缺失、人工项、未知项
- 它不应重新规划 patch

## 固定章节

`verify_report.md` 固定使用以下章节顺序：

1. 验证概览
2. 文件覆盖结果
3. 结构与生成模式校验
4. 行为覆盖结果
5. 人工项与不支持项
6. 偏差与缺口
7. 验证结论
8. 下一步建议

## 模板正文

建议正文如下：

```md
# Verify Report: <requirement-name>

## 1. 验证概览

- Requirement ID: `<requirement-id>`
- Requirement Name: `<requirement-name>`
- Verify Status: `<verified|partial|failed>`
- File Coverage: `<verified|partial|missing|unknown>`
- Behavior Coverage: `<verified|partial|missing|unknown>`
- Structure Coverage: `<verified|partial|missing|unknown>`
- Generation Coverage: `<verified|partial|missing|unknown>`

## 2. 文件覆盖结果

### 已验证文件

- `<file-path>`: `verified`
- `<file-path>`: `partial`

### 缺失或未确认文件

- `<file-path>`: `<missing|unknown>` | <reason>

## 3. 结构与生成模式校验

### 结构已验证文件

- `<file-path>`: `verified`

### 结构待补强文件

- `<file-path>`: `<partial|missing|unknown>` | <reason>

### 生成模式校验

- `<file-path>`: `<partial|missing|unknown>` | <reason>

## 4. 行为覆盖结果

### 已覆盖行为

- `<user-flow-or-acceptance-point>`: `verified`

### 部分覆盖行为

- `<user-flow-or-acceptance-point>`: `partial` | <reason>

### 未覆盖或无法确认行为

- `<user-flow-or-acceptance-point>`: `<missing|unknown>` | <reason>

## 5. 人工项与不支持项

### 人工项

- `<manual-item-1>`
- `<manual-item-2>`

### 不支持项

- `<unsupported-item-1>`
- `<unsupported-item-2>`

## 6. 偏差与缺口

- <deviation-or-gap-1>
- <deviation-or-gap-2>

## 7. 验证结论

- Overall Result: `<verified|partial|failed>`
- Summary:
  - <summary-1>
  - <summary-2>

## 8. 下一步建议

- <next-step-1>
- <next-step-2>
```

## 字段填充规则

### 验证概览

- `Verify Status` 建议值：
  - `verified`
  - `partial`
  - `failed`
- `File Coverage` 和 `Behavior Coverage` 用于快速判断当前缺口主要在哪一层

### 文件覆盖结果

- 应以 `patch_plan.create`、`patch_plan.update` 和 apply 实际结果为依据
- 如果文件存在但结果不完整，可标 `partial`

### 结构与生成模式校验

- 对 `swift_extension` 应优先检查 extension 目标类型和期望方法名
- 对 `swift_file` 应优先检查新文件主类型和期望方法名
- 对 `marker_block` 默认不能给出强结构通过结论

### 行为覆盖结果

- 应以 `behavior.user_flows`、`behavior.acceptance_points`、`behavior.states` 为依据
- 无法确认时必须标 `unknown`，不能默认为已覆盖

### 人工项与不支持项

- 人工项来自 `manual_candidates` 或 verify 中确认仍需人工处理的事项
- 不支持项来自 contract 的 `unsupported`

### 偏差与缺口

- 用于承接“计划与实际不一致”或“执行后仍然缺的部分”
- 不与风险报告重复，重点写验证发现的问题

### 验证结论

- `Overall Result` 应收敛全局判断
- 如果关键验收点未覆盖，通常不能标 `verified`

### 下一步建议

- 如果验证通过，可建议进入人工验收或收尾
- 如果验证部分通过，可建议继续 apply 或补充人工处理
- 如果验证失败，可建议回退到 planner 或 apply

## 结果等级建议

- `verified`
- `partial`
- `failed`

## 生成要求

- `verify_report.md` 必须对 contract 负责，而不是只对 apply 负责
- 不得把未知项写成已验证
- 不得隐藏关键验收点缺失
- 不对源码做任何修改

## 与其他产物的关系

- `requirement_sync_contract.yaml`：验证依据
- `apply_report.md`：执行事实来源
- `verify_report.md`：覆盖结论
