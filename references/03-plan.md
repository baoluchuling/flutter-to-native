# Step 3. plan（同步任务规划）

> 双端同步时，每个平台各执行一次。

先由 CLI 的 LLM 生成 `llm_plan.json`（建议放到 `<run-dir>/<platform>/llm_plan.json`），再执行 planner 落盘与校验。

> 命令须在 Native 仓库根目录下执行，`scripts/atlas_planner.py` 相对于该根目录。

```bash
python3 scripts/atlas_planner.py plan \
  --repo-root <native-project-root> \
  --run-dir <run-dir>/<platform> \
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
- `meta.platform`（必须为 `ios` 或 `android`）
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
- 原生落点（UI/编排/数据/路由，可多对多；使用 platform profile 定义的架构词汇）
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
- 资产依赖（`asset_dependencies`）：该 task 所需的图片/图标资源列表（来自 Flutter `assets/` 目录），每项含：Flutter 路径、Native 目标路径、格式要求（@2x.png）。无资产依赖时显式标注 `[]`
- 本地化 key（`l10n_keys`）：该 task 引入的新翻译 key 列表，每项含：key 名、默认英文文案、使用位置。无新增 key 时显式标注 `[]`
- 集成入口（`integration_point`）：新建 UI 文件必须指明由哪个已有文件/方法调用（如 `ShortViewController.showCardViews()` 调用 `MembershipUnlockV2PopupView.show()`）。修改已有文件时此字段可省略
- 模型等级（`model_tier`）：该 task 派发 subagent 时使用的模型等级，取值 `haiku` / `sonnet` / `opus`。判定依据见 Step 6 "Subagent 模型选择"。**同一 task 内所有 `edit_anchors` 必须属于同一复杂度等级**，若跨等级则必须拆分为多个 task

## 脚本异常处理

`atlas_planner.py plan` 可能因运行时错误退出（非 plan_validation FAIL，而是 Python 异常）。常见场景及处理：

| exit code | 含义 | 处理 |
|-----------|------|------|
| 0 | 成功 | 继续 Step 4 |
| 1 | 运行时异常（如 JSON 解析失败、字段缺失） | 读 stderr，修复 `llm_plan.json` 中的格式问题后重跑 |
| 3 | 文件未找到（run-dir 不存在、必要输入文件缺失） | 检查 `--run-dir`、`--repo-root`、`--llm-resolution-path` 路径是否正确 |

**通用排查步骤**：
1. 读 stderr 中的完整 traceback，定位到具体的 Python 文件和行号
2. 若错误在 `normalize_llm_task()` → `llm_plan.json` 中某个 task 字段格式不对，修正后重跑
3. 若错误在 `ensure_run_dir()` → `--run-dir` 路径不存在或无写入权限

> 脚本异常不等于 plan_validation FAIL。异常是"脚本没跑完"，FAIL 是"跑完了但校验不通过"。异常时修复输入后重跑即可，不需要回退到 Step 2。

## 产物（存入 `<platform>/`）

- `intent.md`
- `edit_tasks.md`
- `edit_tasks.json`
- `native_touchpoints.md`
- `risk_report.md`
- `plan_validation.md`

## Gate Checklist

完成 Step 3 前，逐条核对：

- [ ] `<platform>/intent.md` 已生成
- [ ] `<platform>/edit_tasks.json` 已生成，meta.analysis_mode / generated_by / platform 字段完整
- [ ] 每个 task 含必要字段：title / capability / feature_scope / trigger_lifecycle / behavior_contract / native_touchpoints / edit_anchors / mapping_proof / acceptance
- [ ] 每个 task 含 `asset_dependencies`（图片资源列表，无则为 `[]`）
- [ ] 每个 task 含 `l10n_keys`（本地化 key 列表，无则为 `[]`）
- [ ] 每个新建 UI 文件的 task 含 `integration_point`（指明调用方）
- [ ] `<platform>/edit_tasks.md` 已生成（人类可读版本）
- [ ] `<platform>/native_touchpoints.md` 已生成（含修改文件表 + 新建文件表 + 图片资源表）
- [ ] `<platform>/risk_report.md` 已生成
