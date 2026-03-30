# Flutter-to-Native SOP

Flutter 变更到 Native（iOS / Android）的流程编排工具。以 Claude Code Skill 形式运行，负责流程编排、质量闸门和产物校验，代码理解与修改由 CLI agent 完成。

## 流程概览

```
Step 0  会话初始化        ─── 交互式配置平台、仓库、输入源
Step 1  变更盘点          ─── Flutter diff 采集 + Figma 截图
Step 2  需求意图提炼      ─── 自动映射：能力切片 → 链路抽取 → Native 匹配 → 反证淘汰
Step 3  同步任务规划      ─── 生成 edit_tasks（按平台分叉）
Step 4  规划校验          ─── 自动校验闸门 V7-V14，FAIL 禁止执行
Step 5  人工确认          ─── 审阅 edit_tasks + plan_validation
Step 6  同步实施          ─── CLI agent 改码 + 编译验证
Step 7  代码审查          ─── 全局代码审查
Step 8  验收测试          ─── 验收闭环 + 基准测试
Step 9  总结交付          ─── 交付汇总 + 最终自检
```

Step 0-2.3 共享 Flutter 分析，Step 2.4 起按平台分叉。双端同步时各端独立 agent 并行执行 Step 3-8。

## 平台支持

| 平台 | 语言 | 编排入口 | 编译验证 |
|------|------|---------|---------|
| iOS | Swift | UIViewController / Coordinator / Manager | `xcodebuild build` |
| Android | Kotlin | Activity / Fragment / ViewModel | `./gradlew assembleDebug` |

## 项目结构

```
├── SKILL.md                    # Skill 主定义（流程、原则、进度追踪）
├── README.md                   # 本文件
├── references/
│   ├── 00-session-init.md      # Step 0: 会话初始化（逐步交互式）
│   ├── 01-flutter-changes.md   # Step 1: 变更盘点
│   ├── 02-intent.md            # Step 2: 需求意图提炼 + 自动映射
│   ├── 03-plan.md              # Step 3: 同步任务规划
│   ├── 04-plan-validation.md   # Step 4: 规划校验（V7-V14）
│   ├── 05-confirm.md           # Step 5: 人工确认
│   ├── 06-execute.md           # Step 6: 同步实施（含依赖预检）
│   ├── 07-code-review.md       # Step 7: 代码审查
│   ├── 08-verify.md            # Step 8: 验收测试（含 FAIL 修复循环）
│   ├── 09-finalize.md          # Step 9: 总结交付
│   ├── 10-understand-chat-log.md  # 附录: understand 日志格式
│   ├── 11-run-directory.md     # 附录: Run 目录结构
│   └── platforms/
│       ├── ios.md              # iOS 平台 Profile
│       └── android.md          # Android 平台 Profile
├── scripts/
│   ├── atlas_planner.py        # 规划引擎（plan + plan_validation）
│   ├── atlas_verify.py         # 验收引擎（verify）
│   └── atlas_intent_bridge.py  # Profile 加载 + 触点映射
└── tests/
    ├── test_atlas_planner_v2_only.py
    └── test_atlas_intent_bridge.py
```

## 校验闸门（Plan Validation）

| ID | 检查项 | 级别 |
|----|--------|------|
| V7 | 映射证明完整性 | FAIL |
| V8 | 自动映射流程证据 | FAIL |
| V9 | 入口级映射真实性 | FAIL |
| V10 | 生命周期与证据可执行性 | FAIL |
| V11 | 弹窗入口语义约束 | FAIL |
| V12 | 跨端差异闭环 | FAIL |
| V13 | diff 一致性（新增 class 覆盖） | FAIL |
| V14 | hunk_facts 未覆盖事实 | FAIL/WARN |

## 回退路径

流程非严格线性，失败时按规则回退：

- **Step 4 FAIL** → 回 Step 3 重新规划
- **Step 5 拒绝** → 回 Step 2 重新映射
- **Step 8 FAIL** → 回 Step 6 补码 → Step 7 重审 → Step 8 重验
- 详见 [SKILL.md](SKILL.md) 回退路径表

## 使用

作为 Claude Code Skill 触发，在对话中输入 `/flutter-to-native` 即可启动交互式流程。

### 脚本独立运行

```bash
# 规划
python3 scripts/atlas_planner.py plan \
  --repo-root /path/to/native-project \
  --profile-v2-dir /path/to/profile \
  --run-dir /path/to/run \
  --requirement-id REQ-001 \
  --requirement-name feature-name \
  --llm-resolution-path /path/to/llm_plan.json \
  [--pr-diff-path /path/to/diff] \
  [--debug]

# 验收
python3 scripts/atlas_verify.py verify \
  --run-dir /path/to/run/platform \
  [--repo-root /path/to/native-project] \
  [--swift-parse-check]

# 测试
python3 -m pytest tests/ -v
```

## 核心原则

- **高保真同步**：Flutter 已实现行为为基准，允许架构映射，不允许需求降级
- **禁止伪完成**：不输出 MVP / 占位版 / 简化版，不把"部分完成"写成"已完成"
- **闸门强制**：plan_validation 未通过不得执行，verify 未通过不得交付
