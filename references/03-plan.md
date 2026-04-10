# Step 3. plan（同步任务规划）

> 双端同步时，每个平台各执行一次。

将 Step 2 产出的 `llm_plan.json`（位于 `<run-dir>/<platform>/llm_plan.json`）作为输入，执行 planner 落盘。

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

## CAP → task 覆盖规则（强制）

`native_chain_candidates.json` 中 mapping score > 0 的每个 CAP **必须**生成独立 task。禁止将 CAP 合并到其他 task 中作为"备注"或"行为补充"——合并会导致该能力在执行阶段被静默跳过。mapping score = 0 的 CAP 可不生成 task，但必须在 `llm_plan.json` 的 `excluded_caps` 中列出并附理由。

`plan_validation` V13 会逐个校验此规则，违反直接 FAIL。

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
- 验收断言（完成标准）。**新建 UI 文件的 task 必须包含以下验收断言**（不得省略）：
  `grep -rn "<ClassName>" <项目目录> --include="*.swift" | grep -v "<自身文件名>" 至少有 1 条匹配`
  此断言确保新建的 UI 不是死代码——subagent 看到这条验收断言就知道光创建文件不算完成，必须在 `integration_point` 指向的位置接入调用后才能交差
- 资产依赖（`asset_dependencies`）：该 task 所需的图片/图标资源列表（来自 Flutter `assets/` 目录），每项含：Flutter 路径、Native 目标路径、格式要求（@2x.png）。无资产依赖时显式标注 `[]`
- 本地化 key（`l10n_keys`）：该 task 引入的新翻译 key 列表，每项含：key 名、默认英文文案、使用位置。无新增 key 时显式标注 `[]`
- 集成入口（`integration_point`）：新建 UI 文件必须指明由哪个已有文件/方法调用。**格式强制为 `文件名.方法名:行号 — 操作描述`**，自然语言描述（如"某个 Controller 调用"）直接 FAIL。示例：
  - ✅ `ShortViewController.reader(_:prologueHeaderView:chapterIndex:pageIndex:):932 — 替换现有 ShortAuthorBookCardView 为 ShortHeaderInfoView`
  - ✅ `ChargeManager.openShortRetainDialog(_:scene:countdownTime:isFakeCountdown:):231 — 调用 ShortRetainPopupView.show()`
  - ❌ `ShortViewController 渲染首页时调用`（无方法名、无行号、不可执行）
  
  修改已有文件时此字段可省略。
  
  **集成包含在新建 task 内，不拆为独立 task**：`integration_point` 指向的文件必须出现在该 task 的 `edit_anchors` 中。新建 UI 和接入调用方是同一个 task 的职责——拆成两个 task 会引入 handoff，导致"文件创建了但没人接入"的问题。task 的 `edit_anchors` 应同时包含新建文件和调用方文件。
  
  同时，task 的 `behavior_contract` 必须包含调用方的集成逻辑描述：如何实例化、传什么参数、处理什么回调、替换还是新增、条件判断等。这些信息从 Flutter diff 中调用方的代码提取（Flutter 中新建 UI 和调用它的代码通常在同一次 diff 中）。
- 模型等级（`model_tier`）：该 task 派发 subagent 时使用的模型等级。Step 6 执行时直接使用此字段指定模型，不做二次判断。取值和判定规则如下：

  | model_tier | 判定条件 | 典型任务 |
  |-----------|---------|---------|
  | **haiku** | 改动 ≤2 个文件，无跨文件依赖，纯追加字段/配置/key | 数据模型字段扩展、AB 开关注册、样式微调（颜色/间距）、本地化 key 添加 |
  | **sonnet** | 改动 3-5 个文件，或需理解现有代码模式后仿写 | 流程编排扩展、交互入口修改、现有组件重构、集成接入 |
  | **opus** | 新建大文件（>300行）、涉及复杂 UI 布局、需 Figma 设计判断 | 新建弹窗/页面（含 dark/light 主题）、复杂状态管理 |

  **约束：同一 task 内所有 `edit_anchors` 必须属于同一复杂度等级**，若跨等级则必须拆分为多个 task。

  **code review** 始终使用 **opus**。

  **model_tier 降级检查**：Step 7 code_review 必须检查每个 task 的 model_tier 是否与实际改动复杂度匹配。若 sonnet 级 subagent 产出的代码有明显质量问题（UI 还原度低、状态管理遗漏、边界条件缺失），在 `code_review_report.md` 中标注 `model_tier_mismatch`，修复时升级模型。

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
- [ ] 每个 task 含 `model_tier`（haiku / sonnet / opus），且同一 task 内 edit_anchors 属于同一复杂度等级
- [ ] `<platform>/edit_tasks.md` 已生成（人类可读版本）
- [ ] `<platform>/native_touchpoints.md` 已生成（含修改文件表 + 新建文件表 + 图片资源表）
- [ ] `<platform>/risk_report.md` 已生成
