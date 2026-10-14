from .api import *

# Platform SDK bridges live under the studio namespace: studio.sdk.taptap.pc
# (Windows-only wrappers; importing them loads no DLL and has no side effect).
from . import sdk

# A protected build ships the project's own modules encrypted, so the runtime
# needs an import hook to read them (it stays inactive for plain projects and
# for the editor).
from .common.utils.project_modules import install as _install_project_modules

_install_project_modules()