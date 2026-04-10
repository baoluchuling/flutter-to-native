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
│  Step 4 — 规划校验（V7-V18，FAIL 禁止执行）                   │
│  Step 5 — 人工确认（确认/改细节/改结构/拒绝）                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 6 — 执行（四阶段）                                     │
│                                                             │
│  6A 准备                                                     │
│  │  writing-plans → 选择执行方式 → 接口一致性规则              │
│  │  Prompt 统一模板组装 → 依赖预检 → Figma 上下文隔离          │
│  │                                                          │
│  6B 执行                                                     │
│  │  派发 subagent 改码 → 单 Task 完成后检查（Claude）          │
│  │  ├── A. Code Review（行为契约/集成/规范/bug）               │
│  │  └── B. UI 对齐检查（Figma 设计值 vs 代码 grep）           │
│  │                                                          │
│  6C 收尾                                                     │
│  │  资产/本地化/埋点/集成 遗漏补齐                              │
│  │                                                          │
│  6D 验证                                                     │
│     编译验证（xcodebuild / gradlew）                          │
│                                                             │
│  Gate Checklist: 14 项                                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 7 — 独立 AI 全局审查（Codex 优先）                      │
│                                                             │
│  ★ 与 Step 6 用不同 AI，保证独立验证                          │
│  高保真对齐 / 跨 task 一致性 / 线程安全 / API 版本 / 安全加固   │
│                                                             │
│  APPROVED → Step 8 / CHANGES_REQUESTED → 回 Step 6          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 8 — 验收测试                                           │
│                                                             │
│  atlas_verify.py → diff 覆盖反向检查 + 基准测试               │
│                                                             │
│  PASS/WARN → Step 9 / FAIL → 回 Step 6 → 7 → 8             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 9 — 总结交付                                           │
│                                                             │
│  前置检查 → finalize_report.md → 最终自检（5 问，附证据）      │
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
