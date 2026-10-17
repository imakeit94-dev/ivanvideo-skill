#!/usr/bin/env python3
"""Prepare image/video prompts and register real returned media with project-local provenance."""
import argparse
from datetime import datetime, timezone
import json
import shutil
import sys
import tempfile
from pathlib import Path

from film_core import digest, finite, identity, keys, local, output_path, probe, read, run, tool, write


def asset_id(value):
    if not isinstance(value, str) or not value or not all(c.isalnum() or c in "-_" for c in value):
        raise ValueError("Asset IDs must use letters/digits/hyphens/underscores")
    return value


def load_plan(root, path):
    value = read(path)
    keys(value, ("style", "assets"), "asset plan")
    if not isinstance(value.get("style", ""), str):
        raise ValueError("Asset style must be a string")
    if not isinstance(value.get("assets"), list) or not value["assets"]:
        raise ValueError("Asset plan needs a non-empty assets array")
    seen = set()
    shots = {s["id"] for s in read(root / "storyboard.json")["shots"]}
    for item in value["assets"]:
        keys(item, ("id", "media_type", "role", "purpose", "shot_ids", "aspect_ratio", "prompt", "avoid", "reference_images", "provider", "model", "duration_seconds"), "planned asset")
        label = asset_id(item.get("id"))
        if label in seen:
            raise ValueError("Duplicate asset ID: " + label)
        seen.add(label)
        if item.get("media_type") not in ("image", "video") or item.get("role") not in ("illustration", "background", "b_roll", "cover_subject"):
            raise ValueError("Assets need image/video type and illustration/background/b_roll/cover_subject role")
        for name in ("purpose", "prompt"):
            if not isinstance(item.get(name), str) or not item[name].strip():
                raise ValueError(name + " must describe this asset")
        try:
            a, b = map(int, item["aspect_ratio"].split(":"))
            if a <= 0 or b <= 0:
                raise ValueError()
        except (KeyError, ValueError, AttributeError):
            raise ValueError("aspect_ratio must be positive integers like 16:9")
        for name in ("shot_ids", "avoid", "reference_images"):
            if not isinstance(item.get(name, []), list) or not all(isinstance(x, str) and x for x in item.get(name, [])):
                raise ValueError(name + " must be an array of non-empty strings")
        if set(item.get("shot_ids", [])) - shots:
            raise ValueError("Asset refers to an unknown storyboard shot")
        for name in ("provider", "model"):
            if item.get(name) is not None and (not isinstance(item[name], str) or not item[name]):
                raise ValueError(name + " must be null or a non-empty string")
        if item["media_type"] == "video":
            finite(item.get("duration_seconds"), "Requested video duration", 0.01)
        elif "duration_seconds" in item:
            raise ValueError("Still images do not have a requested duration")
    return value


def prepare(root, path, check=False):
    root, path = Path(root).resolve(), Path(path).resolve()
    plan = load_plan(root, path)
    result = []
    # Include reference hashes in the request revision; changing a reference creates a new request.
    reference_hashes = {p: digest(local(root, p)) if local(root, p).is_file() else None
                        for item in plan["assets"] for p in item.get("reference_images", [])}
    version = identity({"plan": plan, "references": reference_hashes})[:16]
    directory = output_path(root, "references/asset-requests/" + version)
    for item in plan["assets"]:
        missing = [p for p in item.get("reference_images", []) if reference_hashes[p] is None]
        lines = ["Asset purpose: " + item["purpose"], "Media type: " + item["media_type"],
                 "Aspect ratio: " + item["aspect_ratio"], "Style: " + plan.get("style", ""), item["prompt"]]
        if item.get("avoid"):
            lines.append("Avoid: " + "; ".join(item["avoid"]))
        if item["media_type"] == "video":
            lines.append(f"Requested duration: {item['duration_seconds']} seconds; verify provider support before submission.")
        refs = {p: reference_hashes[p] for p in item.get("reference_images", [])}
        request = {"schema_version": 1, "status": "planned", "asset": item, "style": plan.get("style", ""),
                   "prompt_text": "\n".join(lines), "reference_hashes": refs, "missing_references": missing}
        target = directory / (item["id"] + ".json")
        if not check:
            if target.exists() and read(target) != request:
                raise ValueError("Generated request was edited; preserve it as a new plan revision")
            write(target, request)
            (directory / (item["id"] + ".md")).write_text(request["prompt_text"] + "\n", encoding="utf-8")
        result.append({"id": item["id"], "request": str(target.relative_to(root)), "ready": not missing, "missing_references": missing})
    return result


def inspect_media(path, expected):
    ffprobe = tool("ffprobe")
    meta = json.loads(run([ffprobe, "-v", "error", "-count_frames", "-show_format", "-show_streams", "-of", "json", path]).stdout)
    stream = next((s for s in meta["streams"] if s.get("codec_type") == "video"), None)
    if not stream:
        raise ValueError("Returned file has no readable image/video stream")
    still_codecs = {"png": ".png", "mjpeg": ".jpg", "webp": ".webp"}
    count = int(stream.get("nb_read_frames", 0))
    if expected == "image":
        if stream["codec_name"] not in still_codecs or count != 1:
            raise ValueError("Expected one static PNG/JPEG/WebP image")
        extension, length = still_codecs[stream["codec_name"]], None
    else:
        if stream["codec_name"] in still_codecs or count < 2:
            raise ValueError("Expected an actual video, not a renamed still image")
        length = finite(float(stream.get("duration") or meta.get("format", {}).get("duration") or 0), "Media duration", 0.01)
        extension = path.suffix.lower()
        if extension not in (".mp4", ".mov", ".webm", ".mkv"):
            raise ValueError("Use an MP4/MOV/WebM/MKV video file")
    run([tool("ffmpeg"), "-v", "error", "-xerror", "-i", path, "-f", "null", "-"])
    return {"width": stream["width"], "height": stream["height"], "codec": stream["codec_name"],
            "frames": count, "duration_seconds": length, "audio_streams": sum(s.get("codec_type") == "audio" for s in meta["streams"])}, extension


def registered_asset(root, label):
    entries = read(root / "assets/manifest.json")
    if not isinstance(entries, list):
        raise ValueError("Asset manifest must be an array")
    matches = [x for x in entries if isinstance(x, dict) and x.get("id") == label]
    if len(matches) != 1:
        raise ValueError("Registered asset ID must match exactly once: " + str(label))
    item = matches[0]
    if not item.get("sha256") or digest(local(root, item["path"])) != item["sha256"]:
        raise ValueError("Registered asset is missing or changed: " + label)
    provenance = item.get("provenance", {})
    request = local(root, provenance["request_path"])
    if digest(request) != provenance["request_sha256"]:
        raise ValueError("Asset request changed; preserve the request used to generate this asset")
    return item


def register(root, request_path, source, metadata_path):
    root, request_path, source, metadata_path = (Path(x).resolve() for x in (root, request_path, source, metadata_path))
    request, metadata = read(request_path), read(metadata_path)
    if request.get("status") != "planned" or request.get("schema_version") != 1:
        raise ValueError("Use an actual prepared asset request")
    item = request["asset"]
    label = asset_id(item["id"])
    if not source.is_file() or not source.stat().st_size:
        raise ValueError("Generated/provided file is missing or empty; a prompt or job ID is not a video")
    keys(metadata, ("origin", "provider", "model", "source", "license", "job_id", "prompt_used", "notes"), "asset metadata")
    if metadata.get("origin") not in ("ai_generated", "user_provided", "synthetic_test"):
        raise ValueError("origin must distinguish ai_generated, user_provided or synthetic_test")
    for name in ("source", "license"):
        if not isinstance(metadata.get(name), str) or not metadata[name].strip():
            raise ValueError(name + " is required; record unknown if not established")
    if metadata["origin"] == "ai_generated":
        if not isinstance(metadata.get("provider"), str) or not metadata["provider"] or not isinstance(metadata.get("prompt_used"), str) or not metadata["prompt_used"].strip():
            raise ValueError("AI output needs the actual provider and submitted prompt")
    for name in ("provider", "model", "job_id", "prompt_used", "notes"):
        if metadata.get(name) is not None and not isinstance(metadata[name], str):
            raise ValueError(name + " must be null or a string")
    for path, expected in request.get("reference_hashes", {}).items():
        if expected is None or not local(root, path).is_file() or digest(local(root, path)) != expected:
            raise ValueError("Reference is missing or changed; prepare a new request: " + path)
    measured, extension = inspect_media(source, item["media_type"])
    content_hash = digest(source)
    target = output_path(root, f"assets/media/{label}-{content_hash[:16]}{extension}")
    entries = read(root / "assets/manifest.json")
    if not isinstance(entries, list):
        raise ValueError("assets/manifest.json must be an array")
    if any(isinstance(x, dict) and x.get("id") == label for x in entries):
        raise ValueError("Asset ID already exists; use a versioned new ID to preserve approved material")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError("Destination exists without a matching manifest entry; preserve or inspect it first")
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        shutil.copyfile(source, temporary)
        if digest(temporary) != content_hash:
            raise ValueError("Source changed while importing media")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    entry = {"id": label, "path": str(target.relative_to(root)), "media_type": item["media_type"], "role": item["role"],
             "source": metadata["source"], "license": metadata["license"], "status": "needs_review", "sha256": content_hash,
             "media": measured, "provenance": {**metadata, "request_path": str(request_path.relative_to(root)),
                                               "request_sha256": digest(request_path), "reference_hashes": request.get("reference_hashes", {}),
                                               "registered_at": datetime.now(timezone.utc).isoformat()},
             "review": {"visual": "pending", "factual": "pending", "usage_rights": "pending"}}
    try:
        write(root / "assets/manifest.json", entries + [entry])
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare", help="Write prompts/requests only; never claims generation")
    p.add_argument("--plan", default="references/asset-plan.json")
    p.add_argument("--check", action="store_true")
    p = commands.add_parser("register", help="Copy a real returned file and append its traceable manifest entry")
    p.add_argument("--request", required=True)
    p.add_argument("--file", required=True, type=Path)
    p.add_argument("--metadata", required=True)
    p = commands.add_parser("verify")
    p.add_argument("--id", required=True)
    args = parser.parse_args()
    root = args.project.expanduser().resolve()
    if args.command == "prepare":
        result = prepare(root, output_path(root, args.plan), args.check)
    elif args.command == "register":
        result = register(root, output_path(root, args.request), local(root, str(args.file)), output_path(root, args.metadata))
    else:
        result = registered_asset(root, args.id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print("IvanVideo: " + str(error), file=sys.stderr)
        raise SystemExit(2)
