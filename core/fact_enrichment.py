"""Moved to `core.facts.enrichment` (#907). This name stays one wave as an alias of the same
module, so in-flight code keeps importing and `patch("core.fact_enrichment.x")` still patches it.
"""

import sys

from core.facts import enrichment as _moved

sys.modules[__name__] = _moved
