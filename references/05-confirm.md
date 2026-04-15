# Step 5. confirm（人工确认）

## 自动模式跳过规则

读取 `session_config.json` 的 `auto_mode` 字段：

- **`auto_mode: false`（标准模式）**：正常执行本步骤，用户审阅后确认
- **`auto_mode: true`（自动模式）**：
  1. 输出 `edit_tasks.md` 摘要（task 数量、涉及文件数、model_tier 分布）供用户知晓
  2. **不等待用户确认**，直接标记 Step 5 completed，进入 Step 6
  3. 在 `execution_log.md` 开头记录 `## [AUTO_MODE] Step 5 跳过，plan_validation 结论: PASS/WARN`

> **关于简化**：无论标准模式还是自动模式，AI 都**禁止提议简化需求**。只有用户主动说"XX 先不做"时才允许。自动模式下用户没有审阅环节来提出，所以实际上不会有简化发生。

---

## 标准模式流程

用户审阅：`edit_tasks.md + plan_validation.md`

未确认不进入执行。

## 用户提出修改意见时的回环

| 修改范围 | 操作 | 重跑校验 |
|---------|------|---------|
| 个别 task 的描述或验收断言 | 直接修改 `edit_tasks.md` / `edit_tasks.json` | 若修改弱化了验收断言（删除 grep 检查、降低覆盖要求），必须重跑 V15 确认集成入口仍有保障；否则无需重跑 |
| task 的路径/映射字段（`primary_path` / `native_landing` / `mapping_proof`） | 修改后重跑 V9 + V10 | V9（入口级映射）+ V10（证据可执行性） |
| task 结构（新增/删除/拆分 task） | 回到 Step 3 重新生成 | 完整 plan_validation（V7-V17） |
| 拒绝整体方案 | 回到 Step 2 重新规划 | 从 Step 2 开始全部重来 |

**迭代收敛规则**：用户可多次反馈修改意见，每次按上表处理。但每轮只回退到最远需要的步骤，不重复回退。最终用户回复"确认"时结束 Step 5。

## Gate Checklist

完成 Step 5 前，逐条核对：

**标准模式（`auto_mode: false`）：**
- [ ] 用户已明确确认（收到"确认开始"或等效回复，而非仍在反馈修改意见）
- [ ] 用户的修改意见已全部落实到 `edit_tasks.json` / `edit_tasks.md`（Read 确认文件内容已更新）
- [ ] 若用户修改涉及描述/断言：文件已更新，无需重跑校验
- [ ] 若用户修改涉及路径/映射：V9 + V10 已重跑并 PASS
- [ ] 若用户修改涉及 task 结构：完整 plan_validation 已重跑并 PASS
- [ ] 若用户无修改意见：直接确认，以上条件自动满足

**自动模式（`auto_mode: true`）：**
- [ ] plan_validation 结论为 PASS 或 WARN（FAIL 时即使自动模式也必须回退修复，不得跳过）
- [ ] 已输出 edit_tasks.md 摘要
- [ ] `execution_log.md` 已记录 `[AUTO_MODE] Step 5 跳过`
