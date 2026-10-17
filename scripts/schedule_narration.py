#!/usr/bin/env python3
"""Preview or apply a sentence-audio-driven storyboard, preserving content and revisions."""
import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

from film_core import digest, finite, identity, keys, local, output_path, read, srt_text, write
from narrate import verify_manifest


def plan_schedule(root, script_path, manifest_path, resize=False):
    root, script_path, manifest_path = Path(root).resolve(), Path(script_path).resolve(), Path(manifest_path).resolve()
    config, board = read(root / "project.json"), read(root / "storyboard.json")
    manifest = verify_manifest(root, manifest_path, script_path)
    fps = finite(config["fps"], "fps", 0.001)
    shots = board.get("shots")
    if not isinstance(shots, list) or not shots:
        raise ValueError("Scheduling needs an existing storyboard")
    ids = [s["id"] for s in shots]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate storyboard IDs")
    grouped = {name: [] for name in ids}
    order = []
    for part in manifest["segments"]:
        if part["shot_id"] not in grouped:
            raise ValueError("Narration refers to an unknown shot: " + part["shot_id"])
        index = ids.index(part["shot_id"])
        if order and index < order[-1]:
            raise ValueError("Narration segments must follow storyboard order")
        order.append(index)
        grouped[part["shot_id"]].append(part)
    new_config, new_board = copy.deepcopy(config), copy.deepcopy(board)
    narration = new_config.setdefault("narration", {})
    old_owned = set(narration.get("generated_timeline", {}).get("track_ids", []))
    audio = new_config.setdefault("audio", {})
    original_tracks = audio.get("tracks", [])
    if narration.get("audio_path") or any(t.get("role") == "voice" and t.get("id") not in old_owned for t in original_tracks):
        raise ValueError("Existing voice is not owned by this scheduler; use provided segments or a separate project revision")
    tracks = [t for t in original_tracks if t.get("id") not in old_owned]
    generated_tracks, captions, changes = [], [], []
    end_frame, last_voice_end = 0, 0
    for index, shot in enumerate(new_board["shots"]):
        parts = grouped[shot["id"]]
        options = shot.get("voice_timing", {})
        keys(options, ("lead_seconds", "gap_seconds", "tail_seconds", "minimum_seconds"), "voice_timing")
        lead = finite(options.get("lead_seconds", 0.3), "lead_seconds", 0)
        gap = finite(options.get("gap_seconds", 0.18), "gap_seconds", 0)
        tail = finite(options.get("tail_seconds", 0.5), "tail_seconds", 0)
        minimum = finite(options.get("minimum_seconds", 0), "minimum_seconds", 0)
        transition = shot.get("transition_in")
        overlap = 0
        if transition:
            keys(transition, ("from", "duration_seconds", "type"), "transition_in")
            if index == 0 or transition.get("from") != ids[index - 1] or transition.get("type", "fade") != "fade":
                raise ValueError("Schedule supports only fades from the preceding shot")
            overlap = round(finite(transition.get("duration_seconds"), "transition duration", 0.001) * fps)
            transition["duration_seconds"] = overlap / fps
        start_frame = end_frame - overlap
        start = start_frame / fps
        if parts:
            combined = "".join(p["text"] for p in parts)
            if shot.get("narration") and "".join(shot["narration"].split()) != "".join(combined.split()):
                raise ValueError("Storyboard narration and sentence text differ in " + shot["id"] + "; reconcile the approved text first")
            shot["narration"] = combined
            cursor = start + math.ceil(lead * fps - 1e-9) / fps
            if cursor < last_voice_end - 1e-8:
                raise ValueError("Voice would overlap across a fade; increase lead/tail or reduce the fade")
            for part in parts:
                finish = cursor + part["audio"]["duration_seconds"]
                captions.append({"id": part["id"], "shot_id": shot["id"], "text": part["text"],
                                 "start_seconds": cursor, "end_seconds": finish})
                generated_tracks.append({"id": "narration-" + part["id"], "role": "voice", "path": part["path"], "at_seconds": cursor})
                last_voice_end = finish
                cursor = finish + gap
            needed = last_voice_end - start + tail
            frames = max(1, math.ceil(max(needed, minimum) * fps - 1e-9))
        else:
            if shot.get("narration", "").strip():
                raise ValueError("Shot has narration text but no supplied segment: " + shot["id"])
            frames = max(1, round((shot["end_seconds"] - shot["start_seconds"]) * fps), math.ceil(minimum * fps))
        if overlap >= frames or index and overlap >= new_board["shots"][index - 1]["_scheduled_frames"]:
            raise ValueError("Fade must leave independent content in each shot")
        end_frame = start_frame + frames
        shot.update(start_seconds=start, end_seconds=end_frame / fps, _scheduled_frames=frames)
        changes.append({"shot_id": shot["id"], "old": [shots[index]["start_seconds"], shots[index]["end_seconds"]],
                        "new": [start, end_frame / fps]})
    target = config.get("duration_seconds")
    if target is not None and not resize:
        finite(target, "duration_seconds", 0.001)
        target_frames = round(target * fps)
        if abs(target_frames / fps - target) > 1e-6:
            raise ValueError("Requested duration must lie on a frame boundary, or use --resize")
        if end_frame > target_frames:
            raise ValueError("Measured narration exceeds requested duration; revise the script or explicitly use --resize")
        end_frame = target_frames
        new_board["shots"][-1]["end_seconds"] = end_frame / fps
        changes[-1]["new"][1] = end_frame / fps
    for shot in new_board["shots"]:
        shot.pop("_scheduled_frames")
        # Check timing anchors before any authoring files are replaced.
        lookup = {c["id"]: c for c in captions}
        for cue in shot.get("animation", {}).get("cues", []):
            if "anchor" in cue:
                anchor = cue["anchor"]
                if anchor.get("id") not in lookup or anchor.get("edge", "start") not in ("start", "end"):
                    raise ValueError("Unresolved animation narration anchor")
                at = lookup[anchor["id"]][anchor.get("edge", "start") + "_seconds"] + finite(anchor.get("offset_seconds", 0), "anchor offset") - shot["start_seconds"]
            else:
                at = finite(cue.get("at"), "animation cue at", 0)
            if at < 0 or round(at * fps) >= round((shot["end_seconds"] - shot["start_seconds"]) * fps):
                raise ValueError("Animation cue no longer fits " + shot["id"] + "; revise that cue")
        for cue in shot.get("audio_cues", []):
            if cue.get("offset_seconds", -1) < 0 or cue["offset_seconds"] >= shot["end_seconds"] - shot["start_seconds"]:
                raise ValueError("Audio cue no longer fits " + shot["id"])
    for earlier, incoming in zip(new_board["shots"], new_board["shots"][2:]):
        if incoming["start_seconds"] < earlier["end_seconds"] - 1e-8:
            raise ValueError("Reflow would create a three-way transition")
    timing = {"method": "measured", "granularity": "sentence_clip", "audio_path": None, "segments": captions,
              "note": "Measured clip intervals; no word/phoneme alignment or listening review is implied."}
    # Hash exactly the same JSON bytes that write() produces.
    timing_hash = hashlib.sha256((json.dumps(timing, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()).hexdigest()
    immutable = output_path(root, "audio/tts/manifests/" + manifest["fingerprint"] + ".json")
    # Manifests imported by an external caller may not yet have the immutable copy.
    manifest_ref = immutable if immutable.is_file() else manifest_path
    narration.update(enabled=True, audio_path=None, timing_path="audio/narration-timing.json",
                     generated_timeline={"script_path": str(script_path.relative_to(root)), "manifest_path": str(manifest_ref.relative_to(root)),
                                         "timing_sha256": timing_hash, "track_ids": [t["id"] for t in generated_tracks]})
    audio["tracks"] = tracks + generated_tracks
    if len({t["id"] for t in audio["tracks"]}) != len(audio["tracks"]):
        raise ValueError("Generated voice track ID conflicts with an existing track")
    new_config.setdefault("subtitles", {}).update(enabled=True, timing_path="audio/narration-timing.json")
    new_config["duration_seconds"] = end_frame / fps
    result = {"project": new_config, "storyboard": new_board, "timing": timing, "changes": changes,
              "source_hashes": {"project.json": digest(root / "project.json"), "storyboard.json": digest(root / "storyboard.json"),
                                str(script_path.relative_to(root)): digest(script_path), str(manifest_path.relative_to(root)): digest(manifest_path)},
              "note": "Other audio tracks retain their times; inspect music/SFX and source-video lengths after reflow."}
    result["fingerprint"] = identity(result)
    return result


def apply_schedule(root, plan):
    root = Path(root).resolve()
    for path, expected in plan["source_hashes"].items():
        if digest(local(root, path)) != expected:
            raise ValueError("Inputs changed after schedule planning")
    targets = {"project.json": plan["project"], "storyboard.json": plan["storyboard"], "audio/narration-timing.json": plan["timing"]}
    if all(local(root, name).is_file() and read(local(root, name)) == value for name, value in targets.items()):
        return False
    revision = output_path(root, "references/narration-revisions/" + plan["fingerprint"][:16])
    before = {}
    for name in targets:
        target = output_path(root, name)
        before[name] = target.read_bytes() if target.exists() else None
        if target.exists():
            backup = revision / "before" / name
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(before[name])
    write(revision / "transaction.json", {"status": "applying", "targets": list(targets), "fingerprint": plan["fingerprint"]})
    try:
        for name, value in targets.items():
            write(output_path(root, name), value)
        from film_core import verify_generated_narration
        verify_generated_narration(root, plan["project"])
    except Exception:
        for name, content in before.items():
            target = output_path(root, name)
            if content is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(content)
        write(revision / "transaction.json", {"status": "rolled_back"})
        raise
    write(revision / "transaction.json", {"status": "applied", "targets": list(targets), "fingerprint": plan["fingerprint"]})
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--script", default="scripts/narration.json")
    parser.add_argument("--manifest", default="audio/tts/manifest.json")
    parser.add_argument("--apply", action="store_true", help="Apply timing with a recoverable before snapshot")
    parser.add_argument("--resize", action="store_true", help="Explicitly replace requested duration with measured schedule duration")
    parser.add_argument("--check", action="store_true", help="Validate and preview without writing any files")
    args = parser.parse_args()
    root = args.project.expanduser().resolve()
    plan = plan_schedule(root, output_path(root, args.script), output_path(root, args.manifest), args.resize)
    directory = output_path(root, "src/narration-plans/" + plan["fingerprint"][:16])
    changed = False
    if not args.check:
        for name, value in (("project.json", plan["project"]), ("storyboard.json", plan["storyboard"]), ("timing.json", plan["timing"]), ("plan.json", plan)):
            write(directory / name, value)
        (directory / "subtitles.srt").write_text(srt_text(plan["timing"]["segments"]), encoding="utf-8")
        if args.apply:
            changed = apply_schedule(root, plan)
    print(json.dumps({"plan": str(directory.relative_to(root)), "duration_seconds": plan["project"]["duration_seconds"],
                      "segments": len(plan["timing"]["segments"]), "applied": changed, "changes": plan["changes"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print("IvanVideo: " + str(error), file=sys.stderr)
        raise SystemExit(2)
