"""Run 98: the sentence-TTS join billed every multi-sentence render twice.

`concat_audio_segments` wrote the segment paths into `<dest>.concat.txt` exactly as
they arrived. The pipeline's output paths are relative (`output/tapin/audio/...`,
`core/output_paths.py`), and ffmpeg's concat demuxer resolves a relative entry
against the *list file's* folder, not the working directory - so it looked for
`output/tapin/audio/output/tapin/audio/<name>.seg0.mp3`, failed, and
`_generate_audio` re-synthesized the whole script. The operator's log said so:
"sentence TTS concat failed after billing 972 char(s) ... billed twice".

Every existing sentence-path test replaced `concat_audio_segments` with a fake and
used absolute temp paths, so none could see it. These drive the real function with
relative paths, against a fake `subprocess.run` that resolves list entries the way
the demuxer does; the last one uses real ffmpeg where it exists (always under CI).
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from core import tts
from tests.test_wave10 import _has_ffmpeg

_SEG_DIR = os.path.join("output", "tapin", "audio")


@contextmanager
def _in_temp_cwd():
    old = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            yield tmp
        finally:
            os.chdir(old)


class _DemuxerLikeRun:
    """Stands in for `ffmpeg -f concat`: relative entries resolve against the list's
    folder. Records every call so a test can tell whether it happened at all."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, cmd, *args, **kwargs):
        self.calls.append(list(cmd))
        list_file = cmd[cmd.index("-i") + 1]
        base = os.path.dirname(os.path.abspath(list_file))
        chunks: list[bytes] = []
        with open(list_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line.startswith("file "):
                    continue
                entry = line[len("file ") :].strip().strip("'").replace(r"'\''", "'")
                resolved = entry if os.path.isabs(entry) else os.path.join(base, entry)
                if not os.path.isfile(resolved):
                    return subprocess.CompletedProcess(
                        cmd, 4294967294, "", f"[in#0] Error opening input: {resolved}"
                    )
                with open(resolved, "rb") as seg:
                    chunks.append(seg.read())
        with open(cmd[-1], "wb") as out:
            out.write(b"".join(chunks))
        return subprocess.CompletedProcess(cmd, 0, "", "")


class TestTheListNamesFilesFfmpegCanFind(unittest.TestCase):
    def test_relative_segments_concat(self) -> None:
        with _in_temp_cwd():
            os.makedirs(_SEG_DIR)
            dest = os.path.join(_SEG_DIR, "x.mp3")
            segs = [f"{dest}.seg{i}.mp3" for i in range(2)]
            for i, seg in enumerate(segs):
                with open(seg, "wb") as f:
                    f.write(f"seg{i}".encode())
            fake = _DemuxerLikeRun()
            with patch("subprocess.run", side_effect=fake):
                out = tts.concat_audio_segments(segs, dest)
            self.assertEqual(out, dest)
            with open(dest, "rb") as f:
                self.assertEqual(f.read(), b"seg0seg1")

    def test_the_list_body_is_absolute_and_quoted(self) -> None:
        with _in_temp_cwd() as tmp:
            body = tts.concat_list_text(["output/a/b.mp3", "output/a/it's.mp3"])
        lines = body.splitlines()
        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertTrue(line.startswith("file '"), line)
            path = line[len("file '") : -1].replace(r"'\''", "'")
            self.assertTrue(os.path.isabs(path), path)
        self.assertIn(r"it'\''s.mp3", lines[1])
        self.assertIn(os.path.realpath(tmp).replace("\\", "/").split("/")[-1], lines[0])


class TestAMultiSentenceRenderPaysOnce(unittest.TestCase):
    def setUp(self) -> None:
        tts._last_cache_hit = False
        tts._last_piper_mix = False

    def test_each_sentence_is_synthesized_once_and_billed_once(self) -> None:
        script = "First sentence here. Second sentence here."
        seam_calls: list[str] = []
        recorded: list[int] = []

        def fake_seam(spoken, spoken_for_alt, output_path, channel_id, cache_key, **kwargs):
            seam_calls.append(spoken)
            with open(output_path, "wb") as f:
                f.write(b"mp3")
            return output_path

        with _in_temp_cwd() as tmp:
            dest = os.path.join(_SEG_DIR, "run98.mp3")
            env = {
                "TTS_CACHE": "true",
                "TTS_CACHE_DIR": os.path.join(tmp, "cache"),
                "TTS_PROVIDER": "elevenlabs",
            }
            fake = _DemuxerLikeRun()
            with (
                patch.dict(os.environ, env, clear=False),
                patch.object(tts, "synthesize_to_path", side_effect=fake_seam),
                patch.object(tts, "ffmpeg_concat_ready", return_value=True),
                patch.object(tts, "_tts_cache_voice", return_value=""),
                patch.object(tts, "segment_audio_duration", return_value=1.0),
                patch("core.tts_char_cap.record_tts_actual", side_effect=recorded.append),
                patch("subprocess.run", side_effect=fake),
            ):
                tts.generate_audio(script, dest, channel_id="tapin")
            self.assertTrue(os.path.isfile(dest))
        self.assertEqual(len(seam_calls), 2, f"re-synthesized after the join: {seam_calls}")
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(len(recorded), 1)
        self.assertLessEqual(recorded[0], len(script), "billed more characters than the script")


@unittest.skipUnless(_has_ffmpeg(), "ffmpeg not installed (required under CI)")
class TestRealFfmpegOnRelativePaths(unittest.TestCase):
    def test_two_tones_join(self) -> None:
        with _in_temp_cwd():
            os.makedirs(_SEG_DIR)
            dest = os.path.join(_SEG_DIR, "tones.mp3")
            segs = []
            for i, freq in enumerate((440, 660)):
                seg = f"{dest}.seg{i}.mp3"
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        f"sine=frequency={freq}:duration=0.3",
                        "-c:a",
                        "libmp3lame",
                        seg,
                    ],
                    capture_output=True,
                    check=True,
                )
                segs.append(seg)
            tts.concat_audio_segments(segs, dest)
            self.assertGreater(os.path.getsize(dest), 0)


if __name__ == "__main__":
    unittest.main()
