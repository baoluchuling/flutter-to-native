# Step 6. execute（CLI agent 直接改码）

> 双端同步时，每个平台各执行一次。可并行（推荐用 subagent 各自独立执行）。

说明：skill 不内置 agent/注入器。

## 6.0 执行前必须用 superpowers 拆分与调度（强制）

进入任何改码动作之前，必须完成以下两步：

### Step A — 用 superpowers:writing-plans 生成实现计划

调用 `superpowers:writing-plans`，将 `edit_tasks.json` 中的 tasks 转为 superpowers 格式的实现计划：
- 每个 task 对应一个 superpowers task，含：目标文件列表、实现步骤、测试方式、commit 命令
- 计划保存到 `<run-dir>/<platform>/implementation_plan.md`
- 计划中每个 task 必须包含以下步骤（不得省略）：
  1. 调用 `understand-explain <目标类/文件>` 查询调用链与上下文（结果追加到 `understand_chat_log.md`）
  2. 按 `flutter_chain_map.json` 对应 CAP 核对实现范围
  3. 编写 Native 代码
  4. 将改动追加记录到 `execution_log.md`
  5. commit

### Step B — 用 superpowers 执行计划（二选一）

| 方式 | 适用场景 | skill |
|------|----------|-------|
| **推荐**：Subagent-Driven | tasks 相互独立，需要两阶段 review（spec + quality） | `superpowers:subagent-driven-development` |
| 备选：Inline Execution | tasks 有强依赖顺序，需在当前 session 内顺序推进 | `superpowers:executing-plans` |

> **禁止**跳过 Step A 直接改码，或绕过 superpowers 在主 session 逐文件手动修改。

## 执行输入（硬约束）

- `<platform>/edit_tasks.md` / `<platform>/edit_tasks.json`
- `flutter/flutter_changes.md`
- 本次 `pr_diff` 原文（必要时回读具体 Flutter 文件）

## 依赖预检（Step A 之前，强制执行）

在生成实现计划之前，检查 Flutter 变更是否引入了 Native 端尚未集成的外部依赖：

1. **扫描 Flutter diff**：从 `flutter_changes.md` 或 `pr_diff` 中提取新增的 `pubspec.yaml` 依赖项（`dependencies` / `dev_dependencies` 中新增的包）
2. **映射到 Native 等价库**：对每个新增 Flutter 依赖，判断 Native 端是否需要对应的库（如 Flutter `dio` → iOS `Moya`/`Alamofire`，Flutter `shared_preferences` → iOS `UserDefaults`）
3. **检查 Native 项目是否已集成**：
   - iOS：检查 `Podfile` / `Package.swift` / `*.xcodeproj` 中是否已有对应依赖
   - Android：检查 `build.gradle` / `build.gradle.kts` 中是否已有对应依赖
4. **输出依赖检查结果**：
   - 所有依赖已就绪 → 继续
   - 存在缺失依赖 → 列出缺失项，**暂停并提示用户**：需要先集成这些依赖再继续执行
   - 依赖可通过 Native 内置 API 替代（如 `UserDefaults`）→ 标注为"无需额外集成"，继续

> 依赖预检不阻塞"无需额外集成"的情况，仅在真正缺失第三方库时暂停。

## 改码前必做（显式约定）

- 每个 task 的目标符号（类/方法/文件）改动前，必须先执行：
  ```
  /understand-anything:understand-explain <ClassName 或 filePath>
  ```
  查询内容：该符号的调用链（谁调用它）、所属架构层、依赖的子组件、当前已有的状态/逻辑。
- 若需要确认触发入口或调用时机，使用：
  ```
  /understand-anything:understand-chat <具体问题>
  ```
  查询内容：该功能当前在 Native 中如何被触发、由哪个编排入口负责、有无现存同类弹窗/流程可复用。
  **提问必须包含三要素**：场景（在哪个类/页面）+ 操作（什么触发）+ 目标（要看到什么）
- **禁止**直接用 Python/Bash 解析 `.understand-anything/knowledge-graph.json` 代替 skill 调用。
- 每次调用 understand-chat 或 understand-explain 后，必须将问题和摘要结果追加到 `<platform>/understand_chat_log.md`。

## 执行动作

由 CLI 依据以上输入直接执行：
- 读码（结合 understand-explain 结果）
- 改码
- 补调用链
- 改 model/service
- 对 Flutter diff 已实现部分，优先做等价同步；若无法等价，先补齐差异工件（`cross_platform_gap.md` / `design_tradeoff.md` / `acceptance_alignment.md`）再执行代码改动。

禁止仅按 `plan` 产物执行（`plan-only`）。
禁止跳过 understand-explain 直接改码。

## execution_log.md（追加格式，不覆盖旧记录）

```markdown
## [TASK-XX] YYYY-MM-DD HH:MM

**改动文件**:
- Path/To/File（新增 / 修改）

**改动内容**: （1-3 句说明做了什么，对应 hunk_facts 哪个字段）

**commit**: <sha>
```

## 进入 Step 6.5 前必须通过编译验证

所有 task 完成后，执行平台对应的编译命令（参见 platform profile "编译验证命令"）。
编译失败必须修复后再进入 Step 6.5 code_review，**不得带编译错误进入 code_review 或 verify**。
