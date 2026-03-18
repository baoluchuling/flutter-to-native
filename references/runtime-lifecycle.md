# `.ai/t2n/` 产物生命周期

## 目的

本文档定义 `T2N Atlas` 在真实项目中的运行产物应该如何复用、保留和清理。

目标：

- 让 `native-profile` 可以稳定复用
- 让 `runs/` 目录可审计、可回滚、可清理
- 避免一次同步任务污染其他任务

## 标准目录

```text
.ai/t2n/
  native-profile/
  runs/
    <run-id>/
```

## 一、`native-profile/`

用途：

- 缓存原生仓库画像
- 供 planner 重复使用

建议保留周期：

- 默认长期保留
- 只有这些情况建议刷新：
  - 原生仓库发生明显结构变化
  - `scan_meta.json` 标记已过期
  - 用户显式要求重新扫描

不建议做法：

- 每次同步都强制重扫
- 手动修改 profile JSON 内容

## 二、`runs/<run-id>/`

用途：

- 承载一次完整同步任务的所有中间产物和结果

建议命名：

- `YYYY-MM-DD-requirement-name`
- 或 `YYYY-MM-DD-feature-name`

最小产物：

- `requirement_sync_contract.yaml`
- `sync_plan.md`
- `touchpoints.md`
- `risk_report.md`

执行后新增：

- `apply_result.json`
- `apply_report.md`
- `verify_result.json`
- `verify_report.md`

## 三、生命周期建议

### `plan only`

保留建议：

- 至少保留最近 10 到 20 次 run
- 未执行 apply 的 run 可以按时间批量清理

### `apply completed`

保留建议：

- 默认保留
- 至少保留与已合入代码对应的 run 记录

### `verify failed / partial`

保留建议：

- 必须保留，直到问题被修复或废弃
- 这是后续复盘误判和收紧规则的重要依据

## 四、清理策略

优先清理：

- 明显废弃的 `plan only` run
- 重复实验产生的临时 run
- 无对应需求编号、无计划价值的 smoke run

不要清理：

- 当前仍在排查的失败 run
- 唯一一次真实业务 pilot 的完整 run
- 仍需审计的 apply / verify 产物

## 五、推荐做法

1. 原生画像单独复用，run 单独归档
2. 每次同步一个独立 `run-id`
3. 对真实项目，保留至少最近一次成功 run 和最近一次失败 run
4. 当 run 只用于 smoke test，建议在名称里显式带上 `smoke`

## 六、V1 原则

- `native-profile` 是缓存，不是事实源代码
- `runs/` 是审计记录，不是随意覆盖的临时目录
- 清理时优先删临时实验产物，最后才动真实业务 run
