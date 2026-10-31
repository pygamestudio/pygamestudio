"""Spike wrapper around the engine's Android asset injection.

The real implementation is ``src/pygamestudio/gui/build/android_assets.py`` (the
editor calls it right before Gradle). CI still injects the icon/splash into a
dist to keep the spike APK branded, so this wrapper loads that file BY PATH -
importing ``pygamestudio`` would execute the package ``__init__`` and pull in
pygame, which the build container does not have.
"""
import importlib.util
import sys
from pathlib import Path

ENGINE_ASSETS_MODULE = (Path(__file__).resolve().parents[2]
                        / 'src' / 'pygamestudio' / 'gui' / 'build' / 'android_assets.py')


def _load_engine_module():
    if not ENGINE_ASSETS_MODULE.is_file():
        raise SystemExit(f'engine asset module missing: {ENGINE_ASSETS_MODULE}')
    spec = importlib.util.spec_from_file_location('pygs_android_assets',
                                                  ENGINE_ASSETS_MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ENGINE = _load_engine_module()

BACKEND = _ENGINE.BACKEND
AndroidAssetsError = _ENGINE.AndroidAssetsError
run = _ENGINE.run
main = _ENGINE.main


if __name__ == '__main__':
    sys.exit(main())
