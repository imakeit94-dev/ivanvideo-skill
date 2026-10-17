#!/usr/bin/env python3
"""Check a project's configuration, storyboard timing, and referenced asset paths."""
import argparse
import json
import sys
from pathlib import Path


def load(path: Path, errors: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"Missing required file: {path}")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Cannot read {path}: {exc}")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Video project directory")
    args = parser.parse_args()
    root = args.project.expanduser().resolve()
    errors: list[str] = []
    config = load(root / "project.json", errors)
    board = load(root / "storyboard.json", errors)
    assets = load(root / "assets" / "manifest.json", errors)
    if isinstance(config, dict):
        for key in ("title", "width", "height", "fps", "output"):
            if key not in config:
                errors.append(f"project.json is missing {key!r}")
        if not isinstance(config.get("width"), int) or config.get("width", 0) <= 0:
            errors.append("project.json width must be a positive integer")
        if not isinstance(config.get("height"), int) or config.get("height", 0) <= 0:
            errors.append("project.json height must be a positive integer")
        if not isinstance(config.get("fps"), (int, float)) or config.get("fps", 0) <= 0:
            errors.append("project.json fps must be positive")
    shots = board.get("shots") if isinstance(board, dict) else None
    if not isinstance(shots, list):
        errors.append("storyboard.json must contain a shots array")
        shots = []
    required = ("id", "start_seconds", "end_seconds", "purpose", "visual", "motion", "on_screen_text", "narration", "audio_cues", "assets", "source_notes")
    normalized = []
    ids = set()
    for index, shot in enumerate(shots, 1):
        label = shot.get("id", f"shot #{index}") if isinstance(shot, dict) else f"shot #{index}"
        if not isinstance(shot, dict):
            errors.append(f"{label} must be an object")
            continue
        for key in required:
            if key not in shot:
                errors.append(f"{label} is missing {key!r}")
        shot_id = shot.get("id")
        if shot_id in ids:
            errors.append(f"Duplicate shot id: {shot_id}")
        ids.add(shot_id)
        start, end = shot.get("start_seconds"), shot.get("end_seconds")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or start < 0 or end <= start:
            errors.append(f"{label} must have start_seconds >= 0 and end_seconds > start_seconds")
        else:
            normalized.append((start, end, label))
        for key in ("on_screen_text", "audio_cues", "assets", "source_notes"):
            if key in shot and not isinstance(shot[key], list):
                errors.append(f"{label} {key} must be an array")
    normalized.sort()
    for current, following in zip(normalized, normalized[1:]):
        if following[0] < current[1] - 0.001:
            errors.append(f"Unmarked shot overlap: {current[2]} and {following[2]}")
    if normalized and isinstance(config, dict) and isinstance(config.get("duration_seconds"), (int, float)):
        if normalized[-1][1] > config["duration_seconds"] + 0.001:
            errors.append("Storyboard ends after project duration")
    if isinstance(assets, list):
        for item in assets:
            if not isinstance(item, dict) or not item.get("path"):
                errors.append("Each asset manifest entry must be an object with a path")
                continue
            asset_path = Path(item["path"]).expanduser()
            if not asset_path.is_absolute():
                asset_path = root / asset_path
            if not asset_path.exists() and item.get("status") != "missing":
                errors.append(f"Asset path not found (mark status=missing if expected): {item['path']}")
    elif assets is not None:
        errors.append("assets/manifest.json must be an array")
    if errors:
        print("Project validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Project valid: {root} ({len(shots)} shots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
