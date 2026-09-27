"""Moved to `core.voice.plan` (#834). This name stays one wave as an alias of the same
module, so in-flight code keeps importing and `patch("core.voice_plan.x")` still patches it.
"""

import sys

from core.voice import plan as _moved

sys.modules[__name__] = _moved
