# Flutter Profiler Spec

## 目的

`Flutter Profiler` 是 `T2N Atlas` 在 Flutter 侧的前置分析组件。

它的职责不是直接生成原生代码，而是先把 Flutter 仓库扫描成稳定、可复用、可审查的结构化画像，再为单次需求同步生成更聚焦的 `feature digest`。

这样 `Atlas Planner` 就不再直接从原始 Dart 源码、PR diff 和字符串字面量里硬抓语义，而是优先消费 profiler 产物。

## 设计目标

- 降低原始 Flutter 代码带来的噪音
- 把“需求相关语义”和“实现细节噪音”尽量提前分离
- 为 planner 提供稳定的页面、流程、状态、接口、资源和测试证据
- 保留对原始源码和 diff 的回查能力，但不以它们作为第一输入

## 非目标

- 不做 Dart 到 Swift 的逐行翻译
- 不做完整业务逻辑理解或运行时模拟
- 不要求在 V1 里构建完整 AST 级语义分析器
- 不直接修改 Flutter 代码

## 输入

### 仓库级输入

- Flutter 仓库根目录
- 可选的扫描范围
- 可选的基线 commit
- 可选的已有缓存目录

### 需求级输入

- 需求 ID / 名称
- Flutter feature 路径或候选路径
- commit range 或 PR diff
- 可选 PRD
- 可选 Flutter 测试路径

## 输出层次

`Flutter Profiler` 建议输出两层内容。

### 一、仓库级画像

写入：

- `.ai/t2n/flutter-profile/`

用途：

- 复用 Flutter 仓库结构、路由、状态管理、接口和测试模式
- 避免每次需求同步都全仓重扫

### 二、需求级 Digest

写入：

- `.ai/t2n/runs/<run-id>/flutter-feature-digest.json`
- `.ai/t2n/runs/<run-id>/flutter-feature-digest.md`

用途：

- 给单次 `plan` 提供高质量、低噪音的需求侧语义输入
- 作为 `Atlas Planner` 的默认主输入

## 仓库级画像应回答的问题

1. Flutter 仓库主要有哪些业务区和共享区？
2. 路由和页面是如何组织的？
3. 状态管理主要采用哪些模式？
4. API / repository / service / model 如何分布？
5. 多语言、资源、测试的组织方式是什么？
6. 哪些目录或模式最适合做“需求级 digest”的范围切片？

## 需求级 Digest 应回答的问题

1. 这次需求真正影响了哪些页面和交互流？
2. 哪些状态是需求核心状态，哪些只是实现细节？
3. 哪些 API / model / 文案 / 资源属于本需求？
4. 哪些代码只是通用组件或实现噪音，不应直接进入 planner 主结论？
5. 当前需求与仓库已有共享模式之间是什么关系？

## 核心流程

### 1. Flutter 仓库扫描

扫描并索引：

- 页面与路由
- 状态管理实体
- repository / service / api / model
- assets 与 l10n
- 测试目录与关键测试入口

### 2. 结构归类

把文件归入以下逻辑类别：

- feature pages
- feature components
- state holders
- repositories / services
- models / dto
- resources / assets / l10n
- tests

### 3. 需求范围切片

基于以下证据收敛本次需求范围：

- 指定 Flutter 路径
- commit range / PR diff
- 测试
- PRD

### 4. 生成 Digest

输出需求级结论：

- 代表页面
- 关键流程
- 状态机
- API / model
- 文案 / 资源
- 测试断言
- 噪音候选和冲突项

### 5. 供 Planner 消费

Planner 默认顺序应为：

1. `flutter-feature-digest`
2. `flutter-profile`
3. 原始 Flutter 源码
4. PR diff
5. PRD / 测试回查

## 输出文件

### 仓库级

#### `repo_summary.md`

- Flutter 仓库整体结构摘要
- 主要业务区和共享区
- 关键实现模式

#### `route_map.json`

- 路由名
- 页面名
- 所在路径
- 相关 feature

#### `feature_index.json`

- 逻辑 feature 名
- 关联页面
- 关联组件
- 关联状态管理
- 关联数据层

#### `state_patterns.json`

- Bloc / Cubit / Provider / Riverpod / ViewModel 等模式
- 对应文件路径
- 所属 feature

#### `data_flow_index.json`

- repository / service / api / datasource / model 的索引

#### `resource_index.json`

- assets
- l10n / arb
- 字体、主题资源

#### `test_index.json`

- widget tests
- integration tests
- 关键行为断言入口

### 需求级

#### `flutter-feature-digest.json`

建议至少包含：

```json
{
  "requirement": {
    "id": "REQ-123",
    "name": "membership_unlock_v2_short_reader"
  },
  "scope": {
    "source_paths": [],
    "change_range": "",
    "confidence": "high"
  },
  "representative_screens": [],
  "user_flows": [],
  "states": [],
  "interactions": [],
  "api_calls": [],
  "models": [],
  "strings": [],
  "assets": [],
  "tests": [],
  "noise_candidates": [],
  "conflicts": []
}
```

#### `flutter-feature-digest.md`

面向人的摘要，至少说明：

- 本次需求范围
- 代表页面
- 核心流程
- 关键状态
- 数据依赖
- 测试证据
- 噪音候选

## 噪音处理原则

`Flutter Profiler` 不应靠堆大量专项关键词过滤来“假装理解需求”。

更通用的做法是：

- 先做仓库结构归类
- 再做需求范围切片
- 再输出“代表页面 / 关键流程 / 噪音候选”

也就是说：

- 噪音不是直接删掉
- 而是降级为 `noise_candidates`
- 由 planner 在主结论外显式处理

## 与 Planner 的衔接

Planner 集成后应满足：

- 优先读取 `flutter-feature-digest.json`
- 当 digest 缺失时，才退回旧的直接源码提取
- 当 digest 与源码 / diff 明显冲突时，降低置信度并写入 `risk_report.md`

## V1 范围

先做：

- Flutter 仓库扫描
- 需求级 digest 生成
- 与 planner 的单向对接

暂不做：

- 完整 AST 级数据流分析
- 跨 feature 自动因果推理
- 自动修复 Flutter 结构问题
