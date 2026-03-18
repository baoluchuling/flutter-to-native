# Flutter Profiler Schema

## 目的

本文档定义 `Flutter Profiler` 的核心输出 schema，作为后续脚本实现和 `Atlas Planner` 集成的契约。

`Flutter Profiler` 分为两层输出：

- 仓库级画像：缓存到 `.ai/t2n/flutter-profile/`
- 需求级 digest：写入 `.ai/t2n/runs/<run-id>/`

## 一、仓库级输出

### 1. `scan_meta.json`

建议字段：

```json
{
  "profile_version": "v1",
  "generated_at": "2026-03-15T20:00:00Z",
  "repo_root": "/path/to/flutter-repo",
  "git_head": "abcdef123456",
  "baseline_ref": "optional",
  "scan_scope": "full",
  "inputs": {
    "root_filters": [],
    "force": false
  }
}
```

### 2. `route_map.json`

建议字段：

```json
{
  "primary_routing_style": "go_router",
  "route_definitions": [
    {
      "route": "/reader/short",
      "screen": "ShortBookUnlockView",
      "path": "lib/ui/screens/reader/components/chapter/short/short_book_unlock_view.dart",
      "feature": "short_reader",
      "confidence": 0.86
    }
  ],
  "entry_points": [],
  "risky_routing_files": []
}
```

### 3. `feature_index.json`

建议字段：

```json
{
  "features": [
    {
      "name": "short_reader",
      "paths": [
        "lib/ui/screens/reader/components/chapter/short"
      ],
      "screens": [
        "ShortBookUnlockView",
        "ShortUnlockView"
      ],
      "state_holders": [],
      "services": [],
      "models": [],
      "resources": [],
      "tests": [],
      "confidence": 0.82
    }
  ]
}
```

### 4. `state_patterns.json`

建议字段：

```json
{
  "patterns": [
    {
      "kind": "bloc",
      "name": "ShortReaderCubit",
      "path": "lib/features/reader/short_reader_cubit.dart",
      "feature": "short_reader",
      "confidence": 0.78
    }
  ]
}
```

### 5. `data_flow_index.json`

建议字段：

```json
{
  "apis": [],
  "repositories": [],
  "services": [],
  "models": []
}
```

每个条目建议至少包含：

- `name`
- `path`
- `feature`
- `kind`
- `confidence`

### 6. `resource_index.json`

建议字段：

```json
{
  "assets": [
    {
      "path": "assets/short_reader_membership_card_mask.png",
      "feature": "short_reader",
      "confidence": 0.9
    }
  ],
  "l10n_files": [
    {
      "path": "lib/services/language/l10n/app_en.arb",
      "kind": "arb"
    }
  ],
  "fonts": []
}
```

### 7. `test_index.json`

建议字段：

```json
{
  "widget_tests": [],
  "integration_tests": [],
  "behavior_tags": [
    {
      "name": "membership_unlock",
      "paths": [],
      "confidence": 0.6
    }
  ]
}
```

### 8. `repo_summary.md`

人类可读摘要，至少覆盖：

- 主要业务区
- 路由模式
- 状态管理模式
- 数据层模式
- 资源与测试分布
- 高风险或高噪音区域

## 二、需求级输出

### 1. `flutter-feature-digest.json`

这是 `Atlas Planner` 的首选输入。

建议字段：

```json
{
  "requirement": {
    "id": "REQ-123",
    "name": "membership_unlock_v2_short_reader"
  },
  "source": {
    "flutter_root": "/path/to/flutter-repo",
    "feature_paths": [],
    "change_range": "base..head",
    "pr_diff_path": "/tmp/feature.diff",
    "prd_path": null,
    "tests_paths": []
  },
  "scope": {
    "features": [],
    "primary_features": [],
    "supporting_features": [],
    "confidence": "high",
    "reasons": []
  },
  "representative_screens": [
    {
      "name": "ShortBookUnlockView",
      "path": "lib/.../short_book_unlock_view.dart",
      "role": "primary_screen",
      "confidence": 0.88
    }
  ],
  "user_flows": [],
  "states": [],
  "interactions": [],
  "api_calls": [],
  "models": [],
  "strings": [],
  "assets": [],
  "tests": [],
  "noise_candidates": [],
  "conflicts": [],
  "evidence_files": []
}
```

字段约束：

- `primary_features` 表示本次需求的主范围，通常来自显式 `flutter_path`
- `supporting_features` 表示由 diff / 服务 / l10n / 辅助弹窗带进来的配套范围
- `representative_screens` 只放需求相关主页面，不放通用子组件全集
- `user_flows` 应表达业务动作，不是所有 handler 名
- `states` 只保留需求有意义的状态，不直接等于所有实现函数名
- `noise_candidates` 保留可疑项，不静默丢弃
- `conflicts` 用来承接 PRD / diff / 测试 / 源码之间的冲突

### 2. `flutter-feature-digest.md`

建议章节：

1. 需求范围
2. 代表页面
3. 关键流程
4. 状态与交互
5. API / model
6. 文案 / 资源
7. 测试证据
8. 噪音候选
9. 冲突与降级说明

## 三、Planner 接入字段映射

`Atlas Planner` 在集成 `Flutter Profiler` 后，建议映射关系如下：

- `digest.representative_screens` -> contract 的 `flutter_evidence.screens`
- `digest.user_flows` -> contract 的 `behavior.user_flows`
- `digest.states` -> contract 的 `behavior.states`
- `digest.interactions` -> contract 的 `behavior.interactions`
- `digest.api_calls` -> contract 的 `flutter_evidence.api_calls`
- `digest.models` -> contract 的 `flutter_evidence.models`
- `digest.strings` -> contract 的 `behavior.strings`
- `digest.assets` -> contract 的 `behavior.assets`
- `digest.tests` -> contract 的 `flutter_evidence.tests`
- `digest.conflicts` -> `risk_report.md`
- `digest.noise_candidates` -> planner 的人工审查信息

## 四、降级规则

### digest 缺失

- planner 回退到旧的直接源码提取
- 业务范围置信度不得高于 `medium`

### digest 与源码冲突

- 不静默覆盖
- 冲突写入 `risk_report.md`
- 对应行为或范围结论至少降一级

### digest 噪音过高

- 进入 `noise_candidates`
- 不直接写入主结论

## 五、V1 实现优先级

先实现：

- `scan_meta.json`
- `feature_index.json`
- `resource_index.json`
- `test_index.json`
- `flutter-feature-digest.json`
- `flutter-feature-digest.md`

后补：

- 更深的数据流索引
- 路由与状态管理的 AST 级提取
