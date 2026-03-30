# Run 目录（目标形态）

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
