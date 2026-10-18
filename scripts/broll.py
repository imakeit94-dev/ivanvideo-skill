#!/usr/bin/env python3
"""Import SRT, select source intervals and bind packaging shots to the existing storyboard."""
import argparse
import copy
from fractions import Fraction
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

from film_core import digest, duration, finite, identity, keys, local, output_path, probe, read, run, tool, write


def parse_srt(path):
    text = Path(path).read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ValueError("SRT is empty")
    cues, seen, last = [], set(), -1
    pattern = r"(\d{2,}):([0-5]\d):([0-5]\d)[,.](\d{3})\s*-->\s*(\d{2,}):([0-5]\d):([0-5]\d)[,.](\d{3})"
    for block in re.split(r"\n[ \t]*\n", text):
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit():
            raise ValueError("Malformed SRT block; expected numeric ID, timing and text")
        number = int(lines[0].strip())
        match = re.fullmatch(pattern, lines[1].strip())
        if not match or number in seen or number < 1:
            raise ValueError("Invalid SRT timing or duplicate/non-positive cue ID")
        h, m, s, ms, eh, em, es, ems = map(int, match.groups())
        start, end = ((h * 60 + m) * 60 + s) * 1000 + ms, ((eh * 60 + em) * 60 + es) * 1000 + ems
        caption = "\n".join(lines[2:]).strip()
        if not caption or end <= start or start < last:
            raise ValueError("SRT cues need non-empty text, positive intervals and chronological starts")
        cues.append({"id": "srt-" + str(number), "number": number, "start_ms": start, "end_ms": end, "text": caption})
        seen.add(number)
        last = start
    return cues


def import_source(root, srt, master, fps=None, check=False):
    root, srt, master = Path(root).resolve(), Path(srt).resolve(), Path(master).resolve()
    cues = parse_srt(srt)
    meta = probe(master)
    video = next((s for s in meta["streams"] if s.get("codec_type") == "video"), None)
    if not video:
        raise ValueError("Master needs a video stream")
    rate = Fraction(video["avg_frame_rate"])
    if rate <= 0:
        raise ValueError("Master frame rate is unavailable")
    if fps is None:
        if rate.denominator != 1 or video.get("r_frame_rate") != video.get("avg_frame_rate"):
            raise ValueError("Non-integer/possibly variable frame rate: explicitly choose an integer --fps for conversion")
        fps = int(rate)
    if isinstance(fps, bool) or not isinstance(fps, int) or fps <= 0:
        raise ValueError("Output fps must be a positive integer")
    seconds = duration(meta, video)
    frames = round(Fraction(str(seconds)) * fps)
    if frames < 1 or cues[-1]["end_ms"] > seconds * 1000 + 1:
        raise ValueError("Subtitles extend beyond the measured master video")
    if video["width"] % 2 or video["height"] % 2:
        raise ValueError("Use even master dimensions for the H.264 pipeline")
    srt_hash, master_hash = digest(srt), digest(master)
    metadata = {"schema_version": 1, "srt_sha256": srt_hash, "master_path": str(master.relative_to(root)) if master.is_relative_to(root) else str(master),
                "master_sha256": master_hash, "master_rate": str(rate), "fps": fps, "frames": frames,
                "width": video["width"], "height": video["height"], "duration_seconds": seconds,
                "has_audio": any(s.get("codec_type") == "audio" for s in meta["streams"]), "cues": cues,
                "timing_accuracy": "Imported subtitle intervals; not verified speech/word alignment",
                "frame_rate_policy": "CFR output; source time in seconds is preserved"}
    directory = output_path(root, "references/broll-sources/" + identity(metadata)[:16])
    metadata["srt_path"] = str((directory / "source.srt").relative_to(root))
    target = directory / "source.json"
    if not check:
        if target.exists():
            if read(target) != metadata or digest(directory / "source.srt") != srt_hash:
                raise ValueError("Imported source snapshot changed; preserve it and use a new revision")
        else:
            directory.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".srt-", dir=directory.parent) as temp:
                stage = Path(temp)
                shutil.copy2(srt, stage / "source.srt")
                if digest(stage / "source.srt") != srt_hash or digest(master) != master_hash:
                    raise ValueError("Source changed during import")
                write(stage / "source.json", metadata)
                stage.rename(directory)
    return {"source_path": str(target.relative_to(root)), "source": metadata}


def load_source(root, path):
    value = read(path)
    if value.get("schema_version") != 1 or digest(local(root, value["srt_path"])) != value["srt_sha256"]:
        raise ValueError("Imported SRT is missing or changed; import a new revision")
    if parse_srt(local(root, value["srt_path"])) != value["cues"]:
        raise ValueError("Imported cue data differs from its original SRT")
    if digest(local(root, value["master_path"])) != value["master_sha256"]:
        raise ValueError("Master changed; import a new source revision")
    return value


def segment_id(value):
    if not isinstance(value, str) or not value or not all(c.isalnum() or c in "-_" for c in value) or value.startswith("GAP-"):
        raise ValueError("Segment ID must be letters/digits/hyphens/underscores and cannot start GAP-")
    return value


def select_segments(source, selection):
    keys(selection, ("segments",), "selection")
    if not isinstance(selection.get("segments"), list) or not selection["segments"]:
        raise ValueError("Selection needs a non-empty segments array")
    cues = {c["id"]: c for c in source["cues"]}
    result, seen = [], set()
    for item in selection["segments"]:
        keys(item, ("id", "title", "from_cue", "to_cue", "start_ms", "end_ms", "snap"), "segment")
        label = segment_id(item.get("id"))
        if label in seen or not isinstance(item.get("title"), str) or not item["title"].strip():
            raise ValueError("Segment IDs must be unique and titles non-empty")
        seen.add(label)
        snap = item.get("snap", "exact")
        if snap not in ("exact", "expand"):
            raise ValueError("snap must be exact or expand")
        if "from_cue" in item or "to_cue" in item:
            if "start_ms" in item or "end_ms" in item:
                raise ValueError("Choose cue IDs or milliseconds, not both")
            if item.get("from_cue") not in cues or item.get("to_cue") not in cues:
                raise ValueError("Unknown cue ID")
            start, end = cues[item["from_cue"]]["start_ms"], cues[item["to_cue"]]["end_ms"]
        else:
            start, end = item.get("start_ms"), item.get("end_ms")
            if any(isinstance(x, bool) or not isinstance(x, int) for x in (start, end)):
                raise ValueError("start_ms/end_ms must be integers")
        if not 0 <= start < end <= source["duration_seconds"] * 1000 + 1:
            raise ValueError("Selection outside master or reversed")
        hits = [c for c in source["cues"] if c["end_ms"] > start and c["start_ms"] < end]
        if not hits:
            raise ValueError("Selection has no subtitles")
        requested = [start, end]
        if snap == "expand":
            start, end = min(start, min(c["start_ms"] for c in hits)), max(end, max(c["end_ms"] for c in hits))
        first, last = round(Fraction(start * source["fps"], 1000)), round(Fraction(end * source["fps"], 1000))
        if last <= first or last > source["frames"]:
            raise ValueError("Selection has no positive in-range frame interval")
        a, b = first / source["fps"], last / source["fps"]
        hits = [c for c in source["cues"] if c["end_ms"] / 1000 > a and c["start_ms"] / 1000 < b]
        tolerance = 500 / source["fps"] + 1  # Frame-grid rounding is not a meaningful mid-sentence cut.
        result.append({"id": label, "title": item["title"], "start_frame": first, "end_frame": last,
                       "requested_ms": requested, "snap": snap, "cue_ids": [c["id"] for c in hits],
                       "cut_start": any(c["start_ms"] < a * 1000 - tolerance and c["end_ms"] > a * 1000 + tolerance for c in hits),
                       "cut_end": any(c["start_ms"] < b * 1000 - tolerance and c["end_ms"] > b * 1000 + tolerance for c in hits)})
    result.sort(key=lambda x: x["start_frame"])
    if any(b["start_frame"] < a["end_frame"] for a, b in zip(result, result[1:])):
        raise ValueError("Selected intervals overlap after frame rounding")
    return result


def apply_selection(root, source_path, selection):
    root, source_path = Path(root).resolve(), Path(source_path).resolve()
    source = load_source(root, source_path)
    segments = select_segments(source, selection)
    config, board = read(root / "project.json"), read(root / "storyboard.json")
    if board.get("shots") or config.get("broll"):
        raise ValueError("Apply selection only to an empty new packaging project; preserve existing shots")
    updated = copy.deepcopy(config)
    fps = source["fps"]
    updated.update(width=source["width"], height=source["height"], fps=fps, duration_seconds=source["frames"] / fps)
    from math import gcd
    divisor = gcd(source["width"], source["height"])
    updated["aspect_ratio"] = f"{source['width']//divisor}:{source['height']//divisor}"
    updated["broll"] = {"source_path": str(source_path.relative_to(root)), "source_sha256": digest(source_path),
                        "overlay_path": "references/broll-overlay.json"}
    audio = root / f"audio/broll-source/{source['master_sha256'][:16]}.wav"
    timing_path = root / "audio/broll-subtitles.json"
    if timing_path.exists():
        raise ValueError("Subtitle output exists; preserve it")
    if source["has_audio"]:
        audio.parent.mkdir(parents=True, exist_ok=True)
        if audio.exists():
            raise ValueError("Source audio output exists; inspect it before applying selection")
        with tempfile.TemporaryDirectory(prefix=".voice-", dir=audio.parent) as temporary:
            candidate = Path(temporary) / "source.wav"
            run([tool("ffmpeg"), "-v", "error", "-i", local(root, source["master_path"]), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", candidate])
            candidate.replace(audio)
    timing = {"method": "manual", "provenance": "Imported SRT; not speech-aligned or verified", "segments": [
        {"id": c["id"], "text": c["text"], "start_seconds": c["start_ms"] / 1000,
         "end_seconds": min(c["end_ms"] / 1000, source["frames"] / fps)} for c in source["cues"]]}
    updated["narration"] = {"enabled": source["has_audio"], "audio_path": str(audio.relative_to(root)) if source["has_audio"] else None,
                            "timing_path": str(timing_path.relative_to(root)), "notes": "Original first audio track; may already contain music, not certified isolated narration"}
    updated["subtitles"] = {"enabled": False}
    shots, cursor = [], 0
    def gap(first, last):
        if last > first:
            shots.append({"id": "GAP-" + str(first), "start_seconds": first / fps, "end_seconds": last / fps,
                          "purpose": "保留未选区间的母版画面", "narration": "", "assets": [], "audio_cues": [],
                          "visual": "母版实际画面", "motion": "沿用母版动作", "on_screen_text": [],
                          "source_notes": ["Original master: " + source["master_path"]],
                          "media": {"type": "video", "path": source["master_path"], "trim_in_seconds": first / fps}})
    for segment in segments:
        gap(cursor, segment["start_frame"])
        hits = [c for c in source["cues"] if c["id"] in segment["cue_ids"]]
        shots.append({"id": segment["id"], "start_seconds": segment["start_frame"] / fps, "end_seconds": segment["end_frame"] / fps,
                      "purpose": "口播包装：" + segment["title"], "visual": "起步画面；按原字幕完善后审核", "motion": "复用内置动画",
                      "on_screen_text": [segment["title"]], "narration": "".join(c["text"] for c in hits), "assets": [], "audio_cues": [],
                      "source_notes": ["Imported SRT: " + source["srt_path"], "Original master: " + source["master_path"]],
                      "broll_segment": segment, "animation": {"grammar": "t2_keynote_ui", "data": {"title": segment["title"]},
                                                               "cues": [{"at": 0, "kind": "title"}]}})
        cursor = segment["end_frame"]
    gap(cursor, source["frames"])
    backup = root / ("references/broll-apply/" + identity({"project": config, "board": board, "segments": segments})[:16])
    write(backup / "project.before.json", config)
    write(backup / "storyboard.before.json", board)
    write(backup / "state.json", {"state": "applying"})
    try:
        write(timing_path, timing)
        write(root / "project.json", updated)
        write(root / "storyboard.json", {"shots": shots})
        write(backup / "state.json", {"state": "applied"})
    except Exception:
        write(root / "project.json", config)
        write(root / "storyboard.json", board)
        timing_path.unlink(missing_ok=True)
        if source["has_audio"]: audio.unlink(missing_ok=True)
        write(backup / "state.json", {"state": "rolled_back"})
        raise
    return {"segments": segments, "shots": len(shots), "backup": str(backup.relative_to(root))}


def bound_segments(root):
    config, board = read(root / "project.json"), read(root / "storyboard.json")
    state = config.get("broll")
    keys(state, ("source_path", "source_sha256", "overlay_path"), "broll")
    path = local(root, state["source_path"])
    if digest(path) != state["source_sha256"]:
        raise ValueError("Source metadata changed; preserve original import")
    source = load_source(root, path)
    if any(config[k] != source[k] for k in ("fps", "width", "height")):
        raise ValueError("Packaging specifications differ from imported source")
    timing = read(local(root, config["narration"]["timing_path"]))
    expected = [{"id":c["id"], "text":c["text"], "start_seconds":c["start_ms"]/1000,
                 "end_seconds":min(c["end_ms"]/1000,source["frames"]/source["fps"])} for c in source["cues"]]
    if timing.get("segments") != expected:
        raise ValueError("Imported subtitle timing changed; import a new source revision instead of editing the derived timing")
    selected, seen = [], set()
    for shot in board["shots"]:
        segment = shot.get("broll_segment")
        if segment is None: continue
        label = segment_id(segment["id"])
        first, last = segment["start_frame"], segment["end_frame"]
        if label in seen or shot["id"] != label or any(isinstance(v, bool) or not isinstance(v, int) for v in (first, last)):
            raise ValueError("Invalid/duplicate packaging shot binding")
        if not 0 <= first < last <= source["frames"] or abs(shot["start_seconds"] * source["fps"] - first) > 1e-6 or abs(shot["end_seconds"] * source["fps"] - last) > 1e-6:
            raise ValueError("Packaging shot interval changed; create a new selection explicitly")
        hits = [c["id"] for c in source["cues"] if c["end_ms"] * source["fps"] > first * 1000 and c["start_ms"] * source["fps"] < last * 1000]
        if segment["cue_ids"] != hits:
            raise ValueError("Packaging cue binding changed")
        seen.add(label); selected.append((shot, segment))
    if not selected:
        raise ValueError("No selected packaging shots")
    selected.sort(key=lambda pair: pair[1]["start_frame"])
    if any(b[1]["start_frame"] < a[1]["end_frame"] for a,b in zip(selected, selected[1:])):
        raise ValueError("Packaging intervals overlap")
    return source, selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("import")
    p.add_argument("--srt", type=Path, required=True); p.add_argument("--master", type=Path, required=True)
    p.add_argument("--fps", type=int); p.add_argument("--check", action="store_true")
    p = commands.add_parser("list"); p.add_argument("--source", required=True)
    p = commands.add_parser("select"); p.add_argument("--source", required=True); p.add_argument("--selection", required=True)
    p.add_argument("--apply", action="store_true")
    commands.add_parser("check")
    args = parser.parse_args(); root = args.project.expanduser().resolve()
    if args.command == "import":
        result = import_source(root, local(root, str(args.srt)), local(root, str(args.master)), args.fps, args.check)
    elif args.command == "list":
        result = load_source(root, output_path(root, args.source))["cues"]
    elif args.command == "select":
        path, selection = output_path(root, args.source), read(output_path(root, args.selection))
        result = apply_selection(root, path, selection) if args.apply else {"segments": select_segments(load_source(root, path), selection), "applied": False}
    else:
        source, segments = bound_segments(root)
        result = {"valid": True, "segments": len(segments), "fps": source["fps"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try: main()
    except (ValueError, OSError, KeyError, TypeError, ZeroDivisionError) as error:
        print("IvanVideo: " + str(error), file=sys.stderr); raise SystemExit(2)
