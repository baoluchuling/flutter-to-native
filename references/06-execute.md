# Step 6. execute（CLI agent 直接改码）

> 双端同步时，每个平台各执行一次。可并行（推荐用 subagent 各自独立执行）。

说明：skill 不内置 agent/注入器。

## 6.0 执行前必须用 superpowers 拆分与调度（强制）

进入任何改码动作之前，必须完成以下两步：

### Step A — 用 superpowers:writing-plans 生成实现计划

调用 `superpowers:writing-plans`，将 `edit_tasks.json` 中的 tasks 转为 superpowers 格式的实现计划：
- 每个 task 对应一个 superpowers task，含：目标文件列表、实现步骤、测试方式
- 计划保存到 `<run-dir>/<platform>/implementation_plan.md`
- 计划中每个 task 必须包含以下步骤（不得省略）：
  1. 调用 `understand-explain <目标类/文件>` 查询调用链与上下文（结果追加到 `understand_chat_log.md`）
  2. 按 `flutter_chain_map.json` 对应 CAP 核对实现范围
  3. 编写 Native 代码
  4. 将改动追加记录到 `execution_log.md`

### Step B — 用 superpowers 执行计划（二选一）

| 方式 | 适用场景 | skill |
|------|----------|-------|
| **推荐**：Subagent-Driven | tasks 相互独立，需要两阶段 review（spec + quality） | `superpowers:subagent-driven-development` |
| 备选：Inline Execution | tasks 有强依赖顺序，需在当前 session 内顺序推进 | `superpowers:executing-plans` |

> **禁止**跳过 Step A 直接改码，或绕过 superpowers 在主 session 逐文件手动修改。

### 跨 subagent 接口一致性（强制）

多个 subagent 独立工作时，有依赖关系的 task 之间存在接口契约风险（如 TASK-A 创建了 `Foo.show(data:)` 方法，TASK-B 调用时写成 `Foo.show(model:)`）。

**规则**：
- 按批次执行时，**后续批次的 subagent prompt 必须包含前置批次创建的接口签名**（方法名 + 参数名 + 参数类型 + 返回值），不得让 subagent 自行推测
- 具体操作：前置批次 subagent 完成后，主 session 从其产出文件中提取关键接口签名（如 `static func show(in view: UIView, data: ChargeModel, isFakeCountdown: Bool, initialCountdown: Int) -> ShortRetainPopupView`），贴入后续 subagent 的 prompt
- 若前置批次未返回接口签名，主 session 必须先 `Read` 产出文件提取签名后再派发后续批次
- 编译验证是兜底手段，不能替代 prompt 中的接口传递




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

## API 版本兼容约束（硬约束）

生成的 Native 代码必须兼容 `session_config.json` 中 `platform_constraints` 声明的部署目标版本：

- **iOS**：所有使用的 API 必须在 `deployment_target` 版本可用。禁止无条件使用高于部署目标的 API（如部署目标 iOS 14.0，禁止直接使用 `UISheetPresentationController`（iOS 15+）、`UIContentUnavailableConfiguration`（iOS 17+）等）
  - 若 Flutter 功能依赖的 API 仅在更高版本可用 → 必须使用 `if #available(iOS XX, *)` 包裹，并提供低版本 fallback 实现
  - Swift 语法约束同理（如 `deployment_target < 15.0` 时不可使用 `async/await`，除非项目已引入 back-deploy concurrency）
- **Android**：所有使用的 API 必须在 `minSdk` 版本可用。高版本 API 需 `if (Build.VERSION.SDK_INT >= XX)` 保护，或使用 AndroidX compat 库
- **第三方依赖版本**：使用已集成依赖的 API 时，确认该 API 在 `platform_constraints.dependencies` 中记录的版本已存在（如 SnapKit 5.x vs 4.x 的 API 差异）

> 编译验证（Step 6 末尾）能捕获部分版本问题，但不能依赖编译兜底——编译不检查运行时 availability，且 `@available` 遗漏不会报编译错误。

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
- **understand 记录数量约束**：Step 6 完成时，`understand_chat_log.md` 中 Step 6 阶段的记录条数必须 ≥ task 数量（每个 task 至少查询一次）。Gate Checklist 中验证此条件，不满足则 FAIL。subagent 场景下，subagent prompt 中必须明确要求 agent 将 understand 查询结果写入指定文件。

## 执行动作

由 CLI 依据以上输入直接执行：
- 读码（结合 understand-explain 结果）
- 改码
- 补调用链
- 改 model/service
- 对 Flutter diff 已实现部分，优先做等价同步；若无法等价，先补齐差异工件（`cross_platform_gap.md` / `design_tradeoff.md` / `acceptance_alignment.md`）再执行代码改动。

禁止仅按 `plan` 产物执行（`plan-only`）。
禁止跳过 understand-explain 直接改码。

## Subagent Token 记录（每次 Agent 返回后立即执行）

每次 Agent 工具调用返回后，从返回结果中提取 `<usage>total_tokens: xxx</usage>` 和 `duration_ms: xxx`，立即追加一行到 `<run-dir>/token_usage.md` 的明细表：

```markdown
| N | Step X | TASK-XX 任务名 | model | tokens | 耗时 |
```

Step 6 的实现 subagent 和 Step 7 的 code review subagent 都需记录。不得事后批量补填。

## execution_log.md（追加格式，不覆盖旧记录）

```markdown
## [TASK-XX] YYYY-MM-DD HH:MM

**改动文件**:
- Path/To/File（新增 / 修改）

**改动内容**: （1-3 句说明做了什么，对应 hunk_facts 哪个字段）
```

## 资产与本地化落地（强制，所有 task 完成后执行）

在编译验证之前，必须完成以下检查与落地：

### 图片资源迁移
1. 遍历 `edit_tasks.json` 中所有 task 的 `asset_dependencies` 字段
2. 对每个资源，按以下优先级获取：
   - **优先**：从 Flutter 项目 `assets/` 或 `assets/images/` 目录复制源文件
   - **备选**：若 Flutter 中为 SVG 格式，使用 `rsvg-convert` 转为 PNG（指定 @2x 尺寸）
   - **兜底**：若 Flutter 中不存在，从 Figma 设计稿下载（使用 `mcp__plugin_figma_figma__get_design_context` 获取资源 URL，然后 `curl` 下载）
   - **禁止**：使用 SF Symbol 或 placeholder 替代
3. 转换为 Native 格式（iOS：仅 @2x.png，放入 Assets.xcassets 的 `.imageset` 目录，创建 Contents.json）
4. 确认每个资源文件存在且为有效图片（`file` 命令验证为 PNG/JPEG）

### 本地化 key 落地
1. 遍历 `edit_tasks.json` 中所有 task 的 `l10n_keys` 字段
2. 对每个 key：
   - 在 Native 项目的本地化文件中添加（iOS: `Localizable.strings`，Android: `strings.xml`）
   - 至少添加英文（默认语言）和中文
3. 若项目使用远程本地化（服务端下发），确认 key 已在代码中通过本地化方法调用（如 `Lg.t(for:)`），本地文件作为 fallback

### 埋点实现
1. 遍历 `flutter/hunk_facts.json` 中所有文件的 `analytics_events` 字段
2. 对每个事件，确认 Native 代码中有对应的埋点调用
3. 若 Native 埋点框架与 Flutter 不同（如 BeiDou vs SensorsData），使用 Native 框架的等价调用
4. 未实现的埋点事件必须在本步骤补齐，**不得标为"后续"**

### 集成验证

集成是新建 UI task 自身的职责（不是独立 task）。此处验证每个新建 UI 的 task 是否完成了集成：

1. 对每个新建 UI 文件，执行 task 验收断言中的 grep 检查：
   ```bash
   grep -rn "<ClassName>" <项目目录> --include="*.swift" | grep -v "<自身文件名>"
   ```
2. 至少有 1 条匹配 → PASS
3. 无匹配 → 该 task 未完成集成，必须修复（在 `integration_point` 指向的位置添加调用代码 + 调整调用方逻辑）
4. 贴出每个 grep 命令和结果

> 以上任一项未完成，禁止进入编译验证和 code_review。

## 进入 Step 7 前必须通过编译验证

所有 task 完成后，**必须执行**平台对应的编译命令（参见 platform profile "编译验证命令"）：

```bash
# iOS
xcodebuild build -scheme <scheme> -destination 'generic/platform=iOS' 2>&1 | tail -20

# Android
./gradlew assembleDebug 2>&1 | tail -20
```

- 编译命令必须实际执行并在 Gate Checklist 中贴出结果（至少最后 20 行）
- 编译成功：继续进入 Step 7
- 编译失败：分析错误原因，派发修复 subagent（需在 prompt 中贴出完整编译错误），修复后重新编译直到通过
- **不得跳过编译验证**——即使 SourceKit 报错为 IDE 误报，也必须实际执行编译确认。SourceKit 误报和真实编译错误的区分只能通过实际编译确定
- 编译失败的常见原因：跨 subagent 方法签名不匹配、import 缺失、类型名拼写不一致。这些问题只有编译能发现

## Gate Checklist

完成 Step 6 前，逐条核对：

- [ ] 所有 task 的代码均已编写完成（含新建 UI task 的集成部分）
- [ ] `<platform>/execution_log.md` 已生成，每个 task 有记录（改动文件 + 改动内容）
- [ ] `<platform>/implementation_plan.md` 已生成
- [ ] **图片资源**：`edit_tasks.json` 中所有 `asset_dependencies` 列出的资源已复制到 Native 项目（非 placeholder / SF Symbol）
- [ ] **本地化 key**：`edit_tasks.json` 中所有 `l10n_keys` 列出的 key 已添加到本地化文件（至少英文）
- [ ] **埋点**：`hunk_facts.json` 中所有 `analytics_events` 在 Native 代码中有对应实现
- [ ] **集成入口**：每个新建 UI 文件至少有一个外部调用入口（grep 确认有调用，贴出命令和结果）
- [ ] **行为契约**：每个 task 的 `behavior_contract` 中定义的交互/副作用均已实现（不得有 stub/placeholder 回调）
- [ ] 新建文件已注册到项目文件（xcodeproj / build.gradle）
- [ ] `<platform>/understand_chat_log.md` 已追加执行阶段的查询记录，记录条数 ≥ task 数量
- [ ] **编译验证已通过**：贴出编译命令和结果（至少最后 20 行），确认 `BUILD SUCCEEDED`
- [ ] 未执行任何 git commit（整个 SOP 流程不提交，由用户自行决定）
