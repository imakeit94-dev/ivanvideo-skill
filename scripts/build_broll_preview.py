#!/usr/bin/env python3
"""Package an audio-clock review page around IvanVideo's existing clip renderer."""
import argparse
import copy
import functools
import http.server
import json
import re
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

from animation_spec import normalize
from broll import bound_segments
from film_core import (audio_plan, build_timeline, digest, engine_path, finite, identity, keys,
                       local, output_path, read, run, tool, tree_hash, write)
from mix_audio import create_mix
from render_animation import load_input
from render_film import snapshot


def overlay_config(root, config, width, height):
    path = local(root, config["broll"]["overlay_path"])
    value = read(path) if path.exists() else {"regions": []}
    keys(value, ("regions",), "overlay")
    if not isinstance(value.get("regions"), list):
        raise ValueError("Overlay regions must be an array")
    seen = set()
    for region in value["regions"]:
        keys(region, ("id", "kind", "shape", "x", "y", "width", "height", "label", "font_size"), "overlay region")
        label = region.get("id")
        if not isinstance(label, str) or not label or label in seen:
            raise ValueError("Overlay region IDs must be unique non-empty strings")
        seen.add(label)
        if region.get("kind") not in ("avatar", "subtitle", "protected") or region.get("shape", "rect") not in ("rect", "circle"):
            raise ValueError("Overlay kind is avatar/subtitle/protected; shape is rect/circle")
        for k in ("x", "y", "width", "height"):
            finite(region.get(k), "overlay " + k, 0)
        if region["width"] <= 0 or region["height"] <= 0 or region["x"] + region["width"] > 1 or region["y"] + region["height"] > 1:
            raise ValueError("Overlay coordinates must fit the normalized canvas")
        if region.get("shape") == "circle" and abs(region["width"] * width - region["height"] * height) > 1:
            raise ValueError("Circle overlay needs equal pixel width and height")
        if not isinstance(region.get("label", ""), str):
            raise ValueError("Overlay label must be a string")
        if "font_size" in region:
            finite(region["font_size"], "overlay font_size", 1)
    return value, digest(path) if path.exists() else identity(value)


def template_path(root):
    own = root / "src/review-preview"
    return own if own.is_dir() else Path(__file__).resolve().parents[1] / "assets/review-preview"


def preview_inputs(root):
    source, selected = bound_segments(root)
    timeline = build_timeline(root)
    if any(s["overlap_frames"] for s in timeline["shots"]):
        raise ValueError("Packaging review currently uses hard cuts; overlapping transitions need a rendered film preview")
    config = read(root / "project.json")
    overlays, overlay_hash = overlay_config(root, config, timeline["width"], timeline["height"])
    plan = audio_plan(root, timeline)
    if not plan["tracks"]:
        raise ValueError("Sound-synchronized review requires a real project audio track")
    signature = {"timeline": timeline["fingerprint"], "audio": plan["fingerprint"], "overlays": overlay_hash,
                 "engine": tree_hash(engine_path(root)), "templates": tree_hash(template_path(root)),
                 "builder": digest(__file__), "source": identity(source)}
    return source, selected, timeline, plan, overlays, signature


def build(root, directory):
    root, directory = Path(root).resolve(), Path(directory).resolve()
    source, selected, timeline, plan, overlays, signature = preview_inputs(root)
    if directory.exists():
        raise ValueError("Preview directory exists; use a new version")
    master, _ = create_mix(root, timeline, output_path(root, "audio/mixes/" + plan["fingerprint"][:16]))
    runtime = snapshot(root, bool(timeline["captions"]))
    engine, templates = engine_path(root), template_path(root)
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".preview-", dir=directory.parent) as temporary:
        stage = Path(temporary)
        shutil.copytree(engine, stage / "engine", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(templates, stage / "ui")
        shutil.copy2(stage / "ui/index.html", stage / "index.html")
        (stage / "media").mkdir(); (stage / "specs").mkdir()
        shutil.copy2(master, stage / "media/review.wav")
        copies, shots = {}, []
        def media_file(path, is_video=False):
            key = digest(path)
            if key in copies: return copies[key]
            name = key[:20] + (".mp4" if is_video else Path(path).suffix.lower())
            target = stage / "media" / name
            if is_video:
                # Browser-compatible, silent review derivative. Original media remains in the project.
                run([tool("ffmpeg"), "-v", "error", "-i", path, "-map", "0:v:0", "-an", "-vf", f"scale='min(1280,iw)':-2,fps={timeline['fps']}",
                     "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", target])
            else: shutil.copy2(path, target)
            copies[key] = "media/" + name
            return copies[key]
        for shot in timeline["shots"]:
            item = {k: shot[k] for k in ("id", "start_frame", "end_frame")}
            item["type"] = shot["media"]["type"]
            if item["type"] == "animation":
                raw, path, _ = load_input(root, SimpleNamespace(spec=None, shot=shot["id"]))
                spec = normalize(raw, path.parent)
                spec.pop("timing_file", None)
                for part in [spec.get("data", {})] + spec["cues"]:
                    if part.get("image") and not part["image"].startswith("data:"):
                        part["image"] = "../" + media_file(part["image"])
                item["spec"] = "specs/" + shot["id"] + ".json"
                write(stage / item["spec"], spec)
            else:
                item.update(path=media_file(shot["media"]["path"], item["type"] == "video"),
                            trim_in_seconds=shot["media"]["trim_in_seconds"], fit=shot["media"]["fit"])
            shots.append(item)
        data = {"schema_version": 1, "fps": timeline["fps"], "width": timeline["width"], "height": timeline["height"],
                "frames": timeline["frames"], "audio": "media/review.wav", "shots": shots, "overlays": overlays["regions"],
                "captions": [{"id": c["id"], "text": c["text"], "start_seconds": c["start_ms"] / 1000,
                              "end_seconds": c["end_ms"] / 1000} for c in source["cues"]],
                "selected_ids": [s["id"] for _, s in selected], "title": read(root / "project.json").get("title", "IvanVideo")}
        write(stage / "data.json", data)
        if preview_inputs(root)[-1] != signature:
            raise ValueError("Preview inputs changed during build")
        report = {"schema_version": 1, "inputs": signature, "runtime": str(runtime.relative_to(root)),
                  "files": {str(p.relative_to(stage)): digest(p) for p in sorted(stage.rglob("*")) if p.is_file()},
                  "manual_review_pending": ["Full listening and pronunciation", "Overlay geometry matches the actual master", "Graphics, cached text and clipping/occlusion beyond sampled text bounds"],
                  "note": "Same clip engine, audio clock and frame-grid sampling. Overlays are review-only, not baked into deliveries."}
        write(stage / "preview.json", report)
        stage.rename(directory)
    # Preserve the exact UI source for project-local rebuilding, independently of future global updates.
    own = root / "src/review-preview"
    if not own.exists(): shutil.copytree(templates, own)
    own_engine = root / "src/animation-engine"
    if not own_engine.exists(): shutil.copytree(engine, own_engine)
    return report


def verify_bundle(directory):
    report = read(directory / "preview.json")
    for name, expected in report["files"].items():
        path = output_path(directory, name)
        if not path.is_file() or digest(path) != expected:
            raise ValueError("Preview bundle changed: " + name)
    return report


def serve(directory, port=0):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *unused): pass
        def end_headers(self):
            self.send_header("Accept-Ranges", "bytes")
            super().end_headers()
        def send_head(self):
            self.byte_range = None
            header = self.headers.get("Range")
            path = Path(self.translate_path(self.path))
            if not header or not path.is_file(): return super().send_head()
            size = path.stat().st_size
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
            try:
                if not match or not any(match.groups()): raise ValueError()
                a,b=match.groups()
                start = int(a) if a else max(0,size-int(b))
                end = min(size-1,int(b)) if a and b else size-1
                if start < 0 or start > end or start >= size: raise ValueError()
            except ValueError:
                self.send_response(416);self.send_header("Content-Range",f"bytes */{size}");self.send_header("Content-Length","0");self.end_headers();return None
            handle = path.open("rb");handle.seek(start);self.byte_range=(start,end)
            self.send_response(206);self.send_header("Content-Type",self.guess_type(str(path)))
            self.send_header("Content-Range",f"bytes {start}-{end}/{size}");self.send_header("Content-Length",str(end-start+1));self.end_headers()
            return handle
        def copyfile(self, source, target):
            if self.byte_range is None: return super().copyfile(source,target)
            remaining=self.byte_range[1]-self.byte_range[0]+1
            while remaining:
                block=source.read(min(65536,remaining))
                if not block: break
                target.write(block);remaining-=len(block)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Handler, directory=str(directory)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def review_qa(directory, out, times=None):
    from playwright.sync_api import sync_playwright
    directory, out = Path(directory).resolve(), Path(out).resolve()
    verify_bundle(directory)
    data = read(directory / "data.json")
    duration_s = data["frames"] / data["fps"]
    if times is None:
        times = sorted(set([0, (data["frames"] - 1) / data["fps"]] +
                           [max(0, min(duration_s - 1 / data["fps"], f / data["fps"])) for s in data["shots"] for f in (s["start_frame"], s["end_frame"] - 1)] +
                           [i / 2 for i in range(int(duration_s * 2))]))
    if any(not 0 <= t < duration_s for t in times): raise ValueError("QA times must lie inside preview")
    if out.exists(): raise ValueError("QA output exists; use a new version")
    out.mkdir(parents=True)
    server, records, errors = serve(directory), [], []
    try:
        with sync_playwright() as p:
            with p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"]) as browser:
                page = browser.new_page(viewport={"width": 1280, "height": 1000})
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(f"http://127.0.0.1:{server.server_port}/")
                page.wait_for_function("window.ivanPreview && window.ivanPreview.ready")
                for i, t in enumerate(times):
                    page.evaluate("t=>window.ivanPreview.seek(t)", t)
                    record = page.evaluate("window.ivanPreview.inspect()")
                    state = page.evaluate("window.ivanPreview.state()")
                    record["audio_time"] = state["audio_time"]
                    if abs(state["audio_time"] - t) > 1 / data["fps"] + .001:
                        raise ValueError("Audio did not seek to the reviewed frame")
                    record["requested_seconds"] = t
                    if record["warnings"]:
                        png = f"warning-{i:03}.png"; page.locator("#stage-box").screenshot(path=str(out / png)); record["frame"] = png
                    records.append(record)
                page.evaluate("window.ivanPreview.seek(0)")
                page.locator("#play").click()
                page.wait_for_timeout(450)
                playback = page.evaluate("window.ivanPreview.state()")
                page.evaluate("window.ivanPreview.pause()")
                page.screenshot(path=str(out / "review-page.png"))
                if errors or not playback["time"] > 0.1 or abs(playback["time"] - playback["audio_time"]) > 1 / data["fps"] + .02:
                    raise ValueError("Preview playback failed or audio clock differs: " + str(errors))
                report = {"samples": records, "playback": playback, "page_errors": errors, "browser": browser.version,
                          "note": "Text/region intersections are review clues; not a full visual or listening approval."}
                write(out / "qa.json", report)
    finally:
        server.shutdown(); server.server_close()
    verify_bundle(directory)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path); parser.add_argument("--out", default="previews/broll-review-v1")
    parser.add_argument("--check", action="store_true"); parser.add_argument("--qa", action="store_true")
    parser.add_argument("--serve", action="store_true", help="Serve an existing --out bundle with media byte-range support")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(); root = args.project.expanduser().resolve()
    if args.serve:
        out=output_path(root,args.out);verify_bundle(out);server=serve(out,args.port)
        print(f"http://127.0.0.1:{server.server_port}/",flush=True)
        try:
            stop=threading.Event()
            while not stop.wait(1): pass
        except KeyboardInterrupt: pass
        finally: server.shutdown();server.server_close()
        return
    if args.check:
        preview_inputs(root); print(json.dumps({"valid": True, "rendered": False})); return
    out = output_path(root, args.out); report = build(root, out)
    if args.qa: review_qa(out, out.with_name(out.name + "-qa"))
    print(json.dumps({"directory": str(out), "runtime": report["runtime"], "serve": f'python3 "{root / report["runtime"] / "build_broll_preview.py"}" "{root}" --out "{args.out}" --serve'}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try: main()
    except (ValueError, OSError, KeyError, TypeError, ImportError) as error:
        print("IvanVideo: " + str(error), file=sys.stderr); raise SystemExit(2)
