"""Third-party platform SDK bridges shipped with the engine.

Each sub-package wraps one vendor SDK, reachable from game code through the
``sdk`` name of the ``studio`` namespace, e.g. ``studio.sdk.taptap.pc`` (TapTap
PC SDK). The wrappers are pure Python + ctypes: no compiler is needed at build
time and one DLL serves every Python version.
"""

from . import taptap

__all__ = ['taptap']
