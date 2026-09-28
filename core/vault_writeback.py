"""Moved to `core.vault.writeback` (#901). This name stays one wave as an alias of the same
module, so in-flight code keeps importing and `patch("core.vault_writeback.x")` still patches it.
"""

import sys

from core.vault import writeback as _moved

sys.modules[__name__] = _moved
