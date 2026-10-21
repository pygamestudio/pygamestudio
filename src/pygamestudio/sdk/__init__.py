"""Third-party platform SDK bridges shipped with the engine.

Each sub-package wraps one vendor SDK, reachable from game code through the
``sdk`` name of the ``studio`` namespace, e.g. ``studio.sdk.taptap.pc`` (TapTap
PC SDK) or ``studio.sdk.toy`` (Bilibili Toy JS SDK). The TapTap wrappers are
pure Python + ctypes - no compiler needed at build time, one DLL serves every
Python version - while the Toy bridge talks to the ``window.toy`` object the
platform injects into a Toy page.
"""

from . import taptap
from . import toy

__all__ = ['taptap', 'toy']
