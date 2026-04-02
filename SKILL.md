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

### 单端 vs 双端执行

- **单端同步**（仅 iOS 或仅 Android）：无需并行 agent，直接在当前 session 中顺序执行 Step 2.4-8。
- **双端同步**：分叉后（Step 2.4 起），**必须使用 `superpowers:dispatching-parallel-agents` 为每个平台各派发一个独立 agent**，两端并行执行 Step 3-8，互不干扰。

- **iOS agent**：独立执行 Step 3-8，操作 iOS 仓库，产物写入 `<run-dir>/ios/`
- **Android agent**：独立执行 Step 3-8，操作 Android 仓库，产物写入 `<run-dir>/android/`
- **主 session 职责**：派发两端 agent → 等待两端完成 → 汇总进入 Step 9（finalize）

禁止在同一个 agent/session 中交替操作两端仓库，避免上下文污染和状态混乱。

### 双端状态不一致处理

两端 agent 独立推进，可能出现一端 PASS、另一端 FAIL 的情况。规则：
- **各端独立推进**：一端 FAIL 不阻塞另一端继续。FAIL 端按回退路径修复，PASS 端正常进入下一步。
- **Step 9（finalize）必须等两端都完成**：任一端未通过 verify，不得生成 finalize_report。
- **状态差异留档**：若一端因架构缺失无法映射，必须在该端的 `cross_platform_gap.md` 中记录原因和计划，不得静默跳过。
- **finalize_report 中必须标注各端状态**：如 `iOS: PASS, Android: WARN（2 项遗留）`。

## 原则与同步完整性约束

**组织方式**
- Task 按**功能分组（能力单元）**组织，不按类/方法 1:1 映射；Flutter 与 Native 允许多对多映射。
- 自动映射必须经过：capability_split → flutter_chain_extract → native_chain_match → disambiguation，禁止跳步。
- 主落点优先定位到 Native 编排入口层（由 platform profile 定义）；每个映射必须同时给出正向链路与反向回溯，记录 Top1/Top2 淘汰原因。

**高保真同步**
- Flutter **已实现行为**是同步基准（优先级：`用户明确说明 > Flutter 当前实现 > 其他补充文档`）。
- 必须同步：页面结构、交互流程、状态流转、接口语义、错误处理、边界条件、生命周期、异步回调时序。
- 允许架构映射，不允许需求降级。信息部分缺失时做最小必要推断，不自行发明需求。

**质量闸门**
- 未通过 plan_validation，不得进入执行。涉及 UI 的 task，必须提供 Figma 链接和截图。
- 若跨端差异导致无法等价落地，必须输出 `cross_platform_gap.md` + `design_tradeoff.md` + `acceptance_alignment.md`。
- 仅当用户明确要求简化或存在真实外部阻塞时，才允许不完整输出；必须显式写出原因和未对齐项。

**严禁**
- 擅自输出 MVP / 简化版 / 占位版 / mock / stub / placeholder。
- 把复杂模块延后、拆到后续、先只做 UI、先只保留接口。
- 用更容易实现的原生逻辑替代 Flutter 真实逻辑（多状态→单状态、真实接口→假数据等）。
- 创建 UI 文件但不集成到调用入口（死代码）。每个新建 View/弹窗必须有调用方。
- 用 SF Symbol / placeholder 替代 Flutter 已有的图片资源。必须从 Flutter assets 复制或从 Figma 下载。
- 将 Flutter 中已有的埋点、本地化、回调行为标为"后续"或"deferred"。这些是同步基准的一部分。
- 忽略 loading/empty/error、用户取消、权限拒绝、重试、生命周期回调、异步时序等分支。
- 把"部分完成"写成"已完成"。

**Git 提交策略**
- **整个 SOP 流程（Step 0-9）不执行任何 git commit。** 不管是规划产物、代码改动还是审查修复，全部不提交。
- **subagent 执行时**：在 subagent prompt 中明确指示 **不要 commit**，仅编写代码。
- 提交由用户在 SOP 流程结束后自行决定。

**Token 用量追踪**
- 追踪逻辑分布在 Step 0（初始化基线）、Step 6（记录 subagent）、Step 9（汇总），详见各步骤引用文档
- 产物：`<run-dir>/token_usage.md`

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

### 回退路径（非线性流程）

流程不是严格单向的。以下场景必须回退：

| 失败点 | 回退到 | 条件 |
|--------|--------|------|
| Step 4 FAIL | Step 3 | 重新生成 task 后重跑 plan_validation |
| Step 5 用户拒绝整体方案 | Step 2 | 重新规划能力切片 |
| Step 5 用户修改 task 结构 | Step 3 → Step 4 | 重新生成 + 重新校验 |
| Step 5 用户修改 task 细节 | Step 4（增量） | 仅重跑受影响的校验项 |
| Step 6 编译失败 | Step 6 内循环 | 修复编译错误后继续 |
| Step 7 code_review 发现问题 | Step 6 | 修复代码后重跑 code_review |
| Step 8 verify FAIL（代码问题） | Step 6 → Step 7 → Step 8 | 补代码 → 重审 → 重验 |
| Step 8 verify FAIL（留档缺失） | Step 8 内循环 | 补文档后重验，无需重审 |
| Step 8 基准测试 Layer 1 FAIL | Step 2 | 补充提取后走完整 plan→execute 循环 |
| Step 8 基准测试 Layer 4 FAIL | Step 6 → Step 7 → Step 8 | 同 verify FAIL 代码问题 |

### 中止与回滚

当 Step 6 执行过程中发现**无法修复的结构性问题**（如：架构假设错误、目标类已被大规模重构、映射证据失效）时，不应继续修复循环，而应中止并回滚：

**中止判断标准**（满足任一即中止）：
- 编译错误涉及 ≥3 个不相关文件，且修复会引入计划外的架构变更
- `understand-explain` 发现目标符号的调用链与 Step 2 分析时完全不同（如类已被拆分/合并/删除）
- 修复某 task 时必须修改其他已完成 task 的代码，且影响其行为契约

**回滚操作**：
1. 记录中止原因到 `<platform>/execution_log.md`（追加，标注 `## [ABORT]`）
2. 执行 `git checkout .` 撤销所有未提交的代码改动（因 SOP 不 commit，所有改动都是未提交状态）
3. 保留 run 目录中的所有产物（不删除，供后续分析）
4. 根据中止原因决定恢复路径：

| 中止原因 | 恢复路径 |
|---------|---------|
| 映射证据失效（目标文件/类已变） | 回到 Step 2.4（native_chain_match），重新查询后走 Step 3-8 |
| 架构假设错误（编排入口不对） | 回到 Step 2.4，更换映射策略后走 Step 3-8 |
| 外部依赖阻塞（缺少第三方库、需要先合并其他分支） | 暂停流程，提示用户解除阻塞后从 Step 6 重新开始 |

> 回滚不是失败，是质量保障。带着错误假设硬改到底的代价远高于回滚重来。

### 会话中断恢复

若会话中断后需要恢复，通过 run 目录中已存在的产物推断进度：
- 检查 `session_config.json` → 确认平台和仓库路径
- 检查各步骤产物（`flutter_changes.md` → Step 1 完成，`edit_tasks.json` → Step 3 完成，`plan_validation.md` → Step 4 完成，`execution_log.md` → Step 6 进行中/完成，`verify_report.md` → Step 8 完成）
- 从**第一个缺失产物对应的步骤**恢复执行

### 纯逻辑变更（无 UI）

若 Flutter diff 不涉及任何 UI 变更（无新增/修改页面、弹窗、组件），即 Step 1 判定 `含新增 UI 页面 = false`：

- **Step 0.4 Figma**：自动跳过，`session_config.json` 中 `figma` 字段为 `null`
- **Step 1**：`figma_inputs.md` 不生成，不触发 Figma 校验
- **Step 2.1 capability_split**：以 service/model/data 为粒度拆分能力，不要求 UI 类归属
- **Step 2.2 hunk_facts**：重点提取 `new_methods`、`persistence_keys`、`state_fields`，`new_classes` 的 `user_facing` 通常为 `false`
- **Step 4 plan_validation**：UI 强制约束（Figma 链接 + 截图）不触发——仅在 task 涉及 UI 时才要求
- **Step 7 code_review**：跳过"高保真 UI 对齐"检查项，聚焦逻辑正确性、线程安全、接口契约
- **Step 8 verify**：跳过 `user_facing: true` 类的 Native 文件对应检查（因为没有 user_facing 类）

其余步骤照常执行，不简化、不跳步。

### 纯重构 diff（无行为变更）

若 Flutter diff 仅为内部重构（无用户可见行为变更、无新增 class/method/状态/埋点），允许在 Step 2 完成 capability_split 后提前退出：
- 在 `capability_slices.md` 中标注 `行为变更: 无`
- 输出简短说明到 `finalize_report.md`，无需进入 Step 3+

## 步骤完成协议（强制，不得跳过）

每个步骤（Step 0-9）的引用文档末尾都有一个 `## Gate Checklist` 章节。**在将该步标记为 completed 之前，必须逐条核对 gate checklist 中的每一项**：

1. 读取该步引用文档中的 `## Gate Checklist`
2. 对每一项，用工具实际验证（不凭记忆判断）：
   - 产物检查 → 用 `ls` / `Read` 确认文件存在且非空
   - 内容检查 → 用 `Read` / `Grep` 确认字段/内容存在
   - 动作检查 → 用 `Grep` / `Bash` 确认结果（如 grep 确认调用入口存在）
3. 全部 PASS → 标记步骤 completed
4. **任一 FAIL → 必须立即修复，然后重新核对整个 checklist**（不是只重查 FAIL 项）
5. **标记 completed 后，立即记录下一步的 JSONL 行号边界**（用于按步骤统计 token）：
   ```bash
   NEXT_LINE=$(wc -l < "$(cat <run-dir>/token_tracking.json | python3 -c 'import json,sys;print(json.load(sys.stdin)["session_jsonl"])')")
   ```
   追加到 `token_tracking.json` 的 `step_lines` 中：`"step_N": <NEXT_LINE>`

### Gate FAIL 修复协议（强制）

Gate checklist 中发现 FAIL 时，**禁止跳过、禁止标为"已知遗留"、禁止继续下一步**。必须按以下流程处理：

1. **定位**：输出 FAIL 项的具体内容和缺失原因
2. **修复**：
   - 产物缺失 → 立即生成（如缺少 figma_inputs.md → 回到对应子流程生成）
   - 内容缺失 → 立即补充（如 task 缺少 asset_dependencies → 编辑 edit_tasks.json 补充）
   - 代码缺失 → 立即编写（如埋点未实现 → 编写埋点代码并 commit）
   - 集成缺失 → 立即接入（如新建 View 无调用方 → 在 integration_point 指定位置添加调用）
3. **重新核对**：修复后从 checklist 第一项重新核对全部项（修复可能引入新的 FAIL）
4. **全部 PASS 后**才能标记步骤 completed

> Gate checklist 不是事后报告，是**完成条件**。FAIL 项不修复 = 步骤未完成 = 流程阻塞。

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
