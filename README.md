# Flutter-to-Native SOP

将 Flutter 变更高保真同步到 Native（iOS / Android）的流程编排工具。

以 Claude Code Skill 形式运行，在对话中输入 `/flutter-to-native` 即可启动。Skill 负责流程编排与质量闸门，代码理解与修改由 CLI agent 完成。

## 工作原理

整个流程分为三个阶段：

**分析**（Step 1-2）— Flutter 改了什么、要同步什么

```
git diff → hunk_facts 结构化提取 → 四步自动映射（能力切片 → 链路抽取 → Native 匹配 → 反证淘汰）
```

**规划**（Step 3-5）— 怎么改 Native

```
edit_tasks 生成 → V7-V14 校验闸门 → 人工确认
```

**执行**（Step 6-8）— 改代码并验证

```
依赖预检 → agent 改码 + 编译 → 代码审查 → 验收测试 + 基准测试
```

## 流程步骤

| Step | 名称 | 说明 |
|------|------|------|
| 0 | 会话初始化 | 交互式配置平台、仓库、输入源 |
| 1 | 变更盘点 | Flutter diff 采集 + Figma 截图 |
| 2 | 需求意图提炼 | 自动映射子流程 + llm_plan 生成 |
| 3 | 同步任务规划 | 生成 edit_tasks（按平台分叉） |
| 4 | 规划校验 | 自动校验 V7-V14，FAIL 禁止执行 |
| 5 | 人工确认 | 审阅 edit_tasks + plan_validation |
| 6 | 同步实施 | CLI agent 改码 + 编译验证 |
| 7 | 代码审查 | 全局代码审查 |
| 8 | 验收测试 | 验收闭环 + 基准测试 |
| 9 | 总结交付 | 交付汇总 + 最终自检 |

- Step 0-2.3 共享 Flutter 分析，Step 2.4 起按平台分叉
- 双端同步时各端独立 agent 并行执行 Step 3-8
- 流程非严格线性，失败时按回退路径修复（详见 [SKILL.md](SKILL.md)）

## 核心能力

| 能力 | 阶段 | 作用 |
|------|------|------|
| **四步自动映射** | 分析 | 从 Flutter 链路自动定位 Native 落点，决定"改哪里" |
| **V7-V14 校验闸门** | 规划 | 8 项自动校验，映射/证据/一致性全覆盖，决定"能不能改" |
| **understand-anything 知识图谱** | 分析 | Native 仓库架构理解，链路匹配的基础 |
| **hunk_facts 结构化提取** | 分析 | 从 diff 提取 class/字段/埋点/AB 门控，verify 反向检查的依据 |
| **understand-explain 调用链查询** | 执行 | 改码前查调用链和上下文，避免盲改 |

> 前两个决定"改得对不对"，后三个决定"改得全不全"。

## 校验闸门

| ID | 检查项 | 失败级别 |
|----|--------|----------|
| V7 | 映射证明完整性 | FAIL |
| V8 | 自动映射流程证据 | FAIL |
| V9 | 入口级映射真实性 | FAIL |
| V10 | 生命周期与证据可执行性 | FAIL |
| V11 | 弹窗入口语义约束 | FAIL |
| V12 | 跨端差异闭环 | FAIL |
| V13 | diff 一致性（新增 class 覆盖） | FAIL |
| V14 | hunk_facts 未覆盖事实 | FAIL/WARN |

## 平台支持

| 平台 | 语言 | 编排入口 | 编译验证 |
|------|------|---------|---------|
| iOS | Swift | UIViewController / Coordinator / Manager | `xcodebuild build` |
| Android | Kotlin | Activity / Fragment / ViewModel | `./gradlew assembleDebug` |

## 项目结构

```
SKILL.md                         # Skill 主定义
references/
  00-session-init.md ~ 09-finalize.md   # Step 0-9 详细定义
  10-understand-chat-log.md             # 附录
  11-run-directory.md                   # 附录
  platforms/ios.md, android.md          # 平台 Profile
scripts/
  atlas_planner.py               # 规划引擎（plan + V7-V14 校验）
  atlas_verify.py                # 验收引擎
  atlas_intent_bridge.py         # Profile 加载 + 触点映射
tests/
  test_atlas_planner_v2_only.py
  test_atlas_intent_bridge.py
```

## 脚本命令

```bash
# 规划
python3 scripts/atlas_planner.py plan \
  --repo-root <native-project> \
  --profile-v2-dir <profile-dir> \
  --run-dir <run-dir> \
  --requirement-id REQ-001 \
  --requirement-name feature-name \
  --llm-resolution-path <llm_plan.json> \
  [--pr-diff-path <diff>] [--debug]

# 验收
python3 scripts/atlas_verify.py verify \
  --run-dir <run-dir>/platform \
  [--repo-root <native-project>] \
  [--swift-parse-check]

# 测试
python3 -m pytest tests/ -v
```

## 核心原则

- **高保真同步** — Flutter 已实现行为为基准，允许架构映射，不允许需求降级
- **禁止伪完成** — 不输出 MVP / 占位版 / 简化版，不把"部分完成"写成"已完成"
- **闸门强制** — plan_validation 未通过不得执行，verify 未通过不得交付
