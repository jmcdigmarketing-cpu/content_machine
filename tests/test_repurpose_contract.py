import inspect
import unittest

from publishing.repurpose import RepurposeResult, enqueue_repurpose_jobs
from publishing.repurpose_format import format_for_platform


class TestRepurposeContract(unittest.TestCase):
    def test_enqueue_signature(self):
        sig = inspect.signature(enqueue_repurpose_jobs)
        for name in (
            "channel_id",
            "content_run_id",
            "file_path",
            "title",
            "description",
        ):
            self.assertIn(name, sig.parameters)

    def test_repurpose_result_defaults(self):
        r = RepurposeResult()
        self.assertEqual(r.jobs, [])
        self.assertEqual(r.platforms, [])

    def test_youtube_format_truncates_title(self):
        long_title = "x" * 200
        fmt = format_for_platform(
            "youtube",
            file_path="/a.mp4",
            title=long_title,
            description="desc",
        )
        self.assertLessEqual(len(fmt.title), 100)


if __name__ == "__main__":
    unittest.main()
