# Atlas Planner 实现设计

## 目的

本文档把 `Atlas Planner` 从高层规格推进到可实现层。

使用时机：

- 开始实现 planner 脚本前
- 需要明确 planner 内部阶段、输入归一化、产物生成顺序时
- 需要保证 planner 和 `Atlas Profiler`、后续 `Atlas Apply` 对接一致时

## 实现目标

`Atlas Planner` 的职责不是改代码，而是：

- 聚合需求证据
- 推断业务范围
- 提炼 Flutter 行为
- 结合 `native-profile-v2`（repo-profile-core 产物）识别原生触点
- 生成 `requirement_sync_contract.yaml`
- 生成可供确认的 `sync_plan.md`、`touchpoints.md`、`risk_report.md`

Planner 必须在输出这些产物后停止，等待用户确认。

## 推荐脚本形式

V1 先采用单入口脚本：

- `scripts/atlas_planner.py`

后续如果复杂度提升，再拆为多个模块。

## 推荐命令行

推荐主命令：

```bash
python3 scripts/atlas_planner.py plan \
  --repo-root /path/to/native-ios \
  --profile-v2-dir /path/to/native-ios/.ai/t2n/native-profile-v2 \
  --run-dir /path/to/native-ios/.ai/t2n/runs/2026-03-15-requirement-foo
```

推荐子命令：

- `plan`
- `status`

### `plan`

用途：

- 聚合证据并生成本次同步计划产物

建议参数：

- `--repo-root`
- `--profile-v2-dir`
- `--run-dir`
- `--prd-path`
- `--flutter-root`
- `--flutter-path`
- `--pr-diff-path`
- `--tests-path`
- `--requirement-id`
- `--requirement-name`
- `--force`

V1 允许部分参数缺省，但必须至少保证：

- 有 native repo
- 有 native-profile-v2
- 至少有一类 Flutter 侧证据

### `status`

用途：

- 查看某个 `run-dir` 下是否已经存在 contract 和计划产物

建议输出：

- run 目录是否存在
- 已生成哪些产物
- 是否缺失关键文件

## 执行流

### 阶段 0：预检查

任务：

- 校验 `repo-root`
- 校验 `profile-v2-dir`
- 校验 `run-dir`
- 校验输入参数至少满足最小要求
- 创建运行上下文

最小要求：

- native-profile-v2 存在
- `repo-root` 可读
- 存在 PRD、Flutter 代码、PR diff、测试中的至少一项

输出：

- 内存中的 `planning_context`

### 阶段 1：证据聚合

任务：

- 读取 PRD 或需求描述
- 读取 Flutter 代码范围
- 读取 Flutter PR diff
- 读取 Flutter 测试
- 读取 native-profile-v2

目标：

- 把不同来源的证据统一整理成可消费的数据结构
- 对明显是仓库初始化模板或通用脚手架的 PRD 噪声做过滤，避免把无关 README 内容误识别为业务验收点

建议内部结构：

```yaml
planning_context:
  requirement_input:
  flutter_input:
  flutter_diff_input:
  flutter_test_input:
  native_profile_input:
```

### 阶段 2：需求范围推断

任务：

- 从混合证据中识别“这次到底要同步哪个业务功能”
- 汇总功能名称、功能描述、关键流程、验收点

输出：

- `requirement_scope`

建议字段：

- `id`
- `name`
- `summary`
- `user_flows`
- `acceptance_points`
- `confidence`
- `evidence_refs`

范围推断规则：

- 优先以 PRD 和验收点定义业务边界
- 如果 PRD 不完整，则用 Flutter 页面、状态流和测试补齐
- 不按文件夹切功能，按业务行为切范围
- 当 PRD 证据较弱时，可以从 `flutter-path`、关键文件名、diff 文件名中提取业务关键词，辅助收敛范围

### 阶段 3：Flutter 行为提炼

任务：

- 提炼页面和子视图结构
- 提炼交互动作
- 提炼 loading / success / error / retry 状态
- 提炼 API 和 model 依赖
- 提炼 strings / assets
- 标出可能不支持或高风险的行为

当前实现补充：

- 允许对 Flutter feature 目录做轻量文件级扫描
- 当前重点抽取 `.dart` 文件中的 `screens / state_holders / api_calls / models / states / interactions / strings / assets`
- 当前实现优先保证“可稳定提取”，不依赖 AST
- 当 PRD 与 Flutter 证据同时存在时，优先用 Flutter 抽取结果补强 `behavior` 与 `flutter_evidence`

输出：

- `flutter_behavior`

建议字段：

- `screens`
- `subviews`
- `interactions`
- `states`
- `api_calls`
- `models`
- `strings`
- `assets`
- `unsupported_candidates`

V1 原则：

- 输出语义，不输出逐行 widget 映射
- 要用原生友好的结构表达 Flutter 行为

### 阶段 4：原生触点选择

任务：

- 读取 `touchpoint_index.json`
- 读取 `module_map.json`
- 读取 `navigation_map.json`
- 按 `requirement_scope + flutter_behavior` 选择本次可能受影响的原生文件
- 必要时基于业务关键词对原生仓库做轻量级文件名扫描，补足 profile 中未覆盖到的 feature 触点

输出：

- `native_impact`

建议字段：

- `existing_files`
- `new_file_candidates`
- `registration_points`
- `risk_files`
- `selected_touchpoints`

选择规则：

- 高置信度、低风险触点优先
- 高风险的全局文件默认放入人工候选，除非证据非常强
- 每个触点都必须带原因
- 默认排除 `Pods/`、`DerivedData/` 等非业务源码目录
- 优先选择与需求关键词命中的控制器、Presenter、View、API、Model 文件

当前实现补充：

- 轻量级仓库扫描命中后，优先保留 `confidence >= 0.45` 的候选，避免用低质量 fallback 把无关旧文件塞进计划
- `AppDelegate`、`SceneDelegate`、`Router`、`Coordinator`、`TabBar` 等全局路径不会因为简单 fallback 自动进入 `update`
- profiler 给出的 `entry_points / routing_hotspots` 会单独整理为 `registration_points`
- 当 Flutter 有明确 screen 证据，但 planner 没找到稳定的 UIKit screen 触点时，会把注册点升级为 `manual_candidates`
- 当需求文本或 diff 中存在明确的 routing / registration 词级信号时，也会把对应全局触点升级为人工审查项
- 当 `Flutter Profiler` 提供 `representative_screens` 时，planner 会继续尝试把 UIKit 触点映射成 `primary_screen / auxiliary_dialog / auxiliary_overlay / component_view`
- `selected_touchpoints` 现在会额外携带 `ui_role` 和 `source_screens`，供后续 apply / verify 共享
- 当 Flutter 证据中存在 `api_calls` 时，planner 会额外尝试补入 `feature_logic / feature_service` 触点，避免计划长期只落在 UI 与 model
- `scope keywords` 现在拆成 `base / alias / context` 三层：alias 只在对应上下文下展开，避免把第二样例这类 `purchased_chapter_list` 错拉到 `PlayerBuy*`
- 原生触点扫描已从“整路径子串命中”改成“token 级命中”，避免 `short` 命中仓库名 `anyshort` 这类误判
- 在候选排序阶段，planner 会用首个高置信候选做 `anchor cluster` 重排，让同簇 `wallet/unlock/chapter` 或 `player/buy` 触点自然靠前
- 当前多样本结果表明：会员解锁样例仍稳定落在 `Player*` 簇，而章节列表样例已收敛到 `UnlockChapter*` 簇

### 阶段 5：Contract 组装

任务：

- 将 `requirement_scope`
- `flutter_behavior`
- `native_impact`
- 输入来源信息

组装为标准 `requirement_sync_contract`

输出：

- `requirement_sync_contract.yaml`

组装原则：

- contract 必须足够驱动后续 apply 阶段
- contract 中所有高风险点必须显式可见
- contract 中不能隐含关键假设

当前实现补充：

- `native_impact.selected_touchpoints` 现在会同时保留自动 patch 触点和升级后的人工候选触点
- `patch_plan.manual_candidates` 仍保持路径列表，详细原因通过 `risk_files` 和 `selected_touchpoints` 承接
- contract `notes` 中会回写 `scope confidence / native impact confidence / overall risk`

### 阶段 6：计划产物生成

任务：

- 生成 `sync_plan.md`
- 生成 `touchpoints.md`
- 生成 `risk_report.md`

输出顺序：

1. `requirement_sync_contract.yaml`
2. `sync_plan.md`
3. `touchpoints.md`
4. `risk_report.md`

原因：

- 先有机器可消费的 contract
- 再有给人确认的计划和附录

### 阶段 7：确认闸门

任务：

- 输出清晰提示：当前还没有改任何代码
- 标明下一步只有在用户确认后才能进入 apply

Planner 在这里结束。

## 建议内部数据结构

### `planning_context`

作用：

- 汇总所有原始输入和运行配置

### `requirement_scope`

作用：

- 表示业务范围层面的理解结果

### `flutter_behavior`

作用：

- 表示 Flutter 侧行为语义抽取结果

### `native_impact`

作用：

- 表示原生侧潜在触点和风险点

### `planner_result`

作用：

- 汇总最终要写出的 contract 和报告所需内容

## 输入优先级

当多个输入冲突时，建议按以下优先级处理：

1. 明确的 PRD 和验收标准
2. Flutter 测试
3. Flutter PR diff
4. Flutter 实现代码
5. 推断性结论

理由：

- 业务目标应该先于实现细节
- 测试通常比局部代码片段更接近“预期行为”

## 置信度模型

Planner 应对三个层面分别给出置信度：

- 业务范围置信度
- Flutter 行为提炼置信度
- 原生触点选择置信度

建议等级：

- `high`
- `medium`
- `low`

建议升级规则：

- 任一层为 `low`，必须在 `risk_report.md` 中单独指出
- 触碰全局路由、全局容器、全局主题等文件时，至少升为人工重点审查
- PRD 缺失且 Flutter 证据分散时，整体计划置信度不得标为 `high`

详细规则见 [planner-confidence-rules.md](planner-confidence-rules.md)。

## 写文件规则

Planner 只允许写入：

- `.ai/t2n/runs/<run-id>/`

不允许：

- 修改原生源码
- 覆盖 native profile
- 向运行目录之外写入计划产物

## 失败与降级策略

如果输入不足，Planner 不应直接崩掉。

降级策略：

- 如果缺 PRD，则基于 Flutter 代码、diff、测试推断
- 如果缺测试，则降低行为置信度
- 如果 native profile 不完整，则继续生成部分计划，但把触点结论降为低置信度
- 如果无法识别清晰业务范围，则仍写出计划，但显式标记“需人工确认范围”

## 建议内部模块

如果脚本后续拆分，建议模块如下：

- `inputs.py`
- `scope.py`
- `flutter_behavior.py`
- `native_impact.py`
- `contract.py`
- `reports.py`
- `writers.py`

V1 可以先单文件实现，再逐步拆分。

## V1 最小可用版本

第一版 Planner 不需要一次做满全部能力。

最小可用闭环：

- 读取 native profile
- 读取 PRD 或需求文本
- 读取一组 Flutter 代码路径
- 读取 PR diff 或测试中的任意一种
- 推断业务范围
- 生成 `requirement_sync_contract.yaml`
- 生成基础版 `sync_plan.md`
- 生成基础版 `touchpoints.md`
- 生成基础版 `risk_report.md`

做到这一步，就足够支撑后续固定模板和 apply 设计继续推进。
