# Step 2. intent（需求意图提炼）

输入：Flutter 证据（diff/PRD/页面说明/测试点）

在本 skill 中，`intent` 由 `plan` 阶段自动沉淀到工件 `intent.md`。

## 自动映射子流程（强制）

在 `llm_plan` 生成前，必须先完成以下子流程并写入 `llm_plan`：

### 2.1 capability_split

将 Flutter diff 拆分为原子能力（例如：引言更多、解锁按钮禁用、挽留倒计时）。

**必须在 `capability_slices.md` 末尾附加 "新增 Class 归属表"**，列出 diff 中所有新增 class 及其归属 CAP。格式：

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

产物：`capability_slices.md`（含新增 Class 归属表）

### 2.2 flutter_hunk_extract

从业务文件 diff hunk 抽取事实层，**必须使用以下结构化字段**，禁止输出自由文本数组（自由文本无法被后续步骤机械校验，是遗漏的根源）：

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

### 2.3 flutter_chain_extract

为每个能力抽取：触发入口 -> 状态变化 -> 关键交互 -> 副作用。

**完整性传递约束（强制）**：`flutter_chain_map` 生成后，必须对照 `hunk_facts.json` 逐字段校验覆盖情况：
- `new_classes`：每个 `user_facing: true` 的 class 必须出现在某个 CAP 的 `key_interactions` 或独立 CAP 中
- `new_methods`：每个方法必须出现在某个 CAP 的触发入口、交互或副作用中
- `persistence_keys`：每个持久化 key 必须出现在某个 CAP 的 `side_effects` 中
- `analytics_events`：每个埋点事件必须出现在某个 CAP 的 `side_effects` 中
- `ab_gates`：每个 AB 门控必须在对应 CAP 的 `key_interactions` 中注明
- 若发现 `hunk_facts` 中有条目未被任何 CAP 覆盖，必须在 `flutter_chain_map.json` 中输出 `uncovered_facts` 字段列出，并补充到对应 CAP 或新建 CAP，**不得静默跳过**

产物：`flutter_chain_map.json`（含可选 `uncovered_facts` 字段）

### 2.4 native_chain_match

基于 Native 代码理解对每个能力生成 Top-K Native 候选调用链与得分。

**必须**通过调用 `/understand-anything:understand-chat` skill 完成查询，禁止直接用 Python/Bash 解析 `.understand-anything/knowledge-graph.json`。

查询以下内容：
- 该能力对应的 Native 功能域入口（Controller / Manager / Coordinator）
- 现有同类功能的触发方式与调用链（如：弹窗如何 show、充值如何跳转）
- 候选落点的上下文（是编排入口还是纯 UI 组件）

**提问格式（三要素）**：每个问题必须包含以下三个要素：
- **场景**：在哪个页面/模块下（如 `ShortViewController`、充值弹窗）
- **操作**：什么用户操作或系统事件触发（如 用户关闭弹窗、点击 Join Membership）
- **目标**：需要看到什么效果/找到什么（如 弹窗如何 present、调用链是什么、由哪个类负责）
- 示例：`在 ShortViewController 中，用户点击关闭 ShortAudioPurchaseSimpleView 弹窗后，Native 侧有没有已有的回调或 delegate 方法捕获这个关闭事件，由哪个类负责后续逻辑？`

**注意**：查询关键词必须使用 Native 侧的类名/方法名/功能词（如 `ShortViewController`、`ChargeManager`），不要用 Flutter 侧的叫法，否则知识图谱无法匹配到节点

每次查询结果必须追加记录到 `understand_chat_log.md`（见 [understand_chat_log 格式](./09-understand-chat-log.md)）

产物：`native_chain_candidates.json`

### 2.5 disambiguation

对 Top1/Top2 做反证淘汰（触发源、关闭后去向、状态机一致性）。

产物：`mapping_disambiguation.md`

---

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
