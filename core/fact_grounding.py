"""Moved to `core.facts.grounding` (#907). This name stays one wave as an alias of the same
module, so in-flight code keeps importing and `patch("core.fact_grounding.x")` still patches it.
"""

import sys

from core.facts import grounding as _moved

sys.modules[__name__] = _moved
