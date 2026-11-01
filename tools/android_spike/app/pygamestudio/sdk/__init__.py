"""studio.sdk - the platform bridges available to this build.

Android has none of them: the TapTap PC SDK is a Windows desktop library and
the Bilibili Toy bridge talks to a browser page. Game code can still import
this namespace; every bridge it expects is missing on purpose.
"""

__all__ = []
