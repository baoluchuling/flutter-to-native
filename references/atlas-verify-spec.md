# Atlas Verify 职责设计

## 目的

本文档定义 `Atlas Verify` 在 V1 中的职责范围。

目标：

- 明确 verify 负责验证覆盖，不负责重新规划和重新执行
- 明确 verify 的输入、验证目标、输出责任和失败处理方式
- 为后续 `verify_report.md` 和实现阶段提供稳定边界

## 核心定位

`Atlas Verify` 是 `T2N Atlas` 的验证层。

它在 `Atlas Apply` 之后运行，负责回答：

- 本次已执行的 patch 是否覆盖了 contract 中的核心目标
- 哪些计划项已完成
- 哪些计划项未完成
- 哪些地方存在行为偏差或验证缺口

## 不属于 Verify 的职责

以下内容不属于 `Atlas Verify`：

- 重新定义业务范围
- 重新规划触点
- 重新执行 patch
- 在验证过程中直接修改源码
- 因验证失败而自行扩大 patch 范围

如果 verify 发现明显缺失，应输出问题并要求回到 planner 或 apply 阶段，而不是在 verify 阶段直接补代码。

## 输入前提

进入 verify 前必须满足：

- 存在有效的 `native_operation_plan.yaml`
- 存在有效的 `requirement_sync_contract.yaml`
- 存在对应的 `sync_plan.md`
- 存在 `apply_report.md`
- 存在 `apply_result.json`
- 目标 iOS 仓库为 apply 后状态

如果这些前提不满足，verify 不能启动。

## V1 主要职责

### 1. 加载验证上下文

包括：

- contract
- sync plan
- touchpoints
- risk report
- apply report

目的：

- 建立“计划了什么”和“实际做了什么”的对照关系

### 2. 校验文件覆盖情况

包括：

- `operations.action=create_file` 的文件是否已创建
- `operations.action=edit_existing` 的文件是否已更新
- `operations.action=manual_review` 是否被保留为人工项

输出：

- 文件级完成情况

V1.1 验证补充：

- verify 以 `generated patch` 为主，不再依赖旧 `legacy marker` 判定
- 当 `apply_result.json` 中存在 `generation_mode` 时，应优先按生成模式解释结果
- 对 `generated patch`，verify 需要继续检查结构完整性，而不只确认 marker 存在
- 对 `feature_screen / feature_logic / feature_view / feature_service / feature_model`，verify 需要校验期望方法名是否存在
- 当 `touched_files` 中存在 `ui_role` 时，verify 需要按 `primary_screen / auxiliary_dialog / auxiliary_overlay / component_view / non_ui` 使用不同的期望方法名

### 3. 校验行为覆盖情况

依据 contract 中的这些信息做覆盖判断：

- `behavior.user_flows`
- `behavior.acceptance_points`
- `behavior.states`
- `unsupported`

V1 的验证重点不是运行时自动化，而是：

- 计划与结果是否对齐
- 核心行为是否有对应实现落点
- 不支持项是否被正确保留

V1.2 验证补充：

- 对 `swift_extension`，verify 需要确认生成块内存在 `extension <Type>` 和对应的 install / render / interaction / request 方法
- 对 `swift_file`，verify 需要确认新文件中的主类型名和期望方法
- 对 `marker_block`，verify 只能给到 `partial` 或更低的结构结论，不能提升为强结构通过
- 对行为验证，verify 需要优先检查生成数组中的结构化映射：
  - `atlasUserFlows`
  - `atlasAcceptancePoints`
  - `atlasStateNames`
  - `atlasInteractionNames`
- 对行为验证，verify 需要优先在与当前 `ui_role` 匹配的 touched files 中寻找映射，而不是无差别扫描所有文件

V1.3 UIKit 挂接补充：

- 对 `update + swift_extension + ui_role in {primary_screen, auxiliary_dialog, auxiliary_overlay, component_view}` 的场景
- verify 需要确认 install 方法不仅存在于生成块中，还被挂接到了生成块之外的原始文件入口
- 如果只存在生成块而不存在入口调用，结构结论应降为 `partial`

### 4. 校验风险与偏差

包括：

- apply 是否偏离已批准计划
- 高风险文件是否被实际触碰
- 是否出现计划外改动
- 是否有触点未按计划处理

### 5. 输出验证结论

至少输出：

- 已覆盖项
- 未覆盖项
- 人工后续项
- 已知偏差
- 验证中无法确认的项

## 验证对象

Verify 主要验证以下十类对象：

1. 文件层
- 计划创建和更新的文件是否落地

2. 行为层
- 关键用户流程和验收点是否有明确实现落点

3. 风险层
- 高风险项是否被正确暴露和记录

4. 边界层
- 是否出现越过计划范围的执行

5. 结构层
- 目标类型、方法名、片段类型是否与 contract / apply_result 一致

6. 生成模式层
- `swift_extension / swift_file` 是否与触点类型和动作匹配
- 过渡期若出现 `marker_block`，只能判定为 `partial` 或更低

7. **类型安全层（新增）**
- 对照 sync_plan 中的字段对齐表，逐字段验证 model 文件中的声明
- 检查新增字段的 nil/非 nil 策略是否与对齐表一致
- 检查现有 model 协议约定（如 `Modelable` 的默认值模式）是否被遵守
- 检查所有使用新字段的调用方，optional chaining 是否完整
- 不一致项标记为 `type_safety_mismatch`

8. **入口正确性层（新增）**
- 对照 sync_plan 中的调用链分析，验证修改的入口方法位置是否正确
- 检查上游调用者的签名是否兼容
- 检查下游被调用方法/数据源是否可用
- 检查是否破坏了现有功能的调用路径
- 入口不匹配项标记为 `entry_point_mismatch`

9. **UI 合理性层（新增）**
- 检查生成的 UI 代码是否使用项目约定（SnapKit 约束、UIColor(hex:) helper、.F_bold() 字体 helper）
- 检查是否存在 Flutter 风格的直接翻译痕迹（如无意义的嵌套 UIView 对应 Container）
- 检查关键视觉参数是否与 sync_plan 中的参数清单一致
- UI 不合理项标记为 `ui_fidelity_issue`

10. 语法层
- 在启用可选检查时，验证 touched Swift 文件是否通过 `swiftc -parse`

## 写文件边界

Verify 允许写入：

- `.ai/t2n/runs/<run-id>/verify_result.json`
- `.ai/t2n/runs/<run-id>/verify_report.md`

Verify 不允许写入：

- 原生源码
- native profile
- 其他 run 的产物目录

## 验证结果分类

V1 建议使用以下分类：

- `verified`
- `partial`
- `missing`
- `manual`
- `unknown`

说明：

- `verified`：已确认覆盖
- `partial`：部分覆盖，但还不完整
- `missing`：计划中应有，但未覆盖
- `manual`：保留给人工处理
- `unknown`：当前无法确认

当前实现补充：

- verify 结果会额外汇总 `structure_coverage`
- verify 结果会额外汇总 `generation_coverage`
- verify 结果会额外汇总 `semantic_coverage`
- verify 结果会额外汇总 `data_layer_coverage`
- verify 结果会额外汇总 `type_safety_coverage`（新增：字段 nil/非 nil 对齐覆盖率）
- verify 结果会额外汇总 `entry_point_coverage`（新增：入口调用链正确性覆盖率）
- verify 结果会额外汇总 `ui_fidelity_coverage`（新增：UI 实现合理性覆盖率）
- verify 在启用 `--swift-parse-check` 时会额外汇总 `syntax_coverage`
- 文件级结果会记录 `marker_status / structure_status / generation_status`
- `partial / missing / unknown` 会尽量带上结构、生成模式或语法层面的具体原因

## 失败与中止规则

以下情况应标记为验证失败或需回退：

- apply report 缺失，无法确认实际执行
- 计划内关键文件未生成或未更新
- 出现计划外高风险改动
- 关键验收点找不到任何实现落点

处理方式：

- 不自动修复
- 在 `verify_report.md` 中明确写出
- 建议回到 planner 或 apply

## 与 Apply 的关系

`Atlas Apply` 负责“执行了什么”，`Atlas Verify` 负责“这些执行结果是否足够”。

Verify 必须以 apply 的实际产出为事实基础，而不是重新假设代码已经正确生成。

## V1 原则

- Verify 是检查器，不是补丁执行器
- 验证不完整时，优先暴露缺口，而不是掩盖问题
- 所有计划外偏差都必须显式记录
