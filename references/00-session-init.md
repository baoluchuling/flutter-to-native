# Step 0. 会话初始化

Skill 被触发后，**先进入配置阶段，全部确认后再进入 Step 1**。不要跳过任何配置项。

## 交互模式：逐步推进 + AskUserQuestion

**严格一问一答**：每次只问当前步骤的问题，等用户回答后再进入下一步。禁止一次性列出所有配置项。

流程：`0.1 → 等回答 → 0.2 → 等回答 → 0.3 → 等回答 → 0.4 → 等回答 → 0.5 → 等回答 → 0.6（自动） → 0.7（汇总确认）`

### 交互工具

根据步骤类型使用不同交互方式：

- **选择型**（有明确选项）→ 使用 `AskUserQuestion` 工具，用户上下选择
  - 适用步骤：0.1 平台选择、0.5 补充文档、0.7 确认
- **输入型**（需要用户提供路径/范围/链接等）→ 使用 `AskUserQuestion`，提供一个有意义的默认选项，用户可选择或通过自动的 Other 自由输入
  - 适用步骤：0.2 仓库路径、0.3 Flutter 变更范围、0.4 Figma 链接

### 每步规则
- 先尝试从用户已有消息中自动推断，能推断则跳过该步（但在最终汇总中展示推断结果）
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

**AskUserQuestion 调用**（输入型，单端示例）：
```json
{
  "questions": [{
    "question": "Native 仓库路径？",
    "header": "仓库路径",
    "options": [
      {"label": "当前目录", "description": "使用当前工作目录作为 Native 仓库"}
    ],
    "multiSelect": false
  }]
}
```
> 用户可选"当前目录"快捷采用，或通过自动的 Other 输入自定义路径。

双端时发两个 question：
```json
{
  "questions": [
    {
      "question": "iOS Native 仓库路径？",
      "header": "iOS 路径",
      "options": [
        {"label": "当前目录", "description": "使用当前工作目录"}
      ],
      "multiSelect": false
    },
    {
      "question": "Android Native 仓库路径？",
      "header": "Android 路径",
      "options": [
        {"label": "当前目录", "description": "使用当前工作目录"}
      ],
      "multiSelect": false
    }
  ]
}
```

**→ 若需询问：调用 AskUserQuestion 后 STOP，等待用户回答。**

## 0.3 Flutter 变更范围

Flutter 输入固定为 git diff。需要确定 Flutter 仓库路径和 commit 范围。

**需要的信息**：
- Flutter 仓库路径（如果尚未从用户消息中获取）
- Commit 范围：从哪个 commit 到哪个 commit（如 `abc1234..def5678`、`HEAD~3..HEAD`、分支名等）

**自动推断**：
1. 用户消息中提到了 commit hash、分支名、PR 编号 → 直接采用
2. 用户提供了 Flutter 仓库路径 → 记录
3. 无法推断 → 直接文本提问

**AskUserQuestion 调用**（输入型）：
```json
{
  "questions": [
    {
      "question": "Flutter 仓库路径？",
      "header": "Flutter 路径",
      "options": [
        {"label": "当前目录", "description": "使用当前工作目录"}
      ],
      "multiSelect": false
    },
    {
      "question": "Git commit 范围？（如 abc1234..def5678 或 develop..feature/xxx）",
      "header": "Commit 范围",
      "options": [
        {"label": "HEAD~1..HEAD", "description": "最近一次提交的变更"}
      ],
      "multiSelect": false
    }
  ]
}
```
> 用户可选快捷项，或通过自动的 Other 输入自定义值。

获取后自动执行 `git diff <range>` 生成 diff，写入 run 目录。

**→ 若需询问：调用 AskUserQuestion 后 STOP，等待用户回答。**

## 0.4 Figma 设计稿（可选，UI 变更时必填）

如果 Flutter diff 涉及 UI 页面新增或改版，需要 Figma 设计稿作为验收基准。

**自动推断**：
1. 用户消息中包含 Figma 链接 → 直接采用
2. 无法判断是否涉及 UI → 先跳过，Step 1 分析 Flutter 变更后如果发现 `含新增 UI 页面 = true`，回来补充

**AskUserQuestion 调用**（输入型）：
```json
{
  "questions": [{
    "question": "Figma 设计稿链接？（不涉及 UI 可跳过）",
    "header": "Figma",
    "options": [
      {"label": "跳过", "description": "本次不涉及 UI 变更，或稍后再补充"}
    ],
    "multiSelect": false
  }]
}
```
> 用户可选"跳过"，或通过自动的 Other 粘贴 Figma 链接。

**Figma 链接格式**（用户通过 Other 输入时）：
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

**→ 调用 AskUserQuestion 后 STOP，等待用户回答。**

## 0.5 补充技术文档（可选）

用户可提供额外的技术文档辅助理解需求和架构映射。

**自动推断**：
1. 用户消息中提到了文档路径或链接 → 直接采用
2. 否则 → 使用 AskUserQuestion 询问

**AskUserQuestion 调用**（输入型）：
```json
{
  "questions": [{
    "question": "有补充文档吗？（PRD / API spec / 架构说明等）",
    "header": "补充文档",
    "options": [
      {"label": "没有", "description": "跳过，直接进入环境检查"}
    ],
    "multiSelect": false
  }]
}
```
> 用户可选"没有"跳过，或通过自动的 Other 输入文档路径或链接。

支持多个文档，记录到 `session_config.json` 的 `extra_docs` 字段。

**→ 调用 AskUserQuestion 后 STOP，等待用户回答。**

## 0.6 环境检查

所有配置确认后，自动执行环境检查（不需要用户交互）：

- [ ] Python 3.10+ 可用
- [ ] 每个目标 Native 仓库路径存在且可读写
- [ ] 每个目标 Native 仓库的 `.understand-anything/knowledge-graph.json` 存在且非空
  - 不存在 → 提示用户：`知识图谱缺失，需要先运行 npx gitnexus analyze`，**不得继续**
- [ ] Flutter 输入源文件存在

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
Figma:       （3 个页面，6 个截图已拉取）
补充文档:     （无）
Run ID:      <auto-generated>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

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
  "run_id": "2026-03-30-feature-name",
  "run_dir": "/path/to/ios-project/.ai/t2n/runs/2026-03-30-feature-name",
  "created_at": "2026-03-30T14:00:00Z"
}
```

> 后续所有步骤通过读取 `session_config.json` 获取路径和平台信息，不再重复询问。
