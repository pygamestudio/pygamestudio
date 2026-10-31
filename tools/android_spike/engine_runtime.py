"""Spike wrapper around the engine's own "what does an Android build ship" list.

The list lives in the engine (``src/pygamestudio/gui/build/runtime_payload.py``)
so the CI spike and the editor cannot drift apart. This module loads that file
BY PATH on purpose: importing ``pygamestudio`` would execute the package
``__init__``, which imports pygame - and the staging container has no pygame.

Everything the spike scripts use (``stage``, ``iter_runtime_files``,
``ANDROID_MISSING_PYGAME_MODULES``, the skip lists) is re-exported here.
"""
import importlib.util
from pathlib import Path

ENGINE_PAYLOAD_MODULE = (Path(__file__).resolve().parents[2]
                         / 'src' / 'pygamestudio' / 'gui' / 'build' / 'runtime_payload.py')


def _load_engine_module():
    if not ENGINE_PAYLOAD_MODULE.is_file():
        raise SystemExit(f'engine runtime module missing: {ENGINE_PAYLOAD_MODULE}')
    spec = importlib.util.spec_from_file_location('pygs_runtime_payload',
                                                  ENGINE_PAYLOAD_MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ENGINE = _load_engine_module()

RUNTIME_DIRS = _ENGINE.RUNTIME_DIRS
RUNTIME_EXTRA_FILES = _ENGINE.RUNTIME_EXTRA_FILES
RUNTIME_SKIP_FILES = _ENGINE.RUNTIME_SKIP_FILES
RUNTIME_SKIP_DIRS = _ENGINE.RUNTIME_SKIP_DIRS
SDK_STUB_SOURCE = _ENGINE.SDK_STUB_SOURCE
ANDROID_MISSING_PYGAME_MODULES = _ENGINE.ANDROID_MISSING_PYGAME_MODULES
VERSION = _ENGINE.VERSION
PAYLOAD_ENV_FILE = _ENGINE.PAYLOAD_ENV_FILE
SITECUSTOMIZE_SOURCE = _ENGINE.SITECUSTOMIZE_SOURCE

iter_runtime_files = _ENGINE.iter_runtime_files
stage = _ENGINE.stage
make_payload_tar = _ENGINE.make_payload_tar
main = _ENGINE.main


if __name__ == '__main__':
    raise SystemExit(main())
