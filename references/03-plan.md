# Step 3. plan（同步任务规划）

> 双端同步时，每个平台各执行一次。

先由 CLI 的 LLM 生成 `llm_plan.json`（建议放到 `<run-dir>/<platform>/llm_plan.json`），再执行 planner 落盘与校验。

> 命令须在 Native 仓库根目录下执行，`scripts/atlas_planner.py` 相对于该根目录。
>
> Planner 内部通过 `atlas_intent_bridge.py` 加载 profile-v2 数据并转换为 touchpoints，无需单独调用。

### profile-v2 与 understand-anything 的分工

两者**互补**，不互相替代：

| 用途 | 数据源 | 说明 |
|------|--------|------|
| **feature → file 的静态映射** | `--profile-v2-dir`（`feature_registry.json` + `host_mapping.json`） | 由人工维护的功能域→代码实体映射表，planner 用它做初步触点匹配和得分 |
| **调用链 / 上下文 / 架构理解** | `/understand-anything`（knowledge graph） | Step 2.4 查询用，提供动态的代码关系、调用链、依赖分析 |

- `--profile-v2-dir` 是 `atlas_planner.py plan` 的**必填参数**，缺失会报错
- `understand-anything` 是 Step 2.4 `native_chain_match` 的**必用工具**，不经过 planner 脚本
- 两者数据不重叠：profile-v2 是"哪个功能在哪些文件里"，understand-anything 是"这些文件之间怎么调用"

```bash
python3 scripts/atlas_planner.py plan \
  --repo-root <native-project-root> \
  --run-dir <run-dir>/<platform> \
  --requirement-id <REQ-ID> \
  --requirement-name <REQ-NAME> \
  --profile-v2-dir <native-project-root>/.ai/t2n/native-profile-v2 \
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

## 脚本异常处理

`atlas_planner.py plan` 可能因运行时错误退出（非 plan_validation FAIL，而是 Python 异常）。常见场景及处理：

| exit code | 含义 | 处理 |
|-----------|------|------|
| 0 | 成功 | 继续 Step 4 |
| 1 | 运行时异常（如 JSON 解析失败、字段缺失） | 读 stderr，修复 `llm_plan.json` 中的格式问题后重跑 |
| 3 | 文件未找到（profile-v2 缺失、run-dir 不存在） | 检查路径参数是否正确，确认 `feature_registry.json` 和 `host_mapping.json` 存在 |

**通用排查步骤**：
1. 读 stderr 中的完整 traceback，定位到具体的 Python 文件和行号
2. 若错误在 `normalize_llm_task()` → `llm_plan.json` 中某个 task 字段格式不对，修正后重跑
3. 若错误在 `load_profile_v2()` → profile-v2 目录结构不对，检查 `--profile-v2-dir` 路径
4. 若错误在 `ensure_run_dir()` → `--run-dir` 路径不存在或无写入权限

> 脚本异常不等于 plan_validation FAIL。异常是"脚本没跑完"，FAIL 是"跑完了但校验不通过"。异常时修复输入后重跑即可，不需要回退到 Step 2。

## 产物（存入 `<platform>/`）

- `intent.md`
- `edit_tasks.md`
- `edit_tasks.json`
- `native_touchpoints.md`
- `risk_report.md`
- `plan_validation.md`
