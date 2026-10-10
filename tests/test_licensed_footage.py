"""#1040 licensed footage: footage-add must not rewrite a folder licence, and a
recorded Commons / Internet Archive / CC0 search only saves a commercial licence.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from assets import clip_ingest


def _commons_page(
    licence: str | None, *, url: str = "https://upload.wikimedia.org/ex.webm"
) -> dict:
    meta: dict = {}
    if licence is not None:
        meta["LicenseShortName"] = {"value": licence}
        meta["Artist"] = {"value": "Ada Lovelace"}
    return {
        "query": {
            "pages": {
                "1": {
                    "title": "File:Example clip.webm",
                    "imageinfo": [
                        {
                            "url": url,
                            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Example_clip.webm",
                            "extmetadata": meta,
                        }
                    ],
                }
            }
        }
    }


def _archive_doc(licenseurl: str | None) -> dict:
    doc: dict = {
        "identifier": "nasa-launch",
        "title": "Launch",
        "creator": "NASA",
        "downloads": ["https://archive.org/download/nasa-launch/launch.mp4"],
    }
    if licenseurl is not None:
        doc["licenseurl"] = licenseurl
    return {"response": {"docs": [doc]}}


def _nasa_item(*, rights: str = "") -> dict:
    data = {"title": "Apollo liftoff", "nasa_id": "apollo", "media_type": "video", "center": "JSC"}
    if rights:
        data["rights"] = rights
    return {
        "collection": {
            "items": [
                {
                    "data": [data],
                    "links": [
                        {
                            "href": "https://images-assets.nasa.gov/video/apollo/apollo~orig.mp4",
                            "rel": "canonical",
                        }
                    ],
                }
            ]
        }
    }


class TestFootageAddKeepsFolderLicence(unittest.TestCase):
    """2026-09-20: Fortnite (owned) and Marvel Rivals (owned) would have been
    labelled third-party because footage-add rewrote the folder license string.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.lib = os.path.join(self.root, "lib")
        self.folder = os.path.join(self.lib, "gaming", "other", "Fortnite")
        os.makedirs(self.folder)
        Path(self.folder, "owned.mp4").write_bytes(b"owned")
        self.folder_licence = {
            "license": "owned gameplay (operator capture)",
            "owner": "operator",
            "commercial_use": True,
            "sources": ["xbox capture"],
        }
        Path(self.folder, "license.yaml").write_text(
            json.dumps(self.folder_licence), encoding="utf-8"
        )
        self.src = os.path.join(self.root, "download.mp4")
        Path(self.src).write_bytes(b"incoming")

    def _add(self):
        def fake_remux(src, dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(src, dest)

        with (
            patch.object(clip_ingest, "_remux_muted_h264", side_effect=fake_remux),
            patch.object(clip_ingest, "_record_index"),
        ):
            return clip_ingest.add_footage(
                self.src,
                game="Fortnite",
                source_url="https://example.org/cc-by-clip",
                licence="CC BY 4.0",
                library_root=self.lib,
                apply=True,
            )

    def test_owned_folder_licence_is_not_replaced(self):
        row = self._add()
        self.assertEqual(row.status, "copied", row)
        with open(os.path.join(self.folder, "license.yaml"), encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(saved["license"], "owned gameplay (operator capture)")
        self.assertIn("xbox capture", saved["sources"])
        self.assertIn("https://example.org/cc-by-clip", saved["sources"])

    def test_incoming_file_gets_its_own_sidecar(self):
        row = self._add()
        self.assertEqual(row.status, "copied", row)
        sidecar = os.path.splitext(row.dest or "")[0] + ".license.yaml"
        self.assertTrue(os.path.isfile(sidecar), sidecar)
        with open(sidecar, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(saved["license"], "CC BY 4.0")
        self.assertEqual(saved["commercial_use"], True)
        self.assertIn("https://example.org/cc-by-clip", saved["sources"])
        self.assertTrue(str(saved.get("owner") or "").strip())


class TestFileSidecarBeatsFolderLicence(unittest.TestCase):
    def test_clip_credit_uses_the_file_licence(self):
        from assets.local_provider import clip_credit

        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "Fortnite")
            os.makedirs(folder)
            clip = os.path.join(folder, "mixed.mp4")
            Path(clip).write_bytes(b"x")
            Path(folder, "license.yaml").write_text(
                json.dumps(
                    {
                        "license": "owned gameplay (operator capture)",
                        "owner": "operator",
                        "commercial_use": True,
                        "sources": [],
                    }
                ),
                encoding="utf-8",
            )
            Path(folder, "mixed.license.yaml").write_text(
                json.dumps(
                    {
                        "license": "CC BY 4.0",
                        "owner": "Ada",
                        "commercial_use": True,
                        "sources": ["https://example.org/cc-by-clip"],
                    }
                ),
                encoding="utf-8",
            )
            with patch("assets.local_provider.BASE_VIDEO_DIR", tmp):
                line = clip_credit(clip)
        self.assertIsNotNone(line)
        self.assertIn("CC BY 4.0", line or "")
        self.assertNotIn("owned gameplay", line or "")


class TestLicensedSearch(unittest.TestCase):
    def setUp(self):
        from assets.licensed_intake import (
            archive_hits,
            cc0_hits,
            commons_hits,
            refuse_reason,
        )

        self.commons_hits = commons_hits
        self.archive_hits = archive_hits
        self.cc0_hits = cc0_hits
        self.refuse_reason = refuse_reason

    def test_commons_cc_by_is_accepted(self):
        hits = self.commons_hits(_commons_page("CC BY 4.0"))
        self.assertEqual(len(hits), 1)
        self.assertEqual(self.refuse_reason(hits[0]), "")
        self.assertEqual(hits[0].licence, "CC BY 4.0")
        self.assertIn("commons.wikimedia.org", hits[0].source_url)

    def test_commons_noncommercial_is_refused(self):
        hits = self.commons_hits(_commons_page("CC BY-NC-SA 4.0"))
        self.assertEqual(len(hits), 1)
        self.assertIn("non-commercial", self.refuse_reason(hits[0]))

    def test_commons_missing_licence_is_refused(self):
        hits = self.commons_hits(_commons_page(None))
        self.assertEqual(len(hits), 1)
        self.assertIn("missing", self.refuse_reason(hits[0]))

    def test_archive_public_domain_is_accepted(self):
        hits = self.archive_hits(_archive_doc("https://creativecommons.org/publicdomain/zero/1.0/"))
        self.assertEqual(self.refuse_reason(hits[0]), "")
        self.assertIn("publicdomain/zero", hits[0].licence)

    def test_archive_noncommercial_is_refused(self):
        hits = self.archive_hits(_archive_doc("https://creativecommons.org/licenses/by-nc/4.0/"))
        self.assertIn("non-commercial", self.refuse_reason(hits[0]))

    def test_archive_missing_licence_is_refused(self):
        hits = self.archive_hits(_archive_doc(None))
        self.assertIn("missing", self.refuse_reason(hits[0]))

    def test_nasa_public_domain_is_accepted(self):
        hits = self.cc0_hits(_nasa_item())
        self.assertEqual(self.refuse_reason(hits[0]), "")
        self.assertIn("Public domain", hits[0].licence)
        self.assertTrue(hits[0].commercial_use)

    def test_nasa_copyright_is_refused(self):
        hits = self.cc0_hits(_nasa_item(rights="Copyright 2020 example studio"))
        self.assertIn("copyright", self.refuse_reason(hits[0]).lower())


class TestLicensedIngest(unittest.TestCase):
    def test_a_windows_bom_fixture_is_read(self):
        from assets.licensed_intake import ingest_fixture

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "search.json")
            Path(path).write_bytes(
                b"\xef\xbb\xbf" + json.dumps(_commons_page("CC0")).encode("utf-8")
            )
            rows = ingest_fixture(
                path,
                catalogue="commons",
                niche="AI Development",
                subject="robots",
                library_root=os.path.join(tmp, "lib"),
                index_path=os.path.join(tmp, "clip_index.json"),
                apply=False,
            )
        self.assertEqual(rows[0].status, "matched", rows[0].reason)

    def test_refused_hit_writes_nothing_and_accepted_hit_is_indexed(self):
        from assets.licensed_intake import commons_hits, ingest_accepted

        accepted = commons_hits(_commons_page("CC0"))[0]
        refused = commons_hits(
            _commons_page("CC BY-NC 4.0", url="https://upload.wikimedia.org/nc.webm")
        )[0]
        with tempfile.TemporaryDirectory() as tmp:
            library = os.path.join(tmp, "backgrounds")
            index = os.path.join(tmp, "clip_index.json")
            rows = ingest_accepted(
                [accepted, refused],
                niche="AI Development",
                subject="robots",
                library_root=library,
                bodies={accepted.download_url: b"cc0-bytes"},
                index_path=index,
            )
            self.assertEqual([r.status for r in rows], ["copied", "failed"])
            self.assertIn("non-commercial", rows[1].reason)
            saved = list(Path(library).rglob("*.mp4")) + list(Path(library).rglob("*.webm"))
            self.assertEqual(len(saved), 1)
            self.assertIn("AI Development", saved[0].parts)
            self.assertIn("robots", saved[0].parts)
            sidecar = saved[0].with_suffix(".license.yaml")
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(meta["license"], "CC0")
            self.assertEqual(meta["commercial_use"], True)
            self.assertTrue(meta["sources"])
            index_data = json.loads(Path(index).read_text(encoding="utf-8"))
            self.assertIn(str(saved[0]), index_data["clips"])
            self.assertFalse(any("nc" in p.name.lower() for p in Path(library).rglob("*")))


if __name__ == "__main__":
    unittest.main()
