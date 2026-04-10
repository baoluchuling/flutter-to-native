# Step 6. execute（CLI agent 直接改码）

> 双端同步时，每个平台各执行一次。可并行（推荐用 subagent 各自独立执行）。

说明：skill 不内置 agent/注入器。

Step 6 分为四个阶段，必须按顺序执行：

| 阶段 | 名称 | 职责 |
|------|------|------|
| **6A** | 准备 | 依赖预检 → Figma 上下文隔离 → Prompt 统一模板 → writing-plans → 执行方式选择 |
| **6B** | 执行 | 派发 subagent → 改码 → 单 task 完成后检查（Claude 主 session） |
| **6C** | 收尾 | 资产/本地化/埋点遗漏补齐 |
| **6D** | 验证 | 编译验证 |

---

# 阶段 6A：准备

## 6A.1 执行前必须用 superpowers 拆分与调度（强制）

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
| **强制**：Subagent-Driven | tasks 相互独立（无共享状态、无调用依赖），或可通过批次化解耦 | `superpowers:subagent-driven-development` |
| 仅限例外：Inline Execution | tasks 有显式数据依赖且无法通过批次化解决 | `superpowers:executing-plans` |

> **禁止**跳过 Step A 直接改码，或绕过 superpowers 在主 session 逐文件手动修改。
> 选择 Inline Execution 时，必须在 `execution_log.md` 开头记录选择理由。Inline 模式下，subagent 前言模板中的所有硬约束同样适用于主 session 自身。

### 跨 subagent 接口一致性（强制）

多个 subagent 独立工作时，有依赖关系的 task 之间存在接口契约风险（如 TASK-A 创建了 `Foo.show(data:)` 方法，TASK-B 调用时写成 `Foo.show(model:)`）。

**规则**：
- 按批次执行时，**后续批次的 subagent prompt 必须包含前置批次创建的接口签名**（方法名 + 参数名 + 参数类型 + 返回值），不得让 subagent 自行推测
- 具体操作：前置批次 subagent 完成后，主 session 从其产出文件中提取关键接口签名（如 `static func show(in view: UIView, data: ChargeModel, isFakeCountdown: Bool, initialCountdown: Int) -> ShortRetainPopupView`），贴入后续 subagent 的 prompt
- 若前置批次未返回接口签名，主 session 必须先 `Read` 产出文件提取签名后再派发后续批次
- 编译验证是兜底手段，不能替代 prompt 中的接口传递
- **后续批次 subagent prompt 中必须包含 `## 前置接口契约` 字段**，列出所有依赖的方法签名（方法名+参数名+参数类型+返回值）。Gate Checklist 验证：每个非首批次 subagent prompt 包含此字段




## Subagent Prompt 统一模板

每个 subagent prompt 按以下结构组装。顺序固定，不可调换。原则：**做什么 → 参考什么 → 依赖什么 → 怎么做 → 怎么算完成**。

主 session 从 `edit_tasks.json` 中提取当前 task 的字段，按模板填入。`{...}` 表示需要替换的变量。

统一模板，`## 1.` 中 UI 视觉参考为条件段：UI task 必须包含，非 UI task 跳过；Flutter 行为基准始终包含。

```
# Task {TASK-ID}: {title}

{capability 一句话描述}

工作目录: {native-project-root}

---

## 1. 目标与参考

{== 以下 UI 视觉参考段：user_facing: true 时必须包含，user_facing: false 时跳过 ==}

### UI 视觉参考（UI task 必选）

**Figma 链接**: {当前 task 对应的链接}
**截图**: {Read 截图文件路径，让 subagent 直接看到图片}
**设计要点**:
- {布局描述}
- {关键颜色/字号/间距}
- {状态变体}

在编写 UI 代码前，必须先调用 mcp__plugin_figma_figma__get_design_context 获取精确设计值（间距、颜色、字号、圆角），不得从截图目测。

{== UI 视觉参考段结束 ==}

### Flutter 行为基准（所有 task 必选）

以下是 Flutter 中该功能的关键实现事实，你的 Native 实现必须等价覆盖：

**新增方法**:
{从 hunk_facts.json 提取该 task 对应文件的 new_methods，含签名 + triggers + side_effects}

**持久化 key**:
{persistence_keys 列表，含完整 key 格式和变量占位符。无则写"无"}

**状态字段**:
{state_fields 列表。无则写"无"}

---

## 2. 行为契约（核心，每条必须实现）

{直接粘贴 behavior_contract 全文，含状态/交互/副作用/异常}

---

## 3. 实现范围

**改动文件**: {edit_anchors 列表}
**集成入口**: {integration_point — 仅新建 UI 文件的 task 需要，修改已有文件时省略}
**触发条件**: {trigger_lifecycle}

---

## 4. 依赖信息

**前置接口契约**:
{非首批次时，列出前序 task 创建的方法签名; 首批次时写"无"}

**资产依赖**: {asset_dependencies 列表。无则写"无"}
**本地化 key**: {l10n_keys 列表。无则写"无"}
**AB 门控**: {ab_gates 列表 + 处置方案。无则写"无"}

---

## 5. 编码规范

- 禁止执行 git commit
- 禁止直接解析 .understand-anything/knowledge-graph.json，必须使用 /understand-anything:understand-explain
- 修改任何文件前，先 Read 该文件了解上下文，查询结果追加到 {platform}/understand_chat_log.md
  格式: `## Query {TASK-ID}-N: 标题` + `- **问题**: ...` + `- **结果**: ...`
- 图片资源获取失败时，停止并报告 BLOCKED，不得使用任何替代品
- SVG 文件使用 rsvg-convert 转为 @2x PNG
- 部署目标: {deployment_target}，高版本 API 必须 #available 保护并提供 fallback
- 持久化 key 格式必须与 Flutter 完全一致（含变量占位符结构）
- 网络回调 / Timer 回调中操作 UI 或共享状态时必须切到主线程
{以下为 iOS 专用，Android subagent 替换为对应规范}
- 颜色: UIColor(hex:, alpha:)
- 按钮: NoHighlightButton（非系统 UIButton）
- 布局: SnapKit
- 字体: UIFont+Extension（如 .F_medium, .F_bold）
- 导航栏: NavigationView
- 视图: 懒加载创建
- 图片: 仅 @2x.png，放入 Assets.xcassets 的 .imageset 目录

---

## 6. 验收标准（完成前逐条自检）

{直接粘贴 acceptance 全文，含 grep 检查命令}

**完成报告格式**:
- **Status**: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 改动文件列表
- 每条验收标准的 PASS/FAIL
- 遇到的问题或疑虑

遇到无法解决的问题时，报告 BLOCKED 或 NEEDS_CONTEXT，不要猜测或绕过。
```

### UI 视觉参考的强制性

| user_facing | `## 1.` 中 UI 视觉参考段 | 验证 |
|-------------|--------------------------|------|
| `true` | **必选** — 缺少截图或 Figma 链接的 prompt 禁止派发 | Gate Checklist 检查 |
| `false` | **跳过** — 不包含该子段，减少无关上下文 | — |

主 session 组装 prompt 时，根据 `edit_tasks.json` 中 task 的 `user_facing` 字段决定是否包含 UI 视觉参考段。Flutter 行为基准段始终包含，确保所有 task 都有明确的逻辑目标。

### 模板设计说明

| 段落 | 位置 | 原因 |
|------|------|------|
| Task 标题 + UI 截图 | **开头**（高注意力区） | 先建立"做什么"+ 视觉印象 |
| 行为契约 | **第二** | 最核心的实现规范，紧跟目标 |
| 实现范围 + 依赖 | **中间** | 参考信息，不需要最高注意力 |
| 编码规范 | **中后** | 约束规则，已去重精简 |
| 验收标准 | **结尾**（高注意力区） | 完成条件，subagent 最后看到的 = 最后执行的 |

### 相比旧模板的去重

| 旧模板中的重复项 | 处理 |
|---|---|
| "禁止 SF Symbol" 出现在硬约束 + asset_dependencies | 删硬约束中的，asset_dependencies 自带约束 |
| "禁止 placeholder/stub" 出现在硬约束 + behavior_contract + acceptance | 删硬约束中的，behavior_contract 说了"每条必须实现"，acceptance 有 grep 验证 |
| "新建 UI 必须集成" 出现在硬约束 + integration_point + acceptance grep | 删硬约束中的，integration_point 字段 + grep 验收已覆盖 |
| "UIColor/SnapKit" 出现在硬约束 + 代码规范摘要 | 合并到"编码规范"一处 |
| superpowers implementer-prompt 的 Code Organization / Self-Review / Escalation | 精简为验收标准中的报告格式 + 一句话 escalation 指引 |

**验证**：Gate Checklist 中检查每个 subagent prompt 是否包含 `## 2. 行为契约` 和 `## 6. 验收标准` 字样（替代旧的"硬约束"检查）。

## 6A.2 执行输入（硬约束）

- `<platform>/edit_tasks.md` / `<platform>/edit_tasks.json`
- `flutter/flutter_changes.md`
- 本次 `pr_diff` 原文（必要时回读具体 Flutter 文件）
- `flutter/figma_inputs.md`（UI 变更时）— **仅用于主 session 筛选，不整体传入 subagent**

## 6A.3 依赖预检（强制执行）

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

## 6A.4 Subagent Figma 上下文隔离（UI task 强制）

UI 还原精度依赖于 subagent 只看到**当前 task 的截图**。主 session 在组装 prompt 模板的 `## 1. UI 视觉参考` 段时，必须：

1. **筛选截图**：从 `figma_inputs.md` 中找到 `覆盖 task` 匹配当前 task CAP 编号的条目，提取对应截图路径
2. **只传当前 task 的截图**：禁止整体传入 `figma_inputs.md`
3. **非 UI task 跳过整段**：`user_facing: false` 的 task，prompt 中不包含 `## 1. UI 视觉参考`

---

# 阶段 6B：执行

## 6B.1 改码前必做（understand 约束）

subagent prompt 模板 `## 5. 编码规范` 中已包含 understand 指令（禁止直接解析 knowledge-graph.json、查询结果追加到 understand_chat_log.md）。此处补充主 session 层面的约束：

- **understand 记录数量约束**：Step 6 完成时，`understand_chat_log.md` 中 Step 6 阶段的记录条数必须 ≥ task 数量（每个 task 至少查询一次）。Gate Checklist 验证此条件，不满足则 FAIL。
- **提问三要素**（适用于主 session 和 subagent）：场景（在哪个类/页面）+ 操作（什么触发）+ 目标（要看到什么）

## 6B.2 执行动作

由 CLI 依据以上输入直接执行：
- 读码（结合 understand-explain 结果）
- 改码
- 补调用链
- 改 model/service
- 对 Flutter diff 已实现部分，优先做等价同步；若无法等价，先补齐差异工件（`cross_platform_gap.md` / `design_tradeoff.md` / `acceptance_alignment.md`）再执行代码改动。

禁止仅按 `plan` 产物执行（`plan-only`）。
禁止跳过 understand-explain 直接改码。

## 6B.3 单 Task 完成后检查（Claude 主 session，每个 subagent 返回后立即执行）

> **审查者：Claude（主 session）**。利用热上下文趁早发现问题、立即修复。强制执行，不得延迟。

每个 task 的 subagent 完成后，**主 session 必须在记录 token 之前执行以下两项检查**。发现问题时趁上下文还在立即修复，成本远低于 Step 7 回头修。

### A. 单 Task Code Review（所有 task，强制）

对 subagent 新建/修改的每个文件，主 session 执行快速代码审查：

1. **读取 subagent 改动的文件**（Read 或 git diff），检查：
   - 行为契约：`edit_tasks.json` 中该 task 的 `behavior_contract` 定义的每个交互/副作用是否已实现（不得有 stub/TODO/placeholder）
   - 集成完整性：新建 UI 文件是否在 `integration_point` 指定位置被调用（grep 验证）
   - 代码规范：是否符合 subagent 前言模板中的硬约束（NoHighlightButton、UIColor(hex:)、SnapKit 等）
   - 接口一致性：方法签名是否与 `edit_tasks.json` 中 `mapping_proof` 描述一致
   - 明显 bug：可选值未解包、Timer 未 invalidate、强引用循环、iOS 版本兼容等

2. **输出**（追加到 `execution_log.md`）：
   ```
   ### Code Review — T-XX
   - 行为契约: PASS / FAIL (具体缺失项)
   - 集成入口: PASS / FAIL
   - 代码规范: PASS / FAIL
   - 明显 bug: 无 / 列出
   ```

3. **FAIL 处理**：
   - ≤3 项问题：主 session 直接 Edit 修复
   - \>3 项问题：派发修复 subagent，prompt 中贴入问题列表和正确实现要求

### B. UI 对齐检查（仅 `user_facing: true` 的 UI task，强制）

1. **提取设计基准值**：对该 task 对应的每个 Figma 链接，调用 `mcp__plugin_figma_figma__get_design_context` 提取关键设计值：
   - 主色值（背景色、文字色、按钮色、边框色）
   - 关键字号（标题、正文、按钮文字）
   - 关键间距（内边距、元素间距、圆角半径）

2. **在代码中 grep 验证**：对每个提取的设计值，在 subagent 新建/修改的文件中搜索：
   ```bash
   # 示例：验证颜色值 #FFD600 是否在代码中
   grep -n "FFD600\|ffd600" <新建文件>.swift
   # 示例：验证字号 18 是否在代码中
   grep -n "F_bold(18)\|F_semibold(18)\|fontSize.*18" <新建文件>.swift
   ```

3. **输出对齐矩阵**（追加到 `execution_log.md`）：
   ```
   ### UI 对齐检查 — T-XX
   | 设计值 | 类型 | Figma | 代码中 | 状态 |
   |--------|------|-------|--------|------|
   | 主背景色 | color | #1A1A1A | 0x1A1A1A ✓ | PASS |
   | 标题字号 | font | 18pt bold | F_bold(18) ✓ | PASS |
   | 按钮圆角 | radius | 24 | cornerRadius = 24 ✓ | PASS |
   | 卡片间距 | spacing | 12 | offset(12) ✗ 未找到 | FAIL |
   ```

4. **FAIL 处理**：
   - ≤3 项 FAIL：主 session 直接修复（Edit 对应文件）
   - \>3 项 FAIL：派发修复 subagent，prompt 中贴入对齐矩阵和正确设计值
   - 修复后重新 grep 验证，直到全部 PASS

## 6B.4 Subagent Token 记录（每次 Agent 返回后立即执行）

每次 Agent 工具调用返回后，从返回结果中提取 `<usage>total_tokens: xxx</usage>` 和 `duration_ms: xxx`，立即追加一行到 `<run-dir>/token_usage.md` 的明细表：

```markdown
| N | Step X | TASK-XX 任务名 | model | tokens | 耗时 |
```

Step 6 的实现 subagent 和 Step 7 的 code review subagent 都需记录。不得事后批量补填。

## 6B.5 execution_log.md（追加格式，不覆盖旧记录）

```markdown
## [TASK-XX] YYYY-MM-DD HH:MM

**改动文件**:
- Path/To/File（新增 / 修改）

**改动内容**: （1-3 句说明做了什么，对应 hunk_facts 哪个字段）
```

---

# 阶段 6C：收尾

## 6C.1 资产与本地化落地（所有 task 完成后执行）

> **职责分工**：subagent 在执行 task 时负责自己 task 的资产迁移（前言模板已约束）。此处是**遗漏补齐**——检查所有 task 的资产/本地化/埋点是否都已落地，补齐 subagent 遗漏的部分。

在编译验证之前，必须完成以下检查与落地：

### 图片资源迁移
1. 遍历 `edit_tasks.json` 中所有 task 的 `asset_dependencies` 字段
2. 对每个资源，**执行完成后必须满足以下全部条件**（缺一则该 task FAIL）：
   - 文件存在于 Native 项目的 Assets.xcassets 对应 `.imageset` 目录中
   - 文件格式为 PNG/JPEG（`file` 命令验证）
   - 非 placeholder / 非 SF Symbol / 非空文件 / 非损坏图片
3. 获取方式（按此顺序逐一尝试，**全部失败 → FAIL 该 task，不得用替代品**）：
   a. PNG/JPEG 源文件：从 Flutter `assets/` 或 `assets/images/` 直接复制
   b. SVG 源文件：使用 `rsvg-convert -w <2x宽> -h <2x高> input.svg -o output@2x.png` 转换（从 SVG 的 viewBox 计算 2x 尺寸）
   c. Flutter 中不存在：从 Figma 设计稿导出（使用 `mcp__plugin_figma_figma__get_design_context` 获取节点后用 `get_screenshot` 下载）
4. 转换为 Native 格式（iOS：仅 @2x.png，放入 Assets.xcassets 的 `.imageset` 目录，创建 Contents.json）
5. 验证：对每个资源执行 `file <path>` 确认为有效 PNG/JPEG，贴出命令和结果

**subagent 场景**：subagent prompt 统一模板 `## 5. 编码规范` 中已包含资产获取失败的处理指令。此处由主 session 在所有 subagent 完成后统一检查遗漏。

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

---

# 阶段 6D：验证

## 6D.1 编译验证（进入 Step 7 前必须通过）

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
- [ ] **单 Task Code Review**：每个 task 的 execution_log.md 中有 `### Code Review — T-XX` 记录，行为契约/集成/规范全部 PASS
- [ ] **UI 对齐检查**：每个 UI task 的 execution_log.md 中有 `### UI 对齐检查 — T-XX` 矩阵，全部 PASS（或 FAIL 已修复）
- [ ] `<platform>/execution_log.md` 已生成，每个 task 有记录（改动文件 + 改动内容）
- [ ] `<platform>/implementation_plan.md` 已生成
- [ ] **Prompt 结构**：每个 subagent prompt 包含 `## 1. 目标与参考`（含 Flutter 行为基准）、`## 2. 行为契约`、`## 6. 验收标准`；UI task 的 `## 1.` 中必须包含 `### UI 视觉参考`（含截图 + Figma 链接），非 UI task 不含此子段
- [ ] **图片资源**：`edit_tasks.json` 中所有 `asset_dependencies` 列出的资源已复制到 Native 项目（非 placeholder / SF Symbol）
- [ ] **本地化 key**：`edit_tasks.json` 中所有 `l10n_keys` 列出的 key 已添加到本地化文件（至少英文）
- [ ] **埋点**：`hunk_facts.json` 中所有 `analytics_events` 在 Native 代码中有对应实现
- [ ] **集成入口**：每个新建 UI 文件至少有一个外部调用入口（grep 确认有调用，贴出命令和结果）
- [ ] **行为契约**：每个 task 的 `behavior_contract` 中定义的交互/副作用均已实现（不得有 stub/placeholder 回调）
- [ ] 新建文件已注册到项目文件（xcodeproj / build.gradle）
- [ ] `<platform>/understand_chat_log.md` 已追加执行阶段的查询记录，记录条数 ≥ task 数量
- [ ] **编译验证已通过**：贴出编译命令和结果（至少最后 20 行），确认 `BUILD SUCCEEDED`
- [ ] 未执行任何 git commit（整个 SOP 流程不提交，由用户自行决定）
