# Run 目录（目标形态）

## 双端同步

```text
.ai/t2n/runs/<run-id>/
├── session_config.json                 ← Step 0 产物（平台/路径/输入源）
├── token_tracking.json                 ← Step 0 产物（JSONL 基线 + 按步骤行号）
├── token_usage.md                      ← Step 0 创建，Step 6/9 追加（subagent 明细 + 汇总）
├── flutter/                            ← 共享 Flutter 分析产物
│   ├── flutter_changes.md              ← Step 1 产物
│   ├── figma_inputs.md                 ← Step 1 产物（UI 变更时必须）
│   ├── figma_screenshots/              ← Figma 截图目录
│   ├── flutter_digest.json             ← 输入落盘副本（可选）
│   ├── hunk_facts.json                 ← Step 2.2 产物
│   ├── capability_slices.md            ← Step 2.1 产物
│   └── flutter_chain_map.json          ← Step 2.3 产物
├── ios/                                ← iOS 平台产物
│   ├── llm_plan.json
│   ├── intent.md
│   ├── native_chain_candidates.json
│   ├── mapping_disambiguation.md
│   ├── edit_tasks.md
│   ├── edit_tasks.json
│   ├── native_touchpoints.md
│   ├── risk_report.md
│   ├── plan_validation.md
│   ├── implementation_plan.md
│   ├── understand_chat_log.md
│   ├── execution_log.md
│   ├── code_review_report.md
│   ├── verify_report.md
│   ├── verify_result.json
│   ├── cross_platform_gap.md           ← 跨端差异时生成
│   ├── design_tradeoff.md
│   └── acceptance_alignment.md
├── android/                            ← Android 平台产物（结构同 ios/）
│   ├── llm_plan.json
│   ├── ...
│   └── acceptance_alignment.md
└── finalize_report.md                  ← Step 8 产物（合并双端）
```

## 单端同步

单端时无 `flutter/` 子目录，共享产物与平台产物平铺：

```text
.ai/t2n/runs/<run-id>/
├── session_config.json                 ← Step 0 产物
├── token_tracking.json                 ← Step 0 产物
├── token_usage.md                      ← Step 0 创建，Step 6/9 追加
├── flutter_changes.md
├── figma_inputs.md
├── hunk_facts.json
├── capability_slices.md
├── flutter_chain_map.json
├── llm_plan.json
├── intent.md
├── native_chain_candidates.json
├── mapping_disambiguation.md
├── edit_tasks.md
├── edit_tasks.json
├── native_touchpoints.md
├── risk_report.md
├── plan_validation.md
├── implementation_plan.md
├── understand_chat_log.md
├── execution_log.md
├── code_review_report.md
├── verify_report.md
├── verify_result.json
├── finalize_report.md
├── cross_platform_gap.md
├── design_tradeoff.md
└── acceptance_alignment.md
```

> Native 代码结构理解统一由 `/understand-anything` 提供（知识图谱）。Planner 通过 `--llm-resolution-path` 获取 LLM 映射结果，通过启发式文件名匹配兜底。
