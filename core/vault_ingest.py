"""Moved to `core.vault.ingest` (#901). This name stays one wave as an alias of the same
module, so in-flight code keeps importing and `patch("core.vault_ingest.x")` still patches it.
"""

import sys

from core.vault import ingest as _moved

sys.modules[__name__] = _moved
