"""Measured narration, revision and capture-provenance regression tests."""
import json
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from capture_web import load_spec
from film_core import build_timeline, digest, read, write
from narrate import generate, verify_manifest
from schedule_narration import apply_schedule, plan_schedule


@unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg unavailable")
class NarrationContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ivanvideo-narration-")
        self.root = Path(self.temp.name)
        self.config = {"title": "test", "width": 320, "height": 180, "fps": 30, "aspect_ratio": "16:9",
                       "duration_seconds": None, "narration": {}, "output": {"container": "mp4", "video_codec": "h264"}}
        self.shots = [{"id": f"S{i}", "start_seconds": (i - 1) * 2, "end_seconds": i * 2, "narration": text,
                       "media": {"type": "image", "path": "image.ppm"}, "audio_cues": []}
                      for i, text in ((1, "第一句。"), (2, "第二句。"))]
        self.script = {"provider": "provided", "segments": [
            {"id": "v1", "shot_id": "S1", "text": "第一句。", "audio_path": "voice1.wav"},
            {"id": "v2", "shot_id": "S2", "text": "第二句。", "audio_path": "voice2.wav"}]}
        (self.root / "image.ppm").write_bytes(b"P6\n2 2\n255\n" + bytes([30, 50, 120]) * 4)
        self.tone("voice1.wav", 0.5)
        self.tone("voice2.wav", 1.0)
        self.script_path = self.root / "scripts/narration.json"
        self.manifest_path = self.root / "audio/tts/manifest.json"
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def tone(self, name, seconds):
        with wave.open(str(self.root / name), "wb") as handle:
            handle.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
            handle.writeframes(b"".join(struct.pack("<h", int(500 * math.sin(i * 2 * math.pi * 440 / 48000))) for i in range(round(seconds * 48000))))

    def save(self):
        write(self.root / "project.json", self.config)
        write(self.root / "storyboard.json", {"shots": self.shots})
        write(self.script_path, self.script)

    def plan(self, resize=False):
        generate(self.root, self.script_path)
        return plan_schedule(self.root, self.script_path, self.manifest_path, resize)

    def test_duration_cache_and_one_segment_change(self):
        a = generate(self.root, self.script_path)
        self.assertEqual(a["cache_hits"], 0)
        self.assertEqual(generate(self.root, self.script_path)["cache_hits"], 2)
        old = read(self.manifest_path)
        self.tone("voice2.wav", 1.3)
        self.assertEqual(generate(self.root, self.script_path)["cache_hits"], 1)
        new = read(self.manifest_path)
        self.assertEqual(old["segments"][0]["path"], new["segments"][0]["path"])
        self.assertEqual(new["segments"][1]["audio"]["duration_seconds"], 1.3)

    def test_preview_does_not_modify_authoring_and_apply_keeps_content(self):
        before = (self.root / "storyboard.json").read_bytes()
        plan = self.plan()
        self.assertEqual(before, (self.root / "storyboard.json").read_bytes())
        self.assertAlmostEqual(plan["project"]["duration_seconds"], 3.1)
        self.assertTrue(apply_schedule(self.root, plan))
        self.assertTrue(list((self.root / "references/narration-revisions").glob("*/before/storyboard.json")))
        for old, new in zip(self.shots, read(self.root / "storyboard.json")["shots"]):
            self.assertEqual(old["media"], new["media"])
            self.assertEqual(old["narration"], new["narration"])
        self.assertEqual(build_timeline(self.root)["frames"], 93)
        for caption, part in zip(plan["timing"]["segments"], read(self.manifest_path)["segments"]):
            self.assertAlmostEqual(caption["end_seconds"] - caption["start_seconds"], part["audio"]["duration_seconds"])
        second = plan_schedule(self.root, self.script_path, self.manifest_path)
        self.assertFalse(apply_schedule(self.root, second))

    def test_fresh_timed_animation_compiles_without_clip_directory(self):
        self.shots[0].pop("media")
        self.shots[0]["animation"] = {"grammar": "t2_keynote_ui", "data": {"title": "test"},
                                      "cues": [{"anchor": {"id": "v1"}, "kind": "title"}]}
        self.save()
        apply_schedule(self.root, self.plan())
        self.assertEqual(build_timeline(self.root)["shots"][0]["media"]["type"], "animation")
        self.assertFalse((self.root / "src/clips").exists())

    def test_script_change_invalidates_render_inputs(self):
        apply_schedule(self.root, self.plan())
        self.script["segments"][0]["text"] = "修改过的第一句。"
        write(self.script_path, self.script)
        with self.assertRaisesRegex(ValueError, "script changed"):
            build_timeline(self.root)

    def test_provided_source_and_storyboard_text_changes_are_rejected(self):
        apply_schedule(self.root, self.plan())
        self.tone("voice1.wav", 0.8)
        with self.assertRaisesRegex(ValueError, "Provided narration source changed"):
            build_timeline(self.root)
        self.tone("voice1.wav", 0.5)
        board = read(self.root / "storyboard.json")
        board["shots"][0]["narration"] = "新文案。"
        write(self.root / "storyboard.json", board)
        with self.assertRaisesRegex(ValueError, "Storyboard narration changed"):
            build_timeline(self.root)
        board["shots"][0].update(id="renamed", narration="")
        write(self.root / "storyboard.json", board)
        with self.assertRaisesRegex(ValueError, "unknown storyboard shot"):
            build_timeline(self.root)

    def test_track_shift_invalidates_sentence_sync(self):
        apply_schedule(self.root, self.plan())
        config = read(self.root / "project.json")
        config["audio"]["tracks"][0]["at_seconds"] += 0.1
        write(self.root / "project.json", config)
        with self.assertRaisesRegex(ValueError, "no longer match"):
            build_timeline(self.root)

    def test_fixed_duration_budget_and_explicit_resize(self):
        self.config["duration_seconds"] = 2
        self.save()
        generate(self.root, self.script_path)
        with self.assertRaisesRegex(ValueError, "exceeds requested"):
            plan_schedule(self.root, self.script_path, self.manifest_path)
        self.assertAlmostEqual(plan_schedule(self.root, self.script_path, self.manifest_path, True)["project"]["duration_seconds"], 3.1)
        self.config["duration_seconds"] = 6
        self.save()
        self.assertEqual(self.plan()["project"]["duration_seconds"], 6)

    def test_fade_reflow_and_segment_order(self):
        self.shots[1]["transition_in"] = {"from": "S1", "duration_seconds": 0.2}
        self.save()
        plan = self.plan()
        apply_schedule(self.root, plan)
        self.assertEqual(build_timeline(self.root)["shots"][1]["overlap_frames"], 6)
        self.script["segments"].reverse()
        self.save()
        generate(self.root, self.script_path)
        with self.assertRaisesRegex(ValueError, "storyboard order"):
            plan_schedule(self.root, self.script_path, self.manifest_path)

    def test_reject_approved_text_mismatch_and_duplicate_ids(self):
        self.shots[0]["narration"] = "不同文案。"
        self.save()
        with self.assertRaisesRegex(ValueError, "reconcile"):
            self.plan()
        self.script["segments"][1]["id"] = "v1"
        write(self.script_path, self.script)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            generate(self.root, self.script_path)

    def test_apply_rolls_back_on_verification_failure(self):
        plan = self.plan()
        before = {name: (self.root / name).read_bytes() for name in ("project.json", "storyboard.json")}
        with patch("film_core.verify_generated_narration", side_effect=ValueError("injected failure")):
            with self.assertRaisesRegex(ValueError, "injected"):
                apply_schedule(self.root, plan)
        self.assertEqual(before, {name: (self.root / name).read_bytes() for name in before})
        self.assertFalse((self.root / "audio/narration-timing.json").exists())

    def test_corrupt_cache_is_rejected(self):
        generate(self.root, self.script_path)
        part = read(self.manifest_path)["segments"][0]
        with (self.root / part["path"]).open("ab") as handle:
            handle.write(b"changed")
        with self.assertRaisesRegex(ValueError, "Cached narration changed"):
            generate(self.root, self.script_path)

    def test_capture_reference_hash_checks(self):
        spec = {"url": "http://127.0.0.1:1234", "product": "fixture", "version": "test", "platform": "browser", "feature": "view", "steps": [{"id": "view", "action": "capture"}]}
        write(self.root / "scripts/capture.json", spec)
        load_spec(self.root / "scripts/capture.json")
        report = {"display_mode": "real_capture", "spec_path": "scripts/capture.json", "spec_sha256": digest(self.root / "scripts/capture.json"),
                  "assets": [{"id": "view", "type": "image", "path": "image.ppm", "sha256": digest(self.root / "image.ppm")}]}
        write(self.root / "references/capture.json", report)
        self.shots[0]["capture_evidence"] = {"report": "references/capture.json", "asset_id": "view"}
        self.save()
        self.assertIn("capture-S1", build_timeline(self.root)["dependencies"])
        spec["feature"] = "different"
        write(self.root / "scripts/capture.json", spec)
        with self.assertRaisesRegex(ValueError, "Capture specification changed"):
            build_timeline(self.root)
        spec["steps"][0]["id"] = "recording"
        write(self.root / "scripts/capture.json", spec)
        with self.assertRaisesRegex(ValueError, "reserved"):
            load_spec(self.root / "scripts/capture.json")

    @unittest.skipUnless(shutil.which("say"), "macOS say unavailable")
    def test_installed_chinese_tts_and_cache(self):
        if not any(line.startswith("Tingting ") for line in subprocess.check_output(["say", "-v", "?"], text=True).splitlines()):
            self.skipTest("Tingting voice is not installed")
        self.script = {"provider": "macos", "voice": "Tingting", "rate_wpm": 195,
                       "segments": [{"id": "v1", "shot_id": "S1", "text": "你好，世界。"}]}
        write(self.script_path, self.script)
        first = generate(self.root, self.script_path)
        self.assertEqual(first["cache_hits"], 0)
        manifest = verify_manifest(self.root, self.manifest_path, self.script_path)
        self.assertGreater(manifest["segments"][0]["audio"]["samples"], 0)
        self.assertEqual(generate(self.root, self.script_path)["cache_hits"], 1)


if __name__ == "__main__":
    unittest.main()
