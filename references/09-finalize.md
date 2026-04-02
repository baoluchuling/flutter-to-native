# Step 9. finalize（交付）

> 双端同步时，所有平台都通过 verify 后，合并输出一份 finalize_report。

> **进入前置检查（强制，每个平台都必须满足，任一不满足则禁止交付）：**
> 1. `<platform>/verify_result.json` 存在，且 `verify_result` 字段值为 `PASS` 或 `WARN`
> 2. `<platform>/verify_report.md` 中"diff 覆盖矩阵"无 `FAIL` 行
> 3. `<platform>/plan_validation.md` 结论为 `PASS` 或 `WARN`（`FAIL` 状态下不得进入 execute，更不得进入 finalize）
> 4. `<platform>/code_review_report.md` 存在，且结论为 `APPROVED` 或 `APPROVED_WITH_COMMENTS`（所有 issues 已标记 resolved）
>
> 若上述任一条件未满足，输出阻断提示并指引用户回到对应步骤修复，不得继续输出交付内容。

汇总（落盘到 `finalize_report.md`，不仅输出到对话）：

```markdown
## 完成任务

### iOS
- TASK-XX: <功能名> — commit <sha>

### Android
- TASK-XX: <功能名> — commit <sha>

## 遗留风险
- [iOS][WARN] <verify/code_review WARN 条目，含处置意见>
- [Android][WARN] <...>

## 人工项
- <需要人工跟进的事项>

## 回滚点

### iOS
- 起始 commit: <sha>（执行前最后一个 commit）
- 结束 commit: <sha>（所有 task 完成后）

### Android
- 起始 commit: <sha>
- 结束 commit: <sha>

## 后续建议
- <技术债/优化建议>
```

> 单端同步时，省略另一平台的段落即可。

## 对用户输出（默认结构）

- `需求理解`：说明 Flutter 中真实完成了什么、用户视角下的核心流程、同步到 Native 后的目标。
- `Flutter 实现拆解`：至少覆盖页面结构、交互流程、状态流转、数据来源、接口调用、异常处理、边界逻辑、生命周期相关逻辑、依赖组件/工具/插件。
- `原生实现映射`：按平台分别说明落点和行为表达方式。
- `原生代码输出`：当用户要求代码时，按文件输出完整代码，不输出伪代码；若缺少必要上下文，明确标注假设项。
- `差异、阻塞与风险`：显式列出当前无法确定、无法完成、尚未与 Flutter 对齐的部分，以及权限 / 生命周期 / 线程 / 回调 / UI 差异风险。
- `验收清单`：按"是否与 Flutter 一致"列出主流程、交互反馈、状态切换、错误处理、接口参数、返回结果、页面返回恢复、边界情况。

## 最终自检（必做）

- 我是否擅自简化了需求，或把复杂模块拆到后续处理？
- 我是否把 Flutter 的真实行为替换成了更容易实现的版本？
- 我是否遗漏了 Flutter 已有的交互、状态、异常、边界、生命周期、异步回调时序？
- 我是否把备选方案当成默认实现输出？
- 我是否把未完成结果伪装成已完成？
- 任一答案为 `是` 时，先修正输出，再交付。

## Gate Checklist

完成 Step 9 前，逐条核对：

- [ ] 前置检查 4 项全部满足（verify_result / verify_report / plan_validation / code_review_report）
- [ ] `finalize_report.md` 已落盘到 run 目录（非仅对话输出）
- [ ] 完成任务列表：每个 task 有 commit SHA
- [ ] 遗留风险：所有 verify WARN 项已列入，附处置意见
- [ ] 回滚点：起始/结束 commit SHA 准确
- [ ] 最终自检 6 项全部回答"否"
- [ ] `finalize_report.md` 中无"后续待办"或"deferred"项（除非用户在 Step 5 明确同意）
