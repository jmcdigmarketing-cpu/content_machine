"""#418: zoompan at the output size upsamples a frame that is already 1080x1920.

TapIn's shipped zoom is 1.08 and MoneyWise's is 1.05. The peak zoom has to be
sampled from a lanczos pre-scale of that same frame, including a draft 480x854
cut. Punch-in (1.12) and snap-zoom (1.14) are the same shape.
"""

from __future__ import annotations

import unittest

_WORDS = [
    {"word": "This", "start": 0.1, "end": 0.4},
    {"word": "lands.", "start": 0.4, "end": 0.9},
]


class HookZoomSharpnessTests(unittest.TestCase):
    def test_a_bounded_zoom_prescales_the_frame_it_outputs(self):
        from video.hook_motion import first_caption_motion_filter

        filt = first_caption_motion_filter(_WORDS, {"enabled": True, "zoom": 1.08})
        rendered = filt.format(width=1080, height=1920)
        self.assertIn(
            "scale=trunc(1080*1.0800/2)*2:trunc(1920*1.0800/2)*2:flags=lanczos",
            rendered,
        )
        self.assertLess(rendered.index("scale="), rendered.index("zoompan="))
        self.assertIn("s=1080x1920", rendered)

        draft = filt.format(width=480, height=854)
        self.assertIn(
            "scale=trunc(480*1.0800/2)*2:trunc(854*1.0800/2)*2:flags=lanczos",
            draft,
        )
        self.assertIn("s=480x854", draft)
        self.assertNotIn("1080", draft)

    def test_motion_off_adds_no_scale(self):
        from video.hook_motion import first_caption_motion_filter

        self.assertEqual(
            first_caption_motion_filter(_WORDS, {"enabled": False, "zoom": 1.08}),
            "",
        )
        self.assertEqual(first_caption_motion_filter(None, {"enabled": True, "zoom": 1.08}), "")

    def test_named_presets_prescale_by_their_own_peak(self):
        from video.hook_motion import named_motion_filter

        punch = named_motion_filter(_WORDS, {"enabled": True, "preset": "punch-in"})
        snap = named_motion_filter(_WORDS, {"enabled": True, "preset": "snap-zoom"})
        punch_r = punch.format(width=1080, height=1920)
        snap_r = snap.format(width=1080, height=1920)
        self.assertIn("trunc(1080*1.1200/2)*2", punch_r)
        self.assertIn("flags=lanczos", punch_r)
        self.assertIn("trunc(1080*1.1400/2)*2", snap_r)
        self.assertIn("s=1080x1920", snap_r)
