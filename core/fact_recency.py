"""Moved to `core.facts.recency` (#907). This name stays one wave as an alias of the same
module, so in-flight code keeps importing and `patch("core.fact_recency.x")` still patches it.
"""

import sys

from core.facts import recency as _moved

sys.modules[__name__] = _moved
