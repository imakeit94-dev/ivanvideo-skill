"""Asset provenance, optional video import and editable cover regression tests."""
import importlib.util
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from asset_workflow import prepare, register, registered_asset
from film_core import build_timeline, digest, read, write
from render_covers import cover_html, cover_input, render


@unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg unavailable")
class AssetContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ivanvideo-assets-")
        self.root = Path(self.temp.name).resolve()
        self.config = {"width": 320, "height": 180, "fps": 30, "aspect_ratio": "16:9", "narration": {}}
        self.shots = [{"id": "S01", "start_seconds": 0, "end_seconds": 2,
                       "media": {"type": "image", "path": "source.png"}}]
        write(self.root / "project.json", self.config)
        write(self.root / "storyboard.json", {"shots": self.shots})
        write(self.root / "assets/manifest.json", [{"path": "legacy.mov", "status": "needs_review"}])
        self.plan = {"style": "navy/teal", "assets": [{"id": "A01", "media_type": "image", "role": "illustration",
                     "purpose": "test concept", "shot_ids": ["S01"], "aspect_ratio": "1:1", "prompt": "blank art"}]}
        self.plan_path = self.root / "references/asset-plan.json"
        self.metadata = self.root / "references/result.json"
        write(self.metadata, {"origin": "synthetic_test", "source": "FFmpeg fixture, not AI output", "license": "test only"})
        self.run_ffmpeg("-f", "lavfi", "-i", "color=c=navy:s=64x64", "-frames:v", "1", str(self.root / "source.png"))

    def tearDown(self):
        self.temp.cleanup()

    def run_ffmpeg(self, *args):
        subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True, capture_output=True)

    def request(self):
        write(self.plan_path, self.plan)
        return self.root / prepare(self.root, self.plan_path)[0]["request"]

    def imported(self):
        return register(self.root, self.request(), self.root / "source.png", self.metadata)

    def cover(self):
        self.imported()
        spec = {"title": "素材与封面", "subtitle": "中文排版", "asset_id": "A01",
                "variants": [{"id": name, "width": w, "height": h} for name, w, h in
                             (("wide", 640, 360), ("tall", 360, 640), ("square", 480, 480))]}
        path = self.root / "references/cover.json"
        write(path, spec)
        return path, spec

    def test_prepare_check_writes_nothing_and_missing_reference_is_pending(self):
        self.plan["assets"][0]["reference_images"] = ["missing.png"]
        write(self.plan_path, self.plan)
        result = prepare(self.root, self.plan_path, check=True)
        self.assertFalse(result[0]["ready"])
        self.assertFalse((self.root / "references/asset-requests").exists())
        path = self.request()
        self.assertEqual(read(path)["status"], "planned")
        self.assertFalse((self.root / "assets/media").exists())
        with self.assertRaisesRegex(ValueError, "Reference is missing"):
            register(self.root, path, self.root / "source.png", self.metadata)

    def test_plan_rejects_unknown_shot_duplicate_and_invalid_duration(self):
        self.plan["assets"][0]["shot_ids"] = ["unknown"]
        with self.assertRaises(ValueError): self.request()
        self.plan["assets"][0]["shot_ids"] = []
        self.plan["assets"].append(dict(self.plan["assets"][0]))
        with self.assertRaises(ValueError): self.request()
        self.plan["assets"].pop()
        self.plan["assets"][0]["media_type"] = "video"
        with self.assertRaises(ValueError): self.request()

    def test_import_preserves_legacy_and_verifies_bytes(self):
        item = self.imported()
        self.assertEqual(len(read(self.root / "assets/manifest.json")), 2)
        self.assertEqual(item["provenance"]["origin"], "synthetic_test")
        self.assertEqual(registered_asset(self.root, "A01")["sha256"], digest(self.root / "source.png"))
        (self.root / item["path"]).write_bytes(b"changed")
        with self.assertRaises(ValueError): registered_asset(self.root, "A01")

    def test_modified_request_is_rejected(self):
        item = self.imported()
        write(self.root / item["provenance"]["request_path"], {"edited": True})
        with self.assertRaisesRegex(ValueError, "request changed"):
            registered_asset(self.root, "A01")

    def test_reference_changed_after_prepare_is_rejected(self):
        self.plan["assets"][0]["reference_images"] = ["source.png"]
        path = self.request()
        (self.root / "source.png").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "Reference is missing or changed"):
            register(self.root, path, self.root / "source.png", self.metadata)

    def test_duplicate_import_preserves_existing_files(self):
        item = self.imported()
        before = digest(self.root / "assets/manifest.json")
        with self.assertRaisesRegex(ValueError, "ID already exists"):
            register(self.root, self.request(), self.root / "source.png", self.metadata)
        self.assertEqual(before, digest(self.root / "assets/manifest.json"))
        self.assertTrue((self.root / item["path"]).is_file())

    def test_job_id_or_renamed_still_is_not_a_video(self):
        self.plan["assets"][0].update(media_type="video", duration_seconds=2)
        request = self.request()
        with self.assertRaises(ValueError):
            register(self.root, request, self.root / "job-id-only.mp4", self.metadata)
        shutil.copyfile(self.root / "source.png", self.root / "renamed.mp4")
        with self.assertRaisesRegex(ValueError, "actual video"):
            register(self.root, request, self.root / "renamed.mp4", self.metadata)

    def test_actual_coded_video_import_records_measured_length(self):
        self.plan["assets"][0].update(media_type="video", duration_seconds=2)
        self.run_ffmpeg("-f", "lavfi", "-i", "testsrc2=s=64x64:r=15:d=2", "-c:v", "libx264", str(self.root / "fixture.mp4"))
        item = register(self.root, self.request(), self.root / "fixture.mp4", self.metadata)
        self.assertAlmostEqual(item["media"]["duration_seconds"], 2)
        self.assertEqual(item["media"]["frames"], 30)
        self.assertEqual(item["provenance"]["origin"], "synthetic_test")
        self.assertEqual(registered_asset(self.root, "A01")["media_type"], "video")

    def test_ai_result_requires_actual_provider_and_prompt(self):
        write(self.metadata, {"origin": "ai_generated", "source": "unknown", "license": "unknown", "job_id": "job"})
        with self.assertRaisesRegex(ValueError, "actual provider"):
            register(self.root, self.request(), self.root / "source.png", self.metadata)

    def test_film_binding_and_legacy_compatibility(self):
        self.assertEqual(build_timeline(self.root)["shots"][0]["media"]["type"], "image")
        item = self.imported()
        self.shots[0]["asset_evidence"] = {"id": "A01"}
        write(self.root / "storyboard.json", {"shots": self.shots})
        with self.assertRaisesRegex(ValueError, "differs from its registered"):
            build_timeline(self.root)
        self.shots[0]["media"]["path"] = item["path"]
        write(self.root / "storyboard.json", {"shots": self.shots})
        self.assertEqual(build_timeline(self.root)["shots"][0]["media"]["sha256"], item["sha256"])

    def test_cover_schema_and_escaped_editable_text(self):
        path, spec = self.cover()
        cover_input(self.root, path)
        spec["title"] = "中文 <script> & 标题"
        markup = cover_html(spec, spec["variants"][0], "art.png", "font.woff")
        self.assertIn("中文 &lt;script&gt; &amp; 标题", markup)
        self.assertNotIn("<script>", markup)
        spec["variants"].append(spec["variants"][0]); write(path, spec)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            cover_input(self.root, path)

    @unittest.skipUnless(importlib.util.find_spec("playwright"), "Existing Playwright environment required")
    def test_actual_cover_render_three_ratios_and_no_overwrite(self):
        path, spec = self.cover()
        image_hash = digest(self.root / "source.png")
        directory = self.root / "outputs/covers-v1"
        report = render(self.root, path, directory)
        self.assertEqual(len(report["variants"]), 3)
        for variant in report["variants"]:
            dimensions = struct.unpack(">II", (directory / variant["png"]).read_bytes()[16:24])
            self.assertEqual(dimensions, (variant["width"], variant["height"]))
            self.assertFalse(variant["measurements"]["overflow"])
            self.assertIn("素材与封面", (directory / variant["html"]).read_text())
        self.assertEqual(image_hash, digest(self.root / "source.png"))
        self.assertTrue((directory / "assets/OFL.txt").is_file())
        with self.assertRaisesRegex(ValueError, "output exists"):
            render(self.root, path, directory)

    @unittest.skipUnless(importlib.util.find_spec("playwright"), "Existing Playwright environment required")
    def test_cover_overflow_does_not_publish_output(self):
        path, spec = self.cover()
        spec["title"] = "过长标题" * 1000
        write(path, spec)
        directory = self.root / "outputs/overflow"
        with self.assertRaisesRegex(ValueError, "does not fit"):
            render(self.root, path, directory)
        self.assertFalse(directory.exists())


if __name__ == "__main__":
    unittest.main()
