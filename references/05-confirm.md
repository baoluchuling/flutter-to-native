# Step 5. confirm（人工确认）

用户审阅：`edit_tasks.md + plan_validation.md`

未确认不进入执行。

## 用户提出修改意见时的回环

- 修改范围仅涉及个别 task 的**描述或验收断言**（不涉及路径/映射） → 直接修改 `edit_tasks.md` / `edit_tasks.json`，无需重跑 plan_validation，修改后重新 confirm
- 修改范围涉及 task 的 **`primary_path` / `native_landing` / `mapping_proof`** 等路径或映射字段 → 修改后**必须重跑 plan_validation 中的 V9（入口级映射）和 V10（证据可执行性）**，确认修改后的路径/证据仍然有效，通过后重新 confirm
- 修改范围影响 task 结构（新增/删除 task）或映射证明 → 回到 Step 3（plan）重新生成对应 task，重新执行 plan_validation，再 confirm
- 用户拒绝整体方案 → 回到 Step 2（intent/自动映射子流程）重新规划能力切片

## Gate Checklist

完成 Step 5 前，逐条核对：

- [ ] 用户已确认（AskUserQuestion 收到"确认开始"或等效回复）
- [ ] 用户的修改意见已全部落实到 `edit_tasks.json` / `edit_tasks.md`
- [ ] 若用户修改涉及路径/映射，V9/V10 已重跑并 PASS
- [ ] 若用户修改涉及 task 结构，plan_validation 已重跑并 PASS
