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

- 禁止擅自输出 MVP / 简化版 / 占位版 / 演示版 / “先跑通”版。
- 禁止擅自把复杂模块延后、拆到后续、先只做 UI、先只保留接口、先 mock / stub / placeholder。
- 禁止把 Flutter 中已存在的真实逻辑替换成更容易实现的原生逻辑，例如：多状态并单状态、复杂筛选改简单筛选、真实接口改本地假数据、复杂交互改静态展示。
- 禁止忽略 loading / empty / error、用户取消、权限拒绝、重试、页面返回恢复、生命周期回调、特殊输入分支、平台差异、异步时序。
- 禁止把“部分完成”写成“已完成”；若存在阻塞、差异、未对齐项，必须明确标记。

## 0. 前置条件

- Python 3.10+
- iOS 原生仓库可读写
- `understand-anything` 知识图谱就绪：确认 `.understand-anything/knowledge-graph.json` 存在且非空；不存在则直接失败，需先运行 `npx gitnexus analyze` 重建图谱

## 1. flutter_changes（Flutter 变更采集，必做）

输入至少满足其一：
- `--flutter-path`（Flutter 代码路径）
- `--flutter-digest-path`（结构化摘要）
- `--pr-diff-path`（PR diff）

说明：若缺少以上三类证据，`plan` 会直接失败。

`flutter_changes.md` 最少内容（缺少任一项，后续步骤不得使用该文件）：
- **改动文件列表**：每行一个文件名 + 改动类型（新增/修改/删除）
- **能力摘要**：1-3 句说明本次 diff 的核心功能变更
- **含新增 UI 页面**：`true / false`（决定 Figma 强制约束是否触发）

### Figma 输入采集（UI 变更时必做）

若 `含新增 UI 页面 = true`，必须在本步骤完成 Figma 截图落盘：
1. 用户提供 Figma 链接（必须）
2. 使用 `mcp__plugin_figma_figma__get_screenshot` 拉取截图
3. 将链接和截图路径记录到 `figma_inputs.md`

`figma_inputs.md` 格式：
```markdown
## <功能名>
- **Figma 链接**: https://www.figma.com/design/...
- **截图**: ./figma_screenshots/<name>.png
- **覆盖 task**: CAP-XX
```

未完成 Figma 采集时，`plan_validation` 的 UI 强制约束直接 `FAIL`，不得以"后续补充"绕过。

产物：`flutter_changes.md`、`figma_inputs.md`（UI 变更时）

## 2. intent（需求意图提炼）

输入：Flutter 证据（diff/PRD/页面说明/测试点）

在本 skill 中，`intent` 由 `plan` 阶段自动沉淀到工件 `intent.md`。


### 自动映射子流程（强制）

在 `llm_plan` 生成前，必须先完成以下子流程并写入 `llm_plan`：

1. `capability_split`
- 将 Flutter diff 拆分为原子能力（例如：引言更多、解锁按钮禁用、挽留倒计时）。
- **必须在 `capability_slices.md` 末尾附加 "新增 Class 归属表"**，列出 diff 中所有新增 class 及其归属 CAP。格式：

  ```markdown
  ## 新增 Class 归属表

  | class 名 | kind | user_facing | 归属 CAP | 说明 |
  |---------|------|-------------|----------|------|
  | _TermsNoteDialog | StatelessWidget | ✅ | CAP-03 | Terms 弹窗，用户可见交互 |
  | _GradientBorderPainter | CustomPainter | ❌ | CAP-03 | UI 辅助，无独立能力 |
  ```

  - `user_facing: ✅` 的 class 必须归入某个 CAP，不得为空
  - `user_facing: ❌` 的 class（CustomPainter / State / 数据类）归属其父 CAP，可不单独建 CAP
  - 此表作为 V13 的校验基准，不得事后补填

- 产物：`capability_slices.md`（含新增 Class 归属表）

2. `flutter_hunk_extract`
- 从业务文件 diff hunk 抽取事实层，**必须使用以下结构化字段**，禁止输出自由文本数组（自由文本无法被后续步骤机械校验，是遗漏的根源）：

```json
{
  "<file.dart>": {
    "new_classes": [
      {
        "name": "ClassName",
        "kind": "StatelessWidget | StatefulWidget | State | CustomPainter | DataClass | Other",
        "user_facing": true,
        "summary": "一句话说明该 class 的职责和触发方式"
      }
    ],
    "new_methods": [
      {
        "name": "methodName",
        "signature": "完整签名（含参数名和类型）",
        "triggers": ["触发该方法的调用方或用户操作"],
        "side_effects": ["修改的状态字段、调用的外部方法"]
      }
    ],
    "persistence_keys": ["完整 key 格式，含变量占位符，如 shortRetainFakeEndTimePrefix_${userId}_${productId}"],
    "analytics_events": ["事件名（如 charge_page_exposure）及 scene 参数枚举"],
    "ab_gates": ["ABService().isExperiment(ABScreen.xxx)，说明哪个区域受控"],
    "state_fields": ["新增的 @observable 或关键状态字段名及类型"],
    "conditional_flags": ["条件禁用/显示逻辑，如 isPriceLoading ? null : onUnlock"]
  }
}
```

- **必须显式提取同文件内所有新增 `class`**（含私有类 `class _Foo`）；`user_facing: true` 的 class 必须在后续 `capability_split` 中归入某个 CAP，不得因为是私有/嵌套类而跳过。
- 若某字段在该文件 diff 中无对应内容，输出空数组 `[]`，禁止省略字段。
- 产物：`hunk_facts.json`

3. `flutter_chain_extract`
- 为每个能力抽取：触发入口 -> 状态变化 -> 关键交互 -> 副作用。
- **完整性传递约束（强制）**：`flutter_chain_map` 生成后，必须对照 `hunk_facts.json` 逐字段校验覆盖情况：
  - `new_classes`：每个 `user_facing: true` 的 class 必须出现在某个 CAP 的 `key_interactions` 或独立 CAP 中
  - `new_methods`：每个方法必须出现在某个 CAP 的触发入口、交互或副作用中
  - `persistence_keys`：每个持久化 key 必须出现在某个 CAP 的 `side_effects` 中
  - `analytics_events`：每个埋点事件必须出现在某个 CAP 的 `side_effects` 中
  - `ab_gates`：每个 AB 门控必须在对应 CAP 的 `key_interactions` 中注明
  - 若发现 `hunk_facts` 中有条目未被任何 CAP 覆盖，必须在 `flutter_chain_map.json` 中输出 `uncovered_facts` 字段列出，并补充到对应 CAP 或新建 CAP，**不得静默跳过**
- 产物：`flutter_chain_map.json`（含可选 `uncovered_facts` 字段）

4. `native_chain_match`
- 基于 Native 代码理解对每个能力生成 Top-K Native 候选调用链与得分。
- **必须**通过调用 `/understand-anything:understand-chat` skill 完成查询，禁止直接用 Python/Bash 解析 `.understand-anything/knowledge-graph.json`。
- 查询以下内容：
  - 该能力对应的 Native 功能域入口（Controller / Manager / Coordinator）
  - 现有同类功能的触发方式与调用链（如：弹窗如何 show、充值如何跳转）
  - 候选落点的上下文（是编排入口还是纯 UI 组件）
- **提问格式（三要素）**：每个问题必须包含以下三个要素：
  - **场景**：在哪个页面/模块下（如 `ShortViewController`、充值弹窗）
  - **操作**：什么用户操作或系统事件触发（如 用户关闭弹窗、点击 Join Membership）
  - **目标**：需要看到什么效果/找到什么（如 弹窗如何 present、调用链是什么、由哪个类负责）
  - 示例：`在 ShortViewController 中，用户点击关闭 ShortAudioPurchaseSimpleView 弹窗后，Native 侧有没有已有的回调或 delegate 方法捕获这个关闭事件，由哪个类负责后续逻辑？`
- **注意**：查询关键词必须使用 Native 侧的类名/方法名/功能词（如 `ShortViewController`、`ChargeManager`），不要用 Flutter 侧的叫法，否则知识图谱无法匹配到节点
- 每次查询结果必须追加记录到 `understand_chat_log.md`（见下方格式说明）
- 产物：`native_chain_candidates.json`

5. `disambiguation`
- 对 Top1/Top2 做反证淘汰（触发源、关闭后去向、状态机一致性）。
- 产物：`mapping_disambiguation.md`

以上任一步缺失，`plan_validation` 必须 `FAIL`（见 V8）。

## 2.5 llm_plan 生成（必做）

由 CLI 的 LLM 基于以下输入实时生成 `llm_plan.json`：
- `flutter_changes.md`
- `pr_diff` 原文
- `figma_inputs`（链接与截图）
- Native 代码理解结果（替代 native-profile-v2）

最少字段：
- `meta`（含 `analysis_mode / generated_by / evidence.pr_diff_path / evidence.pr_diff_sha256`）
- `meta.mapping_pipeline`（含 `capability_split / flutter_hunk_extract / flutter_chain_extract / native_chain_match / disambiguation`）
- `intent_markdown`
- `hunk_facts`（json，来自 `flutter_hunk_extract`）
- `capability_slices`（markdown 文本）
- `flutter_chain_map`（json 对象）
- `native_chain_candidates`（json 对象）
- `mapping_disambiguation`（markdown 文本）
- `tasks`（按功能分组，含行为契约与逻辑约束）
- `tasks[].mapping_proof`（真实映射证明，见下）

## 3. plan（能力任务规划）

先由 CLI 的 LLM 生成 `llm_plan.json`（建议放到 `<run-dir>/llm_plan.json`），再执行 planner 落盘与校验。

> 命令须在 iOS 仓库根目录（`<ios-project-root>`）下执行，`scripts/atlas_planner.py` 相对于该根目录。

```bash
python3 scripts/atlas_planner.py plan \
  --repo-root <ios-project-root> \
  --run-dir <ios-project-root>/.ai/t2n/runs/<run-id> \
  --requirement-id <REQ-ID> \
  --requirement-name <REQ-NAME> \
  [--prd-path <prd.md>] \
  [--flutter-path <flutter-feature-path>] \
  [--flutter-digest-path <flutter-digest.json>] \
  [--pr-diff-path <flutter.diff>] \
  [--tests-path <tests-dir>] \
  --llm-resolution-path <llm_plan.json> \
  [--force]
```

`--llm-resolution-path` 为必填，至少包含：
- `intent_markdown`
- `tasks`（按功能分组）
- 可选：`risk_report_markdown`、`native_touchpoints_markdown`、`plan_validation`

并且必须包含 `meta`（硬约束）：
- `meta.analysis_mode = "live_llm"`
- `meta.generated_by`（禁止 `demo/example/sample/mock`）
- `meta.evidence.pr_diff_path` 与本次 `--pr-diff-path` 一致
- `meta.evidence.pr_diff_sha256` 与本次 diff 文件 sha256 一致（计算方式：`sha256sum <flutter.diff>` 或 `python3 -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" <flutter.diff>`）

不满足以上约束，`plan` 直接失败（拒绝示例产物/占位产物）。

每个功能组 task 必含：
- 功能目标（用户价值）
- 触发条件/前置条件
- 功能域（`feature_scope`）
- 触发生命周期（`trigger_lifecycle`）
- 行为契约（状态、交互、副作用、异常）
- 原生落点（UI/编排/数据/路由，可多对多）
- 触点子项（UI/编排/数据/路由）
- 编辑锚点（文件/类/方法，候选实现位置）
- 映射证明（`mapping_proof`）：
  - `entry_kind`：`orchestration_entry` / `component_touchpoint`
  - `entry_semantics`：如 `popup_show` / `popup_action` / `state_render`
  - `reverse_trace`：用户动作到调用方的反向回溯证据
  - `status`：必须为 `mapped`
  - `confidence`：`high/medium/low`
  - `evidence_lines`：证据行号（`path:line`）
  - `flutter_entrypoints`：Flutter 入口函数/文件
  - `native_chain`：Native 调用链（入口->编排->落点）
  - `evidence`：映射依据（路径/符号/调用关系）
- 验收断言（完成标准）

产物：
- `intent.md`
- `edit_tasks.md`
- `edit_tasks.json`
- `native_touchpoints.md`
- `risk_report.md`
- `plan_validation.md`

## 4. plan_validation（自动校验闸门）

- 校验未决项、触发方式、行为契约完整性、落点可执行性、风险标注
- 校验映射证明（`V7`）：无 `mapping_proof` 或 `status!=mapped` 直接 `FAIL`
- 校验自动映射流程证据（`V8`）：缺少 `mapping_pipeline` 或缺少四步产物直接 `FAIL`
- 校验入口级映射真实性（`V9`）：主落点若为纯视图且缺少编排入口证据，或缺少反向回溯证据，直接 `FAIL`
- 校验生命周期与证据可执行性（`V10`）：生命周期与 Native 链路不一致，或 `evidence_lines` 无法在仓库定位，直接 `FAIL`；未提供 `--pr-diff-path` 时，`pr_diff_sha256` 校验自动豁免
- 校验弹窗入口语义（`V11`）：task 含 popup/dialog/弹窗 时，首条 `native_chain` 必须是 `show/present`，且 `entry_semantics=popup_show`，否则 `FAIL`
- 校验跨端差异闭环（`V12`）：当 task 标注 `cross_platform_gap=true` 时，若缺少 `cross_platform_gap.md` / `design_tradeoff.md` / `acceptance_alignment.md` 任一项，直接 `FAIL`
- 校验 diff 一致性（`V13`，`diff-consistency`，**强制运行，不得省略**）：
  - 若 Native 方案无法完整解释 Flutter diff 中的结构变化（例如明确存在双弹窗分流但仅规划单弹窗改造），直接 `FAIL`
  - **新增 class 覆盖检查**：枚举 Flutter diff 中所有新增 `class`（含私有类 `class _Foo`），逐一确认 `edit_tasks.md` 中存在对应 task 或触点子项；若任一新增 class 未被覆盖，直接 `FAIL`，并列出未覆盖的 class 名称
- 校验 hunk_facts 未覆盖事实（`V14`）：检查 `flutter_chain_map.json` 中的 `uncovered_facts` 字段：
  - 字段不存在或为空数组：`PASS`
  - 字段非空：每条 uncovered fact 必须附有处置说明（已合并入某 CAP，或明确豁免原因）；无处置说明则 `WARN`；存在 `user_facing: true` 的 class 未覆盖则 `FAIL`
- 结论：
  - `PASS`：可进入执行
  - `WARN`：可执行但需人工关注
  - `FAIL`：禁止执行，回到 plan 修正

UI 强制约束：
- 涉及 UI 的 task，必须有 Figma 链接 + 截图
- 缺失时 `plan_validation` 必须为 `FAIL`

## 5. confirm（人工确认）

用户审阅：`edit_tasks.md + plan_validation.md`

未确认不进入执行。

**用户提出修改意见时的回环：**
- 修改范围仅涉及个别 task 的描述/落点/验收断言 → 直接修改 `edit_tasks.md` / `edit_tasks.json`，**无需重跑 plan_validation**，修改后重新 confirm
- 修改范围影响 task 结构（新增/删除 task）或映射证明 → 回到 Step 3（plan）重新生成对应 task，重新执行 plan_validation，再 confirm
- 用户拒绝整体方案 → 回到 Step 2（intent/自动映射子流程）重新规划能力切片

## 6. execute（CLI agent 直接改码）

说明：skill 不内置 agent/注入器。

### 6.0 执行前必须用 superpowers 拆分与调度（强制）

进入任何改码动作之前，必须完成以下两步：

**Step A — 用 superpowers:writing-plans 生成实现计划**

调用 `superpowers:writing-plans`，将 `edit_tasks.json` 中的 tasks 转为 superpowers 格式的实现计划：
- 每个 task 对应一个 superpowers task，含：目标文件列表、实现步骤、测试方式、commit 命令
- 计划保存到 `<run-dir>/implementation_plan.md`
- 计划中每个 task 必须包含以下步骤（不得省略）：
  1. 调用 `understand-explain <目标类/文件>` 查询调用链与上下文（结果追加到 `understand_chat_log.md`）
  2. 按 `flutter_chain_map.json` 对应 CAP 核对实现范围
  3. 编写 Native 代码
  4. 将改动追加记录到 `execution_log.md`
  5. commit

**Step B — 用 superpowers 执行计划（二选一）**

| 方式 | 适用场景 | skill |
|------|----------|-------|
| **推荐**：Subagent-Driven | tasks 相互独立，需要两阶段 review（spec + quality） | `superpowers:subagent-driven-development` |
| 备选：Inline Execution | tasks 有强依赖顺序，需在当前 session 内顺序推进 | `superpowers:executing-plans` |

> **禁止**跳过 Step A 直接改码，或绕过 superpowers 在主 session 逐文件手动修改。

执行输入（硬约束）：
- `edit_tasks.md` / `edit_tasks.json`
- `flutter_changes.md`
- 本次 `pr_diff` 原文（必要时回读具体 Flutter 文件）

**改码前必做（显式约定）：**
- 每个 task 的目标符号（类/方法/文件）改动前，必须先执行：
  ```
  /understand-anything:understand-explain <ClassName 或 filePath>
  ```
  查询内容：该符号的调用链（谁调用它）、所属架构层、依赖的子组件、当前已有的状态/逻辑。
- 若需要确认触发入口或调用时机，使用：
  ```
  /understand-anything:understand-chat <具体问题>
  ```
  查询内容：该功能当前在 Native 中如何被触发、由哪个 VC/Manager 负责编排、有无现存同类弹窗/流程可复用。
  **提问必须包含三要素**：场景（在哪个类/页面）+ 操作（什么触发）+ 目标（要看到什么），例如：
  `在 ShortViewController 中，用户点击解锁按钮时，现有调用链是怎样的，ShortPurchaseSimpleView_v2 的 delegate 回调到哪里？`
- **禁止**直接用 Python/Bash 解析 `.understand-anything/knowledge-graph.json` 代替 skill 调用。
- 每次调用 understand-chat 或 understand-explain 后，必须将问题和摘要结果追加到 `understand_chat_log.md`。

由 CLI 依据以上输入直接执行：
- 读码（结合 understand-explain 结果）
- 改码
- 补调用链
- 改 model/service
- 对 Flutter diff 已实现部分，优先做等价同步；若无法等价，先补齐差异工件（`cross_platform_gap.md` / `design_tradeoff.md` / `acceptance_alignment.md`）再执行代码改动。

禁止仅按 `plan` 产物执行（`plan-only`）。
禁止跳过 understand-explain 直接改码。

**执行记录写入 `execution_log.md`（追加格式，不覆盖旧记录）：**

```markdown
## [TASK-XX] YYYY-MM-DD HH:MM

**改动文件**:
- novelspa/Path/To/File.swift（新增 / 修改）

**改动内容**: （1-3 句说明做了什么，对应 hunk_facts 哪个字段）

**commit**: <sha>
```

**进入 Step 6.5 前必须通过编译验证：**

所有 task 完成后，执行 `xcodebuild build -scheme <scheme> -destination 'generic/platform=iOS'` 或项目等效命令。
编译失败必须修复后再进入 Step 6.5 code_review，**不得带编译错误进入 code_review 或 verify**。

## 6.5 code_review（代码审查，**强制执行，不得跳过**）

> execute 完成后、verify 开始前必须执行。code review 发现的问题修完后再进 verify，避免带质量缺陷通过验收。
>
> **与 subagent-driven-development 内置 review 的区别**：Step 6.0 使用 `superpowers:subagent-driven-development` 时，每个 task 内部已有 spec compliance + code quality 两阶段 review（按 task 粒度）。Step 6.5 是**全局审查**，关注跨 task 的一致性（如多文件的埋点完整性、持久化 key 统一格式、整体 Flutter 高保真对齐），两者不可互相替代。

使用 `voltagent-qa-sec:code-reviewer` 对本次所有新建/修改文件执行审查，重点关注：

- **高保真对齐**：Native 实现是否与 `flutter_chain_map.json` 中的链路一致（触发入口、状态流转、副作用、异常分支）
- **Swift 代码规范**：参照项目 CLAUDE.md（懒加载、NoHighlightButton、颜色/字体扩展、SnapKit 约束）
- **线程安全**：网络回调/Timer 回调是否在主线程操作 UI 或共享状态
- **持久化 key 一致性**：UserDefaults/YJCache key 格式是否与 `hunk_facts.json` 中的 `persistence_keys` 一致
- **埋点完整性**：`hunk_facts.json` 中 `analytics_events` 列出的事件是否全部有对应实现
- **AB 门控**：`hunk_facts.json` 中 `ab_gates` 列出的条件判断是否在 Native 中有等价实现

审查结论：
- `APPROVED`：可进入 verify
- `APPROVED_WITH_COMMENTS`：修完注释中的 issues 后进入 verify
- `CHANGES_REQUESTED`：必须修复所有 required 问题后重新 review，**不得直接进入 verify**
  - 修复后重新执行 code_review（Step 6.5）
  - 重新 review 通过（`APPROVED` 或 `APPROVED_WITH_COMMENTS`）后，**必须重新执行 verify**（Step 7），因为代码已变更
  - 不得复用旧的 verify_report.md

产物：`code_review_report.md`（记录审查结论、问题列表、修复状态）

finalize 前置检查新增：`code_review_report.md` 存在且结论为 `APPROVED` 或 `APPROVED_WITH_COMMENTS`（所有 issues 已标记 resolved）。

## 7. verify（验收闭环，**强制执行，不得跳过**）

> **严禁跳过 verify**：verify 是防止遗漏功能进入交付的最后一道防线。`verify_report.md` 和 `verify_result.json` 必须存在，否则视为流程未完成，不得进入 finalize。

> 命令须在 iOS 仓库根目录（`<ios-project-root>`）下执行，`scripts/atlas_verify.py` 相对于该根目录。

```bash
python3 scripts/atlas_verify.py verify \
  --run-dir <run-dir> \
  [--repo-root <ios-project-root>] \
  [--swift-parse-check] \
  [--force]
```

按 task 验收断言检查：
- 功能行为覆盖
- 调用链与数据契约
- Flutter 逻辑一致性（与 `flutter_changes.md` / `pr_diff` 对照）
- 编译/测试（可配置）
- 跨端差异留档一致性：当 task 标注 `cross_platform_gap=true` 时，`verify` 必须核对
  - `cross_platform_gap.md` 中的差异点是否被代码或配置实现
  - `design_tradeoff.md` 的取舍是否与最终实现一致
  - `acceptance_alignment.md` 的对齐项是否全部有验收结论（PASS/WARN/FAIL）
- **diff 覆盖反向检查（强制）**：从 `hunk_facts.json` 出发，逐字段核查 Native 实现是否覆盖：
  - `new_classes`：每个 `user_facing: true` 的 class 是否有对应 Native 文件或类
  - `persistence_keys`：每个持久化 key 格式是否在 Native 代码中有等价实现（key 名、变量结构）
  - `analytics_events`：每个埋点事件是否在 Native 中有对应调用（允许平台差异但必须显式标注）
  - `ab_gates`：每个 AB 门控是否在 Native 中有等价条件判断
  - 反向检查结果输出为 `verify_report.md` 中的 "diff 覆盖矩阵" 表，逐行标注 PASS / WARN / FAIL / SKIP（含原因）
  - 若任一 `user_facing: true` class 无 Native 对应，`verify_result` 必须为 `FAIL`
- 若上述任一项缺失或不一致，`verify_result` 必须为 `FAIL`

### verify FAIL 修复循环

verify 结果为 `FAIL` 时，**禁止直接进入 finalize**，必须走以下闭环：

1. 读取 `verify_report.md` 中的 FAIL 条目，确认是代码缺失、逻辑偏差还是留档缺失
2. 根据 FAIL 类型针对性修复（**不是重跑整个 execute，只改 FAIL 条目对应的代码**）：
   - **代码缺失 / 逻辑偏差**：仅补齐或修正 verify_report 中 FAIL 行对应的 Native 代码，追加记录到 `execution_log.md`（不覆盖原有记录）
   - **留档缺失**（`cross_platform_gap.md` / `design_tradeoff.md` / `acceptance_alignment.md`）：补充相应工件，不需要改代码
3. 修复完成后**重新执行 verify**（Step 7），生成新的 `verify_report.md` 和 `verify_result.json`（覆盖旧版）
4. 重新的 verify 通过（`PASS` 或 `WARN`）后，根据修复类型决定下一步：
   - **有代码改动**：必须重新执行 Step 6.5（code_review），不得复用旧的 `code_review_report.md`，通过后才进入 finalize
   - **纯补留档（无代码改动）**：若 `code_review_report.md` 已存在且结论有效，可直接进入 finalize

### verify WARN 处理

verify 结果为 `WARN` 时，**可进入 finalize**，但：
- WARN 条目必须逐条列入 `finalize_report.md` 的"遗留风险"部分，并附处置意见（已知可接受 / 需后续跟进）
- 不得在 finalize 输出中省略 WARN 内容或标记为"已解决"

### 基准测试（**强制运行，不得跳过**）

verify 通过后，必须运行基准测试：

```bash
python3 .ai/t2n/benchmark/run_benchmark.py --case <case-id> --repo-root <ios-root>
# 注：<case-id> 是 benchmark/cases/ 目录下的 case 名（如 short-opz-001），不是带时间戳的 run-id
```

- Layer 1（hunk_facts）FAIL：回到 Step 2 补充提取，重新走 plan → validate → execute 循环
- Layer 4（Swift 代码扫描）FAIL：Native 代码中关键词未落地，视同 verify FAIL，必须修复后重新 verify
- Layer 2/3 FAIL：chain_map 或 edit_tasks 覆盖不足，在 `verify_report.md` 附录中标注 WARN，列入 finalize_report 遗留风险
- 基准测试结果追加到 `verify_report.md` 附录；**Layer 4 FAIL 导致 verify_result 降级为 FAIL**

产物：`verify_report.md`、`verify_result.json`

## 8. finalize（交付）

> **进入前置检查（强制，任一不满足则禁止交付）：**
> 1. `verify_result.json` 存在，且 `verify_result` 字段值为 `PASS` 或 `WARN`
> 2. `verify_report.md` 中"diff 覆盖矩阵"无 `FAIL` 行
> 3. `plan_validation.md` 结论为 `PASS` 或 `WARN`（`FAIL` 状态下不得进入 execute，更不得进入 finalize）
> 4. `code_review_report.md` 存在，且结论为 `APPROVED` 或 `APPROVED_WITH_COMMENTS`（所有 issues 已标记 resolved）
>
> 若上述任一条件未满足，输出阻断提示并指引用户回到对应步骤修复，不得继续输出交付内容。

汇总（落盘到 `finalize_report.md`，不仅输出到对话）：

```markdown
## 完成任务
- TASK-XX: <功能名> — commit <sha>

## 遗留风险
- [WARN] <verify/code_review WARN 条目，含处置意见>

## 人工项
- <需要人工跟进的事项>

## 回滚点
- 起始 commit: <sha>（执行前最后一个 commit）
- 结束 commit: <sha>（所有 task 完成后）

## 后续建议
- <技术债/优化建议>
```

### 对用户输出（默认结构）

- `需求理解`：说明 Flutter 中真实完成了什么、用户视角下的核心流程、同步到 Native 后的目标。
- `Flutter 实现拆解`：至少覆盖页面结构、交互流程、状态流转、数据来源、接口调用、异常处理、边界逻辑、生命周期相关逻辑、依赖组件/工具/插件。
- `原生实现映射`：说明 Native 页面 / ViewModel / Service / Repository / Router / Manager 的落点，以及 Flutter 行为如何在原生表达。
- `原生代码输出`：当用户要求代码时，按文件输出完整代码，不输出伪代码；若缺少必要上下文，明确标注假设项。
- `差异、阻塞与风险`：显式列出当前无法确定、无法完成、尚未与 Flutter 对齐的部分，以及权限 / 生命周期 / 线程 / 回调 / UI 差异风险。
- `验收清单`：按“是否与 Flutter 一致”列出主流程、交互反馈、状态切换、错误处理、接口参数、返回结果、页面返回恢复、边界情况。

### 最终自检（必做）

- 我是否擅自简化了需求，或把复杂模块拆到后续处理？
- 我是否把 Flutter 的真实行为替换成了更容易实现的版本？
- 我是否遗漏了 Flutter 已有的交互、状态、异常、边界、生命周期、异步回调时序？
- 我是否把备选方案当成默认实现输出？
- 我是否把未完成结果伪装成已完成？
- 任一答案为 `是` 时，先修正输出，再交付。

## understand_chat_log.md 格式（必须遵守）

每次调用 `/understand-anything:understand-chat` 或 `/understand-anything:understand-explain` 后，追加以下格式到 run-dir 的 `understand_chat_log.md`：

```markdown
## [序号] [阶段标签] YYYY-MM-DD HH:MM

**工具**: understand-chat | understand-explain
**阶段**: native_chain_match | execute-TASK-XX | ...
**问题**:
> （完整的查询问题原文）

**关键结论**:
- （节点名称、文件路径、调用关系等核心发现，3-10 条）

**用于**: （说明该结论被用在了哪个产物/决策，如 native_chain_candidates.json CAP-01）
```

规则：
- 序号从 1 开始，每次追加递增
- 阶段标签：plan 阶段用 `plan`，执行阶段用 `execute-TASK-XX`
- 禁止把原始 knowledge-graph 节点 JSON 全量粘贴，只写关键结论
- 若 skill 返回"找不到节点"或"无相关结果"，也必须记录（便于排查）

## Run 目录（目标形态）

```text
.ai/t2n/runs/<run-id>/
├── llm_plan.json
├── flutter_changes.md              ← Step 1 产物（含改动文件列表/能力摘要/含新增UI标志）
├── figma_inputs.md                 ← Step 1 产物（UI 变更时必须）
├── figma_screenshots/              ← Figma 截图目录（UI 变更时）
├── flutter_digest.json             ← --flutter-digest-path 输入的落盘副本（可选）
├── intent.md
├── hunk_facts.json
├── capability_slices.md
├── flutter_chain_map.json
├── native_chain_candidates.json    ← 由 understand-chat 查询结果填充
├── mapping_disambiguation.md
├── edit_tasks.md
├── edit_tasks.json
├── native_touchpoints.md
├── risk_report.md
├── plan_validation.md
├── implementation_plan.md          ← Step 6.0 superpowers:writing-plans 产物
├── understand_chat_log.md          ← 所有 understand-chat/explain 调用记录
├── execution_log.md
├── code_review_report.md           ← Step 6.5 voltagent-qa-sec:code-reviewer 产物
├── verify_report.md
├── verify_result.json
├── finalize_report.md              ← Step 8 产物（完成任务/遗留风险/人工项/回滚点）
├── cross_platform_gap.md           ← 跨端差异时生成（V12 / verify 引用）
├── design_tradeoff.md              ← 跨端差异时生成
└── acceptance_alignment.md         ← 跨端差异时生成
```

> `native-profile-v2/` 目录已移除，Native 代码结构理解统一由 `/understand-anything` 提供。
