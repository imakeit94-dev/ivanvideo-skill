#!/usr/bin/env python3
"""Render an editable IvanVideo animation shot using the bundled Canvas runtime."""
import argparse
import base64
import copy
import functools
import hashlib
import http.server
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import unquote, urlparse

from animation_spec import normalize, read_json


def project_path(root, value):
    path = (root / value).expanduser().resolve()
    if not path.is_relative_to(root):
        raise ValueError("Generated files must stay inside the video project")
    return path


def load_input(root, args):
    if args.spec:
        path = project_path(root, args.spec)
        return read_json(path), path, path.stem
    config = read_json(root / "project.json")
    if not args.shot or not all(ch.isalnum() or ch in "-_" for ch in args.shot):
        raise ValueError("Shot id must contain only letters, digits, hyphens or underscores")
    shots = read_json(root / "storyboard.json")["shots"]
    matching = [shot for shot in shots if shot.get("id") == args.shot]
    if len(matching) != 1:
        raise ValueError("--shot must match exactly one storyboard shot")
    shot = matching[0]
    if not isinstance(shot.get("animation"), dict):
        raise ValueError("The shot needs an animation object; see references/animation-production.md")
    raw = copy.deepcopy(shot["animation"])
    raw.update(duration=shot["end_seconds"] - shot["start_seconds"],
               width=config["width"], height=config["height"], fps=config["fps"],
               timeline_start_seconds=shot["start_seconds"])
    raw.setdefault("safe", config.get("safe_area", {}))
    path = project_path(root, "src/clips/" + args.shot + ".json")
    # Storyboard media/timing paths are relative to the project; clip paths are relative to the spec.
    timing = config.get("narration", {}).get("timing_path")
    if timing and "timing_file" not in raw:
        raw["timing_file"] = timing
    for item in [raw.get("data", {})] + raw.get("cues", []):
        if item.get("image") and not item["image"].startswith(("data:", "http:", "https:")):
            item["image"] = os.path.relpath((root / item["image"]).expanduser().resolve(), path.parent)
    if raw.get("timing_file"):
        raw["timing_file"] = os.path.relpath((root / raw["timing_file"]).resolve(), path.parent)
    return raw, path, args.shot


def fingerprint(directory):
    result = hashlib.sha256()
    for path in sorted(directory.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            result.update(str(path.relative_to(directory)).encode())
            result.update(path.read_bytes())
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--spec", help="Project-relative clip JSON")
    source.add_argument("--shot", help="Storyboard shot id with an animation object")
    parser.add_argument("--out", help="Project-relative MP4 or still-image directory")
    parser.add_argument("--stills", help="Comma-separated clip-local seconds; renders PNG instead of MP4")
    parser.add_argument("--audio", help="Project-relative voice/music WAV/MP3; silence is padded, video length is preserved")
    parser.add_argument("--qa", action="store_true", help="Run bundled clip QA (requires numpy and Pillow too)")
    parser.add_argument("--check", action="store_true", help="Validate without rendering, copying the engine, or installing dependencies")
    parser.add_argument("--overwrite", action="store_true", help="Explicitly replace this output; prefer a new version after approval")
    args = parser.parse_args()
    root = args.project.expanduser().resolve()
    raw, source_path, label = load_input(root, args)
    spec = normalize(raw, source_path.parent)
    count = round(spec["duration"] * spec["fps"])
    if args.check:
        print(json.dumps({"valid": True, "grammar": spec["grammar"], "frames": count,
                          "cue_times": [q["at"] for q in spec["cues"]]}, ensure_ascii=False))
        return 0
    times = [float(x) for x in args.stills.split(",")] if args.stills else []
    if any(not 0 <= t < spec["duration"] for t in times):
        raise ValueError("Still times must lie within [0, duration)")
    output = project_path(root, args.out or (f"previews/{label}-frames" if times else f"previews/{label}.mp4"))
    if output.exists() and not args.overwrite:
        raise ValueError("Output exists; choose a new version or use --overwrite")
    if not times and output.suffix.lower() != ".mp4":
        raise ValueError("This renderer exports H.264 MP4; use custom compositing for other formats")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ValueError("FFmpeg and FFprobe are required; no software has been installed")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ValueError("Playwright is unavailable. Use an existing environment or uv run --with playwright (add numpy and pillow for --qa)") from exc
    if args.qa:
        for package in ("numpy", "pillow"):
            try:
                importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError as exc:
                raise ValueError("--qa needs numpy and pillow in this Python environment") from exc
    audio = project_path(root, args.audio) if args.audio else None
    if audio and not audio.is_file():
        raise ValueError("Audio file not found: " + str(audio))
    engine = root / "src/animation-engine"
    bundle = Path(__file__).resolve().parents[1] / "assets/animation-engine"
    if not engine.exists():
        if not bundle.is_dir():
            raise ValueError("The project has no engine snapshot and the bundled runtime is unavailable")
        shutil.copytree(bundle, engine)
    if not (engine / "clip.html").is_file():
        raise ValueError("Project animation-engine is incomplete; existing sources were preserved")
    runtime = root / "scripts/ivanvideo_runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    for name in ("render_animation.py", "animation_spec.py", "validate_video_project.py", "check_video.py",
                 "film_core.py", "compile_timeline.py", "mix_audio.py", "render_film.py",
                 "narrate.py", "schedule_narration.py", "capture_web.py", "asset_workflow.py", "render_covers.py",
                 "broll.py", "build_broll_preview.py", "deliver_broll.py"):
        source_script = Path(__file__).with_name(name)
        target = runtime / name
        if not target.exists():
            shutil.copy2(source_script, target)
    if args.shot:
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    browser_spec = copy.deepcopy(spec)
    allowed = {}
    for item in [browser_spec.get("data", {})] + browser_spec["cues"]:
        image = item.get("image")
        if image and not image.startswith("data:"):
            alias = f"/__media__/{len(allowed)}"
            allowed[alias] = Path(image)
            item["image"] = alias

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def translate_path(self, url):
            path = unquote(urlparse(url).path)
            if path in allowed:
                return str(allowed[path])
            target = (engine / path.lstrip("/")).resolve()
            return str(target) if target.is_relative_to(engine) else str(engine / "__not_found__")

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(engine)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    warnings, errors = [], []
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with sync_playwright() as playwright:
            with playwright.chromium.launch() as browser:
                browser_version = browser.version
                page = browser.new_page(viewport={"width": spec["width"], "height": spec["height"]}, device_scale_factor=1)
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else warnings.append(msg.text) if msg.type == "warning" else None)
                page.add_init_script("window.CLIP_SPEC = " + json.dumps(browser_spec, ensure_ascii=False) + ";")
                page.goto(f"http://127.0.0.1:{server.server_address[1]}/clip.html?render=1")
                page.wait_for_function("window.__ready === true || !!window.__bootFailed", timeout=60000)
                boot = page.evaluate("window.__bootFailed || null")
                if boot or errors:
                    raise ValueError("Animation boot failed: " + str(boot or errors))
                grab = "async t => { await window.prepare(t); window.renderFrame(t); return window.__canvas.toDataURL('image/png').split(',')[1]; }"
                if times:
                    output.mkdir(parents=True, exist_ok=True)
                    for t in times:
                        pixels = base64.b64decode(page.evaluate(grab, t))
                        (output / f"t{t:07.3f}.png").write_bytes(pixels)
                else:
                    with tempfile.NamedTemporaryFile(suffix=".mp4", dir=output.parent, delete=False) as temp:
                        temp_path = Path(temp.name)
                    command = [ffmpeg, "-y", "-v", "error", "-f", "image2pipe", "-framerate", str(spec["fps"]), "-c:v", "png", "-i", "-"]
                    if audio:
                        command += ["-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-af", f"apad,atrim=duration={count / spec['fps']}", "-c:a", "aac"]
                    command += ["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-g", str(spec["fps"]), "-movflags", "+faststart", str(temp_path)]
                    with subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE) as encoder:
                        try:
                            for index in range(count):
                                encoder.stdin.write(base64.b64decode(page.evaluate(grab, index / spec["fps"])))
                            encoder.stdin.close()
                        except Exception:
                            encoder.kill()
                            raise
                        message = encoder.stderr.read().decode(errors="replace")
                        if encoder.wait() != 0:
                            raise ValueError("FFmpeg encoding failed: " + message)
                    info = json.loads(subprocess.check_output([ffprobe, "-v", "error", "-count_frames", "-show_streams", "-of", "json", str(temp_path)]))
                    stream = next(s for s in info["streams"] if s["codec_type"] == "video")
                    if stream["codec_name"] != "h264" or int(stream["nb_read_frames"]) != count or [stream["width"], stream["height"]] != [spec["width"], spec["height"]]:
                        raise ValueError("Encoded video does not match the planned dimensions/codec/frame count")
                    if errors:
                        raise ValueError("Animation runtime errors: " + str(errors))
                    temp_path.replace(output)
        if errors:
            raise ValueError("Animation runtime errors: " + str(errors))
    finally:
        server.shutdown()
        server.server_close()
        if temp_path and temp_path.exists():
            temp_path.unlink()
    qa_dir = output.parent / (output.stem + "-qa")
    qa = None
    if args.qa:
        qa_dir.mkdir(parents=True, exist_ok=True)
        qa_spec = copy.deepcopy(spec)
        qa_spec.pop("timing_file", None)
        for item in [qa_spec.get("data", {})] + qa_spec["cues"]:
            if item.get("image") and not item["image"].startswith("data:"):
                item["image"] = os.path.relpath(item["image"], qa_dir)
        qa_input = qa_dir / "resolved-spec.json"
        qa_input.write_text(json.dumps(qa_spec, ensure_ascii=False, indent=2), encoding="utf-8")
        subprocess.run([sys.executable, str(engine / "qa.py"), "--project", str(engine), "--spec", str(qa_input), "--out", str(qa_dir)], check=True)
        qa = read_json(qa_dir / "qa.json")
    record = {"spec": str(source_path.relative_to(root)), "output": str(output.relative_to(root)),
              "grammar": spec["grammar"], "frames": count, "fps": spec["fps"],
              "engine_sha256": fingerprint(engine), "warnings": warnings,
              "spec_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
              "renderer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "cue_times": [q["at"] for q in spec["cues"]], "audio": args.audio,
              "qa": str(qa_dir.relative_to(root)) if qa else None,
              "runtime": {"python": sys.version.split()[0], "playwright": importlib.metadata.version("playwright"),
                          "chromium": browser_version, "ffmpeg": subprocess.check_output([ffmpeg, "-version"], text=True).splitlines()[0]}}
    record_path = output.parent / (output.stem + ".render.json")
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if qa and any(not segment["deterministic"] for segment in qa["segments"]):
        raise ValueError("QA detected non-deterministic frames; inspect the report before approval")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print("IvanVideo: " + str(error), file=sys.stderr)
        raise SystemExit(2)
