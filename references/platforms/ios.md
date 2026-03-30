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

## 代码规范锚点

参照目标仓库 CLAUDE.md（典型项：懒加载、NoHighlightButton、颜色/字体扩展、SnapKit 约束）

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
