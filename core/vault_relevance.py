"""Moved to `core.vault.relevance` (#901). This name stays one wave as an alias of the same
module, so in-flight code keeps importing and `patch("core.vault_relevance.x")` still patches it.
"""

import sys

from core.vault import relevance as _moved

sys.modules[__name__] = _moved
