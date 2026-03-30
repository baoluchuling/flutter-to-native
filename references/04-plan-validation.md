# Step 4. plan_validation（规划校验）

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

## 结论

- `PASS`：可进入执行
- `WARN`：可执行但需人工关注
- `FAIL`：禁止执行，回到 plan 修正

## UI 强制约束

- 涉及 UI 的 task，必须有 Figma 链接 + 截图
- 缺失时 `plan_validation` 必须为 `FAIL`
