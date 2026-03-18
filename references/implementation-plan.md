# T2N Atlas V1 计划

## 项目命名

- 项目代号：`T2N`
- 项目名称：`Atlas`
- 完整名称：`T2N Atlas`

命名规则：

- `T2N` 用于内部路径、缓存目录、脚本前缀、技术标识。
- `Atlas` 或 `T2N Atlas` 用于面向人的文档、agent 名称、计划和报告标题。

## V1 目标

构建一个手动触发的系统：把一个已经在 Flutter 中完成实现的产品需求，同步到现有的 iOS 原生项目中。目标原生栈为 `Swift + UIKit`。

V1 不做整 app 重生成。V1 只聚焦于“一个完整功能”的同步，并以对现有 iOS 代码库进行 `scoped patch` 的方式落地。

## 已对齐术语

### 产品需求同步

指某个业务需求已经在 Flutter 侧落地完成，系统以这份 Flutter 实现作为原生同步的来源样本。

### 功能同步

这是 V1 的交付单位。一个功能可以是 app 内的独立完整能力，不要求只是很小的改动。

### Scoped Patch

这是 V1 的技术执行方式。即使业务范围是一个完整功能，系统也只修改与该功能相关的原生文件，而不是重建整个原生 app。

关键说明：

- 一个完整独立功能属于 V1 范围。
- “不重建整个 app”是实现边界，不是业务边界。

## 系统包含内容

- 从 PRD、工单或需求描述中接收需求
- 分析 Flutter 实现
- 分析 Flutter PR diff
- 分析测试用例和验收信号
- 扫描现有 Flutter / iOS 工程
- 维护可复用的项目级扫描资产（不是一次性 run 文件）
- 发现原生触点文件
- 生成 `feature_intent_spec`
- 生成 `native_operation_plan`
- 生成 `requirement_sync_contract`
- 生成供确认的同步计划
- 在确认后执行原生代码 patch
- 输出验证结果和报告

## V1 范围

### 目标平台

- iOS
- Swift
- UIKit

### 触发方式

- 仅手动触发

### V1 成功标准

- 同一个完整功能可以在 iOS app 中跑通，行为与 Flutter 实现保持一致。
- 系统在必要时可以新增文件，也可以修改现有原生文件。
- 任何代码修改前都必须先生成计划。

## 输入

V1 应尽量利用所有可用输入：

- PRD 或需求描述
- Flutter 功能代码
- Flutter PR diff
- Flutter 测试
- 现有 iOS 原生仓库

Planner 需要综合这些输入，而不是假设任意单一输入就足够。

## 核心原则

1. 把 Flutter 当作“已完成需求”的来源样本，而不是逐行翻译对象。
2. 在做同步之前，先做原生仓库画像。
3. 先出计划，再改代码。
4. 优先抽取语义和行为，而不是逐行迁移代码。
5. 当功能需要时，允许修改现有原生文件。
6. V1 不做整 app 重生成。
7. 每次都显式输出不支持项和风险项。

## 运行时数据目录

所有扫描结果、contract、计划和报告，默认都写入目标原生仓库下的 `.ai/t2n/`。这是 `T2N Atlas` 的标准运行工作区。

推荐目录结构：

```text
.ai/t2n/
  flutter-profile/
    repo_architecture.yaml
    feature_catalog.yaml
    symbol_index.jsonl
    navigation_registry.yaml
    data_contracts.yaml
    risk_zones.yaml
    scan_meta.yaml
  native-profile/
    repo_architecture.yaml
    feature_catalog.yaml
    symbol_index.jsonl
    navigation_registry.yaml
    data_contracts.yaml
    risk_zones.yaml
    scan_meta.yaml
  shared/
    capability_map.yaml
  runs/
    2026-03-15-requirement-foo/
      feature_intent_spec.yaml
      native_operation_plan.yaml
      requirement_sync_contract.yaml
      sync_plan.md
      touchpoints.md
      risk_report.md
      apply_result.json
      apply_report.md
      verify_result.json
      verify_report.md
```

## 详细设计索引

- 查看 [atlas-profiler-spec.md](atlas-profiler-spec.md)，了解 `Atlas Profiler` 的扫描范围、缓存失效规则和输出文件定义。
- 查看 [atlas-profiler-implementation.md](atlas-profiler-implementation.md)，了解 `Atlas Profiler` 的 CLI、扫描阶段、输出 schema 和启发式优先级。
- 查看 [profile-assets-spec.md](profile-assets-spec.md)，了解可复用项目级扫描资产的标准结构与字段约束。
- 查看 [atlas-planner-spec.md](atlas-planner-spec.md)，了解 `Atlas Planner` 的 contract 字段、同步计划结构和确认流程。
- 查看 [atlas-planner-implementation.md](atlas-planner-implementation.md)，了解 `Atlas Planner` 的执行阶段、内部数据结构、输入优先级和写文件规则。
- 查看 [feature-intent-spec.md](feature-intent-spec.md)，了解 `feature_intent_spec.yaml` 的字段和提取规则。
- 查看 [native-operation-plan-spec.md](native-operation-plan-spec.md)，了解 `native_operation_plan.yaml` 的字段和执行规则。
- 查看 [requirement-sync-contract-schema.md](requirement-sync-contract-schema.md)，了解 `requirement_sync_contract.yaml` 的字段级 schema 和约束。
- 查看 [sync-plan-template.md](sync-plan-template.md)，了解 `sync_plan.md` 的固定章节和填充规则。
- 查看 [touchpoints-template.md](touchpoints-template.md)，了解 `touchpoints.md` 的固定章节和文件级触点填写规则。
- 查看 [risk-report-template.md](risk-report-template.md)，了解 `risk_report.md` 的固定章节和风险填写规则。
- 查看 [planner-confidence-rules.md](planner-confidence-rules.md)，了解 Planner 的置信度计算与升级规则。
- 查看 [atlas-apply-spec.md](atlas-apply-spec.md)，了解 `Atlas Apply` 的输入前提、执行边界和中止条件。
- 查看 [atlas-verify-spec.md](atlas-verify-spec.md)，了解 `Atlas Verify` 的验证目标、结果分类和失败处理方式。
- 查看 [apply-report-template.md](apply-report-template.md)，了解 `apply_report.md` 的固定结构和填写规则。
- 查看 [verify-report-template.md](verify-report-template.md)，了解 `verify_report.md` 的固定结构和填写规则。
- 查看 [approval-safety-rules.md](approval-safety-rules.md)，了解从确认到执行的安全门禁规则。
- 查看 [runtime-lifecycle.md](runtime-lifecycle.md)，了解 `.ai/t2n/` 产物生命周期、复用策略和清理建议。
- 查看 [integration-checklist.md](integration-checklist.md)，了解真实项目接入前需要满足的输入、仓库和执行条件。
- 查看 [flutter-profiler-spec.md](flutter-profiler-spec.md)，了解 `Flutter Profiler` 的目标、输入边界、仓库级画像和需求级 digest 设计。
- 查看 [flutter-profiler-schema.md](flutter-profiler-schema.md)，了解 `Flutter Profiler` 输出文件的字段级 schema 和与 planner 的映射关系。
- 查看 [flutter-profiler-integration.md](flutter-profiler-integration.md)，了解 `Flutter Profiler` 与 `Atlas Planner` 的输入优先级、冲突检测和回退规则。
- 查看 [phase25-migration-checklist.md](phase25-migration-checklist.md)，了解阶段 25 的脚本切换、旧分支删除与回归标准。

## 协作规则

本计划文档是 `T2N Atlas` 的唯一阶段跟踪表。

执行规则：

- 每进入一个新阶段，先在这里列出该阶段要做的事。
- 每完成一项，就在这里更新状态。
- 同一时间只允许一个当前阶段处于活跃状态。
- 前序阶段未完成时，不进入后序阶段。
- 如果某阶段依赖外部真实材料且暂时不具备，可显式标记为“延后”，并先推进后续不依赖该材料的阶段。
- 如果沟通跑偏，直接回到当前阶段的清单，从第一个未完成项继续。

状态规则：

- `[x]` 表示已完成
- `[ ]` 表示未完成
- `(当前阶段)` 表示当前正在推进

## 阶段跟踪

当前状态：

- V1 基础闭环已完成。
- 阶段 8：真实 Patch 生成增强已完成。
- 阶段 9：真实功能同步增强已完成。
- 阶段 10：验证可信度增强已完成。
- 阶段 11：真实仓库试点收敛已完成。
- 阶段 12：Skill 与 Agent 交付增强已完成。
- 阶段 13：Flutter Profiler 设计已完成。
- 阶段 14：Flutter Profiler 实现已完成。
- 阶段 15：Digest-First 计划收敛已完成。
- 阶段 16：Flutter Profiler 硬化已完成。
- 阶段 17：Digest 语义补强已完成。
- 阶段 18：Planner / Apply 真实接线增强已完成。
- 阶段 19：真实 UIKit Patch 实用性增强已完成。
- 阶段 20：真实功能补丁内容增强已完成。
- 阶段 21：Service / Logic 触点扩展已完成。
- 阶段 22：行为验证增强已完成。
- 阶段 23：多样本试点收敛已完成。
- 阶段 24：第三样例与多证据融合（已延后）。
- 阶段 25：前置扫描资产 Skill 化与主链路收口已完成。
- 当前阶段：阶段 26：核心脚本主驱动切换与旧分支清理。
- 当前主要剩余阻塞：
  - 项目级扫描资产尚未统一为“可复用 schema + 增量刷新”标准
  - `flutter-profiler / native-profiler / capability-mapper` 还未拆成独立 skill 边界
  - `apply / verify` 仍主要由 `patch_plan` 驱动，尚未完全切到 `native_operation_plan` 主驱动
  - 旧流程兼容分支仍在（legacy marker / marker_block），增加了执行链路复杂度

### 阶段 0：范围与命名

- [x] 确认 V1 目标平台为 `iOS + Swift + UIKit`
- [x] 确认触发方式为手动
- [x] 确认默认工作目录为 `.ai/t2n/`
- [x] 确认项目命名为 `T2N Atlas`
- [x] 确认主执行流为 `profile -> plan -> confirm -> apply -> verify`

### 阶段 1：V1 架构与 Contract 方向

- [x] 写出主计划文档
- [x] 冻结系统边界与非目标范围
- [x] 确认 `requirement_sync_contract` 为核心中间产物
- [x] 确认高层组件为 `Atlas Profiler`、`Atlas Planner`、`Atlas Apply`、`Atlas Verify`
- [x] 确认 `.ai/t2n/` 下的运行产物布局

### 阶段 2：Atlas Profiler 设计

- [x] 写出 Profiler 高层规格
- [x] 定义 Profiler 输出文件
- [x] 定义缓存复用与失效策略
- [x] 写出 Profiler 实现级设计
- [x] 定义 CLI 形式和推荐子命令
- [x] 定义启发式优先级规则
- [x] 定义 JSON 输出 schema 预期

### 阶段 3：Atlas Planner 设计

- [x] 写出 Planner 高层规格
- [x] 写出 Planner 实现级设计
- [x] 最终确定 `requirement_sync_contract.yaml` 的字段级 schema
- [x] 定义固定的 `sync_plan.md` 模板
- [x] 定义固定的 `touchpoints.md` 模板
- [x] 定义固定的 `risk_report.md` 模板
- [x] 细化 Planner 的置信度与升级规则

### 阶段 4：Atlas Apply 与 Verify 设计

- [x] 细化 apply 阶段的职责
- [x] 细化 verify 阶段的职责
- [x] 定义 `apply_report.md` 结构
- [x] 定义 `verify_report.md` 结构
- [x] 定义从确认到执行的安全规则

### 阶段 5：Atlas Profiler 实现

- [x] 创建 `scripts/` 目录结构
- [x] 创建 `scripts/atlas_profiler.py` 入口脚本
- [x] 实现 `scan` 命令的预检查和输出目录处理
- [x] 实现 Swift、storyboard、xib、plist、test 文件的仓库盘点
- [x] 实现架构推断启发式
- [x] 实现导航识别启发式
- [x] 实现 UI 模式识别启发式
- [x] 实现 networking 和 model 模式识别启发式
- [x] 实现 touchpoint 评分输出
- [x] 实现 risk 评分输出
- [x] 实现 `scan_meta.json` 写入
- [x] 实现 `status` 命令
- [x] 实现 `invalidate` 命令
- [x] 在一个真实 iOS 仓库上做 smoke test
- [x] 复盘 profiler 输出并收紧启发式规则

### 阶段 6：Atlas Planner 实现

- [x] 创建 planner 脚本入口
- [x] 实现 PRD、Flutter 代码、PR diff、测试的证据聚合
- [x] 实现业务范围推断
- [x] 实现 native profile 加载
- [x] 实现 `requirement_sync_contract.yaml` 生成
- [x] 实现 `sync_plan.md` 生成
- [x] 实现 `touchpoints.md` 生成
- [x] 实现 `risk_report.md` 生成
- [x] 用一个真实需求样例做 smoke test

### 阶段 7：Atlas Apply 与 Verify 实现

- [x] 创建 apply 脚本入口
- [x] 实现已批准计划的加载
- [x] 实现文件 patch 执行
- [x] 实现 touched files 记录
- [x] 实现按 contract 验证结果
- [x] 实现 `apply_report.md`
- [x] 实现 `verify_report.md`
- [x] 用一个独立功能做端到端 smoke test

### 阶段 8：真实 Patch 生成增强

- [x] 定义最小可用的 Swift patch 生成策略
- [x] 按触点类型生成可编译的 Swift 扩展骨架
- [x] 支持 `create` 场景下的新文件模板生成
- [x] 在 `apply_result.json` 中记录生成模式与片段类型
- [x] 调整 `verify`，区分 marker patch 与 generated patch
- [x] 用临时 iOS 仓库做真实 patch smoke test

### 阶段 9：真实功能同步增强

- [x] 补全 Planner 的 Flutter 语义抽取：`states / interactions / api_calls / models / strings / assets`
- [x] 让 contract 中的 `behavior` 和 `flutter_evidence` 不再主要依赖 PRD 文本
- [x] 为 `feature_screen / feature_logic / feature_view / feature_service / feature_model` 定义更接近 UIKit 实战的 patch 策略
- [x] 在 `update` 场景里生成可调用的方法骨架，而不只是静态承载扩展
- [x] 在 `create` 场景里生成更完整的 UIKit 文件模板
- [x] 为 `manual_candidates` 和全局注册点补充更明确的升级规则
- [x] 用一个真实业务功能重新跑 `profile -> plan -> apply -> verify`

### 阶段 10：验证可信度增强

- [x] 为 Verify 增加结构级校验，检查目标类型、方法名、生成片段是否和 contract 对齐
- [x] 为 Verify 增加生成模式校验，确认 `swift_extension / swift_file / marker_block` 与触点类型匹配
- [x] 为 Verify 增加行为映射校验，避免只因注释文本存在就判定 `verified`
- [x] 增加可选的编译前检查或静态 Swift 语法检查
- [x] 输出更细粒度的 `partial / missing / unknown` 原因

### 阶段 11：真实仓库试点收敛

- [x] 选择一个真实业务功能作为 pilot，不再只用 synthetic smoke fixtures
- [x] 在真实原生仓库中先执行 `plan`，审查触点、风险和人工项
- [x] 对 pilot 功能执行受控 `apply`
- [x] 复盘 profiler / planner / apply / verify 的误判点
- [x] 收紧触点选择、manual candidate、risk rules
- [x] 形成第一版“真实项目接入准则”

阶段 11 试点记录：

- Flutter 试点仓库：`/Users/admin/anystories-client-flutter`
- 试点基线提交：`84895c0074d12adfa6edee2fc837c14c69329277`
- 真实功能范围：`membership_unlock_v2_short_reader`
- 试点原生仓库：`/Users/admin/Desktop/anyshort-ios`
- 计划产物基线：`/tmp/t2n-anyshort-membership-v2-realpilot-run-v5`
- 受控执行副本：`/tmp/anyshort-ios-realpilot-apply-v5`
- 真实试点收敛结论：
  - 原始 planner 直接读取 Flutter 源码时，容易把 `ScrollChildView`、模板表达式、样式词等噪音当成需求语义
  - 原生触点已基本落在 `PlayerBuyView / PlayerBuyButton / PlayerAutoLockButton` 这一组买断视图及相关模型
  - `apply -> verify --swift-parse-check` 已在临时副本上跑通
  - 下一阶段不再继续靠 planner 内部堆专项过滤，而是引入前置 `Flutter Profiler`

### 阶段 12：Skill 与 Agent 交付增强

- [x] 把当前脚本能力补充回 `SKILL.md` 的操作指引
- [x] 明确从 `profile -> plan -> apply -> verify` 的推荐命令和输入要求
- [x] 明确 `.ai/t2n/` 产物生命周期和清理策略
- [x] 补一份真实项目接入 checklist
- [x] 校验 `agents/openai.yaml` 与当前 skill 能力是否一致

### 阶段 13：Flutter Profiler 设计

- [x] 定义 `Flutter Profiler` 的目标、输入和输出边界
- [x] 设计 profiler 产物 schema，至少覆盖页面、流程、状态、接口、文案、资源、测试断言
- [x] 设计 `Flutter Profiler -> Atlas Planner` 的衔接方式
- [x] 定义 profiler 与原始源码 / PR diff / 测试之间的冲突检测规则

### 阶段 14：Flutter Profiler 实现

- [x] 创建 `scripts/flutter_profiler.py` 入口脚本
- [x] 实现 Flutter 仓库级扫描，输出 `.ai/t2n/flutter-profile/` 基础产物
- [x] 实现需求级 `flutter-feature-digest.json / .md` 生成
- [x] 实现 `status` 与 `invalidate` 命令
- [x] 在 `anystories-client-flutter` 上跑首轮真实 scan / digest
- [x] 复盘 profiler 输出，确认是否明显降低 planner 噪音

阶段 14 当前产物：

- Flutter profile：`/tmp/anystories-flutter-profile`
- Flutter digest：`/tmp/t2n-anystories-flutter-digest-run`
- digest 接入 planner 的真实 run：`/tmp/t2n-anyshort-membership-v2-realpilot-run-v6-digest`

阶段 14 当前结论：

- `flutter_profiler.py` 已可运行，并能稳定输出 repo-level profile 与 run-level digest
- `atlas_planner.py` 已支持 `--flutter-digest-path`，会优先读取 digest
- 在 `anystories` 真实 pilot 上，代表页面已经从 `ScrollChildView / ScrollModeView` 收敛到 `ShortBookUnlockView / ShortUnlockView / UnlockFloatingOverlay / MembershipUnlockV2Alert`
- planner 通过 digest 生成的 `v6` 计划已经显著减少了源码级噪音和无关 API 扩散
- 下一步要继续从“结构归类”和“scope 切片”优化 digest，而不是回到关键词过滤

### 阶段 15：Digest-First 计划收敛

- [x] 把 `flutter-feature-digest` 的 `noise_candidates / conflicts` 显式写入 planner 产物
- [x] 让 `risk_report.md` 区分“Flutter digest 风险”和“native touchpoint 风险”
- [x] 收紧 planner 的旧 Flutter fallback，使 digest 存在时不再混入过多旧提取结果
- [x] 用 `anystories -> anyshort` pilot 对比 `digest 前 / digest 后` 的计划差异

阶段 15 当前结论：

- planner 已支持 digest-first 输入，命令行参数为 `--flutter-digest-path`
- `risk_report.md` 已可显式展示 digest 侧的 `conflicts` 和 `noise_candidates`
- 在 `anystories -> anyshort` pilot 中，digest-first 计划已把 Flutter 主页面从 `ShortBookCompleteTag / MenuEnter` 一类组件收敛到
  `ShortBookUnlockView / ShortUnlockView / UnlockFloatingOverlay / MembershipUnlockV2Alert`
- 原生触点仍稳定落在 `PlayerBuyView / PlayerBuyButton / PlayerAutoLockButton` 一组买断视图及相关模型

### 阶段 16：Flutter Profiler 硬化

- [x] 把 digest 中的 `scope.features` 拆成 `primary / supporting` 两层，避免所有关联目录平铺成主范围
- [x] 继续收紧用户可见文案提取，优先 `l10n / 文案 / CTA`，降低样式词和推荐词进入主结论的概率
- [x] 为代表页面增加“primary / auxiliary / component”更稳定的排序和数量控制
- [x] 用 `anystories -> anyshort` 再跑一轮 plan，对比阶段 15 的 digest-first 输出

阶段 16 当前结论：

- 文案提取已改成优先解析 `AppLanguage.of()?.key ?? fallback`，并回填 `app_en.arb`
- `sync_plan` 中的文案已从 `Completed / Author Directory / PT-SERIF` 一类分散文本，收敛到
  `Join Now / Unlock / Retry / No Ad Unlock / Unlock this book with coins` 这类主流程文案
- digest 已固定为最多 `2 primary + 2 auxiliary` 代表页面
- `atlas_planner` 在 digest 存在时已显著收紧旧 fallback，当前 `states` 已不再被旧 helper 名污染

### 阶段 17：Digest 语义补强

- [x] 为 digest 补一版更稳定的 `states` 提取，避免当前直接变成空列表
- [x] 收紧 `flutter_evidence.key_files`，把主证据和辅助证据分层输出
- [x] 在 `sync_plan.md` 中显式展示 `primary_features / supporting_features`
- [x] 用 `anystories -> anyshort` 再跑一轮验证，确认阶段 16 的硬化没有影响原生触点稳定性

阶段 17 当前结论：

- digest 已能输出稳定状态：`VipInfoLoading / PriceLoading`
- contract 与 sync plan 已支持 `primary_features / supporting_features / key_files_primary / key_files_supporting`
- `v7-hardened` 计划中原生触点仍稳定命中：
  - `PlayerBuyView`
  - `PlayerBuyButton`
  - `PlayerAutoLockButton`
  - `PlayerUnlockedModel`
  - `PlayerBuyResultModel`

### 阶段 18：Planner / Apply 真实接线增强

- [x] 让 planner 把 `primary / auxiliary screens` 和 UIKit 触点类型建立更明确的映射
- [x] 让 apply 生成的 Swift patch 开始区分主页面补丁和辅助弹层补丁
- [x] 让 verify 对 `feature_view / feature_screen / other` 的行为覆盖判断更贴近真实功能语义
- [x] 用 `anystories -> anyshort` 的当前 pilot 再跑一轮 `plan -> apply -> verify`，检查 digest-first 改造没有破坏执行链路

阶段 18 当前结论：

- contract 已支持 `flutter_evidence.representative_screens`
- `selected_touchpoints` 已支持 `ui_role / source_screens`
- `anystories -> anyshort` 当前 pilot 中，UIKit 触点已稳定映射为：
  - `PlayerBuyView -> primary_screen`
  - `PlayerBuyButton -> auxiliary_dialog`
  - `PlayerAutoLockButton -> auxiliary_overlay`
- `apply_result.json` 与 `verify_result.json` 已携带 `ui_role`
- 在临时副本中完成的 `plan -> apply -> verify --swift-parse-check` 结果为 `verified`

### 阶段 19：真实 UIKit Patch 实用性增强

- [x] 让 `apply` 在 `primary_screen` 上优先复用现有 `viewDidLoad / setup / bind` 入口，而不是只追加语义 extension
- [x] 让 `apply` 在 `auxiliary_dialog / auxiliary_overlay` 上补充更贴近 UIKit 的展示入口占位
- [x] 收紧 `other / non_ui` 触点分类，尽量把模型、服务、逻辑触点从 `other` 里拆出来
- [x] 用当前 pilot 继续验证：阶段 19 的增强没有扩大 patch 范围，也没有破坏 `swiftc -parse`

阶段 19 当前结论：

- `apply_result.json` 已支持 `hook_target / hook_inserted`
- `verify` 已会检查 install 调用是否真正落到生成块之外的 UIKit 原始入口
- `anystories -> anyshort` 当前 pilot 中，实际 hook 结果已收敛为：
  - `PlayerBuyView -> refresh`
  - `PlayerBuyButton -> init`
  - `PlayerAutoLockButton -> update`
- `Planner` 已把 `PlayerBuyResultModel / PlayerUnlockedModel` 识别为 `feature_model`
- 在临时副本中完成的 `plan -> apply -> verify --swift-parse-check` 结果仍为 `verified`

### 阶段 20：真实功能补丁内容增强

- [x] 让 `primary_screen` 生成更贴近 UIKit 的状态渲染骨架，而不是只有 `_ = states`
- [x] 让 `auxiliary_dialog / auxiliary_overlay` 生成更贴近展示入口的 CTA / 文案 / 展示方法占位
- [x] 让 `feature_model / feature_service / feature_logic` 生成更贴近数据层的字段和请求骨架
- [x] 用当前 pilot 再跑一轮，确认阶段 20 的补丁增强没有破坏已有 hook、语义映射和 `swiftc -parse`

阶段 20 当前结论：

- `primary_screen` 现在会生成更具体的 `stateFlags / displayCopy / CTA` 骨架
- `auxiliary_dialog / auxiliary_overlay` 现在会生成更具体的展示文案、CTA 和显示状态骨架
- `feature_model` 现在会生成默认字段、字段映射和默认值骨架
- `feature_service / feature_logic` 现在会生成更具体的请求上下文和响应字段骨架
- 在临时副本中完成的 `plan -> apply -> verify --swift-parse-check` 结果仍为 `verified`

### 阶段 21：Service / Logic 触点扩展

- [x] 让 `Planner` 在 Flutter 存在 `api_calls / models / supporting_features` 时，优先补入至少一类 `feature_service / feature_logic` 触点候选
- [x] 让 `Apply` 对 `feature_service / feature_logic` 的生成更贴近 `anyshort-ios` 的 `Manager / ViewModel / Service` 约定
- [x] 让 `Verify` 增加数据层触点分布检查，避免所有行为都只落在 UI 触点
- [x] 用当前 pilot 再跑一轮，确认 service / logic 触点扩展没有破坏现有 UI hook 与 `swiftc -parse`

阶段 21 当前结论：

- `Planner` 现在会在 Flutter 存在 `api_calls` 时主动补入 `feature_logic / feature_service`
- `anystories -> anyshort` 当前 pilot 中，数据层触点已稳定补入：
  - `PlayerViewModel`
  - `PlayerApiManager`
- `Verify` 已新增 `data_layer_coverage`
- 在临时副本中完成的 `plan -> apply -> verify --swift-parse-check` 结果仍为 `verified`

### 阶段 22：行为验证增强

- [x] 让 `Verify` 对关键 CTA / 展示文案 / 状态映射增加更细的结构化检查
- [x] 让 `Verify` 能区分“有数组映射”和“有更具体的展示 / 请求 / 状态骨架”
- [x] 让 `risk_report` 或 `verify_report` 显式提示“结构通过但业务语义仍浅”的情况
- [x] 用当前 pilot 再跑一轮，确认阶段 22 的验证增强没有误伤现有 `verified` 链路

阶段 22 当前结论：

- `Verify` 现在会额外输出 `semantic_coverage`
- 文件级结果现在会区分“结构通过”与“更深层语义骨架通过”
- `verify_report.md` 已显式展示 `Semantic Coverage`
- 在临时副本中重跑后的结果仍为 `verified`

### 阶段 23：多样本试点收敛

- [x] 引入第二个真实需求样例，验证当前规则没有过拟合 `membership_unlock_v2_short_reader`
- [x] 对比不同样例中的 `selected_touchpoints / ui_role / data_layer_coverage`，收紧通用规则
- [x] 复盘 `Flutter Profiler` 与 `Planner` 的噪音项，把通用降噪和优先级策略沉回实现
- [x] 让阶段 23 的结论进入文档，作为后续是否继续做自动接入和更深生成的依据

阶段 23 当前产物：

- 第二个真实样例：`purchased_chapter_list`
- 第二样例 digest：`/private/tmp/t2n-purchased-digest-run.QAtqvd`
- 第二样例 planner run：`/private/tmp/t2n-stage23-purchased-run-v5`
- 第二样例 clean apply / verify 仓库：`/private/tmp/anyshort-stage23c-repo.guDPy0`
- 第一样例回归 planner run：`/private/tmp/t2n-membership-regression-run-v3`

阶段 23 当前结论：

- `Atlas Planner` 现在会把 scope keywords 拆成 `base / alias / context`，不再无条件做 `short -> player`、`unlock -> buy` 这类扩展
- 原生触点匹配已从“整路径子串命中”收敛到“token 级命中 + anchor cluster 重排”，避免 `short` 因仓库名 `anyshort` 把整组 `Player*` 路径错误抬高
- 第二个样例的主触点已经从错误的 `PlayerBuyView` 收敛到 `UnlockChapterViewController`
- 第一条会员样例回归后仍稳定落在 `Player*` 簇，没有被第二样例的收紧规则误伤
- `Atlas Apply` 现在对 `feature_screen + component_view` 也会尝试走 `viewDidLoad / screen lifecycle` hook，第二样例在 clean temp repo 上已重跑到 `verify_status=verified`
- 当前仍有一个残留噪音：第二样例的次级触点里保留了 `PlayerChapterListCell`，说明跨模块 component 级收口还有进一步压缩空间

### 阶段 24：第三样例与多证据融合（已延后）

- [x] 把端到端流程切换为“项目级文档先行”：先做 Flutter/Native 全仓扫描文档，再进入需求级对照
- [x] 在 `plan` 阶段新增并落地 `feature_intent_spec.yaml` 与 `native_operation_plan.yaml`
- [ ] 引入第三个真实需求样例，优先选择同时具备 `PRD / Flutter diff / tests` 中至少两类证据的需求
- [ ] 在 `doc-compare-plan` 阶段收紧跨模块次级触点选择，继续压缩 `PlayerChapterListCell` 这类 residual noise
- [ ] 让 planner 对 `flutter_digest / pr_diff / tests / project-doc` 的权重更显式，减少仍然依赖路径关键词的场景
- [ ] 固化 AI trace 输入格式，要求只在“项目级文档 + 需求级摘要”上下文中输出修改方案
- [x] 把 `apply` 与 `verify` 串行执行约束固定到流程和命令示例中，避免并发导致的误判

阶段 24 延后说明：

- 当前优先级切换到“前置扫描资产可复用化 + skill 拆分 + 主链路收口”。
- 阶段 24 的未完成项保留在 backlog，待阶段 25 完成后恢复推进。

### 阶段 25：前置扫描资产 Skill 化与主链路收口（当前阶段）

- [x] 冻结“前置扫描可复用资产”目标结构（`flutter-profile / native-profile / shared capability_map`）
- [x] 把阶段状态切换规则落到文档：阶段 24 延后，阶段 25 设为当前阶段
- [x] 新增 `profile-assets-spec.md`，定义可复用文档 schema 与最小字段
- [x] 将 `SKILL.md` 的流程说明补齐为“前置扫描 skill + 同步 agent 编排”模式
- [x] 设计并冻结 skill 边界：`flutter-profiler`、`native-profiler`、`capability-mapper`
- [x] 梳理脚本主驱动切换计划：`native_operation_plan + requirement_sync_contract` 驱动 `apply / verify`
- [x] 列出可删除的旧流程分支清单（legacy marker / 冗余兼容路径）并标注删除顺序
- [x] 输出阶段 25 的验收标准与回归用例清单

### 阶段 26：核心脚本主驱动切换与旧分支清理（当前阶段）

- [x] `atlas_apply.py` 增加 `native_operation_plan.yaml` 强依赖校验
- [x] `atlas_apply.py` 切换为 `operations` 主驱动执行，`patch_plan` 仅做一致性校验
- [x] `atlas_verify.py` 切换为 `operations` 主驱动验证，文件覆盖按 operation 维度统计
- [x] 删除 `atlas_apply.py / atlas_verify.py` 中的 `legacy marker` 兼容分支
- [ ] 删除或降级 `marker_block` 主路径，保留明确失败或人工回退
- [x] 更新 `atlas-apply-spec.md` 与 `atlas-verify-spec.md` 以匹配新主驱动
- [x] 跑通一轮本地最小回归：`plan -> apply -> verify`（含门禁用例）

阶段 26 当前验证样例：

- 本地最小冒烟 run：`/tmp/t2n-stage26-smoke.QmgqTJ/run`
- 结果：`apply_status=completed`，`verify_status=verified`

## 系统架构

### 1. `Flutter Profiler Skill`

目的：

- 生成并维护 Flutter 侧可复用项目级资产。

主要职责：

- 扫描 Flutter 仓库并输出标准化 profile 文档
- 支持按 commit/路径增量刷新
- 为需求级 digest 提供稳定索引

主要输出目录：

- `.ai/t2n/flutter-profile/`

### 2. `Native Profiler Skill`

目的：

- 生成并维护 iOS 侧可复用项目级资产。

主要职责：

- 扫描 iOS 仓库并输出标准化 profile 文档
- 标记风险区、注册点、跨模块依赖和候选触点
- 支持按 commit/路径增量刷新

主要输出目录：

- `.ai/t2n/native-profile/`

### 3. `Capability Mapper Skill`

目的：

- 基于双侧 profile 生成“能力语义映射”，作为后续需求同步的对照底座。

主要职责：

- 输出 Flutter 能力语义到 Native 候选触点的映射
- 给出 `confidence / risk / reason / evidence`
- 对低置信映射自动降级为人工项候选

主要输出目录：

- `.ai/t2n/shared/capability_map.yaml`

### 4. `T2N Atlas Agent`

目的：

- 消费前置扫描资产，执行单需求同步编排。

主要职责：

- 输入 `PRD + flutter diff + tests + feature path`
- 生成 `flutter-feature-digest -> feature_intent_spec -> native_operation_plan -> requirement_sync_contract`
- 在确认后执行 `apply`，随后串行执行 `verify`

主要输出目录：

- `.ai/t2n/runs/<run-id>/`

## 端到端执行流

1. 执行 `flutter-profiler skill`，生成或增量刷新 `.ai/t2n/flutter-profile/`
2. 执行 `native-profiler skill`，生成或增量刷新 `.ai/t2n/native-profile/`
3. 执行 `capability-mapper skill`，刷新 `.ai/t2n/shared/capability_map.yaml`
4. 对指定需求执行 Flutter 需求级摘要，输出 `flutter-feature-digest.json(.md)`
5. 聚合 `profile docs + capability_map + flutter digest + PRD + diff + tests`，推断本次同步范围
6. 输出 `feature_intent_spec.yaml`
7. 输出 `native_operation_plan.yaml`
8. 基于 `native_operation_plan` 汇总生成 `requirement_sync_contract.yaml`
9. 生成 `sync_plan.md`、`touchpoints.md`、`risk_report.md`
10. 停止并等待用户确认
11. 用户确认后，对 iOS 代码库执行 patch，输出 `apply_report.md`
12. 串行执行 verify，输出 `verify_report.md`

默认主流程：

- `profile-skills -> requirement-digest -> doc-compare-plan(intent+operation+contract) -> confirm -> apply -> verify`

## Requirement Sync Contract

这是 V1 的核心中间产物，用来描述“一个完整业务功能如何映射到现有 iOS 项目”。

在当前流程中，`requirement_sync_contract` 不是第一产物，而是由 `feature_intent_spec + native_operation_plan` 汇总后生成。

字段级 schema 见 [requirement-sync-contract-schema.md](requirement-sync-contract-schema.md)。

最小 schema：

```yaml
requirement:
  id: PRD-123
  name: user_profile_refresh
  summary: Refresh the profile experience and related user actions

mode: feature_sync
sync_strategy: scoped_patch

source:
  flutter_paths:
    - lib/features/user_profile/
  change_basis:
    - prd
    - flutter_pr_diff
    - flutter_tests
  change_ref: feature/profile-refresh

target:
  platform: ios
  language: swift
  ui_framework: uikit
  repo_root: ../native-ios
  profile_path: .ai/t2n/native-profile

behavior:
  user_flows:
    - open_profile
    - refresh_profile
    - retry_after_error
  acceptance_points:
    - profile header is visible
    - refresh updates profile content
    - error state can recover through retry

flutter_evidence:
  screens:
    - ProfilePage
  state_holders:
    - ProfileBloc
  api_calls:
    - getUserProfile
  tests:
    - profile_page_test.dart

native_impact:
  existing_files:
    - ProfileViewController.swift
    - UserProfileService.swift
  new_files:
    - ProfileHeaderView.swift
  registration_points:
    - AppRouter.swift

patch_plan:
  create:
    - ProfileHeaderView.swift
  update:
    - ProfileViewController.swift
    - UserProfileService.swift
  manual_candidates:
    - AppRouter.swift

unsupported:
  - complex custom animation
```

## Native Profiler 需要回答的问题

Profiler 的存在，是为了让 Planner 尽量自己推断，而不是每次都反复询问用户。

至少需要推断出：

- 项目整体或局部更像 MVC、MVVM、Coordinator，还是混合结构
- view controller 是如何组织的
- 导航如何发起和传播
- networking 如何组织
- model 如何定义和解码
- 哪些基类和公共层被反复复用
- 哪些旧文件最可能成为触点
- 哪些文件或目录风险高，不适合自动 patch

## Planner 需要给出的答案

对于每次需求同步，Planner 至少要回答：

- 本次要同步的业务范围是什么
- 哪些 Flutter 文件和测试最能代表这个功能
- 哪些原生文件必须改
- 哪些原生文件可以新建
- 哪些高风险文件应该保留为人工处理候选
- 在 V1 范围内，最终结果能与 Flutter 一致到什么程度

## V1 支持的结果

V1 主要覆盖：

- UIKit 页面和子视图
- ViewController 的流程与交互逻辑
- 原生仓库中已经存在的状态处理模式
- API 集成与 model 更新
- strings 和静态资源
- 对现有功能文件做合理修改

## V1 暂不承诺

V1 不把这些能力作为核心承诺：

- 整 app 重生成
- CI 自动触发同步
- 任意 iOS 架构的自动适配
- 复杂动画系统的完全自动迁移
- 重型平台 SDK 集成的全自动处理
- 对每个 Flutter 渲染细节的绝对一致复刻

## 安全模型

系统在展示计划前，不得直接写代码。

默认行为：

1. 先生成计划
2. 等待用户确认
3. 只执行已经批准的计划
4. 记录改动文件和未解决项

V1 可以修改现有文件，但前提是：

- 先读取相关文件上下文
- 先识别明确触点
- 先把计划写进 `sync_plan.md`

## 交付路线

### 阶段 1：Native Profiler

构建 iOS 仓库扫描器，并把输出写入 `.ai/t2n/native-profile/`。

退出标准：

- 能较稳定地推断架构、导航、UI 模式、networking 模式和可能触点。

### 阶段 2：Requirement Scope Detection

构建 PRD、Flutter 代码、PR diff、测试的证据聚合层。

退出标准：

- 能从混合输入中稳定识别出目标业务功能。

### 阶段 3：Requirement Sync Contract

构建 contract 提取器，把混合证据和 native profile 变成 `requirement_sync_contract.yaml`。

退出标准：

- 原生开发能够仅通过 contract 理解本次 iOS 实现范围。

### 阶段 4：Sync Plan Generation

构建 Planner，输出 `sync_plan.md`、`touchpoints.md`、`risk_report.md`。

退出标准：

- 计划足够具体，能在改代码前完成确认。

### 阶段 5：Apply and Verify

构建 patch 执行层和验证层。

退出标准：

- 至少一个完整独立功能能被同步到 iOS app，并且剩余人工工作量可控。

## 当前推荐实现顺序

1. 实现 `Atlas Profiler`
2. 实现需求证据聚合
3. 实现 `requirement_sync_contract` 提取
4. 实现触点识别和 `sync_plan` 生成
5. 实现 apply 和 verify

## 成功标准

- 一个已在 Flutter 完成的完整功能，能在不从零重写原生实现的前提下，被带入 iOS UIKit 项目。
- Profiler 能显著减少重复扫描和重复判断。
- 每次运行都能先产出清晰计划，再进行任何代码修改。
- 至少有一个真实独立功能可以在 V1 中完整跑通。
