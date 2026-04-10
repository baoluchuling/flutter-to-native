# iOS Platform Profile

## 标识

- platform: `ios`
- language: Swift
- repo_root_param: `--repo-root <ios-project-root>`

## 架构映射词汇

| 角色 | iOS 术语 |
|------|---------|
| 编排入口 | UIViewController / Coordinator / Manager |
| 视图层 | UIView / UIViewController / SwiftUI View |
| 回调机制 | delegate / closure / NotificationCenter / Combine |
| 状态管理 | 属性 + KVO / Combine / @Observable |
| 依赖注入 | 手动注入 / Swinject |
| 路由 | Coordinator / Router / NavigationController push/present |

## 编译验证命令

```bash
xcodebuild build -scheme <scheme> -destination 'generic/platform=iOS'
```

## 版本兼容规则

生成的代码必须兼容 `session_config.json → platform_constraints.ios.deployment_target` 声明的最低版本。常见陷阱：

| API / 语法 | 最低版本 | 低版本替代 |
|------------|---------|-----------|
| `async/await` | iOS 13（需 back-deploy）/ iOS 15（原生） | completion handler / Combine |
| `UISheetPresentationController` | iOS 15 | 自定义 `UIPresentationController` |
| `UIMenu` / `UIAction` | iOS 14 | `UIAlertController` actionSheet |
| `AttributedString`（Swift 原生） | iOS 15 | `NSAttributedString` |
| `UIContentUnavailableConfiguration` | iOS 17 | 自定义空态视图 |
| `\.sensoryFeedback` (SwiftUI) | iOS 17 | `UIImpactFeedbackGenerator` |
| `@Observable` macro | iOS 17 | `ObservableObject` + `@Published` |

高版本 API 必须用 `if #available(iOS XX, *)` 保护且提供 fallback。

## 代码规范锚点

参照目标仓库 CLAUDE.md（典型项：懒加载、NoHighlightButton、颜色/字体扩展、SnapKit 约束）。

**subagent 传递要求**：Step 6 派发 iOS subagent 时，prompt 中必须包含目标仓库 CLAUDE.md 中的代码规范摘要（至少：懒加载模式、NoHighlightButton 要求、`UIColor(hex:, alpha:)` 颜色用法、`UIFont+Extension` 字体用法、SnapKit 约束写法、`NavigationView` 导航栏用法）。不得依赖 subagent 自行发现 CLAUDE.md——subagent 的工作目录可能不含 CLAUDE.md，或 CLAUDE.md 不在 subagent 的搜索范围内。

## code_review 重点

- Swift 代码规范（参照项目 CLAUDE.md）
- 线程安全：网络回调/Timer 回调是否在主线程操作 UI 或共享状态
- SnapKit 约束正确性
- delegate / closure 循环引用

## verify 扫描参数

```bash
--swift-parse-check
```

## 示例路径格式

```
novelspa/Path/To/File.swift
```

## understand 查询示例

```
在 ShortViewController 中，用户点击解锁按钮时，现有调用链是怎样的，ShortPurchaseSimpleView_v2 的 delegate 回调到哪里？
```
