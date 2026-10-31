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

## 打包时怎么用（已接进编辑器）

「Build 构建」窗口的第三个标签页 **安卓 APK** 会按顺序做：

1. 校验压缩包的 sha256，解压到用户缓存（`platformdirs.user_cache_dir()/PygameStudio/android/runtime-<version>-<abi>/`，
   只解压一次，包里记一个 `.archive.sha256` 标记）；
2. 读「编辑器设置 > 安卓打包」里的 JDK / SDK 路径（空着就自动探测），检查 JDK ≥ 17 和
   `platforms/android-34`（`build-tools` 缺失不阻塞：AGP 会自己装它要的那个版本）；
3. 用 `gui/build/protection.py` 保护工程（去注释 + 加密资源），
   再用 `gui/build/runtime_payload.py` 把引擎运行子集放进去；
4. 把包拷到缓存的 `dist/` 工作目录，**从包里的** `src/res_initial` 恢复 `src/main/res`
   （不能从工作目录恢复，否则上一个工程的图标会一直留着），
   写入图标 / 首屏 / 应用名 / `values/strings.xml` / `AndroidManifest.xml`，
   改 `build.gradle`（namespace、applicationId、versionCode/Name、SDK 版本，
   并删掉包里钉死的 `buildToolsVersion`）和 `local.properties`；
5. 写 `src/main/assets/private.tar`（工程 + 引擎，`.py` 不编译）；
6. 用 `gradlew assembleDebug` / `assembleRelease` 打包，把 APK 拷到 `<输出目录>/build/Android/<应用名>.apk`。

构建类型在 tab 里选：**调试**用 Android 的调试证书，**发布**用你选的 keystore
（密码只在构建时通过环境变量传给 Gradle，不写进任何文件；「新建...」会用 JDK 自带的
`keytool` 现场生成一个）。Gradle 本身可以预装——设置页里选好路径就不会再下载发行版。

Gradle 的缓存放在 `.../android/gradle/`，所以同一个工程第二次构建只需几秒。

## 三个坑（已在代码里绕开）

- **`values/strings.xml` 不在包里**：p4a 是按 `templates/strings.tmpl.xml` 在每次打包时
  现场渲染它的，`src/res_initial` 里没有；而清单引用了 `@string/app_name` 和
  `@style/KivySupportCutout`，少了它 AAPT 直接失败。编辑器会自己生成这个文件。
- **`applicationId`**：AGP 8 默认把 `namespace` 当应用 ID，改包名后必须显式写
  `applicationId`，否则装出来还是旧包名。
- **`buildToolsVersion` 不能钉死**：AGP 8.11 最低要 35，包里是 CI 的版本；钉着只会报警告，
  删掉这一行让 AGP 自己决定（它会自己装）。

## 什么时候需要换这个包

见 `tools/android_spike/README.md` 的「运行时产物冻结」一节。简单说：
**引擎自己的代码变了不用换**（引擎在 `private.tar` 里），但
**pygame-ce / pymunk / cffi 版本**、**p4a 或它的 Java 引导层**、
**Python 版本**、**Android 平台 / NDK** 里任何一项变了，就要重新生成。

## 注意

- 这个目录**不会**被打进网页包（`gui/build/web.py` 的 `_ENGINE_RES_SKIP` 排除了 `android`），
  也不会被打进 APK 自己的 payload（`engine_runtime.RUNTIME_SKIP_DIRS` 同样排除）。
- 桌面版只收集 `common/res/images`、`common/i18n/languages`、`common/res/sdk`，不受影响。
