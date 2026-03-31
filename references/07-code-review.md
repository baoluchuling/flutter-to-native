# Step 7. code_review（代码审查，**强制执行，不得跳过**）

> execute 完成后、verify 开始前必须执行。code review 发现的问题修完后再进 verify，避免带质量缺陷通过验收。
>
> **与 subagent-driven-development 内置 review 的区别**：Step 6 使用 `superpowers:subagent-driven-development` 时，每个 task 内部已有 spec compliance + code quality 两阶段 review（按 task 粒度）。Step 7 是**全局审查**，关注跨 task 的一致性（如多文件的埋点完整性、持久化 key 统一格式、整体 Flutter 高保真对齐），两者不可互相替代。

使用 `voltagent-qa-sec:code-reviewer` 对本次所有新建/修改文件执行审查，重点关注：

- **高保真对齐**：Native 实现是否与 `flutter_chain_map.json` 中的链路一致（触发入口、状态流转、副作用、异常分支）
- **代码规范**：参照目标仓库 CLAUDE.md 中定义的平台规范（参见 platform profile "代码规范锚点"）
- **线程/协程安全**：回调是否在正确线程/作用域操作 UI 或共享状态（参见 platform profile "code_review 重点"）
- **持久化 key 一致性**：key 格式是否与 `hunk_facts.json` 中的 `persistence_keys` 一致
- **埋点完整性**：`hunk_facts.json` 中 `analytics_events` 列出的事件是否全部有对应实现
- **AB 门控**：`hunk_facts.json` 中 `ab_gates` 列出的条件判断是否在 Native 中有等价实现

## 审查结论

- `APPROVED`：可进入 verify
- `APPROVED_WITH_COMMENTS`：修完注释中的 issues 后进入 verify
- `CHANGES_REQUESTED`：必须修复所有 required 问题后重新 review，**不得直接进入 verify**
  - 修复后重新执行 code_review（Step 7）
  - 重新 review 通过（`APPROVED` 或 `APPROVED_WITH_COMMENTS`）后，**必须重新执行 verify**（Step 8），因为代码已变更
  - 不得复用旧的 verify_report.md

产物：`<platform>/code_review_report.md`（记录审查结论、问题列表、修复状态）

finalize 前置检查新增：`code_review_report.md` 存在且结论为 `APPROVED` 或 `APPROVED_WITH_COMMENTS`（所有 issues 已标记 resolved）。
