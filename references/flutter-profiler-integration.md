# Flutter Profiler Integration

## 目的

本文档定义 `Flutter Profiler` 与 `Atlas Planner` 的衔接方式。

目标是让 planner 把 profiler 当作 Flutter 侧主输入，而不是继续以“直接扫描源码和 diff”作为默认路径。

## 一、职责边界

### Flutter Profiler 负责

- 扫描 Flutter 仓库
- 维护仓库级画像
- 为单次需求生成 `flutter-feature-digest`
- 标出噪音候选和冲突项

### Atlas Planner 负责

- 读取 profiler 产物
- 与 native profile 结合，生成 `requirement_sync_contract`
- 选择原生触点
- 输出 `sync_plan.md`、`touchpoints.md`、`risk_report.md`

## 二、推荐执行流

### 1. 先做 Flutter Profiler

```text
flutter repo -> flutter-profile -> flutter-feature-digest
```

### 2. 再做 Atlas Planner

```text
flutter-feature-digest + native-profile + PRD -> requirement_sync_contract + sync_plan
```

### 3. 缺失时回退

只有以下情况才允许 planner 回退到直接源码提取：

- `flutter-feature-digest.json` 缺失
- digest 明显过期
- 用户显式要求跳过 profiler

## 三、输入优先级

planner 应使用以下优先级：

1. `flutter-feature-digest.json`
2. `.ai/t2n/flutter-profile/` 仓库级索引
3. PRD
4. Flutter 测试
5. Flutter PR diff
6. Flutter 源码回查

关键约束：

- PR diff 和源码回查用于补证据，不直接覆盖 digest 主结论
- 当低优先级输入与高优先级输入冲突时，优先保留 digest，并显式记录冲突

## 四、字段映射策略

### Digest -> Contract

- `representative_screens` -> `flutter_evidence.screens`
- `user_flows` -> `behavior.user_flows`
- `states` -> `behavior.states`
- `interactions` -> `behavior.interactions`
- `api_calls` -> `flutter_evidence.api_calls`
- `models` -> `flutter_evidence.models`
- `strings` -> `behavior.strings`
- `assets` -> `behavior.assets`
- `tests` -> `flutter_evidence.tests`

### Digest -> 风险与人工项

- `noise_candidates` -> `risk_report.md` 的“证据噪音”章节
- `conflicts` -> `risk_report.md` 的“输入冲突”章节

## 五、冲突检测规则

### 规则 1：digest 与 PRD 冲突

例子：

- PRD 说是“会员解锁”
- digest 主页面却只落到无关页面

处理：

- scope confidence 至少降一级
- 写入 `risk_report.md`
- 保留人工确认提示

### 规则 2：digest 与 PR diff 冲突

例子：

- digest 说关键页面是 A
- diff 主修改文件却集中在 B / C

处理：

- 不自动覆盖 digest
- 把 B / C 作为 `noise_candidates` 或 `conflicts`
- 需要时升级为人工审查

### 规则 3：digest 与测试冲突

例子：

- digest 没提到某关键交互
- 测试却覆盖了该交互

处理：

- 该交互进入 `conflicts`
- Planner 不得把对应行为标为 `high confidence`

### 规则 4：digest 噪音过多

例子：

- 代表页面大多是通用子组件
- 字符串大多是样式值或模板表达式

处理：

- Flutter 行为提炼置信度不得为 `high`
- planner 必须提示“digest 质量不足”

## 六、回退策略

### 仅有仓库级画像，无需求级 digest

- 可用仓库级画像辅助 planner
- 但 planner 只能给出 `medium` 及以下的 Flutter 语义置信度

### 只有源码和 diff

- 允许继续生成计划
- 但必须在 `risk_report.md` 中明确标注：
  - 未使用 profiler digest
  - 本次计划更容易受源码噪音影响

## 七、V1 最小集成要求

- planner 能探测 `flutter-feature-digest.json`
- 若存在，优先用 digest 生成 `behavior` 和 `flutter_evidence`
- 若不存在，回退旧逻辑
- 冲突和噪音可进入 `risk_report.md`

## 八、真实 pilot 验证目标

以 `anystories-client-flutter` 的真实 pilot 为基准，验证以下两点：

1. 代表页面不再优先落到 `ScrollChildView / ScrollModeView` 这类通用子组件
2. 字符串和状态不再主要由模板表达式、样式词和实现细节主导
