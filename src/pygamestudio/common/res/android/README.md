# Android 运行时产物（打包 APK 用）

这个目录放**冻结的 Android 运行时**——一份压缩包 + `VERSION.json`，由
`tools/android_spike/freeze_runtime.py` 从 CI 产出的 p4a `dist/` 生成：

```
pygs-android-runtime-1.0.0-arm64-v8a.zip   ~21 MB（LZMA）
VERSION.json                               版本 / 路径 / 包清单 / sha256
```

打包安卓时，编辑器只需要三样外部东西：**JDK、Android SDK、这个压缩包**。
不需要 NDK，也不需要联网（p4a 的 Gradle 工程只把预编译好的 `libs/<abi>/*.so`
装进 APK，`build.gradle` 里没有 `externalNativeBuild`）。

## 压缩包里有什么

| 内容 | 说明 |
|---|---|
| `_python_bundle__arm64-v8a/_python_bundle/` | `stdlib.zip` + `modules/`（C 扩展）+ `site-packages/`（pygame-ce / pymunk / cffi / setuptools） |
| `libs/arm64-v8a/*.so` | libpython、libpybundle（Python 载荷）、SDL2 全家桶、freetype、openssl、sqlite… |
| `src/main/java/` | p4a 的 Java 引导层 |
| `src/res_initial/` | 干净的资源目录（每次打包从这里恢复再注入图标/首屏） |
| `templates/` + `build.gradle` + `gradlew` | Gradle 工程骨架 |

不含 `build/`、`obj/`、`jni/`、`.gradle/`（构建垃圾，其中 `jni/` 是 573 MB 的 SDL 源码），
也不含任何工程的 `assets/private.tar`——那份由编辑器按用户工程生成。

## 打包时怎么用

1. 解压到缓存目录（例如 `%LOCALAPPDATA%\PygameStudio\android-runtime-<version>\`）；
2. 建 `assets/private.tar`（工程 + 引擎子集，`.py` 不编译）；
3. 往 `src/main/res` 注入图标 / 首屏 / 应用名，并同步写 `src/res_initial`（p4a 每次打包都会从它恢复）；
4. 拷 `gradlew` + SDK 路径跑 `assembleDebug` / `assembleRelease`。

## 什么时候需要换这个包

见 `tools/android_spike/README.md` 的「运行时产物冻结」一节：
只要**引擎运行时代码**、**pygame-ce / pymunk 版本**、**p4a 或它的 Java 引导层**、
**Android 平台 / NDK** 里任何一项变了，就要重新生成。

## 注意

- 这个目录**不会**被打进网页包（`gui/build/web.py` 的 `_ENGINE_RES_SKIP` 排除了 `android`），
  也不会被打进 APK 自己的 payload（`engine_runtime.RUNTIME_SKIP_DIRS` 同样排除）。
- 桌面版只收集 `common/res/images`、`common/i18n/languages`、`common/res/sdk`，不受影响。
