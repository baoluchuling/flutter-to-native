# Flutter-to-Native SOP

将 Flutter 变更高保真同步到 Native（iOS / Android）的流程编排工具。

以 Claude Code Skill 形式运行，在对话中输入 `/flutter-to-native` 即可启动。Skill 负责流程编排与质量闸门，代码理解与修改由 CLI agent 完成。

## 全流程总览

```
用户触发 /flutter-to-native
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 0 — 会话初始化                                         │
│                                                             │
│  一问一答配置：                                               │
│  0.1 平台？ → iOS / Android / 双端                           │
│  0.2 Native 仓库路径？                                       │
│  0.3 Flutter 仓库 + commit 范围？ → 自动 git diff             │
│  0.4 Figma 链接？（UI 变更时必填）→ 自动拉截图                  │
│  0.5 补充文档？（可选）                                       │
│  0.6 环境检查（自动）：                                       │
│      - Python 3.10+                                         │
│      - 知识图谱存在？不存在 → 阻塞，让用户先跑 /understand      │
│      - 部署目标采集（iOS deployment_target / Android minSdk）  │
│      - Codex 可用？→ 决定 Step 7 审查工具                     │
│  0.7 汇总确认 → 用户说"确认开始"                              │
│                                                             │
│  产物：session_config.json, token_tracking.json              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1 — Flutter 变更采集                                   │
│                                                             │
│  读 git diff → 生成改动文件列表 + 能力摘要                     │
│  判断：含新增 UI 页面？                                       │
│    ├── true → 检查 Figma 截图是否已拉取，没有就回 Step 0.4 补  │
│    └── false → Figma 相关约束不触发                           │
│                                                             │
│  产物：flutter_changes.md, figma_inputs.md（UI 时）           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2 — 需求意图提炼（最复杂的一步）                         │
│                                                             │
│  ┌─ 2.1 capability_split（共享）                             │
│  │  Flutter diff → 拆成原子能力 CAP-01, CAP-02...            │
│  │  大文件(>200行)必须逐条列出行为变更，禁止笼统概括              │
│  │  输出"新增 Class 归属表"                                   │
│  │  ★ UI 变更时：回到 figma_inputs.md 补 CAP 映射             │
│  │                                                          │
│  ├─ 2.2 flutter_hunk_extract（共享）                         │
│  │  从 diff hunk 提取结构化事实：                              │
│  │  new_classes / new_methods / persistence_keys /           │
│  │  analytics_events / ab_gates / state_fields /             │
│  │  conditional_flags                                        │
│  │  对 >200 行的文件做内容质量抽查                              │
│  │                                                          │
│  ├─ 2.3 flutter_chain_extract（共享）                        │
│  │  每个 CAP → 触发入口 → 状态变化 → 交互 → 副作用             │
│  │  对照 hunk_facts 逐字段校验覆盖，未覆盖的输出 uncovered_facts │
│  │                                                          │
│  │  ═══ 以上共享，只做一次 ═══                                │
│  │  ═══ 以下按平台分叉 ═══                                   │
│  │                                                          │
│  ├─ 2.4 native_chain_match（按平台）                         │
│  │  用 /understand-anything:understand-chat 查 Native 代码    │
│  │  每个 CAP → 找 Native 侧的候选调用链 Top-K                 │
│  │  ★ 新建 UI 的 CAP 必须查到 file:method:line 级别           │
│  │                                                          │
│  └─ 2.5 disambiguation（按平台）                             │
│     Top1 vs Top2 反证淘汰，记录选择理由和淘汰原因               │
│                                                             │
│  最后：组装 llm_plan.json（映射流水线 + tasks）                │
│                                                             │
│  产物：capability_slices.md, hunk_facts.json,                │
│        flutter_chain_map.json, native_chain_candidates.json, │
│        mapping_disambiguation.md, llm_plan.json              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3 — 同步任务规划                                       │
│                                                             │
│  llm_plan.json → atlas_planner.py plan → edit_tasks.json    │
│                                                             │
│  每个 task 必含：                                             │
│  ┌──────────────────────────────────────────────┐           │
│  │ title / capability / behavior_contract        │           │
│  │ edit_anchors / integration_point              │           │
│  │ mapping_proof（native_chain + evidence_lines） │           │
│  │ acceptance（含 grep 验收断言）                  │           │
│  │ asset_dependencies / l10n_keys                │           │
│  │ model_tier（haiku / sonnet / opus）            │           │
│  └──────────────────────────────────────────────┘           │
│                                                             │
│  规则：每个 score>0 的 CAP 必须有独立 task，禁止合并           │
│                                                             │
│  产物：edit_tasks.json, edit_tasks.md, intent.md,            │
│        native_touchpoints.md, risk_report.md                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4 — 规划校验                                           │
│                                                             │
│  V7  映射证明存在且 status=mapped？                           │
│  V8  映射流水线五步产物齐全？                                  │
│  V9  入口级映射真实性（非纯视图 + 有反向回溯）？                 │
│  V10 生命周期与证据可执行性？                                  │
│  V11 弹窗入口语义（首条必须是 show/present）？                  │
│  V12 跨端差异闭环（gap/tradeoff/alignment 三件套）？           │
│  V13 CAP→task 覆盖 + 新增 class 覆盖？                       │
│  V14 hunk_facts 未覆盖事实？                                  │
│  V15 新建文件集成入口（file:method:line 格式 + grep 验证）？    │
│  V16 资产与本地化完整性？                                     │
│  V17 task 复杂度一致性（model_tier）？                        │
│  V18 AB 门控处置方案？                                        │
│                                                             │
│  FAIL → 回 Step 3 修   PASS/WARN → 继续                     │
│                                                             │
│  产物：plan_validation.md                                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5 — 人工确认                                           │
│                                                             │
│  用户审阅 edit_tasks.md + plan_validation.md                 │
│                                                             │
│  ├── 确认 → 进入 Step 6                                     │
│  ├── 改细节 → 改文件，必要时重跑部分校验                       │
│  ├── 改结构 → 回 Step 3 重新生成                              │
│  └── 拒绝 → 回 Step 2 重新规划                               │
│                                                             │
│  ★ 双端同步时：从这里开始可以派两个 parallel agent              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 6 — 执行（四阶段）                                     │
│                                                             │
│  ┌── 6A 准备 ──────────────────────────────────────────┐    │
│  │  6A.1 writing-plans → 生成 implementation_plan.md    │    │
│  │       选择执行方式（subagent-driven 强制 / inline 例外）│    │
│  │       跨 subagent 接口一致性规则                       │    │
│  │  Prompt 统一模板：                                    │    │
│  │       §1 目标与参考（UI视觉参考+Flutter行为基准）       │    │
│  │       §2 行为契约                                     │    │
│  │       §3 实现范围                                     │    │
│  │       §4 依赖信息                                     │    │
│  │       §5 编码规范                                     │    │
│  │       §6 验收标准                                     │    │
│  │  6A.2 执行输入确认                                    │    │
│  │  6A.3 依赖预检（Flutter 新增依赖 → Native 是否已集成） │    │
│  │  API 版本兼容约束                                     │    │
│  │  6A.4 Figma 上下文隔离（按 CAP 筛选截图）             │    │
│  └───────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌── 6B 执行 ──────────────────────────────────────────┐    │
│  │  6B.1 understand 约束（每 task 至少查询一次）         │    │
│  │  6B.2 派发 subagent 改码                              │    │
│  │  6B.3 单 Task 完成后检查（Claude 主 session）         │    │
│  │       ├── A. Code Review（行为契约/集成/规范/bug）     │    │
│  │       │   FAIL ≤3 → 主 session 直接修                 │    │
│  │       │   FAIL >3 → 派修复 subagent                   │    │
│  │       └── B. UI 对齐检查（仅 UI task）                │    │
│  │           Figma 设计值 vs 代码 grep → 对齐矩阵         │    │
│  │           FAIL → 修复后重新 grep 直到全 PASS           │    │
│  │  6B.4 Token 记录                                      │    │
│  │  6B.5 execution_log 追加                              │    │
│  └───────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌── 6C 收尾 ──────────────────────────────────────────┐    │
│  │  遗漏补齐（subagent 各管各的，这里统一扫一遍）：       │    │
│  │  - 图片资源：file 命令验证每个文件存在且有效            │    │
│  │  - 本地化 key：确认 Localizable.strings 有对应条目     │    │
│  │  - 埋点：确认每个 analytics_event 有 Native 调用       │    │
│  │  - 集成验证：grep 确认每个新建 UI 有外部调用            │    │
│  │  任一缺失 → 补齐，禁止进入编译                         │    │
│  └───────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌── 6D 验证 ──────────────────────────────────────────┐    │
│  │  xcodebuild / gradlew 编译                            │    │
│  │  成功 → Step 7                                        │    │
│  │  失败 → 分析错误 → 派修复 subagent → 重新编译          │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                             │
│  Gate Checklist: 14 项全部 PASS 才算完成                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 7 — 独立 AI 全局审查                                   │
│                                                             │
│  审查者：Codex（优先）或 code-reviewer subagent               │
│  ★ 与 Step 6 用不同 AI，保证独立验证                          │
│                                                             │
│  审查要点：                                                  │
│  - 高保真对齐（Native vs flutter_chain_map.json）            │
│  - 跨 task 一致性（持久化 key 格式统一、埋点全覆盖）           │
│  - 线程/内存安全（delegate 循环引用、Timer 泄漏）             │
│  - API 版本兼容（#available 保护）                           │
│  - 安全加固（Token 存储、日志、证书、组件导出）                │
│                                                             │
│  APPROVED → Step 8                                           │
│  CHANGES_REQUESTED → 回 Step 6 修 → 重新 review              │
│                                                             │
│  产物：code_review_report.md                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 8 — 验收测试                                           │
│                                                             │
│  atlas_verify.py verify → 按 task 验收断言检查                │
│                                                             │
│  diff 覆盖反向检查（从 hunk_facts 出发）：                    │
│  - new_classes（user_facing）→ 有 Native 对应？              │
│  - persistence_keys → key 格式一致？                         │
│  - analytics_events → 埋点调用存在？（缺失直接 FAIL）         │
│  - ab_gates → 条件判断存在？                                 │
│  资产/本地化/集成入口 → 最终 grep 确认                        │
│                                                             │
│  基准测试：run_benchmark.py                                  │
│  - Layer 1 FAIL → 回 Step 2                                 │
│  - Layer 4 FAIL → 回 Step 6                                 │
│                                                             │
│  PASS/WARN → Step 9                                          │
│  FAIL → 修代码 → 重走 Step 7 → 重走 Step 8                  │
│                                                             │
│  产物：verify_report.md, verify_result.json                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 9 — 总结交付                                           │
│                                                             │
│  前置检查（全部满足才能交付）：                                │
│  ✓ verify_result = PASS/WARN                                │
│  ✓ plan_validation = PASS/WARN                              │
│  ✓ code_review = APPROVED                                   │
│                                                             │
│  输出 finalize_report.md：                                   │
│  - 完成任务清单                                              │
│  - 遗留风险（WARN 项 + 处置意见）                             │
│  - 变更文件清单（供用户 commit 参考）                          │
│  - Token 用量（按模型 + 按步骤 + 费用）                       │
│                                                             │
│  最终自检（5 问，必须附机械化证据）：                           │
│  1. 擅自简化了？→ CAP 数 vs task 数                          │
│  2. 行为替换了？→ diff 覆盖矩阵 PASS/FAIL 统计               │
│  3. 遗漏了？→ analytics_events 总数 vs 实现数                │
│  4. 资产对了？→ asset_dependencies 总数 vs 实际文件数         │
│  5. 完成了？→ 每个新建 UI 的 grep 外部引用数                  │
│                                                             │
│  ★ 整个流程不 git commit，用户自行决定                        │
└─────────────────────────────────────────────────────────────┘
```

## 回退路径

```
Step 4 FAIL ──────────→ Step 3（重新生成 task）
Step 5 拒绝整体 ──────→ Step 2（重新规划能力）
Step 5 改结构 ────────→ Step 3 → Step 4
Step 6 编译失败 ──────→ Step 6 内循环（修→编译→修）
Step 6 中止 ─────────→ git checkout . → Step 2.4 或 Step 6
Step 7 CHANGES_REQ ──→ Step 6（修码）→ Step 7（重审）
Step 8 FAIL（代码）──→ Step 6 → Step 7 → Step 8
Step 8 FAIL（留档）──→ Step 8 内循环（补文档→重验）
Step 8 基准 L1 FAIL ─→ Step 2（补提取）→ 全链路重走
Step 8 基准 L4 FAIL ─→ Step 6 → Step 7 → Step 8
```

## 双端同步分叉点

```
Step 0-1          共享（一次）
Step 2.1-2.3      共享（一次）
Step 2.4+         分叉 → iOS agent / Android agent 各走一轮
Step 3-8          两端并行（dispatching-parallel-agents）
Step 9            合并（等两端都完成）
```

## 三道独立审查

| 审查 | 审查者 | 粒度 | 时机 |
|------|--------|------|------|
| subagent 自审 | subagent 自身 | 单 task | 改码完成时 |
| Step 6B.3 检查 | Claude 主 session | 单 task | subagent 返回后立即 |
| Step 7 全局审查 | 独立 AI（Codex 优先） | 所有改动文件 | 编译通过后 |

## 产物路径

各步骤产物路径根据同步模式解析：

| 引用写法 | 双端同步 | 单端同步 |
|---------|---------|---------|
| `flutter/hunk_facts.json` | `<run-dir>/flutter/hunk_facts.json` | `<run-dir>/hunk_facts.json` |
| `<platform>/edit_tasks.json` | `<run-dir>/ios/edit_tasks.json` | `<run-dir>/edit_tasks.json` |
| `finalize_report.md` | `<run-dir>/finalize_report.md` | 同左 |

## 校验闸门

| ID | 检查项 | 失败级别 |
|----|--------|----------|
| V7 | 映射证明完整性 | FAIL |
| V8 | 自动映射流程证据 | FAIL |
| V9 | 入口级映射真实性 | FAIL |
| V10 | 生命周期与证据可执行性 | FAIL |
| V11 | 弹窗入口语义约束 | FAIL |
| V12 | 跨端差异闭环 | FAIL |
| V13 | diff 一致性（CAP 行为覆盖 + 新增 class 覆盖） | FAIL |
| V14 | hunk_facts 未覆盖事实 | FAIL/WARN |
| V15 | 新建文件集成入口（禁止死代码） | FAIL |
| V16 | 资产与本地化完整性 | WARN |
| V17 | task 复杂度一致性（edit_anchors 同一等级） | FAIL |
| V18 | AB 门控处置方案 | WARN/FAIL |

## Subagent Prompt 统一模板

所有 task 使用同一模板，UI 视觉参考为条件段：

```
§1 目标与参考
   ├── UI 视觉参考（UI task 必选：截图 + Figma + 设计要点 + get_design_context 指令）
   └── Flutter 行为基准（所有 task 必选：new_methods + persistence_keys + state_fields）
§2 行为契约（核心，每条必须实现）
§3 实现范围（edit_anchors + integration_point + trigger）
§4 依赖信息（前置接口 + 资产 + 本地化 + AB 门控）
§5 编码规范（平台规范 + understand 指令 + 版本约束）
§6 验收标准（acceptance + 报告格式）
```

排列原则：**做什么 → 参考什么 → 依赖什么 → 怎么做 → 怎么算完成**。行为契约和验收标准分别占据高注意力的开头和结尾位置。

## Subagent 模型分级

| model_tier | 判定条件 | 典型任务 |
|-----------|---------|---------|
| **haiku** | ≤2 文件，纯追加字段/配置/key | 数据模型扩展、AB 开关注册、样式微调 |
| **sonnet** | 3-5 文件，需理解现有模式后仿写 | 流程编排扩展、交互入口修改、组件重构 |
| **opus** | 新建大文件（>300行）、复杂 UI + Figma | 新建弹窗/页面、复杂状态管理 |

code review 始终使用 **opus**。同一 task 内 edit_anchors 跨等级则必须拆分。

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
README.md                        # 本文档（全流程说明）
references/
  00-session-init.md             # Step 0（含 Token 初始化 + 环境检查）
  01-flutter-changes.md          # Step 1（含 Figma 截图→CAP 映射规则）
  02-intent.md                   # Step 2（含 2.1-2.5 子流程）
  03-plan.md                     # Step 3（含 model_tier 规则）
  04-plan-validation.md          # Step 4（V7-V18）
  05-confirm.md                  # Step 5
  06-execute.md                  # Step 6（6A准备→6B执行→6C收尾→6D验证）
  07-code-review.md              # Step 7（独立 AI 审查 + 安全加固检查）
  08-verify.md                   # Step 8（含 diff 覆盖矩阵 + 基准测试）
  09-finalize.md                 # Step 9（含 token 汇总 + 最终自检）
  10-understand-chat-log.md      # 附录：查询日志格式
  11-run-directory.md            # 附录：run 目录结构
  platforms/ios.md               # iOS 平台 Profile
  platforms/android.md           # Android 平台 Profile
```
