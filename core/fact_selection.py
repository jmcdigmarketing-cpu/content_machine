"""Moved to `core.facts.selection` (#907). This name stays one wave as an alias of the same
module, so in-flight code keeps importing and `patch("core.fact_selection.x")` still patches it.
"""

import sys

from core.facts import selection as _moved

sys.modules[__name__] = _moved
