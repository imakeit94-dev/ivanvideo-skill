#!/usr/bin/env python3
"""Create a non-destructive IvanVideo Skill project skeleton."""
import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New video project directory")
    parser.add_argument("--title", default="Untitled video")
    parser.add_argument("--topic", default="")
    parser.add_argument("--assets", type=Path, action="append", default=[], help="Existing asset directory (repeatable)")
    parser.add_argument("--duration", type=float, default=None, help="Requested duration in seconds")
    parser.add_argument("--language", default=None)
    parser.add_argument("--platform", default=None)
    parser.add_argument("--aspect-ratio", choices=("16:9", "9:16", "1:1"), default=None)
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--fps", type=int, default=30)
    args = parser.parse_args()

    output = args.output.expanduser().resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        print(f"Refusing to initialize a non-empty directory: {output}", file=sys.stderr)
        return 2
    if args.duration is not None and (not math.isfinite(args.duration) or args.duration <= 0):
        parser.error("--duration must be greater than zero")
    if (args.width is None) != (args.height is None):
        parser.error("Provide both --width and --height, or neither")
    defaults = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080)}
    if args.width is None:
        args.width, args.height = defaults[args.aspect_ratio or "16:9"]
    if args.width <= 0 or args.height <= 0 or args.fps <= 0:
        parser.error("width, height, and fps must be greater than zero")
    divisor = math.gcd(args.width, args.height)
    actual_ratio = f"{args.width // divisor}:{args.height // divisor}"
    if args.aspect_ratio and args.aspect_ratio != actual_ratio:
        parser.error("--aspect-ratio conflicts with width and height")
    args.aspect_ratio = actual_ratio

    roots = [p.expanduser().resolve() for p in args.assets]
    missing_roots = [str(p) for p in roots if not p.exists()]
    items = []
    for root in roots:
        if root.is_dir():
            for item in sorted(root.rglob("*")):
                if item.is_file():
                    items.append({"path": str(item), "media_type": "unknown", "role": "unclassified", "source": "user-provided directory", "license": "unknown", "status": "needs_review"})
        elif root.is_file():
            items.append({"path": str(root), "media_type": "unknown", "role": "unclassified", "source": "user-provided file", "license": "unknown", "status": "needs_review"})

    output.mkdir(parents=True, exist_ok=True)
    for folder in ("scripts", "references", "assets", "src", "audio", "previews", "outputs"):
        (output / folder).mkdir(exist_ok=True)
    project = {
        "title": args.title, "topic": args.topic, "audience": None, "purpose": None,
        "duration_seconds": args.duration, "language": args.language, "platform": args.platform,
        "aspect_ratio": args.aspect_ratio, "width": args.width, "height": args.height, "fps": args.fps,
        "output": {"container": "mp4", "video_codec": "h264", "path": "outputs/final.mp4"},
        "narration": {"enabled": None, "voice": None, "notes": "", "audio_path": None, "timing_path": None},
        "audio": {"sample_rate": 48000, "tracks": [], "ducking": {"enabled": False}, "normalization": None},
        "subtitles": {"enabled": False},
        "safe_area": {"top": 0, "bottom": 0, "left": 0, "right": 0},
        "visual_system": {"palette": [], "fonts": [], "concept_colors": {}, "motion_notes": ""},
        "reference_videos": [], "asset_roots": [str(p) for p in roots],
        "missing_items": missing_roots, "assumptions": [], "status": "brief", "created_at": datetime.now(timezone.utc).isoformat()
    }
    write_json(output / "project.json", project)
    write_json(output / "storyboard.json", {"shots": []})
    write_json(output / "assets" / "manifest.json", items)
    (output / "scripts" / "brief.md").write_text("# Video brief\n\n- Audience:\n- Purpose:\n- Key message:\n- Required facts / sources:\n- Tone and visual direction:\n- Narration:\n- Constraints:\n- Open questions / missing materials:\n", encoding="utf-8")
    (output / "references" / "README.md").write_text("# Reference materials\n\nKeep reference-analysis reports and source links here. Store large source media in its original location and record the path in `project.json`.\n", encoding="utf-8")
    print(f"Initialized project: {output}")
    print(f"Asset files indexed: {len(items)}; missing asset roots: {len(missing_roots)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
