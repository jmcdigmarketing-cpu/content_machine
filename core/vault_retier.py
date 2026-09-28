"""Moved to `core.vault.retier` (#901). This name stays one wave as an alias of the same
module, so in-flight code keeps importing and `patch("core.vault_retier.x")` still patches it.
"""

import sys

from core.vault import retier as _moved

sys.modules[__name__] = _moved
