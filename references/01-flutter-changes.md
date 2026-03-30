# Step 1. flutter_changes（Flutter 变更采集，必做）

输入源来自 `session_config.json` 中的 `flutter_input`（Step 0 已确认）。

`flutter_changes.md` 最少内容（缺少任一项，后续步骤不得使用该文件）：
- **改动文件列表**：每行一个文件名 + 改动类型（新增/修改/删除）
- **能力摘要**：1-3 句说明本次 diff 的核心功能变更
- **含新增 UI 页面**：`true / false`（决定 Figma 强制约束是否触发）

## Figma 输入校验（UI 变更时必做）

若 `含新增 UI 页面 = true`：
1. 检查 `session_config.json` 中是否已有 Figma 链接和截图
   - **已有** → 将链接和截图路径记录到 `figma_inputs.md`
   - **没有** → 回到 Step 0.4 交互式补充 Figma 链接，拉取截图后继续
2. 将 Figma 信息关联到对应能力

`figma_inputs.md` 格式：
```markdown
## <功能名>
- **Figma 链接**: https://www.figma.com/design/...
- **截图**: ./figma_screenshots/<name>.png
- **覆盖 task**: CAP-XX
```

未完成 Figma 采集时，`plan_validation` 的 UI 强制约束直接 `FAIL`，不得以"后续补充"绕过。

产物：`flutter_changes.md`、`figma_inputs.md`（UI 变更时）
