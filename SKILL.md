---
name: flutter-to-native
description: "Flutter 需求到 Native（iOS/Android）的流程编排型经验工具（SOP）：结构建模→Flutter变更采集→意图提炼→同步任务规划→规划校验→人工确认→CLI执行→验收闭环→交付。支持单端或双端同时同步。"
---

# Flutter-to-Native SOP

## 定位

这是一个**流程与质量闸门**工具，不是内置 agent 或代码注入器。

- Skill 负责：流程编排、LLM 产物校验、工件落盘与验收闸门。
- CLI（Claude Code / Codex）负责：理解代码、编辑代码、修改代码。

## 平台支持

支持 `ios` 和 `android` 两个目标平台。每个平台有独立的 platform profile：
- [iOS Platform Profile](references/platforms/ios.md)
- [Android Platform Profile](references/platforms/android.md)

平台选择在 Step 0（会话初始化）中确定，不需要提前指定。双端同步时，Flutter 分析（Step 1 ~ Step 2.3）共享，从 Step 2.4（native_chain_match）开始按平台分叉。

## 原则

- Task 按**功能分组（能力单元）**组织，不按类/方法 1:1 映射；触点仅作为子项。
- Flutter 与 Native 允许多对多映射；类/方法仅是实现锚点。
- Flutter diff **已有实现**的需求，必须按 Flutter diff 的实现逻辑同步到 Native（触发链路/状态机/副作用一致）。
- 若因双端差异导致 Flutter 逻辑无法等价落地，允许重设计；但必须输出并留档：
  - `cross_platform_gap.md`（差异说明）
  - `design_tradeoff.md`（取舍理由）
  - `acceptance_alignment.md`（验收对齐项）
- 未通过 plan_validation，不得进入执行。
- 涉及 UI 的 task，必须提供 Figma 链接和截图。
- `plan` 的业务分析与任务生成由 LLM 完成，脚本不做业务推理。
- 自动映射必须经过：能力切片（capability_split）→Flutter链路抽取（flutter_chain_extract）→Native链路匹配（native_chain_match）→反证淘汰（disambiguation），禁止跳步。
- 主落点必须优先定位到 Native 编排入口层（由 platform profile 定义）；纯组件视图只能作为触点子项，除非有完整反证证明该组件就是业务入口。
- 每个映射必须同时给出正向链路（入口->编排->落点）与反向回溯（用户动作->回调/事件->调用方），并记录 Top1/Top2 淘汰原因。

## 高保真同步约束（强制）

- 将 Flutter **已实现行为**作为同步基准。若需求说明、历史实现、补充文档冲突，按：`用户当前明确说明 > Flutter 当前实现 > 其他补充文档`。
- 以高保真同步为首要目标；必须同步页面结构、交互流程、状态流转、接口语义、错误处理、边界条件、生命周期、异步回调时序。
- 允许架构映射，不允许需求降级；可以用 Native 侧既有架构表达同一行为，但不得因为原生实现更复杂就删减真实流程。
- 当信息部分缺失但可推断时，优先基于 Flutter 现有代码做最小必要推断；不要自行发明需求。
- 仅当用户明确要求简化，或存在真实外部阻塞（SDK / 接口定义 / 依赖模块 / 资源文件 / 平台接入信息缺失）时，才允许不完整输出；并必须显式写出原因、影响范围、未完成项、未对齐项。

## 严禁降级与伪完成

- 禁止擅自输出 MVP / 简化版 / 占位版 / 演示版 / "先跑通"版。
- 禁止擅自把复杂模块延后、拆到后续、先只做 UI、先只保留接口、先 mock / stub / placeholder。
- 禁止把 Flutter 中已存在的真实逻辑替换成更容易实现的原生逻辑，例如：多状态并单状态、复杂筛选改简单筛选、真实接口改本地假数据、复杂交互改静态展示。
- 禁止忽略 loading / empty / error、用户取消、权限拒绝、重试、页面返回恢复、生命周期回调、特殊输入分支、平台差异、异步时序。
- 禁止把"部分完成"写成"已完成"；若存在阻塞、差异、未对齐项，必须明确标记。

## 流程步骤

> 双端同步时：Step 0-1 和 Step 2.1-2.3 只执行一次（共享 Flutter 分析），Step 2.4 起按平台各执行一轮。

| Step | 名称 | 说明 | 共享/分叉 | 详情 |
|------|------|------|----------|------|
| 0 | 会话初始化 | 交互式确认平台、仓库路径、输入源，生成 session config | 共享 | [00-session-init.md](references/00-session-init.md) |
| 1 | flutter_changes | Flutter 变更采集 + Figma 截图（UI 时必做） | 共享 | [01-flutter-changes.md](references/01-flutter-changes.md) |
| 2 | intent | 需求意图提炼 + 自动映射子流程 + llm_plan 生成 | 2.1-2.3 共享 / 2.4+ 分叉 | [02-intent.md](references/02-intent.md) |
| 3 | plan | 同步任务规划，执行 `atlas_planner.py plan` | 按平台 | [03-plan.md](references/03-plan.md) |
| 4 | plan_validation | 自动规划校验（V7-V14），FAIL 禁止执行 | 按平台 | [04-plan-validation.md](references/04-plan-validation.md) |
| 5 | confirm | 人工审阅 edit_tasks + plan_validation | 按平台 | [05-confirm.md](references/05-confirm.md) |
| 6 | execute | superpowers 拆分调度 + CLI 改码 + 编译验证 | 按平台 | [06-execute.md](references/06-execute.md) |
| 7 | code_review | 全局代码审查，强制执行 | 按平台 | [07-code-review.md](references/07-code-review.md) |
| 8 | verify | 验收闭环 + 基准测试，执行 `atlas_verify.py verify` | 按平台 | [08-verify.md](references/08-verify.md) |
| 9 | finalize | 交付汇总 + 最终自检 | 合并 | [09-finalize.md](references/09-finalize.md) |

## 进度追踪（强制）

**Skill 触发后，必须在进入 Step 0 之前，使用 `TaskCreate` 一次性创建所有步骤的任务**，让用户能看到完整的流程进度。

### 启动时创建任务

按以下顺序创建（subject 格式固定为 `Step X — 名称`）：

| subject | description | activeForm |
|---------|------------|------------|
| `Step 0 — 会话初始化` | 交互式确认平台、仓库路径、输入源，生成 session config | `配置会话参数` |
| `Step 1 — 变更盘点` | Flutter 变更采集 + Figma 截图 | `采集 Flutter 变更` |
| `Step 2 — 需求意图提炼` | 需求意图提炼 + 自动映射子流程 + llm_plan 生成 | `提炼需求意图` |
| `Step 3 — 同步任务规划` | 同步任务规划，生成 edit_tasks | `生成任务规划` |
| `Step 4 — 规划校验` | 自动规划校验（V7-V14） | `执行规划校验` |
| `Step 5 — 人工确认` | 人工审阅 edit_tasks + plan_validation | `等待人工确认` |
| `Step 6 — 同步实施` | CLI 改码 + 编译验证 | `执行代码同步` |
| `Step 7 — 代码审查` | 全局代码审查 | `执行代码审查` |
| `Step 8 — 验收测试` | 验收闭环 + 基准测试 | `执行验收检查` |
| `Step 9 — 总结交付` | 交付汇总 + 最终自检 | `生成交付汇总` |

### 步骤间的依赖

创建完所有任务后，使用 `TaskUpdate` 的 `addBlockedBy` 设置依赖链：
- Step 1 blockedBy Step 0
- Step 2 blockedBy Step 1
- Step 3 blockedBy Step 2
- Step 4 blockedBy Step 3
- Step 5 blockedBy Step 4
- Step 6 blockedBy Step 5
- Step 7 blockedBy Step 6
- Step 8 blockedBy Step 7
- Step 9 blockedBy Step 8

### 执行时更新状态

- **开始某步时**：`TaskUpdate` 将该步设为 `in_progress`
- **完成某步时**：`TaskUpdate` 将该步设为 `completed`，然后将下一步设为 `in_progress`

这样用户随时能看到当前处于哪个步骤、已完成哪些步骤、还剩哪些步骤。

## 附录

- [understand_chat_log 格式](references/10-understand-chat-log.md)
- [Run 目录结构](references/11-run-directory.md)
