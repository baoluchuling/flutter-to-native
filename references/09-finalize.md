# Step 9. finalize（交付）

> 双端同步时，所有平台都通过 verify 后，合并输出一份 finalize_report。

> **进入前置检查（强制，每个平台都必须满足，任一不满足则禁止交付）：**
> 1. `<platform>/verify_result.json` 存在，且 `verify_result` 字段值为 `PASS` 或 `WARN`
> 2. `<platform>/verify_report.md` 中"diff 覆盖矩阵"无 `FAIL` 行
> 3. `<platform>/plan_validation.md` 结论为 `PASS` 或 `WARN`（`FAIL` 状态下不得进入 execute，更不得进入 finalize）
> 4. `<platform>/code_review_report.md` 存在，且结论为 `APPROVED` 或 `APPROVED_WITH_COMMENTS`（所有 issues 已标记 resolved）
>
> 若上述任一条件未满足，输出阻断提示并指引用户回到对应步骤修复，不得继续输出交付内容。

汇总（落盘到 `finalize_report.md`，不仅输出到对话）：

```markdown
## 完成任务

### iOS
- TASK-XX: <功能名>

### Android
- TASK-XX: <功能名>

## 遗留风险
- [iOS][WARN] <verify/code_review WARN 条目，含处置意见>
- [Android][WARN] <...>

## 人工项
- <需要人工跟进的事项>

## 变更文件清单
- <列出所有新建和修改的文件，供用户 commit 时参考>

## Token 用量
<按以下流程生成，不得手动估算>

## 后续建议
- <技术债/优化建议>
```

> 单端同步时，省略另一平台的段落即可。

## 对用户输出（默认结构）

- `需求理解`：说明 Flutter 中真实完成了什么、用户视角下的核心流程、同步到 Native 后的目标。
- `Flutter 实现拆解`：至少覆盖页面结构、交互流程、状态流转、数据来源、接口调用、异常处理、边界逻辑、生命周期相关逻辑、依赖组件/工具/插件。
- `原生实现映射`：按平台分别说明落点和行为表达方式。
- `原生代码输出`：当用户要求代码时，按文件输出完整代码，不输出伪代码；若缺少必要上下文，明确标注假设项。
- `差异、阻塞与风险`：显式列出当前无法确定、无法完成、尚未与 Flutter 对齐的部分，以及权限 / 生命周期 / 线程 / 回调 / UI 差异风险。
- `验收清单`：按"是否与 Flutter 一致"列出主流程、交互反馈、状态切换、错误处理、接口参数、返回结果、页面返回恢复、边界情况。

## Token 用量汇总（必做）

在生成 finalize_report 时，执行以下操作生成最终汇总。

### 1. 从 session JSONL 按步骤统计用量

读取 `token_tracking.json` 中的 `step_lines`（每步开始时的 JSONL 行号），分段统计：

```python
import json, re

tracking = json.load(open("<run-dir>/token_tracking.json"))
jsonl_path = tracking["session_jsonl"]
step_lines = tracking["step_lines"]  # {"step_0": 100, "step_1": 150, ...}

# 读取所有行
with open(jsonl_path) as f:
    lines = f.readlines()

# 按步骤分段统计
steps = sorted(step_lines.items(), key=lambda x: int(x[0].split("_")[1]))
step_tokens = {}

for idx, (step_name, start) in enumerate(steps):
    end = steps[idx + 1][1] if idx + 1 < len(steps) else len(lines)
    tokens = 0
    for line in lines[start:end]:
        for m in re.finditer(r'"output_tokens":(\d+)', line):
            tokens += int(m.group(1))
        for m in re.finditer(r'"input_tokens":(\d+)', line):
            tokens += int(m.group(1))
        for m in re.finditer(r'"cache_creation_input_tokens":(\d+)', line):
            tokens += int(m.group(1))
        for m in re.finditer(r'"cache_read_input_tokens":(\d+)', line):
            tokens += int(m.group(1))
    step_tokens[step_name] = tokens
```

主 Session 模型名从 JSONL 中提取（`"model"` 字段，如 `claude-opus-4-6`），用于"按模型"表的行标题。

### 2. 读取 subagent 明细表，按 model 分组求和

### 3. 写入汇总到 token_usage.md（三张表）

在 subagent 明细表之后追加：

```markdown
## 总计

| 指标 | 数量 |
|------|------|
| 总 Tokens | xxx |
| 预估总费用 | $x.xx |

## 按模型

| 模型 | Tokens | 费用 |
|------|--------|------|
| {主session实际模型名，从JSONL的model字段提取，如 claude-opus-4-6} | xxx | $x.xx |
| Subagent haiku | xxx | $x.xx |
| Subagent sonnet | xxx | $x.xx |
| Subagent opus | xxx | $x.xx |

## 按步骤

| 步骤 | Tokens | 费用 |
|------|--------|------|
| Step 0 — 会话初始化 | xxx | $x.xx |
| Step 1 — 变更盘点 | xxx | $x.xx |
| Step 2 — 需求意图提炼 | xxx | $x.xx |
| Step 3 — 同步任务规划 | xxx | $x.xx |
| Step 4 — 规划校验 | xxx | $x.xx |
| Step 5 — 人工确认 | xxx | $x.xx |
| Step 6 — 同步实施 | xxx | $x.xx |
| Step 7 — 代码审查 | xxx | $x.xx |
| Step 8 — 验收测试 | xxx | $x.xx |
| Step 9 — 总结交付 | xxx | $x.xx |
```

**费用计算**：主 Session 按 input $15/MTok + cache_read $1.875/MTok + output $75/MTok；Subagent 按 haiku $1.25/MTok、sonnet $15/MTok、opus $75/MTok（output 价，简化计算）。

### 4. 将汇总复制到 finalize_report.md 的"Token 用量"段

## 最终自检（必做，需附机械化证据）

自检不得仅依赖主观回答。每题必须附客观数据，数据不匹配则自检 FAIL。

| # | 问题 | 必附证据 |
|---|------|---------|
| 1 | 我是否擅自简化了需求，或把复杂模块拆到后续处理？ | `flutter_chain_map.json` 中 CAP 数量 vs `edit_tasks.json` 中 task 数量（含 excluded_caps 说明） |
| 2 | 我是否把 Flutter 的真实行为替换成了更容易实现的版本？ | `verify_report.md` 中 diff 覆盖矩阵的 PASS/FAIL 统计 |
| 3 | 我是否遗漏了 Flutter 已有的交互、状态、异常、边界、生命周期、异步回调时序？ | `hunk_facts.json` 中 analytics_events 总数 vs `code_review_report.md` 中确认的埋点实现数 |
| 4 | 我是否把备选方案当成默认实现输出？ | 资产落地检查：`asset_dependencies` 总数 vs Native 项目中实际存在的文件数 |
| 5 | 我是否把未完成结果伪装成已完成？ | 集成入口 grep 结果：每个新建 UI 文件的外部引用数 |

- 任一答案为 `是` 或数据不匹配时，先修正输出，再交付。

## Gate Checklist

完成 Step 9 前，逐条核对：

- [ ] 前置检查 4 项全部满足（verify_result / verify_report / plan_validation / code_review_report）
- [ ] `finalize_report.md` 已落盘到 run 目录（非仅对话输出）
- [ ] 完成任务列表：每个 task 已列出
- [ ] 遗留风险：所有 verify WARN 项已列入，附处置意见
- [ ] 回滚点：起始/结束 commit SHA 准确
- [ ] 最终自检 6 项全部回答"否"
- [ ] `finalize_report.md` 中无"后续待办"或"deferred"项（除非**用户主动提出**跳过特定功能项，必须可追溯到对话中的具体文字。AI 不得建议简化）
- [ ] `token_usage.md` 已包含 subagent 明细 + 主 session 汇总 + 费用汇总
- [ ] `finalize_report.md` 的"Token 用量"段已填入汇总数据
