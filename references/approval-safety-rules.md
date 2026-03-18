# 从确认到执行的安全规则

## 目的

本文档定义 `T2N Atlas` 在 `plan -> confirm -> apply` 之间必须遵守的安全规则。

目标：

- 防止在未确认计划前直接改代码
- 防止 apply 阶段越过已批准范围
- 为中止、回退和人工介入提供明确规则

## 基本原则

1. 没有确认，不进入 apply
2. 没有批准的触点，不允许写入对应文件
3. 发现超范围需求时，中止执行，不在 apply 阶段临时扩范围
4. 所有计划外偏差都必须显式记录

## 一、确认前规则

在用户确认前，只允许：

- 生成 `requirement_sync_contract.yaml`
- 生成 `sync_plan.md`
- 生成 `touchpoints.md`
- 生成 `risk_report.md`
- 读取原生代码和 Flutter 代码用于分析

在用户确认前，不允许：

- 修改原生源码
- 新建计划外原生文件
- 删除原生文件
- 修改历史 run 产物

## 二、确认动作定义

V1 中，“确认”至少意味着：

- 当前 `sync_plan.md` 被接受
- 当前 `touchpoints.md` 被接受
- 当前 `risk_report.md` 中的风险被知悉

只有在这三个前提成立后，apply 才能启动。

## 三、执行前校验

进入 apply 前必须通过以下校验：

- 当前 run 目录下存在 contract、plan、touchpoints、risk report
- 目标仓库路径正确
- 计划中的关键触点文件路径可定位
- 用户确认对应的是当前版本的计划产物，而不是旧版本

如果校验失败：

- 不进入 apply
- 记录原因

## 四、允许执行的范围

apply 允许执行的范围仅限于：

- `patch_plan.create`
- `patch_plan.update`
- 已明确批准自动处理的特殊项

默认不自动执行的范围：

- `manual_candidates`
- 高风险全局文件
- 计划外新增触点

## 五、必须中止的情况

以下情况必须中止 apply：

- 需要修改的文件不在已批准触点范围内
- 需要扩大 patch 范围才能完成功能
- 关键文件结构与计划假设严重不符
- 关键风险在计划中未暴露
- 发现原生仓库已发生重大变化，导致原计划失效

中止后必须：

- 停止写入更多代码
- 记录中止点
- 在 `apply_report.md` 中写明原因
- 视情况回到 planner 阶段

## 六、人工候选项规则

对 `manual_candidates`：

- 默认不自动执行
- 如果用户明确批准自动处理，才允许纳入 apply
- 即便被批准，也必须在 `apply_report.md` 中单独标记

## 七、计划与实际不一致时的处理

如果执行时发现计划与实际情况不一致：

- 小偏差：可继续执行，但必须记录
- 大偏差：必须中止并回到 planner

大偏差示例：

- 文件职责与计划判断完全不同
- 需要触碰新的全局文件
- 已批准 patch 不足以实现功能主路径

## 八、版本一致性规则

Apply 应只基于同一 run 目录下的产物执行。

不允许：

- 用 A run 的 contract 搭配 B run 的 sync plan
- 用旧版 touchpoints 驱动新版 apply

## 九、验证前置规则

只有在 apply 完成或中止后，verify 才能启动。

verify 必须基于：

- 当前 run 的 contract
- 当前 run 的 apply_report
- apply 之后的代码状态

## 十、V1 原则

- 先可控，再自动化
- 先暴露风险，再执行
- 先中止错误执行，再追求“尽量做完”
