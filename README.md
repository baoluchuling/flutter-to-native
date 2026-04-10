# Flutter-to-Native SOP

将 Flutter 变更高保真同步到 Native（iOS / Android）的流程编排工具。

以 Claude Code Skill 形式运行，输入 `/flutter-to-native` 启动。Skill 负责流程编排与质量闸门，代码理解与修改由 CLI agent 完成。整个流程不执行 git commit，由用户自行决定提交。

## 全流程

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
│  0.6 环境检查：知识图谱 / Python / 部署目标采集 / Codex 可用性   │
│  0.7 汇总确认 → 用户说"确认开始"                              │
│                                                             │
│  产物：session_config.json, token_tracking.json              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1 — Flutter 变更采集                                   │
│                                                             │
│  读 git diff → 改动文件列表 + 能力摘要                        │
│  含新增 UI？→ true：检查 Figma 截图 / false：跳过 Figma 约束   │
│                                                             │
│  产物：flutter_changes.md, figma_inputs.md（UI 时）           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2 — 需求意图提炼                                       │
│                                                             │
│  2.1 capability_split  → 拆原子能力 CAP-01, 02...（共享）    │
│  2.2 hunk_extract      → 结构化事实提取（共享）               │
│  2.3 chain_extract     → 触发→状态→交互→副作用（共享）        │
│  ─── 以上共享，以下按平台分叉 ───                              │
│  2.4 native_chain_match → understand-chat 查 Native 候选链   │
│  2.5 disambiguation     → Top1/Top2 反证淘汰                 │
│  → 组装 llm_plan.json                                        │
│                                                             │
│  产物：capability_slices.md, hunk_facts.json,                │
│        flutter_chain_map.json, llm_plan.json 等              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3 — 同步任务规划                                       │
│                                                             │
│  llm_plan.json → atlas_planner.py → edit_tasks.json         │
│  每个 task 含：behavior_contract / edit_anchors /            │
│  integration_point / mapping_proof / acceptance /            │
│  asset_dependencies / l10n_keys / model_tier                 │
│                                                             │
│  产物：edit_tasks.json, edit_tasks.md, intent.md 等          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4 — 规划校验                                           │
│                                                             │
│  12 项自动校验（V7-V18）：                                    │
│  - 映射证明完整性、流水线产物齐全、入口真实性                    │
│  - 生命周期一致性、弹窗入口语义、跨端差异闭环                    │
│  - CAP→task 覆盖 + 新增 class 覆盖                           │
│  - 集成入口格式（file:method:line）+ grep 验证                │
│  - 资产/本地化完整性、model_tier 一致性、AB 门控处置             │
│                                                             │
│  FAIL → 回 Step 3 修正   PASS/WARN → 继续                    │
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
│  ★ 双端同步时：从这里开始派两个 parallel agent                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 6 — 执行（四阶段）                                     │
│                                                             │
│  ┌── 6A 准备 ──────────────────────────────────────────┐    │
│  │  writing-plans → 生成 implementation_plan.md          │    │
│  │  选择执行方式（subagent-driven 强制 / inline 例外）    │    │
│  │  跨 subagent 接口一致性规则                            │    │
│  │  Prompt 统一模板组装（§1-§6，按 user_facing 决定内容）  │    │
│  │  依赖预检（Flutter 新增依赖 → Native 是否已集成）       │    │
│  │  API 版本兼容约束                                      │    │
│  │  Figma 上下文隔离（按 CAP 筛选截图，禁止整体传入）      │    │
│  └───────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌── 6B 执行 ──────────────────────────────────────────┐    │
│  │  understand 约束（每 task 至少查询一次）               │    │
│  │  派发 subagent 改码（按 model_tier 分级）              │    │
│  │  单 Task 完成后检查（Claude 主 session，趁热修复）：    │    │
│  │  ├── A. Code Review                                   │    │
│  │  │   行为契约/集成完整性/代码规范/接口一致性/明显 bug    │    │
│  │  │   FAIL ≤3 → 主 session 直接修                      │    │
│  │  │   FAIL >3 → 派修复 subagent                        │    │
│  │  └── B. UI 对齐检查（仅 UI task）                     │    │
│  │      get_design_context 提取设计值 → 代码 grep 验证     │    │
│  │      输出对齐矩阵（颜色/字号/间距/圆角）                │    │
│  │      FAIL → 修复后重新 grep 直到全 PASS                │    │
│  │  Token 记录 + execution_log 追加                       │    │
│  └───────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌── 6C 收尾 ──────────────────────────────────────────┐    │
│  │  遗漏补齐（subagent 各管各的，这里统一扫一遍）：       │    │
│  │  - 图片资源：file 命令验证每个文件存在且有效            │    │
│  │  - 本地化 key：确认本地化文件有对应条目                 │    │
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
│  - 高保真对齐（Native vs flutter_chain_map.json 链路）       │
│  - 跨 task 一致性（持久化 key 格式统一、埋点全覆盖）           │
│  - 线程/内存安全（delegate 循环引用、Timer 泄漏）             │
│  - API 版本兼容（#available / Build.VERSION 保护）           │
│  - 安全加固（Token 存储、日志敏感数据、证书验证、组件导出）     │
│                                                             │
│  APPROVED → Step 8                                           │
│  CHANGES_REQUESTED → 回 Step 6 修码 → 重新 review            │
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
│  - Layer 1 FAIL → 回 Step 2（补提取）                        │
│  - Layer 4 FAIL → 回 Step 6（补代码）                        │
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

## 双端同步

```
Step 0-1          共享（一次）
Step 2.1-2.3      共享（一次）
Step 2.4+         分叉 → iOS / Android 各走一轮
Step 3-8          两端并行（dispatching-parallel-agents）
Step 9            合并（等两端都完成）
```

## 三道审查

| 审查 | 审查者 | 粒度 | 时机 |
|------|--------|------|------|
| subagent 自审 | subagent 自身 | 单 task | 改码完成时 |
| Step 6B.3 | Claude 主 session | 单 task | subagent 返回后立即 |
| Step 7 | 独立 AI（Codex 优先） | 全部改动 | 编译通过后 |

## Subagent Prompt 模板

所有 task 使用同一模板，UI 视觉参考为条件段（UI task 必选，非 UI task 跳过）：

```
§1 目标与参考
   ├── UI 视觉参考（UI task 必选）
   └── Flutter 行为基准（所有 task 必选）
§2 行为契约
§3 实现范围
§4 依赖信息
§5 编码规范
§6 验收标准
```

排列原则：**做什么 → 参考什么 → 依赖什么 → 怎么做 → 怎么算完成**。

## 产物路径

| 引用写法 | 双端同步 | 单端同步 |
|---------|---------|---------|
| `flutter/xxx` | `<run-dir>/flutter/xxx` | `<run-dir>/xxx` |
| `<platform>/xxx` | `<run-dir>/ios/xxx` 或 `android/xxx` | `<run-dir>/xxx` |
| `finalize_report.md` | `<run-dir>/finalize_report.md` | 同左 |

## 项目结构

```
SKILL.md                         # 流程定义 + 原则 + 协议
README.md                        # 本文档
references/
  00-session-init.md             # Step 0
  01-flutter-changes.md          # Step 1
  02-intent.md                   # Step 2（2.1-2.5 子流程）
  03-plan.md                     # Step 3（含 model_tier）
  04-plan-validation.md          # Step 4（V7-V18）
  05-confirm.md                  # Step 5
  06-execute.md                  # Step 6（6A→6B→6C→6D）
  07-code-review.md              # Step 7（独立 AI + 安全加固）
  08-verify.md                   # Step 8（diff 覆盖 + 基准测试）
  09-finalize.md                 # Step 9（token 汇总 + 自检）
  10-understand-chat-log.md      # 附录：查询日志格式
  11-run-directory.md            # 附录：run 目录结构
  platforms/ios.md               # iOS Profile
  platforms/android.md           # Android Profile
```

详细规则见 [SKILL.md](SKILL.md) 和各步骤引用文档。
