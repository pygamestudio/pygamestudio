# Android 运行时验证（spike）

这一步**不产出编辑器功能**，只回答三个问题。三项都过了再写 `gui/build/android.py`。

| # | 问题 | 判定标准 | 产出 |
|---|---|---|---|
| 1 | pygame-ce / cffi / pymunk 能不能为 arm64-v8a 交叉编译？ | `buildozer -v android debug` 结束于 BUILD SUCCESSFUL，且 `bin/` 里有 APK | APK + 完整 `buildozer.log` |
| 2 | Windows 上能否只用标准库重建 `private.tar`（不装 Linux）？ | `inspect_dist.py roundtrip` 输出 `RESULT : identical member list` | 报告 + `private_rebuilt.tar` |
| 3a | 真机上 pygame 的显示/图片/字体/音频是否可用？ | Demo 屏幕 4 项全绿、触摸有日志 | 截图 + `adb logcat` 片段 |
| 3b | **真机上引擎能不能跑起来？**（无 PySide6、项目配置、场景、脚本、触摸、画布缩放） | 屏幕上 `engine/project/scene` 全绿、拖动方块跟手、点按 pad 有 `[ENGINE]` 日志 | 截图 + `adb logcat` 片段 |

## 目录

```
tools/android_spike/
├─ buildozer.spec            # 构建配置（arm64-v8a, sdl2 bootstrap, NDK r25b）
├─ p4a_recipes/
│  ├─ pygame_ce/__init__.py  # 复用 p4a 的 pygame recipe，只换源码地址
│  └─ pymunk/__init__.py     # p4a 自带 recipe 是 6.0.0，这里提到 7.3.1
├─ engine_runtime.py         # 挑选「运行时需要的引擎子集」并拷进 app/（未来运行时产物的原型）
├─ project_scan.py           # 静态扫 import：运行时没有的模块直接报错，而不是装机后黑屏
├─ smoke_engine.py           # 本机无头预演：真的加载场景、拖动、点按、跑一遍 main.py
├─ spike1_pygame_only.py     # spike 1/3a 的纯 pygame demo（不进 APK，留作对照）
├─ app/
│  ├─ main.py                # spike 3b 入口：引擎 Game + 屏幕自检报告
│  ├─ project.pygs           # 最小工程配置（800×600 画布，current_scene）
│  ├─ scenes/main.scene      # 画布 + 标题 + 提示 + 触摸区 + 可拖动方块
│  ├─ scripts/drag.py        # 只实现鼠标拖拽族（验证“手指也会走 on_drag”）
│  ├─ scripts/pad.py         # 只实现触摸族（验证 FINGER 事件与去重）
│  └─ assets/box.png         # 拖拽用的 128×128 精灵
├─ android_assets.py         # 图标 / 首屏 / 应用名注入
├─ assets/                   # 图标与首屏素材
└─ inspect_dist.py           # Windows 上检查 dist 并验证 payload 可重建
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

> 这版 p4a 的 dist **没有 `private.tar`**：Python 运行时以目录形式躺在
> `_python_bundle__arm64-v8a/_python_bundle/`（`modules/` + `site-packages/` + `stdlib.zip`），
> 到打 APK 时才被 `make_tar()` 打成 `libs/<abi>/libpybundle.so`（一个 gzip tar，扩展名却像库），
> 应用代码则打成 `assets/private.tar`。两者都是普通压缩包，所以 Windows 上可以自己生成。

拿到 `dist`（解压 `pygs-dist.tgz`）后：

```powershell
py -3.10 tools/android_spike/inspect_dist.py inspect <dist_dir>
py -3.10 tools/android_spike/inspect_dist.py bundle  <dist_dir> --out libpybundle.so
```

`inspect` 会打印：bundle 目录构成（stdlib.zip / modules / site-packages）、
pygame / pymunk / cffi / pygame 扩展模块是否齐全、`libs/<abi>/*.so` 体积明细、
Java 引导包名、Manifest 模板位置。

`bundle` 按 p4a 的规则（gzip、USTAR、uid/gid=0、mtime=0、成员相对
`_python_bundle__<arch>`）重建 `libpybundle.so`，并校验顶层目录是 `_python_bundle`。

> 两个子命令都在合成数据上验证过：`inspect` 的输出与 CI 的 grep 门禁逐条匹配，
> `bundle` 产出的归档解出来就是 `_python_bundle/{modules,site-packages,stdlib.zip}`。

## 图标 / 首屏（spike 3c）

`assets/icon.png`（1024×1024 PNG，带透明）与 `assets/presplash.jpg`（1920×1080）由
`android_assets.py` 写进 dist，CI 会在第一次打包后自动执行并重新打包：

```powershell
py -3.10 tools/android_spike/android_assets.py <dist_dir> `
  --icon tools/android_spike/assets/icon.png `
  --presplash tools/android_spike/assets/presplash.jpg
```

> 图像处理有两个后端：编辑器/开发机用 **PySide6**（引擎已有依赖），CI 容器没有 Qt 也没有显示服务，
> 自动退回 **Pillow**（`pip install pillow`），输出等价。

生成的内容（都只动 `src/main/res`，不需要改 p4a 源码）：

| 目标 | 说明 |
|---|---|
| `mipmap-{mdpi..xxxhdpi}/icon.png` | 48/72/96/144/192，另写 `mipmap/icon.png` 兜底 |
| `drawable-{mdpi..xxxhdpi}/ic_launcher.png` | 同尺寸，p4a launcher 资源保持一致 |
| `mipmap-anydpi-v26/icon.xml` | Android 8+ 自适应图标 |
| `drawable-*/ic_launcher_foreground.png` | 108dp 五档，图形限制在中心 66% 安全区 |
| `drawable/presplash.jpg` | p4a 用 `ScaleType.FIT_CENTER` 显示，不裁剪不拉伸 |
| `values/strings.xml` + `templates/strings.tmpl.xml` | `presplash_color` 自动取首屏图四角的主色（两张图底色一致就不会露边） |

> 注意：`values/strings.xml` 在每次打包时都会从 `templates/strings.tmpl.xml` 重新渲染，
> 所以两个文件都要写，否则第二次打包会退回默认的 `#000000`。
>
> 还有一个更隐蔽的坑：p4a 的 `make_package()` 开头会执行
> `rmdir(src/main/res)` + `copytree(src/res_initial, src/main/res)`（"make res_dir
> stateless"），也就是说**每次打包都会把资源重置成 `src/res_initial` 里的那份**。
> 只改 `src/main/res` 的话，下一次打包（例如注入后再打一次）就会把图标还原成 Kivy。
> 脚本因此同时写入 `src/main/res` 和 `src/res_initial`。
>
> 第三个坑：`make_package()` 还会把 p4a 自带的默认图
> `templates/kivy-icon.png` / `templates/kivy-presplash.jpg` 拷进 res 覆盖同名资源。
> 只改 res 的话首屏永远退回 Kivy logo（图标侥幸没被覆盖，因为它的目标路径不同）。
> 脚本会把这两个模板文件也一起替换。

## spike 3：真机验证

APK 在 CI 的 artifact 里（Actions → 那次运行 → 页面底部 Artifacts → `pygs-android-spike`，
下载后解压，里面的 `bin/pygsspike-0.1.0-arm64-v8a-debug.apk` 就是）：

```powershell
adb install -r bin\pygsspike-0.1.0-arm64-v8a-debug.apk
adb logcat -s python          # p4a 的 Python 输出都带这个 tag
```
屏幕会逐行显示自检结果，点一下屏幕会打印触摸事件。

## spike 3b：引擎上机

前面三项证明的是「pygame 能用」。这一项证明的是「**引擎**能用」——APK 里跑的是真的
`pygamestudio` 运行时：真的 `project.pygs`、真的 `.scene`、真的行为脚本、真的触摸分发。

### 引擎子集怎么进 APK

设备上没有 pip、没有 PySide6，所以只拷运行时需要的那部分（`engine_runtime.py`）：

| 进 | 不进 |
|---|---|
| `api/`（Game / 场景加载 / 音频 / 物理 / 窗口） | `game/core/manager.py`、`game/core/command.py`（Qt 场景树、QUndoCommand） |
| `game/`（场景对象、碰撞、物理） | `common/utils/config.py`、`theme.py`、`qr.py`（QSettings / QSS / QImage） |
| `common/`（i18n 词条、资源容器、路径工具） | `common/res/resources_rc.py`（Qt 编译资源） |
| `gui/console/logger.py`（运行时经翻译器用到它，纯 Python） | `common/res/{fonts,pyodide,wheels,qss,templates,sdk,audios}`（9.3 MB 字体、14.5 MB pyodide…） |
| `common/res/images/`（`window.py` 用 logo 当默认图标，0.12 MB） | `sdk/`（TapTap 是 Windows DLL，Toy 是浏览器 SDK），改成空的 `sdk/__init__.py` 占位 |

当前规模：**156 个文件 / 0.6 MB**。

CI 在第一次构建前执行 `engine_runtime.py src/pygamestudio tools/android_spike/app`，
引擎就直接躺在 `app/` 里，跟着应用代码一起进 `assets/private.tar`。

### 两个必须知道的 p4a 行为

1. **p4a 默认把 `.py` 编译成 `.pyc`**（`make_tar(byte_compile_python=True)`），
   `private.tar` 里只剩 `main.pyc`。本引擎的行为脚本是按路径读的
   （`scripts/drag.py`），编译掉就静默不挂载脚本。`buildozer.spec` 里因此加了：
   ```
   p4a.extra_args = --no-byte-compile-python
   ```
   这对正式版是硬要求：加密发布时，工程里的模块是**密文**，`compileall` 会直接语法错误。
2. **入口是 `PyRun_SimpleFile(main.py)`**（见 `jni/application/src/start.c`），
   所以 `main.py` 就是最外层 Python 帧，`Game._init_game()` 的
   `inspect.stack()[-1]` 能正确拿到 `/data/data/<pkg>/files/app/main.py`，
   项目根目录也就是它所在目录。spike 会把「引擎解析出的路径」和「本文件所在目录」都打印出来对照。
3. **p4a 编出来的 pygame 少了几个可选 C 扩展**：`_freetype`、`_camera`、`pypm`、`system`
   （p4a 的 pygame recipe 明确不管 freetype / midi / camera）。第一次上机就栽在这：
   `game/object/text.py` 顶部有一行**没用到**的 `import pygame.freetype`，桌面环境有这模块、
   手机上直接 `ModuleNotFoundError: No module named 'pygame._freetype'`，整个引擎 import 失败。
   已删掉那行；引擎的文字渲染一直用的是 `pygame.font.Font`，行为不变。

   这类问题桌面永远测不出来，所以 `smoke_engine.py` 里加了一道门禁：
   在子进程里用 import hook **屏蔽** `engine_runtime.ANDROID_MISSING_PYGAME_MODULES` 列出的模块，
   再 import 整个运行时（`api` + `game.object.*`），模拟真机的 import 图。
   顺带一条产品结论：用户游戏里若用了 `pygame.freetype` / `pygame.midi` / `pygame.camera`，
   在 Android 上跑不起来——要支持就得自己往 recipe 里补依赖。

### 上机前先在本机跑一遍（省一个 CI 来回）

```powershell
py -3.10 tools/android_spike/smoke_engine.py
```

它把**将要进 APK 的那批文件**拷到临时目录，用 `SDL_VIDEODRIVER=dummy` 无头跑：

* 引擎导入 / 工程配置 / 场景加载 / 两个行为脚本挂载 / 图片对象出图；
* 模拟鼠标拖拽（方块要动）和手指点按（`on_touch_*` 要收到 3 次 move）；
* 渲染一帧；
* **屏蔽 Android 上缺失的 pygame 扩展后**再 import 一遍整个运行时（真机 import 图）；
* 最后用 `python main.py` **在子进程里跑真的入口**（`SPIKE_MAX_FRAMES=3` 自动退出），
  验证 `Game.run()` 全链路和项目路径解析。

全绿时最后一行是 `RESULT : the staged engine runs the spike project headless`。

### 上机要看什么

屏幕上方的报告面板（红字 = 失败，绿字 = 通过）逐行是：
`engine / project / pygame / scene / screen / pointer+ finger 计数 / fps`。

| 行 | 期望 | 说明 |
|---|---|---|
| `engine` | `imported` | 没有 PySide6 也能 import |
| `project` | `'PyGS engine spike' canvas (800, 600)` | `project.pygs` 读到了 |
| `scene` | `5 object(s), 2 script(s)` | 场景 + 行为脚本都挂上了 |
| `screen` | `2400x1080 window for a 800x600 canvas -> scale 3.00` | **关键测量**：Android 给的窗口像素 vs 编辑器画布 |
| 计数 | 拖动时 `pointer` 增长，点 pad 时 `finger` 增长 | 两族事件都到了引擎 |

`[ENGINE]` 前缀的日志来自场景脚本，`adb logcat -s python` 里能直接看到
`drag_start / drag #n / drag_end` 和 `touch_down / touch_move #n / touch_up / tap`。

> `screen` 那行会暴露一个已知问题：引擎现在把场景按 1:1 像素画在窗口左上角，
> 手机分辨率远大于 800×600 时画面只占左上角一块。真机数字出来后，
> 再决定是「引擎加设计分辨率缩放层」还是「构建时让项目按设备分辨率出图」。

## 画面自适应（已实现，可挑选适配方式）

真机第一轮先试了 SDL 自带的 `pygame.SCALED`（逻辑分辨率）。它确实生效了——
报告里 `surface 800x600 / window 1920x1038`——但**画面居中不变大**：SDL 把缩放比交给
renderer，实际按整倍数取整（1.73 → 1.0），于是 800×600 原样居中。缩放比不可控，
也不能按项目选适配方式。

所以引擎改成自己做这一层（`api/core/game.py`）：

```
窗口 surface (_display)  = 真实屏幕 1920×1038
画布 surface (_screen)   = 项目画布 800×600   ← get_screen() 返回它，脚本/场景对象都画在这里
每帧：_present() = smoothscale(画布 → 适配矩形) + blit 到窗口 + flip
```

* 坐标：窗口像素 → 画布像素的换算在 `run()` 里对每个鼠标事件做一次（`_to_canvas`），
  触摸事件本来就是归一化坐标，也走同一条路——命中测试、拖拽、脚本回调全部还是编辑器坐标系；
* 黑边：窗口先清成黑色，之后只覆盖适配矩形，所以黑边不需要每帧重画。

### 适配方式（`screen_scale_mode`）

| 值 | 语义 | 800×600 → 1920×1038 的结果 |
|---|---|---|
| `none`（默认） | 不缩放，1:1 画在左上角 | 800×600 在左上角 |
| `show_all` | 完整显示画布，多余留黑边 | 1384×1038 居中，左右各 268px 黑边 |
| `no_border` | 铺满屏幕，超出部分裁掉 | 1920×1440，上下各裁 201px |
| `fixed_width` | 宽度总是铺满 | 1920×1440，上下裁 |
| `fixed_height` | 高度总是铺满 | 1384×1038，左右黑边 |
| `exact_fit` | 拉伸铺满，不管比例 | 1920×1038（会变形） |
| `integer` | 最大整数倍，像素不糊 | 800×600 居中（1.73 → 1 倍） |

编辑器的 **项目设置 → 游戏窗口 → 移动端屏幕适配** 就是这一项（下拉框，默认"无适配"），
写进 `project.pygs` 的 `screen_scale_mode`。旧的工程没有这个键，读出来就是 `none`，
行为和以前完全一致。

```json
{
  "screen_size": [800, 600],
  "screen_scaled": true,
  "screen_scale_mode": "show_all",
  "screen_scale_filter": "nearest"
}
```

* `screen_scaled: false` → 完全不缩放（等价于 `none`，保留给老构建）；
* `screen_scale_filter`: `nearest`（默认，快）或 `smooth`（双线性，好看但极慢，见下）；
* 桌面（编辑器「运行」、桌面版）完全不进这套逻辑，仍然开真的 800×600 窗口。

真机上要看的新报告行（`_fit_rect` 的 7 种模式在 `smoke_engine.py` 里有断言）：

```
screen: surface 800x600, window 1875x1054 (sdl 828x1180), mode show_all, present 1406x1054 at (240, 0) = 1.76x
```

> 注意 `window` 和 `sdl` 两个数字可能不同：前者是我们真正 blit 进去的 display surface，
> 后者是 SDL 报告的窗口尺寸（设备密度不同）。缩放以 **surface** 为准。

## 性能

### 真实数据（三轮）

| 轮次 | 引擎 | 结论 |
|---|---|---|
| 第 1 轮（1:1，无缩放） | 26 fps | 空帧呈现 809 fps → 瓶颈在引擎：`ObjectCanvas` 每帧重建 800×600 SRCALPHA 表面 |
| 第 2 轮（smoothscale 呈现） | **6 fps** | **我们自己把帧率砸下去的**：`smoothscale` 一帧 141.9 ms（整屏双线性），`other 155 ms` 就是它 |
| 第 3 轮（本轮） | 待测 | 画布缓存已修 + 默认改 `nearest` + 1:1/整屏两条快路径 |

教训：**整屏双线性缩放不要放在每帧路径上**，尤其在 ARM / 模拟器上。
现在默认 `nearest`（`pygame.transform.scale`，接近内存拷贝），`smooth` 只作为可选项留给
桌面或性能充裕的机型；`present` 还加了两条快路径：画布大小等于窗口时直接 blit（不缩放），
`exact_fit` 时直接缩放到窗口表面（省掉中转表面和第二次整屏 blit）。

### 这一轮的测量

`on_start` 里的探针会**两个滤镜都测一遍**：

```
perf: present: nearest 3.8 ms, smooth 141.9 ms (canvas 800x600)
```

面板里每秒还有一行分项：

```
frame: scene draw 4.2 ms, other 12.5 ms, fps 60
```

* `scene draw` = `load_scene()` 的耗时（场景绘制 + 脚本 + 物理）；
* `other` = 一帧剩余时间（事件 + `_present` + flip + 60Hz 上限）。

> MuMu 这类模拟器跑的是 x86 上的 ARM 翻译 + 软件合成，fps 参考价值有限；真机数字才作数。



## 依赖扫描（构建前就报错，而不是装机后黑屏）

运行时只带 **stdlib + pygame-ce + pymunk + cffi + 引擎**，别的第三方库一律没有；
p4a 编出来的 pygame 还少了 `_freetype` / `_camera` / `pypm` / `system`。
用户工程一旦 import 这些，APK 照样能打出来，然后在手机上 `ModuleNotFoundError` + 黑屏。

`project_scan.py` 用 `ast` 扫工程里的 `import`，对照「运行时能提供的模块」白名单：

```powershell
py -3.10 tools/android_spike/project_scan.py tools/android_spike/app
```

```
scanned: 3 python file(s)
imports: os, pathlib, pygame, pygamestudio, sys, time, traceback
RESULT : project imports ok
```

负例（`import numpy` + `import pygame.freetype`）：

```
  BLOCKED pygame.freetype (main.py:2) - p4a does not build it
  MISSING numpy (main.py:1) - not part of the Android runtime
RESULT : imports UNSUPPORTED      (exit 1)
```

CI 在构建前就跑这一步（`scan.log` 也会上传），失败时给出的是模块名，不是一台黑屏的手机。



## 失败时的处置（按概率排序）

| 现象 | 原因 | 处置 |
|---|---|---|
| `You need cython. https://cython.org/` | pygame-ce 的 sdist 是 `.pyx` 源码，hostpython 里没有 Cython | 已在 recipe 里加 `hostpython_prerequisites = ['Cython<3.1']` |
| `Could not invoke sanity check executable` / `meson.build:1:0` | pygame-ce 2.5+ 用 meson-python 作为 PEP 517 后端，meson 无法在这里交叉编译 | 已在 `prebuild_arch` 里把 `[build-system]` 换成 setuptools，让 pip 走 legacy setup.py（p4a 原本就是这么编 pygame 的） |
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
