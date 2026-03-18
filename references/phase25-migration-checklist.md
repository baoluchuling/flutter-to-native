# Phase 25 Migration Checklist

## 目标

把 `T2N Atlas` 执行链路从“旧 contract/patch_plan 主驱动”收口到“`native_operation_plan + requirement_sync_contract` 主驱动”，并清理历史兼容分支。

## A. 脚本主驱动切换计划

### A1 `atlas_planner.py`

- 保留当前输出：`feature_intent_spec.yaml`、`native_operation_plan.yaml`、`requirement_sync_contract.yaml`
- 新增约束：`patch_plan` 必须由 `native_operation_plan.operations` 派生，不允许独立分叉

### A2 `atlas_apply.py`

- 输入门禁：
  - 必须存在 `native_operation_plan.yaml`
  - 必须存在 `requirement_sync_contract.yaml`
- 执行驱动：
  - `create/update/manual` 以 `native_operation_plan.operations` 为主
  - `requirement_sync_contract.patch_plan` 仅做一致性校验
- 一致性规则：
  - `operation.action` 与 `patch_plan` 不一致时立即中止并要求回到 planner

### A3 `atlas_verify.py`

- 验证对象：
  - 以 `native_operation_plan.operations` 生成计划文件清单与动作期望
  - 以 `apply_result.touched_files` 验证实际落地
- 合规结论：
  - 结构、生成模式、语义覆盖均按 operation 维度统计
  - `patch_plan` 仅保留 cross-check 角色

## B. 旧流程分支删除顺序

### B1 第一批（先删）

- `legacy marker` 检测与兼容判定
- `marker_block` 生成与对应 verify 放宽逻辑

### B2 第二批（随后删）

- 仅依赖 `patch_plan` 的 apply/verify 主循环
- 未引用 `native_operation_plan` 的旧状态输出字段

### B3 第三批（最后删）

- 只服务于旧 run 目录的回退分支
- 与新 schema 冲突的字段兼容代码

## C. 阶段 25 验收标准

- `plan` 产物齐全：
  - `feature_intent_spec.yaml`
  - `native_operation_plan.yaml`
  - `requirement_sync_contract.yaml`
- `apply` 启动前强校验 `native_operation_plan.yaml` 存在
- `verify` 结果中可按 operation 维度看到覆盖情况
- 旧 `legacy marker / marker_block` 路径不再出现在主执行链路

## D. 回归用例清单

### D1 正常链路

- 输入完整（PRD + diff + tests + profile）
- `plan -> confirm -> apply -> verify` 全链路通过

### D2 缺文件门禁

- 缺少 `native_operation_plan.yaml` 时，`apply` 必须失败并给出明确报错

### D3 一致性门禁

- 人为篡改 `patch_plan` 与 `operations` 使之冲突，`apply` 必须中止

### D4 风险门禁

- `action=manual_review` 项目不能被自动写入源码

### D5 语义与结构验证

- `verify` 对每个 operation 输出结构与语义状态，且能区分 `verified/partial/missing`
