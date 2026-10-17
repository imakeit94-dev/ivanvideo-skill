#!/usr/bin/env python3
"""Capture a running web UI with explicit interactions, assertions and provenance."""
import argparse
from datetime import datetime, timezone
import json
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from film_core import digest, finite, keys, local, output_path, probe, read, run, tool, write


def load_spec(path):
    spec = read(path)
    keys(spec, ("url", "product", "version", "platform", "feature", "sources", "viewport", "record_video", "steps"), "capture spec")
    if not isinstance(spec.get("url"), str) or urlparse(spec["url"]).scheme not in ("http", "https"):
        raise ValueError("Capture needs an explicit HTTP(S) URL")
    for name in ("product", "version", "platform", "feature"):
        if not isinstance(spec.get(name), str) or not spec[name].strip():
            raise ValueError("Capture needs " + name + "; use 'unknown' rather than invent a version")
    if not isinstance(spec.get("sources", []), list) or not all(isinstance(x, str) for x in spec.get("sources", [])):
        raise ValueError("sources must be an array of strings")
    viewport = spec.get("viewport", {"width": 1280, "height": 720})
    keys(viewport, ("width", "height"), "viewport")
    if any(not isinstance(viewport.get(k), int) or isinstance(viewport[k], bool) or viewport[k] <= 0 or viewport[k] % 2 for k in ("width", "height")):
        raise ValueError("Capture viewport dimensions must be positive even integers")
    if not isinstance(spec.get("record_video", True), bool):
        raise ValueError("record_video must be boolean")
    steps = spec.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Capture needs non-empty explicit steps")
    seen = set()
    for step in steps:
        keys(step, ("id", "action", "selector", "value", "seconds", "assert_text", "assert_url_contains"), "capture step")
        sid = step.get("id")
        if not isinstance(sid, str) or not sid or not all(c.isalnum() or c in "-_" for c in sid) or sid in seen:
            raise ValueError("Capture step IDs must be unique letters/digits/hyphens/underscores")
        if sid == "recording" and spec.get("record_video", True):
            raise ValueError("recording is reserved for the recorded video asset")
        seen.add(sid)
        if step.get("action") not in ("capture", "click", "fill", "wait_for", "hold"):
            raise ValueError("Unsupported capture action")
        if step["action"] in ("click", "fill", "wait_for") and not isinstance(step.get("selector"), str):
            raise ValueError("Interaction requires a selector")
        if step["action"] == "fill" and not isinstance(step.get("value"), str):
            raise ValueError("fill requires a value")
        if not 0 <= finite(step.get("seconds", 0.2), "step seconds", 0) <= 30:
            raise ValueError("Step holds must be at most 30 seconds")
        for name in ("assert_text", "assert_url_contains"):
            if name in step and (not isinstance(step[name], str) or not step[name]):
                raise ValueError(name + " must be a non-empty string")
    return spec, viewport


def capture(root, spec_path, directory):
    root, spec_path, directory = Path(root).resolve(), Path(spec_path).resolve(), Path(directory).resolve()
    spec, viewport = load_spec(spec_path)
    original_hash = digest(spec_path)
    if directory.exists():
        raise ValueError("Capture directory exists; select a new version")
    try:
        from playwright.sync_api import sync_playwright
        import importlib.metadata
    except ImportError as error:
        raise ValueError("Use an existing Playwright/Chromium environment; nothing was installed") from error
    directory.parent.mkdir(parents=True, exist_ok=True)
    assets, observations, errors = [], [], []
    with tempfile.TemporaryDirectory(prefix=".capture-", dir=directory.parent) as temporary:
        stage = Path(temporary)
        with sync_playwright() as playwright:
            with playwright.chromium.launch() as browser:
                options = {"viewport": viewport}
                if spec.get("record_video", True):
                    options.update(record_video_dir=str(stage / "raw"), record_video_size=viewport)
                context = browser.new_context(**options)
                page = context.new_page()
                page.set_default_timeout(15000)
                page.on("pageerror", lambda error: errors.append(str(error)))
                started = time.monotonic()
                response = page.goto(spec["url"], wait_until="load", timeout=30000)
                if response is None or response.status >= 400:
                    raise ValueError("Initial page did not return a successful HTTP response")
                for step in spec["steps"]:
                    action = step["action"]
                    if action == "click":
                        page.locator(step["selector"]).click()
                    elif action == "fill":
                        page.locator(step["selector"]).fill(step["value"])
                    elif action == "wait_for":
                        page.locator(step["selector"]).wait_for(state="visible")
                    page.wait_for_timeout(step.get("seconds", 0.2) * 1000)
                    page.evaluate("document.fonts.ready")
                    if step.get("assert_text") and step["assert_text"] not in page.locator("body").inner_text():
                        raise ValueError("Text assertion failed in " + step["id"])
                    if step.get("assert_url_contains") and step["assert_url_contains"] not in page.url:
                        raise ValueError("URL assertion failed in " + step["id"])
                    image = stage / (step["id"] + ".png")
                    page.screenshot(path=str(image), animations="allow")
                    assets.append({"id": step["id"], "type": "image", "path": str((directory / image.name).relative_to(root)), "sha256": digest(image)})
                    observations.append({"id": step["id"], "action": action, "url": page.url,
                                         "wall_seconds": time.monotonic() - started,
                                         "text_assertion": step.get("assert_text"), "url_assertion": step.get("assert_url_contains"), "assertions_passed": True})
                movie = page.video
                browser_version = browser.version
                context.close()
                if movie:
                    raw = Path(movie.path())
                    shutil.copy2(raw, stage / "recording.webm")
        if spec.get("record_video", True):
            run([tool("ffmpeg"), "-v", "error", "-y", "-i", stage / "recording.webm", "-an", "-vf", "fps=30",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", stage / "recording.mp4"])
            metadata = probe(stage / "recording.mp4")
            if not any(s.get("codec_type") == "video" for s in metadata["streams"]):
                raise ValueError("Recorded video is unreadable")
            assets.append({"id": "recording", "type": "video", "path": str((directory / "recording.mp4").relative_to(root)),
                           "sha256": digest(stage / "recording.mp4"), "duration_seconds": float(metadata["format"]["duration"])})
            shutil.rmtree(stage / "raw")
        if digest(spec_path) != original_hash:
            raise ValueError("Capture specification changed during capture")
        report = {"schema_version": 1, "display_mode": "real_capture", "spec_path": str(spec_path.relative_to(root)),
                  "spec_sha256": original_hash, "url": spec["url"], "product": spec["product"], "version": spec["version"],
                  "platform": spec["platform"], "feature": spec["feature"], "sources": spec.get("sources", []),
                  "viewport": viewport, "observations": observations, "assets": assets, "page_errors": errors,
                  "runtime": {"chromium": browser_version, "playwright": importlib.metadata.version("playwright")},
                  "created_at": datetime.now(timezone.utc).isoformat(), "review_status": "pending",
                  "limitations": ["Fresh browser context; no existing login or native desktop capture.",
                                  "Wall-clock observations are not frame-accurate recording timestamps.",
                                  "Assertions verify selected observed states, not all product claims."]}
        write(stage / "capture.json", report)
        stage.rename(directory)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--spec", required=True, help="Project-relative capture specification")
    parser.add_argument("--out", help="New project-relative directory for capture assets and report")
    parser.add_argument("--check", action="store_true", help="Validate specification without launching or visiting a page")
    args = parser.parse_args()
    root = args.project.expanduser().resolve()
    spec = output_path(root, args.spec)
    load_spec(spec)
    if args.check:
        print(json.dumps({"valid": True, "note": "No page was visited"}))
        return 0
    directory = output_path(root, args.out or "assets/captures/" + uuid.uuid4().hex[:12])
    result = capture(root, spec, directory)
    print(json.dumps({"report": str((directory / 'capture.json').relative_to(root)), "assets": result["assets"], "page_errors": result["page_errors"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print("IvanVideo: " + str(error), file=sys.stderr)
        raise SystemExit(2)
