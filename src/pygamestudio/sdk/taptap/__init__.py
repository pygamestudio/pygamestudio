"""studio.sdk.taptap - the TapTap platform bridges.

``pc`` is the TapTap PC SDK bridge (Windows x64): login, DLC, achievements,
cloud saves, leaderboards, compliance (China release) and online battle.
"""

from . import pc

__all__ = ['pc']
