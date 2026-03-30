# Step 5. confirm（人工确认）

用户审阅：`edit_tasks.md + plan_validation.md`

未确认不进入执行。

## 用户提出修改意见时的回环

- 修改范围仅涉及个别 task 的描述/落点/验收断言 → 直接修改 `edit_tasks.md` / `edit_tasks.json`，**无需重跑 plan_validation**，修改后重新 confirm
- 修改范围影响 task 结构（新增/删除 task）或映射证明 → 回到 Step 3（plan）重新生成对应 task，重新执行 plan_validation，再 confirm
- 用户拒绝整体方案 → 回到 Step 2（intent/自动映射子流程）重新规划能力切片
