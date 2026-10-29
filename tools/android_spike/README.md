# Android 运行时验证（spike）

这一步**不产出编辑器功能**，只回答三个问题。三项都过了再写 `gui/build/android.py`。

| # | 问题 | 判定标准 | 产出 |
|---|---|---|---|
| 1 | pygame-ce / cffi / pymunk 能不能为 arm64-v8a 交叉编译？ | `buildozer -v android debug` 结束于 BUILD SUCCESSFUL，且 `bin/` 里有 APK | APK + 完整 `buildozer.log` |
| 2 | Windows 上能否只用标准库重建 `private.tar`（不装 Linux）？ | `inspect_dist.py roundtrip` 输出 `RESULT : identical member list` | 报告 + `private_rebuilt.tar` |
| 3 | 真机上 pygame 的显示/图片/字体/音频是否可用？ | Demo 屏幕 4 项全绿、触摸有日志 | 截图 + `adb logcat` 片段 |

## 目录

```
tools/android_spike/
├─ buildozer.spec            # 构建配置（arm64-v8a, sdl2 bootstrap, NDK r25b）
├─ p4a_recipes/
│  ├─ pygame_ce/__init__.py  # 复用 p4a 的 pygame recipe，只换源码地址
│  └─ pymunk/__init__.py     # p4a 自带 recipe 是 6.0.0，这里提到 7.3.1
├─ app/main.py               # 最小 demo：显示 / 图片 / 字体 / 音频 四项自检
└─ inspect_dist.py           # Windows 上检查 dist 并验证 private.tar 可重建
```

`.github/workflows/android-runtime-spike.yml` 会在 GitHub 的 Linux runner 里跑同一套流程。
**只有这台 runner 允许下载 Android SDK/NDK**——用户机器永远不下载工具链。

## 跑法 A：GitHub Actions（推荐，本机零安装）

本机目前的状态：`java 17 ✅`、`docker ❌`、`wsl 无发行版 ❌`、`adb/gradle ❌`。

1. 把 `tools/android_spike/` 和 workflow 提交并 push；
2. GitHub → Actions → `android-runtime-spike` → Run workflow；
3. 首次约 25–45 分钟（下载 SDK/NDK + 编译 CPython/SDL2/pygame），之后有缓存会快很多；
4. 下载 artifact `pygs-android-spike`：
   - `bin/pygsspike-*-arm64-v8a-debug.apk` → spike 1 的证据，也是 spike 3 的测试包；
   - `buildozer.log` → 看每一项 recipe 是否真的编译成功；
   - `pygs-dist.tgz` → 完整 `dist/`，spike 2 的输入。

## 跑法 B：本机 Docker Desktop

```powershell
# 一次：在仓库根目录
docker run --rm -it -v "${PWD}:/home/user/hostcwd" -w /home/user/hostcwd/tools/android_spike `
  kivy/buildozer:latest bash -lc "buildozer -v android debug"
```
之后 `tools/android_spike/bin/` 里就是 APK，`.buildozer/android/platform/build-arm64-v8a/dists/pygsspike/` 是 dist。

## spike 2：在 Windows 上检查并重建 payload

拿到 `dist`（解压 `pygs-dist.tgz`）后：

```powershell
py -3.10 tools/android_spike/inspect_dist.py inspect <dist_dir>
py -3.10 tools/android_spike/inspect_dist.py roundtrip <dist_dir> --out rebuilt.tar
```

`inspect` 会打印：private.tar 的顶层构成、Python 版本目录、`site-packages` 里
pygame / pymunk / cffi / pygamestudio 是否齐全、pygame 的扩展模块清单（缺哪个就说明
recipe 少编了哪块，比如 `font` 缺失 = SDL2_ttf/freetype 没编进去）、`libs/<abi>/*.so`
体积明细、Java 引导包名、Manifest 模板位置。

> 这套检查已经在合成数据上验证过：`inspect` 与 `roundtrip` 都能跑通（roundtrip 会连
> symlink 一起比对）。

## spike 3：真机验证

```powershell
adb install -r tools\android_spike\bin\pygsspike-0.1.0-arm64-v8a-debug.apk
adb logcat -s python          # p4a 的 Python 输出都带这个 tag
```
屏幕会逐行显示 `image / font / mixer` 的自检结果，点一下屏幕会打印触摸事件。

## 失败时的处置（按概率排序）

| 现象 | 原因 | 处置 |
|---|---|---|
| `You need cython. https://cython.org/` | pygame-ce 的 sdist 是 `.pyx` 源码，hostpython 里没有 Cython | 已在 recipe 里加 `hostpython_prerequisites = ['Cython<3.1']` |
| `KeyError: 'pygame_ce'` 或 recipe 找不到 | buildozer 没读到 `p4a.local_recipes` | 确认在 `tools/android_spike` 下运行；必要时把 spec 里改成绝对路径 |
| `buildconfig/Setup.Android.SDL2.in` 不存在 | pygame-ce 新版删了旧构建模板 | 回退 recipe 到 `pygame-ce 2.5.4`，或用 `Pygame2Recipe` 之外自写 `CompiledComponentsPythonRecipe` |
| pygame 编译报找不到 SDL2 头文件 | 子类没有继承到 p4a 的 env | recipe 里显式加回 `USE_SDL2/PYGAME_ANDROID` 与 include 路径 |
| pymunk 链接报 `undefined symbol: __android_log_print` | 少了 `-llog` | 已在 recipe 的 `get_recipe_env` 里加了，确认覆盖生效 |
| `error: use of undeclared identifier 'cpMessage'` 之类 | Chipmunk 源码与 NDK 版本不匹配 | 先把 `android.ndk` 固定为 `25b` 再试 |
| 首次构建超时（CI 150 分钟） | 缓存未命中 | 重跑一次，缓存命中后只编译增量 |

## 三项都通过之后

1. 固化 `VERSION.json`（python / pygame-ce / pymunk / abi / 平台 sdl2 版本 / 校验和）；
2. 写 `AndroidRuntime`（校验 + 版本匹配）与 `AndroidAppBuilder`（重组 private.tar → 注入 → Gradle）；
3. `BuildWindowBody` 加第三个 tab，设置页加 Android 页（SDK/JDK/Gradle 路径 + 检测）。
