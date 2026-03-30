---
name: flutter-to-native
description: "Flutter 需求到 iOS Native 的流程编排型经验工具（SOP）：结构建模→Flutter变更采集→意图提炼→能力任务规划→校验闸门→人工确认→CLI执行→验收闭环→交付。"
---

# Flutter-to-Native SOP

## 定位

这是一个**流程与质量闸门**工具，不是内置 agent 或代码注入器。

- Skill 负责：流程编排、LLM 产物校验、工件落盘与验收闸门。
- CLI（Claude Code / Codex）负责：理解代码、编辑代码、修改代码。

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
- 主落点必须优先定位到 Native 调用入口/编排层（Controller/Coordinator/Manager）；纯组件视图只能作为触点子项，除非有完整反证证明该组件就是业务入口。
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

| Step | 名称 | 说明 | 详情 |
|------|------|------|------|
| 0 | 前置条件 | Python 3.10+、iOS 仓库、知识图谱就绪 | [00-prerequisites.md](references/00-prerequisites.md) |
| 1 | flutter_changes | Flutter 变更采集 + Figma 截图（UI 时必做） | [01-flutter-changes.md](references/01-flutter-changes.md) |
| 2 | intent | 需求意图提炼 + 自动映射子流程（capability_split → hunk_extract → chain_extract → native_match → disambiguation）+ llm_plan 生成 | [02-intent.md](references/02-intent.md) |
| 3 | plan | 能力任务规划，执行 `atlas_planner.py plan` | [03-plan.md](references/03-plan.md) |
| 4 | plan_validation | 自动校验闸门（V7-V14），FAIL 禁止执行 | [04-plan-validation.md](references/04-plan-validation.md) |
| 5 | confirm | 人工审阅 edit_tasks + plan_validation | [05-confirm.md](references/05-confirm.md) |
| 6 | execute | superpowers 拆分调度 + CLI 改码 + 编译验证 | [06-execute.md](references/06-execute.md) |
| 6.5 | code_review | 全局代码审查，强制执行 | [06.5-code-review.md](references/06.5-code-review.md) |
| 7 | verify | 验收闭环 + 基准测试，执行 `atlas_verify.py verify` | [07-verify.md](references/07-verify.md) |
| 8 | finalize | 交付汇总 + 最终自检 | [08-finalize.md](references/08-finalize.md) |

## 附录

- [understand_chat_log 格式](references/09-understand-chat-log.md)
- [Run 目录结构](references/10-run-directory.md)
