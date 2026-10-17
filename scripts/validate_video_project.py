#!/usr/bin/env python3
"""Check a project's configuration, storyboard timing, and referenced asset paths."""
import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from animation_spec import normalize, number


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
    parser.add_argument("--delivery", action="store_true", help="Require complete timeline and all referenced assets")
    parser.add_argument("--film", action="store_true", help="Also compile renderable media, transitions, subtitles and measured audio (requires FFprobe for audio)")
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
        if not number(config.get("fps")) or config.get("fps", 0) <= 0:
            errors.append("project.json fps must be positive")
        width, height = config.get("width"), config.get("height")
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            try:
                a, b = map(int, config["aspect_ratio"].split(":"))
                if a <= 0 or b <= 0 or width * b != height * a:
                    raise ValueError("aspect ratio mismatch")
            except (KeyError, ValueError, AttributeError):
                errors.append("aspect_ratio must agree with width and height")
        if config.get("duration_seconds") is not None and (not number(config["duration_seconds"]) or config["duration_seconds"] <= 0):
            errors.append("duration_seconds must be null or a finite positive number")
    else:
        errors.append("project.json must be an object")
    shots = board.get("shots") if isinstance(board, dict) else None
    if not isinstance(shots, list):
        errors.append("storyboard.json must contain a shots array")
        shots = []
    if args.delivery and not shots:
        errors.append("Delivery needs a non-empty storyboard")
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
        if not isinstance(shot_id, str) or not shot_id:
            errors.append(f"{label} needs a non-empty string id")
            continue
        if shot_id in ids:
            errors.append(f"Duplicate shot id: {shot_id}")
        ids.add(shot_id)
        start, end = shot.get("start_seconds"), shot.get("end_seconds")
        if not number(start) or not number(end) or start < 0 or end <= start:
            errors.append(f"{label} must have start_seconds >= 0 and end_seconds > start_seconds")
        else:
            normalized.append((start, end, label))
        for key in ("on_screen_text", "audio_cues", "assets", "source_notes"):
            if key in shot and not isinstance(shot[key], list):
                errors.append(f"{label} {key} must be an array")
        if "animation" in shot:
            try:
                from render_animation import load_input
                raw, path, _ = load_input(root, SimpleNamespace(spec=None, shot=shot_id))
                normalize(raw, path.parent)
            except (ValueError, OSError, KeyError, TypeError) as exc:
                errors.append(f"{label} animation: {exc}")
        if "media" in shot:
            try:
                from film_core import media_spec
                media_spec(root, shot)
            except (ValueError, OSError, KeyError, TypeError) as exc:
                # Missing media may remain explicitly declared during planning.
                pending = isinstance(shot.get("media"), dict) and any(
                    isinstance(item, dict) and item.get("path") == shot["media"].get("path") and item.get("status") == "missing"
                    for item in (assets if isinstance(assets, list) else []))
                if args.delivery or args.film or not pending or "Missing media:" not in str(exc):
                    errors.append(f"{label} media: {exc}")
    normalized.sort()
    for current, following in zip(normalized, normalized[1:]):
        if following[0] < current[1] - 0.001:
            next_shot = next(s for s in shots if isinstance(s, dict) and s.get("id") == following[2])
            transition = next_shot.get("transition_in", {})
            overlap = current[1] - following[0]
            if not isinstance(transition, dict) or transition.get("from") != current[2] or not number(transition.get("duration_seconds")) or abs(transition["duration_seconds"] - overlap) > 0.001:
                errors.append(f"Unmarked shot overlap: {current[2]} and {following[2]}")
        elif args.delivery and following[0] > current[1] + 0.001:
            errors.append(f"Uncovered timeline interval after {current[2]}; add an explicit pause/black shot if intended")
    if normalized and isinstance(config, dict) and number(config.get("duration_seconds")):
        if normalized[-1][1] > config["duration_seconds"] + 0.001:
            errors.append("Storyboard ends after project duration")
        if args.delivery and (abs(normalized[0][0]) > 0.001 or abs(max(x[1] for x in normalized) - config["duration_seconds"]) > 0.001):
            errors.append("Delivery storyboard must cover the requested duration from zero")
    if isinstance(assets, list):
        for item in assets:
            if not isinstance(item, dict) or not item.get("path"):
                errors.append("Each asset manifest entry must be an object with a path")
                continue
            if not isinstance(item["path"], str):
                errors.append("Asset paths must be strings")
                continue
            asset_path = Path(item["path"]).expanduser()
            if not asset_path.is_absolute():
                asset_path = root / asset_path
            if not asset_path.exists() and item.get("status") != "missing":
                errors.append(f"Asset path not found (mark status=missing if expected): {item['path']}")
    elif assets is not None:
        errors.append("assets/manifest.json must be an array")
    declared_missing = {item["path"] for item in assets if isinstance(item, dict) and isinstance(item.get("path"), str) and item.get("status") == "missing"} if isinstance(assets, list) else set()
    for shot in shots:
        if not isinstance(shot, dict) or not isinstance(shot.get("assets"), list):
            continue
        for path in shot["assets"]:
            if not isinstance(path, str):
                errors.append(f"{shot.get('id')} assets must list project-relative or absolute paths")
            elif not (root / path).expanduser().exists() and (args.delivery or path not in declared_missing):
                errors.append(f"{shot.get('id')} references a missing asset: {path}")
    if args.film and not errors:
        try:
            from film_core import audio_plan, build_timeline
            audio_plan(root, build_timeline(root))
        except (ValueError, OSError, KeyError, TypeError) as exc:
            errors.append("Film inputs: " + str(exc))
    if errors:
        print("Project validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Project valid: {root} ({len(shots)} shots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
