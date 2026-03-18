# 真实项目接入 Checklist

## 目的

本文档用于在把 `T2N Atlas` 接入真实 iOS 项目前，快速检查前置条件是否具备。

## 一、原生仓库

- [ ] 目标仓库是 `iOS + Swift + UIKit`
- [ ] 仓库本地可读写
- [ ] 允许在仓库下创建 `.ai/t2n/`
- [ ] 关键业务代码不在 `Pods/`、构建产物或只读目录中
- [ ] 团队接受 `plan -> confirm -> apply -> verify` 流程

## 二、Flutter 输入

- [ ] 至少能提供 `Flutter 功能目录 / PR diff / 测试` 之一
- [ ] 最好能提供 PRD
- [ ] Flutter 代码能定位到主要页面、状态、接口或模型
- [ ] 如果是 smoke fixture，团队知道它不等于最终 pilot

## 三、原生扫描

- [ ] 已完成一次 profiler 扫描
- [ ] `.ai/t2n/native-profile/` 产物齐全
- [ ] 当前 profile 没有明显过期
- [ ] 关键导航入口和高风险文件已被 profiler 识别

## 四、计划阶段

- [ ] 已生成 `requirement_sync_contract.yaml`
- [ ] 已生成 `sync_plan.md`
- [ ] 已生成 `touchpoints.md`
- [ ] 已生成 `risk_report.md`
- [ ] 计划中所有会被修改的现有文件都已经显式列出
- [ ] 高风险全局文件没有被静默塞进自动 patch

## 五、执行阶段

- [ ] 已完成人工确认
- [ ] 当前 run 目录独立，不会覆盖其他任务产物
- [ ] 如果是第一次验证，优先在临时副本仓库执行 apply

## 六、验证阶段

- [ ] 已生成 `apply_report.md`
- [ ] 已生成 `verify_report.md`
- [ ] 如果需要更强验证，已启用 `--swift-parse-check`
- [ ] `partial / missing / unknown` 的原因已可读

## 七、当前已知阻塞

这些项缺失时，不建议把它当作真实 pilot 完成：

- [ ] 没有真实业务 PRD 或真实 Flutter 功能输入
- [ ] 没有真实业务 owner 对 plan 做审阅
- [ ] 没有真实仓库上的误判复盘

## 八、V1 建议

1. 先用临时副本做 apply / verify
2. 第一轮真实接入先选独立功能，不选全局改动重的需求
3. 遇到 `manual_candidates` 时，优先保持人工处理，不要急着放开自动 patch
