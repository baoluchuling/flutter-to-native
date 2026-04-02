# Step 7. code_review（代码审查，**强制执行，不得跳过**）

> execute 完成后、verify 开始前必须执行。code review 发现的问题修完后再进 verify，避免带质量缺陷通过验收。

### 与 Step 6 内置 review 的关系

Step 6 使用 `superpowers:subagent-driven-development` 时，每个 task 内部已有 spec compliance + code quality 两阶段 review。Step 7 是**全局审查**，两者**始终都执行、不可互相替代**，职责划分如下：

| 维度 | Step 6 subagent review（按 task） | Step 7 全局 code_review |
|------|-----------------------------------|------------------------|
| **粒度** | 单个 task 内的文件 | 本次所有改动文件 |
| **关注点** | task 实现是否符合 edit_tasks 中的行为契约 | 跨 task 一致性 + 整体质量 |
| **典型检查** | 单 task 逻辑正确性、接口契约 | 埋点完整性、持久化 key 格式统一、AB 门控全覆盖、API 版本兼容 |
| **Flutter 对齐** | task 级别的行为匹配 | 整体 `flutter_chain_map.json` 链路对齐 |
| **线程/内存安全** | task 内的明显问题 | 跨 task 的 delegate 循环引用、Timer 泄漏、多 task 共享状态竞争 |

> 即使 Step 6 使用 inline execution（非 subagent），Step 7 仍然必须执行。

使用 `voltagent-qa-sec:code-reviewer` 对本次所有新建/修改文件执行审查，重点关注：

- **高保真对齐**：Native 实现是否与 `flutter_chain_map.json` 中的链路一致（触发入口、状态流转、副作用、异常分支）
- **代码规范**：参照目标仓库 CLAUDE.md 中定义的平台规范（参见 platform profile "代码规范锚点"）
- **线程/协程安全**：回调是否在正确线程/作用域操作 UI 或共享状态（参见 platform profile "code_review 重点"）
- **持久化 key 一致性**：key 格式是否与 `hunk_facts.json` 中的 `persistence_keys` 一致
- **埋点完整性**：`hunk_facts.json` 中 `analytics_events` 列出的事件是否全部有对应实现
- **AB 门控**：`hunk_facts.json` 中 `ab_gates` 列出的条件判断是否在 Native 中有等价实现
- **API 版本兼容性**：逐一检查新增/修改代码中调用的系统 API 和第三方库 API 是否兼容 `session_config.json` 中 `platform_constraints` 声明的部署目标。重点关注：
  - iOS：`UISheetPresentationController`（15+）、`UIContentUnavailableConfiguration`（17+）、`\.sensoryFeedback`（17+）、`async/await`（需 13+ back-deploy 或 15+）、`AttributedString`（15+）等常见高版本 API
  - Android：Compose（minSdk 21+）、`WindowInsetsCompat`（API level 差异）、`LifecycleOwner` 扩展等
  - 已使用 `#available` / `Build.VERSION.SDK_INT` 保护的高版本 API 需检查 fallback 分支是否有等价实现（不能为空或仅 return）
  - 发现未保护的高版本 API → `CHANGES_REQUESTED`

## 禁止 "deferred" 的场景

以下问题**不得标为 deferred / 后续跟进 / 已知遗留**，必须在 code_review 阶段解决：

1. **行为契约违反**：task 的 `behavior_contract` 中定义的交互（如 onPay 触发支付）未实现 → `CHANGES_REQUESTED`
2. **死代码**：新建的 UI 文件未被任何代码调用（缺少集成入口）→ `CHANGES_REQUESTED`
3. **资产缺失**：task 的 `asset_dependencies` 中列出的图片资源未复制到 Native 项目 → `CHANGES_REQUESTED`
4. **本地化缺失**：task 的 `l10n_keys` 中列出的翻译 key 未添加到本地化文件 → `CHANGES_REQUESTED`
5. **埋点缺失**：`hunk_facts.json` 中 `analytics_events` 列出的事件在 Native 中无对应实现 → `CHANGES_REQUESTED`

仅以下情况允许 deferred：
- 需要第三方团队配合（如后端接口未就绪）且已在 `cross_platform_gap.md` 中记录
- 用户在 Step 5 (confirm) 中明确同意简化

## 审查结论

- `APPROVED`：可进入 verify
- `APPROVED_WITH_COMMENTS`：修完注释中的 issues 后进入 verify
- `CHANGES_REQUESTED`：必须修复所有 required 问题后重新 review，**不得直接进入 verify**
  - 修复后重新执行 code_review（Step 7）
  - 重新 review 通过（`APPROVED` 或 `APPROVED_WITH_COMMENTS`）后，**必须重新执行 verify**（Step 8），因为代码已变更
  - 不得复用旧的 verify_report.md

产物：`<platform>/code_review_report.md`（记录审查结论、问题列表、修复状态）

finalize 前置检查新增：`code_review_report.md` 存在且结论为 `APPROVED` 或 `APPROVED_WITH_COMMENTS`（所有 issues 已标记 resolved）。

## Gate Checklist

完成 Step 7 前，逐条核对：

- [ ] `<platform>/code_review_report.md` 已生成
- [ ] 结论为 `APPROVED` 或 `APPROVED_WITH_COMMENTS`（若曾为 `CHANGES_REQUESTED`，必须已修复并重新 review 通过）
- [ ] 所有 Critical issues 已标记 resolved
- [ ] 所有 Important issues 已标记 resolved 或有明确合理的 deferred 理由（仅限需第三方配合的场景）
- [ ] 无行为契约违反被标为 deferred
- [ ] 无死代码被标为 deferred
- [ ] 无资产/本地化/埋点缺失被标为 deferred
- [ ] 若有 CHANGES_REQUESTED → 修复后已重新 review 并获得 APPROVED
