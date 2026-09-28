"""Moved to `core.vault.evals` (#901). This name stays one wave as an alias of the same
module, so in-flight code keeps importing and `patch("core.vault_evals.x")` still patches it.
"""

import sys

from core.vault import evals as _moved

sys.modules[__name__] = _moved
