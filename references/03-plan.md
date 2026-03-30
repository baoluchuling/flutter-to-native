# Step 3. plan（能力任务规划）

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

## Task 结构要求

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

## 产物

- `intent.md`
- `edit_tasks.md`
- `edit_tasks.json`
- `native_touchpoints.md`
- `risk_report.md`
- `plan_validation.md`
