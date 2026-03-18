---
name: flutter-to-native
description: "将 Flutter 已完成的功能需求同步到现有 iOS 原生项目。输入 Flutter diff，LLM 自动提炼功能意图、生成修改计划、执行代码变更并验证。支持跨模块需求，按功能组织计划和执行。"
---

# T2N Atlas v2

## 定位

将已在 Flutter 中完成实现的产品需求，同步到现有 iOS Swift 原生项目。

核心理念：**LLM 驱动**，不做逐行翻译，而是理解功能意图后按原生架构生成代码。

## 何时使用

- 需要把 Flutter 已完成需求同步到 iOS 原生项目
- 需要扫描 iOS 原生仓库，生成架构画像
- 用户提到"同步"、"迁移"、"移植" Flutter 功能到 iOS

不适合：
- 逐行代码翻译
- 重生成整个 app

## 前置条件

- 环境变量 `ANTHROPIC_API_KEY` 已设置
- Python 3.12+ 且已安装 `anthropic` 包

## 标准流程

### 1. profile — 原生项目画像（一次性，手动触发）

扫描原生 iOS 项目，生成可复用的架构画像。已有画像时复用，除非用户要求重新扫描。

```bash
python3 scripts/profile_native.py \
  --repo-root <ios-project-root> \
  [--output-dir <path>]    # 默认: <repo-root>/.ai/t2n/native-profile
  [--force]                # 强制覆盖
```

产物：
```
.ai/t2n/native-profile/
├── overview.md              # 架构模式 + 模块/子功能索引
├── conventions.md           # 代码规范、库用法
└── modules/
    ├── <module>/
    │   ├── <sub-feature>.md # 子功能详情 + 类/文件映射
    │   └── ...
    └── ...
```

### 2. digest — 提炼功能意图

读取 Flutter diff，LLM 用业务语言提炼功能意图。

```bash
python3 scripts/digest_flutter.py \
  --diff <flutter.diff> \
  --run-dir <ios-root>/.ai/t2n/runs/<run-id> \
  [--prd <prd.md>]         # 可选 PRD
  [--extra <doc1> <doc2>]  # 可选补充文档
```

产物：`<run-dir>/feature_intent.md`

内容结构——每个功能一节：
- 业务描述
- 涉及数据变更
- 涉及交互
- **触发方式**（用户主动触发 / 自动触发 / 条件触发，必须明确说明）
- 副作用（网络、存储、埋点）

#### 2a. UI 微调合并规则

Flutter diff 中的 UI 微调（间距、颜色、圆角、字体大小等小幅调整）**不得单独排除**。即使看起来只是"格式化"或"微调"，只要涉及视觉参数变更，就必须：
- 识别出该微调属于哪个功能模块
- 合并到对应功能的 intent 中（如某页面的按钮圆角变更合并到该页面的功能 intent）
- 在 intent 中明确列出具体的视觉参数变更（如 `cornerRadius: 100 → 200`、`color: 0xFF0000 → 0x47091A`）

只有以下变更可以排除：
- 纯代码格式化（缩进、换行、import 排序）且**不涉及任何视觉参数变更**
- 纯 Flutter 框架内部重构（如 Widget 类替换）且 iOS 无对应组件

### 3. plan — 生成修改计划

基于功能意图 + 原生画像，按需加载模块文件，读取目标原生文件原文，生成功能级修改计划。

```bash
python3 scripts/plan.py \
  --run-dir <run-dir> \
  --native-root <ios-project-root> \
  [--profile-dir <native-profile-dir>]
```

产物：`<run-dir>/sync_plan.md`

格式——按功能分节：
```markdown
## 功能 1：阅读完成同步书架

涉及模块：Reader、Shelf

### Reader 模块
**ReaderViewController.swift**
- 新增 `onReadingComplete()`
- 修改 `pageDidFlip()` — 在最后一页时调用 onReadingComplete

### Shelf 模块
**ShelfViewModel.swift**
- 新增 `refreshAfterReading(bookId: String)`
```

#### 3a. Model 字段对齐表（必须）

当功能涉及 model 变更时，sync_plan 中必须包含字段对齐表：

```markdown
### Model 字段对齐

| Flutter 字段 | 类型 | nullable? | iOS 字段 | iOS 类型 | 默认值策略 | 说明 |
|---|---|---|---|---|---|---|
| fakeCountdown | int | ? | fakeCountdown | Int | = 0 | 服务端可能不返回 |
| countdownText | String | ? | countdownText | String? | optional | 服务端可能不返回 |
```

规则：
- 逐字段对齐，不能批量处理
- 必须检查 iOS 目标 model 的现有协议约定（如 `Modelable` 用 `var x = ""` 而非 optional）
- 新增字段的 nil 策略取决于：(1) 服务端是否一定返回该字段 (2) 现有 model 的约定模式
- 对齐表必须在用户确认前完成

#### 3b. 入口调用链追踪（必须）

当功能涉及修改现有文件的入口方法时，sync_plan 中必须包含调用链分析：

```markdown
### 入口调用链

**目标入口：** `ShortViewController.purchaseSimpleViewDidClickChargeProduct`

**iOS 侧完整调用链：**
1. `ShortPurchaseSimpleView_v2` 用户点击 → delegate 回调
2. → `ShortViewController.purchaseSimpleViewDidClickChargeProduct()`
3. → 当前逻辑：直接调用 `ChargeWebViewController`
4. → 修改为：展示 `MembershipUnlockV2AlertController`

**Flutter 侧对应位置：**
- `PurchaseStore.onProductTap()` → MobX action
- 注意：Flutter 是 Store 模式，iOS 是 delegate 模式，不能 1:1 映射入口

**上下游兼容性：**
- 上游：delegate 签名不变 ✅
- 下游：需要传递 `shortProductList`，确认数据源 ✅
```

定位规则（按顺序执行）：
1. **先明确功能场景**：这个功能在什么条件下、由什么事件触发？（如"用户翻到锁定章节时自动弹出购买 UI"）
2. **从场景出发找 iOS 方法**：在 iOS 代码中找承担同一功能场景的方法（如找"翻页事件处理 → 锁定检测 → 展示购买 UI"这条链路），而不是从 Flutter 方法名 grep iOS 代码
3. **禁止方法名 grep 定位**：不能因为 Flutter 叫 `showMembershipPayment`，就在 iOS 里 grep `membership` / `payment` / `charge` 然后挑一个看起来相关的方法
4. **验证职责一致性**：找到的 iOS 方法必须与 Flutter 方法承担相同的功能职责（如都是"自动展示购买 UI"），而不仅仅是名字相似
5. **完整调用链追踪**：确认后，追踪上下游调用链，检查兼容性
6. 架构差异（MVVM+Presenter vs MobX+Store）必须在计划中说明

#### 3c. Plan 阶段完整性要求

sync_plan 中**不得出现"需确认"、"待定"、"TBD"等未决项**。以下内容必须在 plan 阶段完成，不能留给 apply：
- 每个功能的修改入口方法（通过场景定位，不是方法名 grep）
- 每个 model 变更的字段对齐表
- 每个 UI 组件的设计参考来源

如果 plan 阶段无法确定某项内容，应标记为 `manual_candidate` 并说明原因，而不是写"需确认"然后让 apply 自行决定。

**此步骤完成后必须停下来，先执行 plan 校验。**

### 3.5 validate — Plan 校验（自动，plan 完成后立即执行）

plan 生成 `sync_plan.md` 后，自动执行校验检查。**校验不通过则不能进入 confirm 阶段。**

校验清单：

| # | 检查项 | 通过条件 | 不通过处理 |
|---|--------|----------|-----------|
| V1 | 无未决项 | sync_plan 中不包含"需确认"、"待定"、"TBD"、"需要确认"、"具体文件待定" | 回到 plan 补完 |
| V2 | 入口已定位 | 每个涉及修改现有文件的功能，都有明确的目标方法名和调用链分析 | 回到 plan，按场景定位补完 |
| V3 | 入口定位方式 | 调用链分析中说明了功能场景和 iOS 侧追踪路径，而非只写方法名 | 回到 plan，补充场景和追踪过程 |
| V4 | 字段对齐表 | 每个涉及 model 变更的功能都有逐字段对齐表 | 回到 plan 补完 |
| V5 | UI 设计参考 | 每个 UI 组件标注了设计参考来源（Figma/截图/无），无设计稿的标记为 manual_candidate | 回到 plan 补完或向用户要设计稿 |
| V6 | 触发方式 | 每个功能标注了触发方式（auto/user_action/conditional） | 回到 plan 补完 |

校验结果写入 `<run-dir>/plan_validation.md`，格式：

```markdown
# Plan Validation

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| V1 | 无未决项 | ✅ PASS | |
| V2 | 入口已定位 | ❌ FAIL | 功能8 "涉及会员弹窗调用处（需确认具体文件）" |
| V3 | 入口定位方式 | ✅ PASS | |
| V4 | 字段对齐表 | ✅ PASS | |
| V5 | UI 设计参考 | ⚠️ WARN | 功能5 无设计稿，已标记 manual_candidate |
| V6 | 触发方式 | ❌ FAIL | 功能8 未标注触发方式 |

**结论：FAIL — 需回到 plan 阶段修复 V2、V6**
```

- **全部 PASS**：自动进入 confirm 阶段，展示给用户审查
- **有 FAIL**：回到 plan 阶段修复后重新校验，不展示给用户
- **有 WARN 无 FAIL**：进入 confirm 阶段，但需向用户高亮 WARN 项

### 4. confirm — 用户确认

展示 `sync_plan.md` 和 `plan_validation.md` 给用户审查。未确认前不执行 apply。

### 5. apply — 执行代码修改

用户确认后，按功能逐个执行代码生成和文件写入。

```bash
python3 scripts/apply.py \
  --run-dir <run-dir> \
  --native-root <ios-project-root> \
  [--profile-dir <native-profile-dir>] \
  --approved
```

执行规则：
- `--approved` 必须提供，否则拒绝执行
- 按功能逐个执行（完成一个功能再进下一个）
- 原文件自动备份到 `<run-dir>/backup/`
- 出错跳过，继续执行下一功能

#### 5a. Model 字段写入规则

修改 model 文件时，必须严格遵循 sync_plan 中的字段对齐表：
- 按对齐表逐字段写入，不得自行决定 nil/非 nil 策略
- 先读取目标 model 文件，确认现有字段的声明模式（`var x = ""` vs `var x: String?`）
- 新字段必须与现有模式保持一致，除非对齐表明确要求不同
- 写入后检查调用方的 optional chaining 是否完整

#### 5b. UI 实现规则

生成 UI 代码时，禁止从 Flutter Widget 树直接翻译：
- Flutter 代码仅作为**逻辑参考**（交互流程、状态、数据绑定）
- 视觉实现必须参考设计稿（Figma/截图），如无设计稿则向用户要求提供
- 关键视觉参数（间距、颜色值、圆角、渐变角度、字体大小）必须与设计稿对照
- UIKit 布局使用项目约定（SnapKit 约束），不要翻译 Flutter 的 Container/Stack/Positioned
- 复杂 UI 组件（渐变、动画、自定义绘制）在生成前列出关键参数清单，请用户确认

#### 5c. 入口修改规则

修改现有文件的入口/调用链时，必须严格遵循 sync_plan 中的调用链分析：
- 先完整读取目标文件，理解 delegate chain / notification / KVO 流程
- 确认修改位置是 sync_plan 中标注的位置，不能自行 grep 后直接修改
- 修改后检查上下游兼容性（签名、参数、返回值）
- 如果发现 sync_plan 中的入口分析有误，中止并要求回到 plan 阶段

产物：`<run-dir>/apply_report.md`

### 6. verify — 验证结果

按 A → C → B 顺序验证：

```bash
python3 scripts/verify.py \
  --run-dir <run-dir> \
  --native-root <ios-project-root> \
  [--skip-syntax]
```

验证维度：
- **A 计划符合性**：对照 sync_plan 检查文件是否都已修改/创建
- **B 类型安全性**：对照字段对齐表，验证每个 model 字段的 nil/非 nil 声明是否正确，调用方 optional chaining 是否完整
- **C 意图符合性**：LLM 对照 feature_intent 审查代码实现
- **D 入口正确性**：验证修改的入口方法是否在正确的调用链位置，上下游是否兼容
- **E UI 合理性**：检查生成的 UI 代码是否使用了项目约定（SnapKit、项目色值 helper、字体 helper），而非 Flutter 风格的布局代码
- **F Swift 语法检查**：`swiftc -parse` 检查语法（可跳过）

产物：`<run-dir>/verify_report.md`

## 执行边界

- 以 Flutter diff 为最权威输入，PRD 等为补充
- 不做 Widget 到 UIKit 的 1:1 映射
- 修改计划按功能组织，跨模块天然支持
- 复杂动画、平台通道等默认为高风险，计划中标注

## 运行产物

```
.ai/t2n/
├── native-profile/            # Phase 1 缓存画像
│   ├── overview.md
│   ├── conventions.md
│   └── modules/**/*.md
└── runs/<run-id>/             # 每次需求
    ├── feature_intent.md
    ├── sync_plan.md
    ├── plan_validation.md     # Plan 校验结果
    ├── apply_report.md
    ├── verify_report.md
    └── backup/                # 原文件备份
```
