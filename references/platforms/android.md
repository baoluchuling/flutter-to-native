# Android Platform Profile

## 标识

- platform: `android`
- language: Kotlin
- repo_root_param: `--repo-root <android-project-root>`

## 架构映射词汇

| 角色 | Android 术语 |
|------|-------------|
| 编排入口 | Activity / Fragment / ViewModel |
| 视图层 | Compose Composable / XML Layout + ViewBinding |
| 回调机制 | LiveData / StateFlow / Callback / EventBus |
| 状态管理 | ViewModel + StateFlow / MutableState / SavedStateHandle |
| 依赖注入 | Hilt / Dagger / Koin |
| 路由 | Navigation Component / Intent / FragmentTransaction |

## 编译验证命令

```bash
./gradlew assembleDebug
```

## 版本兼容规则

生成的代码必须兼容 `session_config.json → platform_constraints.android.min_sdk` 声明的最低 API level。常见陷阱：

| API / 语法 | 最低 API | 低版本替代 |
|------------|---------|-----------|
| `WindowInsetsController` | API 30 | `WindowInsetsControllerCompat` |
| `BlendMode` (Canvas) | API 29 | `PorterDuff.Mode` |
| `Build.VERSION_CODES.S` 特性 | API 31 | 条件判断 + 兼容方案 |
| `SplashScreen` API | API 31 | `androidx.core.splashscreen` |
| `PhotoPicker` | API 33 | `ActivityResultContracts.GetContent` |
| `PredictiveBackHandler` | API 34 | 常规 `OnBackPressedCallback` |

高版本 API 必须用 `if (Build.VERSION.SDK_INT >= XX)` 保护，优先使用 AndroidX compat 库。

## 代码规范锚点

参照目标仓库 CLAUDE.md（典型项：Compose 规范、Coroutine 用法、Hilt Module 组织）

## code_review 重点

- Kotlin 代码规范（参照项目 CLAUDE.md）
- 协程安全：viewModelScope / lifecycleScope 正确使用，避免泄漏
- Compose recomposition 性能（避免不必要重组）
- Fragment 生命周期 vs ViewLifecycleOwner

## verify 扫描参数

```bash
--kotlin-parse-check
```

## 示例路径格式

```
app/src/main/java/com/example/feature/FeatureViewModel.kt
```

## understand 查询示例

```
在 ShortFragment 中，用户点击解锁按钮时，现有调用链是怎样的，ViewModel 的 purchaseFlow 如何触发 UI 更新？
```
