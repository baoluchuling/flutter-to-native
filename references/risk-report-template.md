# `risk_report.md` 固定模板

## 目的

本文档定义 `risk_report.md` 的固定结构，用于 `Atlas Planner` 输出本次同步计划的风险附录。

目标：

- 让用户快速判断本次计划的主要风险
- 把高风险触点、行为缺口、测试缺口从主计划中拆出来
- 为后续 apply 阶段设置明确的审查重点

## 模板使用规则

- `risk_report.md` 是 `sync_plan.md` 的风险附录
- 必须把技术风险和产品一致性风险分开写
- 任何 `low confidence` 的关键结论都必须在这里出现
- 任何高风险文件都必须在这里被显式点名

## 固定章节

`risk_report.md` 固定使用以下章节顺序：

1. 风险总览
2. 架构与仓库不确定性
3. 高风险旧文件
4. Flutter 不支持或难以自动同步的行为
5. 一致性风险
6. 测试与验证缺口
7. 建议审查重点

## 模板正文

建议正文如下：

```md
# Risk Report: <requirement-name>

## 1. 风险总览

- Requirement ID: `<requirement-id>`
- Requirement Name: `<requirement-name>`
- Overall Risk: `<low|medium|high>`
- Scope Confidence: `<high|medium|low>`
- Native Impact Confidence: `<high|medium|low>`

### 主要风险

- <risk-summary-1>
- <risk-summary-2>

## 2. 架构与仓库不确定性

- <uncertainty-1>
- <uncertainty-2>

## 3. 高风险旧文件

### `<file-path>`

- Risk: `<medium|high>`
- Reason: <why this file is risky>
- Potential Impact:
  - <impact-1>
  - <impact-2>

## 4. Flutter 不支持或难以自动同步的行为

- <unsupported-behavior-1>
- <unsupported-behavior-2>

## 5. 一致性风险

- <parity-risk-1>
- <parity-risk-2>

## 6. 测试与验证缺口

- <test-gap-1>
- <test-gap-2>

## 7. 建议审查重点

- <review-focus-1>
- <review-focus-2>
```

## 字段填充规则

### 风险总览

- `Overall Risk` 是本次计划总体风险等级
- `Scope Confidence` 来自业务范围推断置信度
- `Native Impact Confidence` 来自原生触点选择置信度

### 架构与仓库不确定性

- 放项目结构不清晰、画像证据不足、模块边界混乱等问题
- 如果没有明显问题，也建议写明“未发现高影响结构性不确定性”

### 高风险旧文件

- 这里只列 `risk=high` 或关键 `risk=medium` 文件
- 文件级风险应与 `touchpoints.md` 保持一致

### Flutter 不支持或难以自动同步的行为

- 来自 contract 中的 `unsupported`
- 也可补充“理论可做但 V1 不自动做”的行为

### 一致性风险

- 指最终结果可能与 Flutter 表现不完全一致的点
- 例如复杂动画、边缘状态、全局导航行为、共享组件差异

### 测试与验证缺口

- 指测试不足、验收条件不全、无法自动验证的部分
- 如果缺少 Flutter 测试，必须显式指出

### 建议审查重点

- 给 apply 阶段和人工 review 提供明确关注点
- 建议控制在 3 到 5 条

## 风险等级建议值

- `low`
- `medium`
- `high`

## 生成要求

- `risk_report.md` 重点在“风险说明”，不重复主计划内容
- 不把所有触点都堆进这里，只点关键风险
- 风险必须带原因，不能只写结论
- 如果某项风险可以通过人工审查缓解，应明确写出

## 与其他产物的关系

- `requirement_sync_contract.yaml`：记录机器可消费的不支持项和风险点
- `sync_plan.md`：主计划
- `touchpoints.md`：文件级触点附录
- `risk_report.md`：风险附录
