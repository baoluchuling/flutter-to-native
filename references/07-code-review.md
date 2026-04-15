# Step 7. code_review（独立 AI 全局审查，**强制执行，不得跳过**）

> execute 完成后、verify 开始前必须执行。code review 发现的问题修完后再进 verify，避免带质量缺陷通过验收。

## 独立 AI 审查原则

Step 6 的单 Task 检查由 **Claude（主 session）** 执行——利用热上下文趁早修复。Step 7 的全局审查必须使用**独立 AI**，确保两次审查的独立性：

| 维度 | Step 6 单 Task 检查 (Claude) | Step 7 全局审查 (独立 AI) |
|------|----------------------------|--------------------------|
| **审查者** | Claude 主 session | **Codex / code-reviewer subagent / 其他独立 AI** |
| **粒度** | 单个 task 内的文件 | 本次所有改动文件 |
| **关注点** | 行为契约、集成、规范、明显 bug、UI 设计值对齐 | 跨 task 一致性 + 整体质量 + 安全 |
| **修复时机** | 立即修复（上下文热） | 发现问题后回到 Step 6 修复 |
| **独立性价值** | 同一 AI 审自己的产出，有盲区 | 不同 AI 从零审代码，能发现 Claude 的系统性盲区 |

> 即使 Step 6 使用 inline execution（非 subagent），Step 7 仍然必须执行。

### 审查工具选择

读取 `session_config.json` 的 `review_tool` 字段（Step 0 已检测），按该字段决定审查方式：

| review_tool 值 | 使用方式 |
|----------------|---------|
| `codex` | 使用 `codex` 命令启动独立审查会话，传入改动文件和审查 prompt |
| `code-reviewer-subagent` | 使用 `Agent` 工具，`subagent_type: "code-reviewer"`，传入审查 prompt |

**兜底**：若以上均不可用，使用 `superpowers:requesting-code-review`。**禁止降级为 Claude 主 session 目视检查**——主 session 已经在 Step 6 做过检查，Step 7 的价值在于独立视角。`code_review_report.md` 必须存在。

### Codex 审查 Prompt 模板

使用 Codex 时，传入以下 prompt：

```
审查以下 Native 代码改动，这些代码是从 Flutter 同步到 {iOS/Android} 的实现。

改动文件列表：
{列出所有新建/修改的文件路径}

审查要点（必须逐项检查）：
1. 高保真对齐：对照 flutter_chain_map.json 中的链路，检查触发入口、状态流转、副作用、异常分支是否一致
2. 跨文件一致性：持久化 key 格式是否统一、埋点事件是否全覆盖、AB 门控是否全实现
3. 线程/内存安全：delegate 循环引用、Timer 未 invalidate、闭包强引用
4. API 版本兼容：是否有未用 #available / Build.VERSION.SDK_INT 保护的高版本 API
5. 安全：Token 存储、日志敏感数据、证书验证、组件导出

参考文件：
- flutter_chain_map.json: {路径}
- hunk_facts.json: {路径}
- edit_tasks.json: {路径}

输出格式：对每个问题给出 文件:行号 + 问题描述 + 严重等级(Critical/Important/Minor)
```

重点关注：

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

## 安全加固检查

当同步的代码涉及以下场景时，**必须额外参考 `security-hardening` skill 中对应平台的检查项**：

- Token / 密码存储 → iOS 用 Keychain，Android 用 EncryptedSharedPreferences（禁止 UserDefaults / SharedPreferences 明文）
- 网络请求 → iOS 确认 ATS 配置，Android 确认 NetworkSecurityConfig（禁止全局关闭证书验证）
- 深链接 / URL Scheme → 验证 Intent/URL 数据合法性，禁止盲信外部输入
- WebView → 禁止 JavaScript + FileAccess 同时开启加载不可信内容
- 日志 → 禁止 NSLog / Log.d 输出 Token、密码、用户隐私（Release 也会被抓取）
- 组件导出 → Android `exported="false"` 除非确实需要外部访问

发现安全问题 → `CHANGES_REQUESTED`，不得 deferred。

## 禁止 "deferred" 的场景

以下问题**不得标为 deferred / 后续跟进 / 已知遗留**，必须在 code_review 阶段解决：

1. **行为契约违反**：task 的 `behavior_contract` 中定义的交互（如 onPay 触发支付）未实现 → `CHANGES_REQUESTED`
2. **死代码**：新建的 UI 文件未被任何代码调用（缺少集成入口）→ `CHANGES_REQUESTED`
3. **资产缺失**：task 的 `asset_dependencies` 中列出的图片资源未复制到 Native 项目 → `CHANGES_REQUESTED`
4. **本地化缺失**：task 的 `l10n_keys` 中列出的翻译 key 未添加到本地化文件 → `CHANGES_REQUESTED`
5. **埋点缺失**：`hunk_facts.json` 中 `analytics_events` 列出的事件在 Native 中无对应实现 → `CHANGES_REQUESTED`

仅以下情况允许 deferred：
- 需要第三方团队配合（如后端接口未就绪）且已在 `cross_platform_gap.md` 中记录
- **用户主动提出**跳过某个特定功能项（如用户说"XX 功能先不做"，必须可追溯到对话中的具体文字）。AI 不得建议或引导用户简化。通用确认（如"确认开始"）不构成简化许可

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
