"""Contract and FFmpeg smoke tests; run with python3 -m unittest discover -s tests -v."""
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from film_core import audio_plan, build_timeline, write
from mix_audio import create_mix, verify_mix


class FilmContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ivanvideo-test-")
        self.root = Path(self.temp.name)
        self.config = {"title": "test", "width": 320, "height": 180, "fps": 30, "aspect_ratio": "16:9",
                       "duration_seconds": 2, "output": {"container": "mp4", "video_codec": "h264"},
                       "narration": {"enabled": False}}
        (self.root / "image.ppm").write_bytes(b"P6\n2 2\n255\n" + bytes([20, 70, 120]) * 4)
        self.shots = [self.shot("S01", 0, 1), self.shot("S02", 1, 2)]
        write(self.root / "assets/manifest.json", [])
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def shot(self, name, start, end):
        return {"id": name, "start_seconds": start, "end_seconds": end, "purpose": "test", "visual": "test",
                "motion": "hold", "on_screen_text": [], "narration": "", "audio_cues": [], "assets": [], "source_notes": [],
                "media": {"type": "image", "path": "image.ppm"}}

    def save(self):
        write(self.root / "project.json", self.config)
        write(self.root / "storyboard.json", {"shots": self.shots})

    def test_absolute_boundaries_no_accumulated_rounding(self):
        self.shots = [self.shot(f"S{i}", i / 7, (i + 1) / 7) for i in range(14)]
        self.save()
        film = build_timeline(self.root)
        self.assertEqual(sum(s["frames"] for s in film["shots"]), 60)
        self.assertTrue(all(a["end_frame"] == b["start_frame"] for a, b in zip(film["shots"], film["shots"][1:])))

    def test_legacy_animation_schema(self):
        for s in self.shots:
            del s["media"]
            s["animation"] = {"grammar": "t2_keynote_ui", "data": {"title": "test"}, "cues": [{"at": 0, "kind": "title"}]}
        self.save()
        self.assertEqual(build_timeline(self.root)["frames"], 60)

    def test_matching_overlap_and_fade(self):
        self.shots[1]["start_seconds"] = 0.8
        self.shots[1]["transition_in"] = {"from": "S01", "duration_seconds": 0.2}
        self.save()
        self.assertEqual(build_timeline(self.root)["shots"][1]["overlap_frames"], 6)

    def test_reject_gaps_unmarked_overlap_and_unsupported_transition(self):
        for start, transition in ((1.1, None), (0.8, None), (0.8, {"from": "S01", "duration_seconds": 0.2, "type": "wipe"})):
            with self.subTest(start=start, transition=transition):
                self.shots[1]["start_seconds"] = start
                self.shots[1].pop("transition_in", None)
                if transition:
                    self.shots[1]["transition_in"] = transition
                self.save()
                with self.assertRaises(ValueError):
                    build_timeline(self.root)

    def test_reject_media_animation_ambiguity(self):
        self.shots[0]["animation"] = {}
        self.save()
        with self.assertRaises(ValueError):
            build_timeline(self.root)

    def test_reject_nan_and_odd_dimensions(self):
        for key, value in (("fps", math.nan), ("width", 321)):
            original = self.config[key]
            self.config[key] = value
            (self.root / "project.json").write_text(json.dumps(self.config))
            with self.assertRaises(ValueError):
                build_timeline(self.root)
            self.config[key] = original

    def test_missing_media(self):
        self.shots[0]["media"]["path"] = "missing.mp4"
        self.save()
        with self.assertRaises(ValueError):
            build_timeline(self.root)

    def test_subtitle_intervals_and_duplicate_ids(self):
        self.config["subtitles"] = {"enabled": True, "timing_path": "audio/timing.json"}
        segment = {"id": "v1", "text": "字幕", "start_seconds": 0, "end_seconds": 1}
        write(self.root / "audio/timing.json", {"method": "draft", "segments": [segment]})
        self.save()
        self.assertEqual(len(build_timeline(self.root)["captions"]), 1)
        write(self.root / "audio/timing.json", {"method": "draft", "segments": [segment, segment]})
        with self.assertRaises(ValueError):
            build_timeline(self.root)

    def test_source_hash_changes_timeline(self):
        first = build_timeline(self.root)["fingerprint"]
        with (self.root / "image.ppm").open("ab") as handle:
            handle.write(b"\n")
        self.assertNotEqual(first, build_timeline(self.root)["fingerprint"])

    def test_reject_non_integer_sample_rate(self):
        self.config["audio"] = {"sample_rate": 48000.0}
        self.save()
        with self.assertRaisesRegex(ValueError, "sample_rate"):
            audio_plan(self.root, build_timeline(self.root))

    def test_original_initializer_and_validator(self):
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        for ratio, size in (("16:9", (1920, 1080)), ("9:16", (1080, 1920)), ("1:1", (1080, 1080))):
            target = self.root / ratio.replace(":", "-")
            subprocess.run([sys.executable, str(scripts / "init_video_project.py"), str(target), "--aspect-ratio", ratio], check=True, capture_output=True)
            value = json.loads((target / "project.json").read_text())
            self.assertEqual((value["width"], value["height"]), size)
            subprocess.run([sys.executable, str(scripts / "validate_video_project.py"), str(target)], check=True, capture_output=True)
        # Existing configurations with no new fields still validate.
        self.save()
        subprocess.run([sys.executable, str(scripts / "validate_video_project.py"), str(self.root), "--delivery"], check=True, capture_output=True)

    def tone(self):
        with wave.open(str(self.root / "tone.wav"), "wb") as handle:
            handle.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
            handle.writeframes(b"".join(struct.pack("<h", int(1500 * math.sin(i * 2 * math.pi * 440 / 48000))) for i in range(24000)))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg tools unavailable")
    def test_mix_measured_duration_cache_and_stale_rejection(self):
        self.tone()
        self.config["audio"] = {"tracks": [{"id": "v", "role": "voice", "path": "tone.wav", "at_seconds": 0.3},
                                            {"id": "m", "role": "music", "path": "tone.wav", "at_seconds": 0.3}],
                                "ducking": {"enabled": True}, "normalization": {"integrated_lufs": -20, "true_peak_db": -2}}
        self.save()
        timeline = build_timeline(self.root)
        target = self.root / "audio/mix-test"
        master, report = create_mix(self.root, timeline, target)
        self.assertTrue(master.is_file())
        self.assertEqual(report["plan"]["tracks"][0]["duration_seconds"], 0.5)
        self.assertIsNotNone(report["normalization_result"])
        self.assertEqual(verify_mix(self.root, timeline, target)[0], master)
        self.assertEqual(create_mix(self.root, timeline, target)[0], master)
        self.config["audio"]["tracks"][0]["gain_db"] = -2
        self.save()
        with self.assertRaisesRegex(ValueError, "stale"):
            verify_mix(self.root, build_timeline(self.root), target)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg tools unavailable")
    def test_reject_audio_beyond_end_and_negative_cue_start(self):
        self.tone()
        self.config["audio"] = {"tracks": [{"id": "m", "role": "music", "path": "tone.wav", "at_seconds": 1.8}]}
        self.save()
        with self.assertRaisesRegex(ValueError, "past film"):
            audio_plan(self.root, build_timeline(self.root))
        self.config.pop("audio")
        self.shots[0]["audio_cues"] = [{"path": "tone.wav", "offset_seconds": 0, "sync_offset_seconds": 0.1}]
        self.save()
        with self.assertRaises(ValueError):
            audio_plan(self.root, build_timeline(self.root))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg tools unavailable")
    def test_real_render_fade_then_cut_and_cut_then_fade(self):
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        self.config["duration_seconds"] = 3
        for i, rgb in enumerate(((255, 0, 0), (0, 255, 0), (0, 0, 255))):
            (self.root / f"color{i}.ppm").write_bytes(b"P6\n2 2\n255\n" + bytes(rgb) * 4)
        for sequence in ("fade-cut", "cut-fade"):
            with self.subTest(sequence=sequence):
                boundaries = ((0, 1.2), (1, 2), (2, 3)) if sequence == "fade-cut" else ((0, 1), (1, 2.2), (2, 3))
                self.shots = [self.shot(f"S{i}", a, b) for i, (a, b) in enumerate(boundaries)]
                for i, shot in enumerate(self.shots):
                    shot["media"]["path"] = f"color{i}.ppm"
                incoming = 1 if sequence == "fade-cut" else 2
                self.shots[incoming]["transition_in"] = {"from": f"S{incoming - 1}", "duration_seconds": 0.2}
                self.save()
                result = subprocess.run([sys.executable, str(scripts / "render_film.py"), str(self.root), "--out", f"outputs/{sequence}.mp4"], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads((self.root / f"outputs/{sequence}.film.json").read_text())
                self.assertEqual(report["timeline"]["frames"], 90)
                self.assertTrue(report["checks"]["full_decode"])
                for second, channel in ((0.5, 0), (1.5, 1), (2.5, 2)):
                    pixels = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", str(second), "-i", str(self.root / f"outputs/{sequence}.mp4"),
                                                      "-frames:v", "1", "-vf", "format=rgb24,crop=1:1:160:90", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
                    self.assertGreater(pixels[channel], 200)
                    self.assertTrue(all(v < 30 for i, v in enumerate(pixels) if i != channel))


if __name__ == "__main__":
    unittest.main()
