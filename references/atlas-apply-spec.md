# Atlas Apply 职责设计

## 目的

本文档定义 `Atlas Apply` 在 V1 中的职责范围。

目标：

- 明确 apply 只负责执行，不负责重新规划
- 明确 apply 的输入、边界、写文件规则和输出责任
- 让后续实现阶段不会把 apply 做成“边改边猜”的不稳定执行器

## 核心定位

`Atlas Apply` 是 `T2N Atlas` 的执行层。

它只在用户已确认 `sync_plan.md` 之后运行，并依据以下输入执行 patch：

- `native_operation_plan.yaml`
- `requirement_sync_contract.yaml`
- `sync_plan.md`
- `touchpoints.md`
- `risk_report.md`
- 目标 iOS 原生仓库

## 不属于 Apply 的职责

以下内容不属于 `Atlas Apply`：

- 重新定义需求范围
- 重新推断 Flutter 业务行为
- 重新选择主要原生触点
- 绕过确认流程直接改代码
- 擅自扩大 patch 范围

如果执行时发现计划和实际代码差异过大，应中止执行并要求回到 planner 阶段，而不是在 apply 阶段临时重规划。

## 输入前提

进入 apply 前必须满足：

- 存在有效的 `native_operation_plan.yaml`
- 存在有效的 `requirement_sync_contract.yaml`
- 存在与 contract 对应的 `sync_plan.md`
- 存在 `touchpoints.md`
- 用户已明确批准当前计划
- 目标 iOS 仓库路径可读写

如果任一条件不满足，apply 不能启动。

## V1 主要职责

### 1. 校验执行前置条件

包括：

- 校验 contract 文件存在且可读
- 校验 plan 文件存在且可读
- 校验目标仓库路径有效
- 校验计划中的关键触点文件是否存在或应被创建

### 2. 加载已批准的计划

Apply 必须把以下信息加载进执行上下文：

- 需求标识
- operation 列表（create / update / manual）
- 目标行为摘要
- 计划创建文件
- 计划更新文件
- 人工候选文件
- 不支持项

### 3. 执行文件级 patch

包括：

- 新建原生文件
- 更新现有原生文件
- 仅在已批准触点范围内写入代码

V1.1 最小生成策略：

- 对已有 `.swift` 文件，优先追加可编译的 `extension` 骨架
- 对 `create` 场景，按触点类型生成最小可编译的 Swift 文件模板
- 对无法稳定识别 Swift 类型的文件，优先转为 `manual_review`
- 过渡期仍允许 `marker_block` 回退，但不再允许 `legacy marker` 路径

执行原则：

- 先处理低风险、局部文件
- 后处理共享或注册类文件
- 不在计划外新增触点

### 3a. Model 字段写入规则

修改 model 文件时，apply 必须：

- 严格遵循 sync_plan 中的字段对齐表，逐字段写入
- 先读取目标 model 文件全文，确认现有字段的声明模式
- 新字段的 nil/非 nil 策略必须与对齐表一致，不得自行决定
- 如果目标 model 使用 `Modelable` 协议（字段用默认值 `var x = ""`），新字段也应遵循此模式，除非对齐表明确要求 optional
- 写入后检查所有调用方的 optional chaining 是否完整
- 如果发现对齐表与实际代码不一致，中止并回到 planner

### 3b. UI 生成规则

生成 UI 代码时，apply 必须：

- **禁止**从 Flutter Widget 树直接翻译（Container→UIView、Stack→不对等）
- Flutter 代码仅作为逻辑参考（交互流程、状态机、数据绑定）
- 视觉实现必须基于设计稿或 sync_plan 中明确列出的视觉参数
- 使用项目已有的 UI 约定：SnapKit 约束、`UIColor(hex:)` helper、`.F_bold()` 字体 helper、`Lg.t(for:)` 本地化
- 复杂 UI（渐变、动画、自定义绘制）在生成前需确认关键参数
- 如果没有设计稿且 sync_plan 未提供视觉参数，标记为 `manual_review` 而非强行生成

### 3c. 入口修改规则

修改现有文件入口时，apply 必须：

- 严格遵循 sync_plan 中通过功能场景定位的方法，不得自行重新定位
- 先完整读取目标文件，确认 sync_plan 中标注的方法确实承担对应的功能职责
- **禁止从 Flutter 方法名 grep iOS 代码来寻找修改位置**——入口定位是 plan 阶段的职责，apply 只负责在已确认的位置执行
- 修改后验证：(1) 上游调用签名兼容 (2) 下游数据源可用 (3) 不破坏现有功能
- 如果发现 sync_plan 的入口定位有误（方法职责不匹配），中止并回到 planner，不得临场重规划

### 4. 记录实际改动

每个被改动文件都需要记录：

- 路径
- 动作类型：`create` 或 `update`
- 与计划是否一致
- 是否存在执行时偏差
- 生成模式：`swift_extension`、`swift_file`，过渡期允许 `marker_block`（必须显式标记原因）
- 片段类型：`feature_screen`、`feature_logic`、`feature_view`、`feature_service`、`feature_model`、`other`
- UI 语义角色：`primary_screen`、`auxiliary_dialog`、`auxiliary_overlay`、`component_view`、`non_ui`
- 关联的 Flutter 代表页面：`source_screens`
- 如果插入了现有 UIKit 入口，还要记录 `hook_target / hook_inserted`

V1.2 语义补丁补充：

- Apply 需要优先读取 contract 中的 `selected_touchpoints[].ui_role`
- 对 `primary_screen`，生成的 Swift patch 需要体现主页面安装与渲染骨架
- 对 `auxiliary_dialog`，生成的 Swift patch 需要体现辅助弹层/弹窗入口骨架
- 对 `auxiliary_overlay`，生成的 Swift patch 需要体现覆盖层刷新与交互骨架
- 对 `component_view / non_ui`，继续走较保守的通用骨架

V1.3 UIKit 挂接补充：

- 对已有 Swift 文件的 `update` 场景，apply 应优先尝试把 install 调用插入现有入口方法
- 典型入口包括：`viewDidLoad / setup / bind / refresh / update / init`
- 如果没有找到稳定入口，可以退回到“仅追加 extension”，但要在结果里显式记录 fallback
- 当触点是 `feature_screen + component_view` 组合时，仍应优先尝试 `viewDidLoad / screen lifecycle`，而不是只走 `init / setupView`
- apply 和 verify 的实际执行必须串行，不能在同一个 run 上并发启动 `apply` 与 `verify`

### 5. 输出 apply 阶段结果

至少输出：

- 实际改动的文件清单
- 未执行项
- 因风险转为人工处理的项
- 执行中出现的异常或偏差

## 写文件边界

Apply 允许写入：

- 目标原生仓库中已批准的文件路径
- `.ai/t2n/runs/<run-id>/apply_result.json`
- `.ai/t2n/runs/<run-id>/apply_report.md`

Apply 不允许写入：

- 计划未列出的原生文件
- `.ai/t2n/native-profile/`
- 与当前 run 无关的历史产物目录

## 计划与执行一致性规则

Apply 必须遵守以下一致性规则：

- `native_operation_plan.operations` 是执行主驱动
- `requirement_sync_contract.patch_plan` 仅作为一致性校验，不再作为主循环驱动
- `touchpoints.md` 中未出现的现有文件，不得被更新
- `operations.action=create_file` 之外的文件，不得被当作“计划新建”
- `operations.action=edit_existing` 之外的文件，不得被当作“计划更新”
- `manual_candidates` 默认不自动执行，除非计划中明确说明已批准自动处理

## 中止条件

以下情况应中止 apply：

- 目标文件与计划描述明显不一致
- 计划要求修改的文件不存在，且不应是创建场景
- 风险文件需要超出既定范围的修改
- 运行时发现必须扩大 patch 范围才能完成功能

中止后要求：

- 不继续扩大执行
- 记录中止原因
- 回到 planner 重新出计划

## 输出责任

Apply 阶段至少要为后续 verify 留下这些结果：

- 已执行文件清单
- 未执行文件清单
- 被跳过的人工候选项
- 计划与实际不一致点
- 执行中的关键说明
- 一份 machine-readable 的 `apply_result.json`

## 与后续 Verify 的关系

`Atlas Apply` 负责“做了什么”，`Atlas Verify` 负责“做得够不够”。

Apply 不负责证明功能已经完整符合 Flutter，只负责：

- 在批准范围内完成 patch
- 记录实际执行事实

## V1 原则

- Apply 是受控执行器，不是自由创作器
- 能中止时优先中止，不靠临场扩范围硬做完
- 所有执行偏差都要显式记录
