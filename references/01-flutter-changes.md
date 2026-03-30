# Step 1. flutter_changes（Flutter 变更采集，必做）

输入至少满足其一：
- `--flutter-path`（Flutter 代码路径）
- `--flutter-digest-path`（结构化摘要）
- `--pr-diff-path`（PR diff）

说明：若缺少以上三类证据，`plan` 会直接失败。

`flutter_changes.md` 最少内容（缺少任一项，后续步骤不得使用该文件）：
- **改动文件列表**：每行一个文件名 + 改动类型（新增/修改/删除）
- **能力摘要**：1-3 句说明本次 diff 的核心功能变更
- **含新增 UI 页面**：`true / false`（决定 Figma 强制约束是否触发）

## Figma 输入采集（UI 变更时必做）

若 `含新增 UI 页面 = true`，必须在本步骤完成 Figma 截图落盘：
1. 用户提供 Figma 链接（必须）
2. 使用 `mcp__plugin_figma_figma__get_screenshot` 拉取截图
3. 将链接和截图路径记录到 `figma_inputs.md`

`figma_inputs.md` 格式：
```markdown
## <功能名>
- **Figma 链接**: https://www.figma.com/design/...
- **截图**: ./figma_screenshots/<name>.png
- **覆盖 task**: CAP-XX
```

未完成 Figma 采集时，`plan_validation` 的 UI 强制约束直接 `FAIL`，不得以"后续补充"绕过。

产物：`flutter_changes.md`、`figma_inputs.md`（UI 变更时）
