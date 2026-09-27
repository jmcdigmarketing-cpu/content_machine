"""Moved to `core.voice.catalog` (#834). This name stays one wave as an alias of the same
module, so in-flight code keeps importing and `patch("core.voice_catalog.x")` still patches it.
"""

import sys

from core.voice import catalog as _moved

sys.modules[__name__] = _moved
