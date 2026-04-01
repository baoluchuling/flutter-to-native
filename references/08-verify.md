# Step 8. verify（验收闭环，**强制执行，不得跳过**）

> **严禁跳过 verify**：verify 是防止遗漏功能进入交付的最后一道防线。`verify_report.md` 和 `verify_result.json` 必须存在，否则视为流程未完成，不得进入 finalize。

> 命令须在 Native 仓库根目录下执行，`scripts/atlas_verify.py` 相对于该根目录。

```bash
python3 scripts/atlas_verify.py verify \
  --run-dir <run-dir>/<platform> \
  [--repo-root <native-project-root>] \
  [--swift-parse-check]    # iOS
  [--kotlin-parse-check]   # Android
  [--force]
```

按 task 验收断言检查：
- 功能行为覆盖
- 调用链与数据契约
- Flutter 逻辑一致性（与 `flutter_changes.md` / `pr_diff` 对照）
- 编译/测试（可配置）
- 跨端差异留档一致性：当 task 标注 `cross_platform_gap=true` 时，`verify` 必须核对
  - `cross_platform_gap.md` 中的差异点是否被代码或配置实现
  - `design_tradeoff.md` 的取舍是否与最终实现一致
  - `acceptance_alignment.md` 的对齐项是否全部有验收结论（PASS/WARN/FAIL）
- **diff 覆盖反向检查（强制）**：从 `flutter/hunk_facts.json` 出发，逐字段核查 Native 实现是否覆盖：
  - `new_classes`：每个 `user_facing: true` 的 class 是否有对应 Native 文件或类
  - `persistence_keys`：每个持久化 key 格式是否在 Native 代码中有等价实现（key 名、变量结构）
  - `analytics_events`：每个埋点事件是否在 Native 中有对应调用（允许平台差异但必须显式标注）
  - `ab_gates`：每个 AB 门控是否在 Native 中有等价条件判断
  - 反向检查结果输出为 `verify_report.md` 中的 "diff 覆盖矩阵" 表，逐行标注 PASS / WARN / FAIL / SKIP（含原因）
  - 若任一 `user_facing: true` class 无 Native 对应，`verify_result` 必须为 `FAIL`
- 若上述任一项缺失或不一致，`verify_result` 必须为 `FAIL`

## verify FAIL 修复循环

verify 结果为 `FAIL` 时，**禁止直接进入 finalize**，必须走以下闭环：

1. 读取 `verify_report.md` 中的 FAIL 条目，确认是代码缺失、逻辑偏差还是留档缺失
2. 根据 FAIL 类型针对性修复（**不是重跑整个 execute，只改 FAIL 条目对应的代码**）：
   - **代码缺失 / 逻辑偏差**：仅补齐或修正 verify_report 中 FAIL 行对应的 Native 代码，追加记录到 `execution_log.md`（不覆盖原有记录）
   - **留档缺失**（`cross_platform_gap.md` / `design_tradeoff.md` / `acceptance_alignment.md`）：补充相应工件，不需要改代码
3. 根据修复类型决定下一步：
   - **有代码改动**：必须先重新执行 Step 7（code_review），通过后再重新执行 Step 8（verify），不得复用旧的 `code_review_report.md` 和 `verify_report.md`
   - **纯补留档（无代码改动）**：直接重新执行 Step 8（verify），生成新的 `verify_report.md` 和 `verify_result.json`
4. verify 通过（`PASS` 或 `WARN`）后进入 finalize

## verify WARN 处理

verify 结果为 `WARN` 时，**可进入 finalize**，但：
- WARN 条目必须逐条列入 `finalize_report.md` 的"遗留风险"部分，并附处置意见（已知可接受 / 需后续跟进）
- 不得在 finalize 输出中省略 WARN 内容或标记为"已解决"

## 基准测试（**强制运行，不得跳过**）

verify 通过后，必须运行基准测试：

```bash
python3 .ai/t2n/benchmark/run_benchmark.py --case <case-id> --repo-root <native-root>
# 注：<case-id> 是 benchmark/cases/ 目录下的 case 名（如 short-opz-001），不是带时间戳的 run-id
```

- Layer 1（hunk_facts）FAIL：回到 Step 2 补充提取，重新走 plan → validate → execute 循环
- Layer 4（Native 代码扫描）FAIL：Native 代码中关键词未落地，视同 verify FAIL，必须修复后重新 verify
- Layer 2/3 FAIL：chain_map 或 edit_tasks 覆盖不足，在 `verify_report.md` 附录中标注 WARN，列入 finalize_report 遗留风险
- 基准测试结果追加到 `verify_report.md` 附录；**Layer 4 FAIL 导致 verify_result 降级为 FAIL**

## 脚本异常处理

`atlas_verify.py verify` 可能因运行时错误退出（非 verify FAIL，而是 Python 异常）。常见场景：

| exit code | 含义 | 处理 |
|-----------|------|------|
| 0 | 成功 | 读取 `verify_result.json` 判断 PASS/WARN/FAIL |
| 1 | 运行时异常 | 读 stderr，通常是 run 目录中缺少必要产物文件（如 `edit_tasks.json` 不存在） |
| 3 | 文件未找到 | 检查 `--run-dir` 路径和 `--repo-root` 是否正确 |

**排查步骤**：
1. 读 stderr traceback，定位缺失的文件或字段
2. 若缺少产物文件 → 确认前序步骤已正确执行（如 `edit_tasks.json` 由 Step 3 生成）
3. 若 `--swift-parse-check` / `--kotlin-parse-check` 报错 → 确认编译工具链可用（Xcode / Gradle）

> 脚本异常时修复输入后重跑即可，不需要回退到 Step 6。已有的代码改动不受影响。

产物：`<platform>/verify_report.md`、`<platform>/verify_result.json`
