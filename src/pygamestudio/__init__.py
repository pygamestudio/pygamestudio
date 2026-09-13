from .api import *

# A protected build ships the project's own modules encrypted, so the runtime
# needs an import hook to read them (it stays inactive for plain projects and
# for the editor).
from .common.utils.project_modules import install as _install_project_modules

_install_project_modules()