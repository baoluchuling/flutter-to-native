# Step 0. 会话初始化

Skill 被触发后，**先进入配置阶段，全部确认后再进入 Step 1**。不要跳过任何配置项。

## 0.0 Token 追踪初始化（最先执行，在一切交互之前）

Skill 触发后第一个动作，在任何用户交互之前执行：

1. 定位当前 session 的 JSONL 文件：
   ```bash
   PROJECT_DIR=$(ls -dt ~/.claude/projects/*/ | head -1)
   SESSION_JSONL=$(ls -t "${PROJECT_DIR}"*.jsonl | head -1)
   START_LINE=$(wc -l < "$SESSION_JSONL")
   ```

2. 将基线信息写入 `<run-dir>/token_tracking.json`（run 目录尚未创建时，先暂存到内存，在 0.7 创建 run 目录后立即写入）：
   ```json
   {
     "session_jsonl": "<SESSION_JSONL 路径>",
     "start_line": <START_LINE>,
     "start_time": "<ISO 时间>",
     "step_lines": { "step_0": <START_LINE> }
   }
   ```

3. 初始化 `<run-dir>/token_usage.md`（同样在 run 目录创建后写入）：
   ```markdown
   # Token Usage

   ## Subagent 明细

   | # | Step | Task | Model | Tokens | 耗时 |
   |---|------|------|-------|--------|------|
   ```

> 此步骤不需要用户交互，静默执行。

## 交互模式：逐步推进 + AskUserQuestion

**严格一问一答**：每次只问当前步骤的问题，等用户回答后再进入下一步。禁止一次性列出所有配置项。

流程：`0.0（自动） → 0.1 → 等回答 → 0.2 → 等回答 → 0.3 → 等回答 → 0.4 → 等回答 → 0.5 → 等回答 → 0.6（自动） → 0.7（汇总确认）`

### 交互工具

根据步骤类型使用不同交互方式：

- **选择型**（有明确选项）→ 使用 `AskUserQuestion` 工具，用户上下选择
  - 适用步骤：0.1 平台选择、0.5 补充文档、0.7 确认
- **输入型**（需要用户提供路径/范围/链接等）→ 直接输出提示文本，等待用户回答
  - 适用步骤：0.2 仓库路径、0.3 Flutter 变更范围、0.4 Figma 链接

### 每步规则
- 先尝试从用户已有消息中自动推断，能推断则跳过该步（但在最终汇总中展示推断结果）。**自动推断仅限有明确文字依据的情况**（用户消息中包含路径字符串、平台关键词等）。不得从上下文氛围推断（如"用户之前在 iOS 项目中工作"→推断平台为 iOS）。
- 不能推断时，使用 `AskUserQuestion` 发起交互，然后停下等用户回答
- 用户回答后，记录结果，进入下一步
- 若用户在某步的回答中顺带提供了后续步骤的信息，记录下来，后续步骤自动跳过

## 0.1 平台选择

**自动推断**（按优先级）：
1. 用户明确说了平台（如"同步到 iOS"、"双端都做"）→ 直接采用
2. 用户提供了仓库路径 → 检测项目标志：
   - 存在 `.xcodeproj` 或 `.xcworkspace` → `ios`
   - 存在 `build.gradle` 或 `build.gradle.kts` → `android`
   - 两者都有 → 候选 `ios,android`
3. 无法推断 → 使用 AskUserQuestion 询问

**AskUserQuestion 调用**：
```json
{
  "questions": [{
    "question": "目标平台？",
    "header": "平台",
    "options": [
      {"label": "iOS", "description": "同步到 iOS 项目"},
      {"label": "Android", "description": "同步到 Android 项目"},
      {"label": "双端", "description": "同时同步到 iOS 和 Android"}
    ],
    "multiSelect": false
  }]
}
```

确认后加载对应 platform profile：[iOS](platforms/ios.md) / [Android](platforms/android.md)

**→ 若需询问：调用 AskUserQuestion 后 STOP，等待用户回答。**

## 0.2 仓库路径

每个目标平台需要一个 Native 仓库根目录。

**自动推断**：
1. 用户提供了路径 → 直接采用
2. 当前工作目录是 Native 仓库 → 采用 cwd
3. 无法推断 → 直接文本提问

**询问方式**（纯文本，等待用户输入）：

单端时：
```
Step 0.2 — Native 仓库路径
请输入仓库路径（如 /path/to/ios-project）：
```

双端时：
```
Step 0.2 — Native 仓库路径
请输入 iOS 仓库路径（如 /path/to/ios-project）：
请输入 Android 仓库路径（如 /path/to/android-project）：
```

**→ 若需询问：输出提示后 STOP，等待用户回答。**

## 0.3 Flutter 变更范围

Flutter 输入固定为 git diff。需要确定 Flutter 仓库路径和 commit 范围。

**需要的信息**：
- Flutter 仓库路径（如果尚未从用户消息中获取）
- Commit 范围：从哪个 commit 到哪个 commit（如 `abc1234..def5678`、`HEAD~3..HEAD`、分支名等）

**自动推断**：
1. 用户消息中提到了 commit hash、分支名、PR 编号 → 直接采用
2. 用户提供了 Flutter 仓库路径 → 记录
3. 无法推断 → 直接文本提问

**询问方式**（纯文本，等待用户输入）：
```
Step 0.3 — Flutter 变更范围
请输入 Flutter 仓库路径（如 /path/to/flutter-project）：
请输入 commit 范围（如 abc1234..def5678 或 develop..feature/xxx）：
```

获取后自动执行 `git diff <range>` 生成 diff，写入 run 目录。

**→ 若需询问：输出提示后 STOP，等待用户回答。**

## 0.4 Figma 设计稿（可选，UI 变更时必填）

如果 Flutter diff 涉及 UI 页面新增或改版，需要 Figma 设计稿作为验收基准。

**自动推断**：
1. 用户消息中包含 Figma 链接 → 直接采用
2. 无法判断是否涉及 UI → 先跳过，Step 1 分析 Flutter 变更后如果发现 `含新增 UI 页面 = true`，回来补充

**询问方式**（纯文本，等待用户输入）：
```
Step 0.4 — Figma 设计稿（涉及 UI 变更时必填）
如涉及 UI 变更，请粘贴 Figma 链接；不涉及请回复"跳过"。
```

**Figma 链接格式**：
```
页面名称
dark：https://www.figma.com/design/xxx?node-id=xxx&m=dev
light：https://www.figma.com/design/xxx?node-id=xxx&m=dev

（按页面/组件分组，每组标注名称，链接按变体标注 dark/light 或其他标签）
```

**链接解析规则**：
- 按空行分组，每组第一行为页面/组件名称
- 每个链接行格式为 `标签：URL` 或 `标签 URL`（标签如 dark、light、无倒计时、有倒计时等）
- 解析后按组存入 `figma_inputs`，保留页面名称和变体标签

提供后对每个链接使用 `mcp__plugin_figma_figma__get_screenshot` 拉取截图，按 `{页面名称}_{标签}` 命名，写入 `figma_inputs.md`。

**→ 输出提示后 STOP，等待用户回答。**

## 0.5 补充技术文档（可选）

用户可提供额外的技术文档辅助理解需求和架构映射。

**自动推断**：
1. 用户消息中提到了文档路径或链接 → 直接采用
2. 否则 → 使用 AskUserQuestion 询问

**询问方式**（纯文本，等待用户输入）：
```
Step 0.5 — 补充技术文档（可选）
有补充文档吗？（PRD / API spec / 架构说明等）
请输入路径或链接，没有请回复"跳过"。
```

支持多个文档，记录到 `session_config.json` 的 `extra_docs` 字段。

**→ 输出提示后 STOP，等待用户回答。**

## 0.6 环境检查

所有配置确认后，自动执行环境检查（不需要用户交互）：

- [ ] Python 3.10+ 可用
- [ ] 每个目标 Native 仓库路径存在且可读写
- [ ] 每个目标 Native 仓库的 `.understand-anything/knowledge-graph.json` 存在且非空
  - 不存在 → 提示用户：`知识图谱缺失，需要先运行 /understand-anything:understand 生成知识图谱`，**不得继续**
- [ ] Flutter 输入源文件存在
- [ ] **Step 7 审查工具检测**（自动，不需用户交互）：
  - 检查 `codex` 命令是否可用（`which codex`）
  - 可用 → 记录到 `session_config.json` 的 `review_tool: "codex"`
  - 不可用 → 记录 `review_tool: "code-reviewer-subagent"`，输出提示：`Codex 未安装，Step 7 将使用 code-reviewer subagent 作为独立审查工具`
  - 此项不阻塞流程，仅确定 Step 7 使用的审查方式
- [ ] **部署目标与依赖版本采集**（自动，不需用户交互）：
  - iOS：从 `.xcodeproj/project.pbxproj` 提取 `IPHONEOS_DEPLOYMENT_TARGET`；从 `Podfile` 提取 `platform :ios, 'xx.x'`；从 `Package.swift` 提取 `.iOS(.vXX)`（取三者最高值为最低部署目标）
  - Android：从 `build.gradle` / `build.gradle.kts` 提取 `minSdk`、`compileSdk`、`targetSdk`
  - 同时扫描已集成的第三方依赖及其版本：iOS 从 `Podfile.lock` / `Package.resolved`，Android 从 `build.gradle` 的 `dependencies` 块
  - 采集结果写入 `session_config.json` 的 `platform_constraints` 字段（见下方格式）
  - 采集失败（如找不到 project.pbxproj）→ **WARN**（提示用户手动补充），不阻塞流程。但若用户未补充且 Step 6 涉及 UI 代码生成，`deployment_target` 缺失将导致无法保证 API 版本兼容性——Step 6 subagent prompt 必须包含 `deployment_target` 值，值缺失时不得派发 UI task

任一检查失败 → 输出具体失败项和修复建议，**等用户修复后重新检查**。

## 0.7 确认 Session Config

将以上配置汇总输出给用户确认，使用 AskUserQuestion：

先输出汇总文本：
```
━━━ T2N Session Config ━━━
平台:        ios
Native 仓库:  /path/to/ios-project
Flutter 仓库: /path/to/flutter-project
Commit 范围:  abc1234..def5678
部署目标:     iOS 14.0 / Swift 5.9
Figma:       （3 个页面，6 个截图已拉取）
补充文档:     （无）
Run ID:      <auto-generated>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

> 双端时分别展示各平台的部署目标（如 `iOS 14.0 / minSdk 24`）。`platform_constraints` 采集失败时展示 `⚠️ 未检测到，请确认`。

然后调用：
```json
{
  "questions": [{
    "question": "确认以上配置，开始同步？",
    "header": "确认",
    "options": [
      {"label": "确认开始", "description": "配置无误，进入 Step 1"},
      {"label": "重新配置", "description": "返回修改某项配置"}
    ],
    "multiSelect": false
  }]
}
```

> 无 Figma 或补充文档时显示"（无）"。

用户确认后：
1. 创建 run 目录（双端时含 `flutter/` + `ios/` + `android/` 子目录）
2. 将 session config 写入 `<run-dir>/session_config.json`
3. 进入 Step 1

**session_config.json 格式**：
```json
{
  "platforms": ["ios", "android"],
  "repos": {
    "ios": "/path/to/ios-project",
    "android": "/path/to/android-project"
  },
  "flutter_input": {
    "repo": "/path/to/flutter-project",
    "commit_range": "abc1234..def5678",
    "diff_path": "<run-dir>/flutter/changes.diff"
  },
  "figma": {
    "pages": [
      {
        "name": "引言样式",
        "variants": [
          {"label": "dark", "link": "https://www.figma.com/design/xxx?node-id=xxx&m=dev", "screenshot": "flutter/figma_screenshots/引言样式_dark.png"},
          {"label": "light", "link": "https://www.figma.com/design/xxx?node-id=xxx&m=dev", "screenshot": "flutter/figma_screenshots/引言样式_light.png"}
        ]
      }
    ]
  },
  "extra_docs": [
    {"type": "prd", "path": "/path/to/prd.md"},
    {"type": "api_spec", "path": "/path/to/api.yaml"}
  ],
  "platform_constraints": {
    "ios": {
      "deployment_target": "14.0",
      "swift_version": "5.9",
      "dependencies": {
        "SnapKit": "5.6.0",
        "Moya": "15.0.0"
      }
    },
    "android": {
      "min_sdk": 24,
      "compile_sdk": 34,
      "target_sdk": 34,
      "kotlin_version": "1.9.0",
      "dependencies": {
        "androidx.compose": "1.5.0"
      }
    }
  },
  "review_tool": "codex",
  "run_id": "2026-03-30-feature-name",
  "run_dir": "/path/to/ios-project/.ai/t2n/runs/2026-03-30-feature-name",
  "created_at": "2026-03-30T14:00:00Z"
}
```

> 后续所有步骤通过读取 `session_config.json` 获取路径和平台信息，不再重复询问。

## Gate Checklist

完成 Step 0 前，逐条核对：

- [ ] `session_config.json` 已写入 run 目录且格式合法（JSON 可解析）
- [ ] `platforms` 字段非空（ios / android / 双端）
- [ ] 每个平台的 `repos` 路径存在且可读写
- [ ] `flutter_input.repo` 路径存在
- [ ] `flutter_input.commit_range` 非空且 git 可解析
- [ ] `platform_constraints` 已采集（deployment_target / dependencies），或标注 ⚠️ 未检测到
- [ ] Figma 链接已解析并分组（UI 变更时），或 `figma` 字段为 `null`（非 UI 变更时）
- [ ] Figma 截图已拉取（UI 变更时），每个链接对应一张截图
- [ ] 知识图谱 `.understand-anything/knowledge-graph.json` 存在且非空
- [ ] `review_tool` 已检测并写入 session_config.json（`codex` 或 `code-reviewer-subagent`）
- [ ] 用户已确认 session config（AskUserQuestion 收到"确认开始"）
- [ ] `token_tracking.json` 已写入 run 目录（含 session_jsonl 路径和 start_line）
- [ ] `token_usage.md` 已创建（含表头）
