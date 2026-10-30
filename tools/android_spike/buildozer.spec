# Buildozer spec for the Android *runtime* spike.
#
# This is NOT the editor's Android build. It exists to answer three questions
# once, on a machine that is allowed to install the Android SDK/NDK:
#   1. do pygame-ce / cffi / pymunk cross-compile for arm64-v8a?
#   2. what does a p4a `dist/` look like (private.tar layout, libs, java src)?
#   3. does a pygame app actually run on a device with touch + font + image + audio?
#
# Run it with:  buildozer -v android debug      (inside kivy/buildozer)
# The resulting APK is in bin/, the reusable payload in .buildozer/.../dists/.

[app]

title = PyGS Spike
package.name = pygsspike
package.domain = org.pygamestudio

# The demo app: a real engine project (project.pygs + scene + scripts) plus the
# staged runtime engine. ``spike1_pygame_only.py`` is the previous, engine-free
# demo kept for reference - it stays out of the APK.
source.dir = app
source.include_exts = py,png,pygs,scene,json
source.exclude_patterns = spike1_pygame_only.py

version = 0.1.0

# pygame_ce + pymunk are the two custom recipes in ./p4a_recipes; cffi comes
# from p4a itself as a dependency of pymunk.
requirements = python3,pygame_ce,pymunk

orientation = landscape
fullscreen = 0

android.api = 34
android.minapi = 24
# NDK r25b is the version p4a is tested against; a newer one changes the
# sysroot layout and breaks several recipes.
android.ndk = 25b
android.ndk_api = 24
# arm64 only: this is what the shipped runtime will contain.
android.archs = arm64-v8a
# Needed for the SDK download in CI (unattended license accept).
android.accept_sdk_license = True
# Keep artefacts small and predictable.
android.debug_artifact = apk
android.allow_backup = False

# SDL2 bootstrap = the bootstrap that provides the SDL surface the pygame
# window is drawn on. This is the piece Chaquopy does not have.
p4a.bootstrap = sdl2
p4a.local_recipes = p4a_recipes

# Ship the app's .py files verbatim instead of letting p4a byte-compile them
# (p4a's make_package() replaces every .py with a .pyc, and the runtime loads
# the object scripts by path - ``scripts/drag.py`` would not exist). It is also
# a hard requirement for real builds: protected projects ship ENCRYPTED modules,
# which compileall cannot parse at all.
p4a.extra_args = --no-byte-compile-python

[buildozer]
log_level = 2
warn_on_root = 0
