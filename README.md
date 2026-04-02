# Flutter-to-Native SOP

将 Flutter 变更高保真同步到 Native（iOS / Android）的流程编排工具。

以 Claude Code Skill 形式运行，在对话中输入 `/flutter-to-native` 即可启动。Skill 负责流程编排与质量闸门，代码理解与修改由 CLI agent 完成。

## 工作原理

整个流程分为三个阶段：

**分析**（Step 0-2）— Flutter 改了什么、要同步什么

```
会话初始化 → git diff → hunk_facts 结构化提取 → 四步自动映射（能力切片 → 链路抽取 → Native 匹配 → 反证淘汰）
```

**规划**（Step 3-5）— 怎么改 Native

```
edit_tasks 生成（含 model_tier / asset_dependencies / l10n_keys / integration_point）
→ V7-V17 校验闸门 → 人工确认
```

**执行**（Step 6-9）— 改代码并验证

```
依赖预检 → subagent 改码（按 model_tier 分级派发）→ 资产/本地化/埋点落地
→ 代码审查 → 验收测试 → 交付汇总（含 token 用量）
```

## 流程步骤

| Step | 名称 | 说明 |
|------|------|------|
| 0 | 会话初始化 | Token 追踪初始化 + 交互式配置平台、仓库、输入源 |
| 1 | 变更盘点 | Flutter diff 采集 + Figma 截图 |
| 2 | 需求意图提炼 | 自动映射子流程 + llm_plan 生成 |
| 3 | 同步任务规划 | 生成 edit_tasks，按复杂度标注 model_tier，混合复杂度必须拆分 |
| 4 | 规划校验 | 自动校验 V7-V17，FAIL 禁止执行 |
| 5 | 人工确认 | 审阅 edit_tasks + plan_validation |
| 6 | 同步实施 | Subagent 按 model_tier 派发改码 + 资产/本地化/埋点落地 |
| 7 | 代码审查 | 全局代码审查，禁止 deferred 核心功能 |
| 8 | 验收测试 | 验收闭环 + diff 覆盖矩阵 |
| 9 | 总结交付 | 交付汇总 + token 用量统计 + 最终自检 |

- Step 0-2.3 共享 Flutter 分析，Step 2.4 起按平台分叉
- 双端同步时各端独立 agent 并行执行 Step 3-8
- 流程非严格线性，失败时按回退路径修复（详见 [SKILL.md](SKILL.md)）
- **整个 SOP 不执行任何 git commit**，由用户自行决定提交

## 四层质量防护

| 层级 | 位置 | 职责 |
|------|------|------|
| **L1 规划约束** | Step 3-4 | task 必填 asset_dependencies / l10n_keys / integration_point / model_tier + V15-V17 校验 |
| **L2 步骤通关** | Step 0-9 每步 | Gate Checklist 逐条核对（共 84 项），全 PASS 才能 completed |
| **L3 全局审查** | Step 7-8 | code_review 禁止 deferred + verify diff 覆盖矩阵 |
| **L4 交付闸门** | Step 9 | finalize 前置检查 + 自检 6 问 + 禁止"后续待办" |

### Gate Checklist 修复协议

Gate 检查发现 FAIL 时：定位 → 修复 → **重新核对整个 checklist** → 全 PASS → completed。禁止跳过、禁止标为"已知遗留"。

## 校验闸门

| ID | 检查项 | 失败级别 |
|----|--------|----------|
| V7 | 映射证明完整性 | FAIL |
| V8 | 自动映射流程证据 | FAIL |
| V9 | 入口级映射真实性 | FAIL |
| V10 | 生命周期与证据可执行性 | FAIL |
| V11 | 弹窗入口语义约束 | FAIL |
| V12 | 跨端差异闭环 | FAIL |
| V13 | diff 一致性（按 CAP 行为覆盖 + 新增 class 覆盖） | FAIL |
| V14 | hunk_facts 未覆盖事实 | FAIL/WARN |
| V15 | 新建文件集成入口（禁止死代码） | FAIL |
| V16 | 资产与本地化完整性 | WARN |
| V17 | task 复杂度一致性（edit_anchors 同一等级） | FAIL |

## Subagent 模型分级

在 Step 3 规划阶段为每个 task 标注 `model_tier`，Step 6 直接使用：

| model_tier | 判定条件 | 典型任务 |
|-----------|---------|---------|
| **haiku** | ≤2 文件，纯追加字段/配置/key | 数据模型扩展、AB 开关注册、样式微调 |
| **sonnet** | 3-5 文件，需理解现有模式后仿写 | 流程编排扩展、交互入口修改、组件重构 |
| **opus** | 新建大文件（>300行）、复杂 UI + Figma | 新建弹窗/页面、复杂状态管理 |

code review 始终使用 **opus**。同一 task 内 edit_anchors 跨等级则必须拆分。

## Token 用量追踪

| 时机 | 操作 |
|------|------|
| Step 0.0 | 记录 session JSONL 路径 + 起始行号 |
| 每步 completed 后 | 记录 JSONL 行号边界（用于按步骤统计） |
| Step 6/7 Agent 返回 | 追加 subagent 明细到 token_usage.md |
| Step 9 | 按 step_lines 分段解析 JSONL，生成三张汇总表（总计 / 按模型 / 按步骤） |

主 session 模型从 JSONL 的 `"model"` 字段精确读取（如 `claude-opus-4-6`），不用占位名。

## 核心原则

- **高保真同步** — Flutter 已实现行为为基准，允许架构映射，不允许需求降级
- **禁止伪完成** — 不输出 MVP / 占位版 / 简化版，不把"部分完成"写成"已完成"
- **禁止遗留** — 图片不用 SF Symbol 替代，埋点/本地化/回调不标"后续"，新建 View 必须有调用方
- **闸门强制** — plan_validation 未通过不得执行，verify 未通过不得交付
- **不提交** — 整个 SOP 不执行 git commit，subagent 也不提交

## 平台支持

| 平台 | 语言 | 编排入口 | 编译验证 |
|------|------|---------|---------|
| iOS | Swift | UIViewController / Coordinator / Manager | `xcodebuild build` |
| Android | Kotlin | Activity / Fragment / ViewModel | `./gradlew assembleDebug` |

## 项目结构

```
SKILL.md                         # Skill 主定义（流程索引 + 原则 + 协议）
references/
  00-session-init.md             # Step 0（含 0.0 Token 初始化）
  01-flutter-changes.md          # Step 1
  02-intent.md                   # Step 2（含 2.1-2.5 子流程）
  03-plan.md                     # Step 3（含 model_tier 规则）
  04-plan-validation.md          # Step 4（V7-V17）
  05-confirm.md                  # Step 5
  06-execute.md                  # Step 6（含资产/本地化/埋点落地）
  07-code-review.md              # Step 7（含禁止 deferred 场景）
  08-verify.md                   # Step 8（含 diff 覆盖矩阵）
  09-finalize.md                 # Step 9（含 token 汇总）
  10-understand-chat-log.md      # 附录：查询日志格式
  11-run-directory.md            # 附录：run 目录结构
  platforms/ios.md               # iOS 平台 Profile
  platforms/android.md           # Android 平台 Profile
```
