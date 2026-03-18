# Atlas Planner 置信度与升级规则

## 目的

本文档定义 `Atlas Planner` 的统一置信度模型和升级规则。

目标：

- 让 planner 对“自己有多确定”给出稳定表达
- 让低置信度结论自动进入风险和人工审查流程
- 为 `sync_plan.md`、`touchpoints.md`、`risk_report.md` 提供统一判定依据

## 置信度层次

V1 对以下三个层面分别评估置信度：

1. 业务范围置信度
2. Flutter 行为提炼置信度
3. 原生触点选择置信度

这三个层面不能混成一个值来判断。

## 统一等级

所有 Planner 置信度统一使用：

- `high`
- `medium`
- `low`

## 一、业务范围置信度

### 含义

表示 Planner 对“本次到底要同步哪个功能，以及边界是什么”的确定程度。

### `high`

通常满足：

- PRD 或需求描述清晰
- 验收点明确
- Flutter 代码范围与需求高度对应
- 测试或 PR diff 对关键流程有明确支撑

### `medium`

通常满足：

- 需求描述基本清楚，但边界有少量模糊
- Flutter 侧证据能支撑主要流程
- 仍有个别边缘行为需要人工确认

### `low`

通常满足任一项：

- PRD 缺失或严重不完整
- Flutter 代码涉及多个业务方向，无法明确切范围
- 测试不能支撑核心业务行为
- 不同输入之间存在明显冲突

## 二、Flutter 行为提炼置信度

### 含义

表示 Planner 对 Flutter 行为语义的抽取质量。

### `high`

通常满足：

- 页面结构清晰
- 关键交互明确
- 状态流可识别
- API / model 依赖可定位
- 测试覆盖关键行为

### `medium`

通常满足：

- 主路径可识别
- 部分边缘交互或状态不够明确
- API 或 model 的局部映射仍需推断

### `low`

通常满足任一项：

- 关键行为依赖大量隐式逻辑
- 状态流无法清晰识别
- 主要 API、model 或交互来源不明确
- 测试缺失且代码结构分散

## 三、原生触点选择置信度

### 含义

表示 Planner 对“原生里该改哪些文件”的判断可信度。

### `high`

通常满足：

- native profile 结构清晰
- 触点与业务范围高度对应
- 文件职责明确
- 风险可控

### `medium`

通常满足：

- 能识别主要触点
- 但部分文件职责有混合或边界不清
- 注册点或共享层仍需谨慎审查

### `low`

通常满足任一项：

- native profile 不完整
- 仓库结构混乱
- 高风险全局文件不可避免
- 候选触点很多，无法稳定收敛

## 总体计划置信度

总体计划置信度不是单独自由判断，而是从三类置信度收敛而来。

建议规则：

- 任一层为 `low`，总体计划置信度不得为 `high`
- 两层及以上为 `medium`，总体计划置信度通常为 `medium`
- 只有三层都为 `high`，总体计划置信度才允许为 `high`

## 升级规则

以下情况必须升级审查：

### 规则 1：任一层为 `low`

要求：

- 在 `risk_report.md` 中单独列出
- 在 `sync_plan.md` 中明确标注置信度

### 规则 2：触碰全局基础设施

包括：

- 全局路由
- 全局依赖注入
- 全局主题
- App 启动入口

要求：

- 默认升级为人工重点审查
- 即使触点选择置信度高，也不能静默进入 apply

当前实现补充：

- `AppDelegate`、`SceneDelegate`、`Router`、`Coordinator`、`TabBar` 等路径默认按全局基础设施处理
- 这类文件不会因为普通 fallback 被直接加入 `patch_plan.update`
- 只有在命中明确 routing / registration 信号，或 Flutter screen 证据缺少稳定 UIKit screen 触点时，才会进入 `manual_candidates`

### 规则 3：PRD 缺失且 Flutter 证据分散

要求：

- 业务范围置信度不得为 `high`
- `sync_plan.md` 中必须提示“需人工确认范围”

### 规则 4：高风险旧文件被计划更新

要求：

- 文件必须出现在 `touchpoints.md`
- 文件必须出现在 `risk_report.md`
- 需要给出具体风险原因

### 规则 5：存在不支持行为

要求：

- 写入 contract 的 `unsupported`
- 在 `sync_plan.md` 和 `risk_report.md` 中都要可见

## 输入降级规则

### 缺 PRD

- 业务范围置信度至少降一级
- 需要更多依赖 Flutter 测试和 PR diff

### 缺 Flutter 测试

- Flutter 行为提炼置信度至少降一级

### Native Profile 不完整

- 原生触点选择置信度至少降为 `low` 或 `medium`
- 高风险文件默认进入人工候选

### 低质量 fallback 候选

- `confidence < 0.45` 的 profile 触点默认不进入计划
- 如果 planner 只能拿到低质量 fallback，原生触点选择置信度不得为 `high`

### 输入互相冲突

- 冲突未消解前，业务范围置信度不得为 `high`

## 产物落地规则

### `requirement_sync_contract.yaml`

- 记录触点级 `confidence`
- 记录高风险文件
- 记录 `unsupported`

### `sync_plan.md`

- 展示总体计划置信度
- 展示业务范围置信度

### `touchpoints.md`

- 每个触点都应带 `Confidence`
- 高风险文件必须同时带 `Risk`

### `risk_report.md`

- 负责承接所有升级规则命中的项
- 负责解释“为什么这次需要更谨慎”

## V1 原则

- 低置信度不是错误，但必须显式暴露
- Planner 可以给出不完整结论，但不能伪装成高确定性结论
- 所有升级规则都优先服务于“先计划、后执行、风险可见”
