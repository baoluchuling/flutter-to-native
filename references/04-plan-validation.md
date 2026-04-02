# Step 4. plan_validation（规划校验）

- 校验未决项、触发方式、行为契约完整性、落点可执行性、风险标注
- 校验映射证明（`V7`）：无 `mapping_proof` 或 `status!=mapped` 直接 `FAIL`
- 校验自动映射流程证据（`V8`）：缺少 `mapping_pipeline` 或缺少四步产物直接 `FAIL`
- 校验入口级映射真实性（`V9`）：主落点若为纯视图且缺少编排入口证据，或缺少反向回溯证据，直接 `FAIL`
- 校验生命周期与证据可执行性（`V10`）：生命周期与 Native 链路不一致，或 `evidence_lines` 无法在仓库定位，直接 `FAIL`；未提供 `--pr-diff-path` 时，`pr_diff_sha256` 校验自动豁免
- 校验弹窗入口语义（`V11`）：task 含 popup/dialog/弹窗 时，首条 `native_chain` 必须是 `show/present`，且 `entry_semantics=popup_show`，否则 `FAIL`
- 校验跨端差异闭环（`V12`）：当 task 标注 `cross_platform_gap=true` 时，若缺少 `cross_platform_gap.md` / `design_tradeoff.md` / `acceptance_alignment.md` 任一项，直接 `FAIL`
- 校验 diff 一致性（`V13`，`diff-consistency`，**强制运行，不得省略**）：
  - 逐个 CAP 检查：Native task 是否覆盖了该 CAP 在 Flutter 中的所有行为（触发入口、状态流转、交互分支、副作用）。若某个 CAP 无对应 Native task，或 Native task 的行为契约明显缺失 Flutter 已有的分支（如 Flutter 有 V1/V2 双弹窗但 Native 只规划了单弹窗），直接 `FAIL`
  - **新增 class 覆盖检查**：枚举 Flutter diff 中所有新增 `class`（含私有类 `class _Foo`），逐一确认 `edit_tasks.md` 中存在对应 task 或触点子项；若任一新增 class 未被覆盖，直接 `FAIL`，并列出未覆盖的 class 名称
- 校验新建文件集成入口（`V15`，**强制运行，不得省略**）：
  - 枚举 `edit_tasks.json` 中所有新建（Create）的 UI 文件（弹窗 / 页面 / 视图）
  - 每个新建 UI 文件必须有 `integration_point` 字段，指明由哪个已有文件/方法实例化并调用
  - 若新建 UI 文件缺少 `integration_point`，或 `integration_point` 指向的文件不在任何 task 的 `edit_anchors` 中，直接 `FAIL`
  - 此校验防止出现"创建了 View 但无人调用"的死代码
- 校验资产与本地化完整性（`V16`，**强制运行，不得省略**）：
  - 枚举 Flutter diff 中新增的图片资源文件（`assets/`、`assets/images/` 下的 png/svg/webp）
  - 若 task 的 UI 引用了这些资源（通过 Figma 截图可见、或 Flutter 代码中 `Image.asset()` 引用），对应 task 的 `asset_dependencies` 必须非空
  - 枚举 Flutter diff 中新增的 l10n key（`app_en.arb` 等 ARB 文件中的新增 key）
  - 若 task 的 UI 中使用了这些 key 对应的文案，对应 task 的 `l10n_keys` 必须非空
  - 任一资产/l10n 依赖缺失 → `WARN`（不阻塞，但必须在 plan_validation 输出中标注）
- 校验 task 复杂度一致性（`V17`，**强制运行，不得省略**）：
  - 每个 task 必须有 `model_tier` 字段（haiku / sonnet / opus）
  - 检查每个 task 的 `edit_anchors` 是否属于同一复杂度等级：
    - 纯字段/配置追加（新增属性、注册 key、调整颜色值）→ haiku
    - 修改现有逻辑、仿写现有 pattern、集成接入 → sonnet
    - 新建大文件（>300 行）、复杂 UI 布局、需 Figma 设计判断 → opus
  - 若同一 task 内 edit_anchors 跨等级（如既有 haiku 级的字段追加又有 sonnet 级的逻辑扩展）→ `FAIL`，必须回到 Step 3 拆分
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

## Gate Checklist

完成 Step 4 前，逐条核对：

- [ ] `<platform>/plan_validation.md` 已生成
- [ ] V7-V16 每项都有明确结论（PASS / WARN / FAIL）
- [ ] 无任何 FAIL 项（有 FAIL 则必须回退 Step 3 修复后重跑）
- [ ] V13 新增 class 覆盖表：每个 `user_facing: true` class 都有对应 TASK
- [ ] V15 集成入口：每个新建 UI 文件有 `integration_point` 且指向的文件在某 task 的 `edit_anchors` 中
- [ ] V16 资产/本地化：每个 UI task 的 `asset_dependencies` 和 `l10n_keys` 已检查
- [ ] UI 强制约束：涉及 UI 的 task 都有 Figma 链接 + 截图
- [ ] 最终结论为 PASS 或 WARN（非 FAIL）
