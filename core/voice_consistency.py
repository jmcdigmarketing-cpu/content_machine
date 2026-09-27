"""Moved to `core.voice.consistency` (#834). This name stays one wave as an alias of the same
module, so in-flight code keeps importing and `patch("core.voice_consistency.x")` still patches it.
"""

import sys

from core.voice import consistency as _moved

sys.modules[__name__] = _moved
