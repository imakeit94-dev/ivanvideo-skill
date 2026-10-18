#!/usr/bin/env python3
"""Shared, dependency-free contracts for IvanVideo film compilation and delivery."""
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace


def read(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def finite(value, label, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(label + " must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(label + f" must be >= {minimum}")
    return value


def local(root, value):
    if not isinstance(value, str) or not value:
        raise ValueError("File path must be a non-empty string")
    return (root / Path(value).expanduser()).resolve()


def output_path(root, value):
    path = local(root, value)
    if not path.is_relative_to(root):
        raise ValueError("Generated files must stay inside the video project")
    return path


def keys(value, allowed, label):
    if not isinstance(value, dict):
        raise ValueError(label + " must be an object")
    unknown = set(value) - set(allowed)
    if unknown:
        raise ValueError(label + " has unsupported fields: " + ", ".join(sorted(unknown)))


def tool(name):
    found = shutil.which(name)
    if not found:
        raise ValueError(name + " is required; no software has been installed")
    return found


def run(command, cwd=None):
    result = subprocess.run([str(x) for x in command], cwd=cwd, capture_output=True, text=True)
    if result.returncode:
        raise ValueError("Command failed: " + str(command[0]) + "\n" + result.stderr[-5000:])
    return result


def probe(path):
    return json.loads(run([tool("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", path]).stdout)


def duration(meta, stream):
    value = stream.get("duration", meta.get("format", {}).get("duration"))
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError("Media duration could not be measured")
    return finite(result, "Media duration", 0)


def tree_hash(directory):
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError("Missing animation engine snapshot: " + str(directory))
    return identity({str(p.relative_to(directory)): digest(p) for p in sorted(directory.rglob("*"))
                     if p.is_file() and "__pycache__" not in p.parts})


def engine_path(root):
    own = root / "src/animation-engine"
    return own if own.is_dir() else Path(__file__).resolve().parents[1] / "assets/animation-engine"


def subtitle_font(root, settings):
    if settings.get("font_path"):
        return local(root, settings["font_path"])
    own = root / "src/film-fonts/NotoSansSC-500.woff"
    return own if own.is_file() else engine_path(root) / "lib/fonts/NotoSansSC-500.woff"


def media_spec(root, shot):
    media = shot.get("media")
    keys(media, ("type", "path", "trim_in_seconds", "fit"), "media")
    if "animation" in shot:
        raise ValueError(shot["id"] + ": choose media or animation, not both")
    if media.get("type") not in ("video", "image"):
        raise ValueError("media.type must be video or image")
    path = local(root, media.get("path"))
    if not path.is_file():
        raise ValueError("Missing media: " + str(path))
    trim = finite(media.get("trim_in_seconds", 0), "trim_in_seconds", 0)
    if media["type"] == "image" and trim:
        raise ValueError("Images cannot have a trim offset")
    fit = media.get("fit", "contain")
    if fit not in ("contain", "cover"):
        raise ValueError("media.fit must be contain or cover")
    return {"type": media["type"], "path": str(path), "trim_in_seconds": trim, "fit": fit,
            "sha256": digest(path)}


def srt_text(segments):
    def stamp(seconds):
        ms = round(seconds * 1000)
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    return "\n\n".join(f"{i}\n{stamp(c['start_seconds'])} --> {stamp(c['end_seconds'])}\n{c['text']}"
                       for i, c in enumerate(segments, 1)) + "\n"


def verify_generated_narration(root, config):
    state = config.get("narration", {}).get("generated_timeline")
    if state is None:
        return {}
    keys(state, ("script_path", "manifest_path", "timing_sha256", "track_ids"), "generated_timeline")
    from narrate import verify_manifest
    script = local(root, state["script_path"])
    manifest_path = local(root, state["manifest_path"])
    manifest = verify_manifest(root, manifest_path, script)
    board = read(root / "storyboard.json")
    known_shots = {shot["id"] for shot in board["shots"]}
    if any(part["shot_id"] not in known_shots for part in manifest["segments"]):
        raise ValueError("Generated narration refers to an unknown storyboard shot")
    for shot in board["shots"]:
        parts = [p for p in manifest["segments"] if p["shot_id"] == shot["id"]]
        if "".join(shot.get("narration", "").split()) != "".join("".join(p["text"] for p in parts).split()):
            raise ValueError("Storyboard narration changed; reconcile the script and regenerate the schedule")
    timing = local(root, config["narration"]["timing_path"])
    if digest(timing) != state["timing_sha256"]:
        raise ValueError("Generated narration timing changed; regenerate schedule or explicitly switch to manual timing")
    subtitles = config.get("subtitles", {})
    if subtitles.get("enabled") and local(root, subtitles.get("timing_path") or config["narration"]["timing_path"]) != timing:
        raise ValueError("Generated narration and enabled subtitles must share their timing source")
    segments = read(timing)["segments"]
    tracks = config.get("audio", {}).get("tracks", [])
    if len(segments) != len(manifest["segments"]) or len(state["track_ids"]) != len(segments):
        raise ValueError("Generated voice/caption segment count differs")
    for segment, part, track_id in zip(segments, manifest["segments"], state["track_ids"]):
        matches = [t for t in tracks if t.get("id") == track_id]
        if len(matches) != 1:
            raise ValueError("Generated voice track is missing or duplicated")
        track = matches[0]
        if (segment["id"] != part["id"] or segment["text"] != part["text"] or track.get("role") != "voice"
                or track.get("path") != part["path"] or abs(track.get("at_seconds", -1) - segment["start_seconds"]) > 1e-8
                or track.get("trim_in_seconds", 0) != 0 or track.get("duration_seconds") is not None
                or abs(segment["end_seconds"] - segment["start_seconds"] - part["audio"]["duration_seconds"]) > 1e-8):
            raise ValueError("Generated voice and sentence captions no longer match; regenerate the schedule")
    return {"narration_script": digest(script), "narration_manifest": digest(manifest_path), "narration_timing": digest(timing)}


def verify_capture(root, shot, media):
    evidence = shot.get("capture_evidence")
    if evidence is None:
        return {}
    keys(evidence, ("report", "asset_id"), "capture_evidence")
    report_path = local(root, evidence["report"])
    report = read(report_path)
    if report.get("display_mode") != "real_capture":
        raise ValueError("Capture evidence must describe an actual capture")
    if digest(local(root, report["spec_path"])) != report["spec_sha256"]:
        raise ValueError("Capture specification changed; recapture or retain its original version")
    matches = [a for a in report["assets"] if a["id"] == evidence["asset_id"]]
    if len(matches) != 1 or media["type"] not in ("image", "video"):
        raise ValueError("Shot capture asset ID is missing or ambiguous")
    asset = matches[0]
    if local(root, asset["path"]) != Path(media["path"]) or asset["sha256"] != media["sha256"] or asset["type"] != media["type"]:
        raise ValueError("Shot media differs from its real capture evidence")
    return {"capture-" + shot["id"]: digest(report_path)}


def verify_asset(root, shot, media):
    evidence = shot.get("asset_evidence")
    if evidence is None:
        return {}
    keys(evidence, ("id",), "asset_evidence")
    from asset_workflow import registered_asset
    item = registered_asset(root, evidence["id"])
    if (local(root, item["path"]) != Path(media["path"]) or item["media_type"] != media["type"]
            or item["sha256"] != media.get("sha256")):
        raise ValueError("Shot media differs from its registered asset")
    return {"asset-" + shot["id"]: identity(item)}


def build_timeline(root):
    """Compile authoring seconds to absolute frame boundaries; no files are written."""
    root = Path(root).expanduser().resolve()
    config, board = read(root / "project.json"), read(root / "storyboard.json")
    if not isinstance(config, dict) or not isinstance(board, dict):
        raise ValueError("project.json and storyboard.json must be objects")
    fps = finite(config["fps"], "fps", 0.001)
    for name in ("width", "height"):
        value = config[name]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value % 2:
            raise ValueError(name + " must be a positive even integer for H.264/yuv420p")
    safe = config.get("safe_area", {})
    if not isinstance(safe, dict):
        raise ValueError("safe_area must be an object")
    for side in ("top", "bottom", "left", "right"):
        finite(safe.get(side, 0), "safe_area." + side, 0)
    if safe.get("top", 0) + safe.get("bottom", 0) >= config["height"] or safe.get("left", 0) + safe.get("right", 0) >= config["width"]:
        raise ValueError("Safe area must leave visible content")
    try:
        a, b = map(int, config["aspect_ratio"].split(":"))
        if a <= 0 or b <= 0 or config["width"] * b != config["height"] * a:
            raise ValueError()
    except (ValueError, KeyError, AttributeError):
        raise ValueError("aspect_ratio must agree with width and height")
    if config.get("output", {}).get("container", "mp4") != "mp4" or config.get("output", {}).get("video_codec", "h264") != "h264":
        raise ValueError("The film renderer currently supports MP4/H.264 only")
    dependencies = {"project.json": digest(root / "project.json"), "storyboard.json": digest(root / "storyboard.json")}
    dependencies.update(verify_generated_narration(root, config))
    if config.get("broll") is not None:
        from broll import bound_segments
        source, _ = bound_segments(root)
        dependencies["broll_source"] = identity(source)
    shots = board.get("shots")
    if not isinstance(shots, list) or not shots:
        raise ValueError("Film compilation needs a non-empty shots array")
    compiled, seen = [], set()
    previous = None
    engine_hash = None
    for shot in shots:
        label = shot.get("id") if isinstance(shot, dict) else None
        if not isinstance(label, str) or not label or not all(c.isalnum() or c in "-_" for c in label) or label in seen:
            raise ValueError("Shot IDs must be unique non-empty letters/digits/hyphens/underscores")
        seen.add(label)
        start = finite(shot["start_seconds"], label + " start", 0)
        end = finite(shot["end_seconds"], label + " end", 0)
        first, last = round(start * fps), round(end * fps)
        if end <= start or last <= first:
            raise ValueError(label + " has no positive frame interval")
        overlap = 0
        transition = shot.get("transition_in")
        if previous is None:
            if abs(start) > 1e-8 or transition:
                raise ValueError("First shot must start at zero without an incoming transition")
        else:
            difference = previous["end_seconds"] - start
            if difference < -1e-6:
                raise ValueError("Timeline gap before " + label + "; add an explicit image/video shot")
            if difference > 1e-6:
                keys(transition, ("from", "duration_seconds", "type"), "transition_in")
                seconds = finite(transition.get("duration_seconds"), "transition duration", 0)
                if transition.get("from") != previous["id"] or abs(seconds - difference) > 1e-6 or transition.get("type", "fade") != "fade":
                    raise ValueError("Incoming fade must exactly describe overlap with the preceding shot")
                overlap = previous["end_frame"] - first
                if overlap <= 0 or overlap >= min(previous["frames"], last - first):
                    raise ValueError("Fade must leave non-overlapping content in both shots")
                if len(compiled) > 1 and first < compiled[-2]["end_frame"]:
                    raise ValueError("Three-way transitions are unsupported")
            elif transition:
                raise ValueError("transition_in needs a real overlapping interval")
            elif first != previous["end_frame"]:
                raise ValueError("Frame gap before " + label)
        if "animation" in shot:
            if "media" in shot:
                raise ValueError(label + ": choose media or animation, not both")
            from render_animation import load_input
            from animation_spec import normalize
            raw, path, _ = load_input(root, SimpleNamespace(spec=None, shot=label))
            spec = normalize(raw, path.parent)
            engine_hash = engine_hash or tree_hash(engine_path(root))
            source_hashes = {}
            for item in [spec.get("data", {})] + spec["cues"]:
                if item.get("image") and not item["image"].startswith("data:"):
                    source_hashes[item["image"]] = digest(item["image"])
            if raw.get("timing_file"):
                source_hashes["timing"] = digest((path.parent / raw["timing_file"]).resolve())
            cache = identity({"raw": raw, "media": source_hashes, "engine": engine_hash,
                              "renderer": digest(Path(__file__).with_name("render_animation.py")),
                              "spec_contract": digest(Path(__file__).with_name("animation_spec.py"))})
            media = {"type": "animation", "path": str(root / f"previews/film-clips/{label}-{cache[:16]}.mp4"),
                     "cache_key": cache, "fit": "contain", "trim_in_seconds": 0}
            dependencies[label] = cache
        elif "media" in shot:
            media = media_spec(root, shot)
            dependencies[label] = media["sha256"]
        else:
            raise ValueError(label + " needs media or animation; descriptions alone cannot be rendered")
        dependencies.update(verify_capture(root, shot, media))
        dependencies.update(verify_asset(root, shot, media))
        current = {"id": label, "start_seconds": start, "end_seconds": end, "start_frame": first,
                   "end_frame": last, "frames": last - first, "overlap_frames": overlap, "media": media}
        compiled.append(current)
        previous = current
    expected = config.get("duration_seconds")
    if expected is not None:
        finite(expected, "duration_seconds", 0.001)
        if abs(expected - compiled[-1]["end_seconds"]) > 1e-6:
            raise ValueError("Storyboard must cover the requested duration exactly")
    captions = []
    settings = config.get("subtitles", {})
    keys(settings, ("enabled", "timing_path", "font_path", "font_name", "font_size", "margin_bottom"), "subtitles")
    if not isinstance(settings.get("enabled", False), bool):
        raise ValueError("subtitles.enabled must be boolean")
    if settings.get("enabled"):
        timing = local(root, settings.get("timing_path") or config.get("narration", {}).get("timing_path"))
        value = read(timing)
        if not isinstance(value, dict):
            raise ValueError("Subtitle timing must be an object")
        dependencies["subtitle_timing"] = digest(timing)
        if value.get("method") not in ("manual", "aligned", "draft", "measured"):
            raise ValueError("Subtitle timing must record manual, aligned, draft or measured method")
        segments = value.get("segments")
        if not isinstance(segments, list) or not segments:
            raise ValueError("Enabled subtitles need non-empty timing segments")
        last_end, caption_ids = 0, set()
        for segment in segments:
            if not isinstance(segment, dict):
                raise ValueError("Each caption must be an object")
            sid, text = segment.get("id"), segment.get("text")
            s = finite(segment.get("start_seconds"), "caption start", 0)
            e = finite(segment.get("end_seconds"), "caption end", 0)
            if not isinstance(sid, str) or not sid or sid in caption_ids or not isinstance(text, str) or not text.strip():
                raise ValueError("Captions need unique IDs and non-empty text")
            if s < last_end or e <= s or e > compiled[-1]["end_seconds"]:
                raise ValueError("Captions must be ordered, non-overlapping, and inside the film")
            if round(e * 100) <= round(s * 100):
                raise ValueError("Caption is shorter than ASS centisecond precision")
            caption_ids.add(sid)
            captions.append({"id": sid, "text": text, "start_seconds": s, "end_seconds": e})
            last_end = e
        font = subtitle_font(root, settings)
        if not font.is_file():
            raise ValueError("Subtitle font not available: " + str(font))
        dependencies["subtitle_font"] = digest(font)
        finite(settings.get("font_size", round(config["height"] * 0.038)), "font_size", 1)
        finite(settings.get("margin_bottom", 36), "margin_bottom", 0)
        if settings.get("margin_bottom", 36) >= config["height"]:
            raise ValueError("Subtitle margin_bottom must lie inside the frame")
        if settings.get("font_name") and any(c in settings["font_name"] for c in ",\r\n"):
            raise ValueError("Invalid ASS font name")
    result = {"schema_version": 1, "width": config["width"], "height": config["height"], "fps": fps,
              "frames": compiled[-1]["end_frame"], "duration_seconds": compiled[-1]["end_frame"] / fps,
              "shots": compiled, "captions": captions, "dependencies": dependencies}
    result["fingerprint"] = identity(result)
    return result


def audio_plan(root, timeline):
    config, board = read(root / "project.json"), read(root / "storyboard.json")
    settings = config.get("audio", {})
    keys(settings, ("tracks", "ducking", "normalization", "sample_rate"), "audio")
    rate = settings.get("sample_rate", 48000)
    if not isinstance(rate, int) or isinstance(rate, bool) or rate not in (44100, 48000):
        raise ValueError("audio.sample_rate must be 44100 or 48000")
    tracks = settings.get("tracks", [])
    if not isinstance(tracks, list):
        raise ValueError("audio.tracks must be an array")
    tracks = [dict(t) for t in tracks]
    narration = config.get("narration", {})
    if narration.get("enabled") is True and not narration.get("audio_path") and not any(t.get("role") == "voice" for t in tracks):
        raise ValueError("Narration is enabled but no voice audio was supplied")
    if narration.get("audio_path") and narration.get("enabled") is not False:
        if any(t.get("role") == "voice" for t in tracks):
            raise ValueError("Choose narration.audio_path or explicit voice tracks to avoid duplicate narration")
        tracks.append({"id": "narration", "role": "voice", "path": narration["audio_path"], "at_seconds": 0})
    landmarks = {}
    for shot in board["shots"]:
        for i, cue in enumerate(shot.get("audio_cues", [])):
            keys(cue, ("id", "path", "offset_seconds", "sync_offset_seconds", "trim_in_seconds", "duration_seconds", "gain_db"), "audio_cue")
            offset = finite(cue.get("offset_seconds"), "cue offset_seconds", 0)
            if offset >= shot["end_seconds"] - shot["start_seconds"]:
                raise ValueError("Audio cue must target a moment inside its shot")
            sync = finite(cue.get("sync_offset_seconds", 0), "sync_offset_seconds", 0)
            track = {k: v for k, v in cue.items() if k not in ("offset_seconds", "sync_offset_seconds")}
            track.update(id=cue.get("id", f"{shot['id']}-sfx-{i + 1}"), role="sfx",
                         at_seconds=shot["start_seconds"] + offset - sync)
            landmarks[track["id"]] = {"sync_offset_seconds": sync, "action_seconds": shot["start_seconds"] + offset}
            tracks.append(track)
    seen, measured = set(), []
    for track in tracks:
        keys(track, ("id", "role", "path", "at_seconds", "trim_in_seconds", "duration_seconds", "gain_db"), "audio track")
        label, role = track.get("id"), track.get("role")
        if not isinstance(label, str) or not label or label in seen or role not in ("voice", "music", "sfx"):
            raise ValueError("Audio tracks need unique IDs and role voice/music/sfx")
        seen.add(label)
        at = finite(track.get("at_seconds", 0), "track at_seconds", 0)
        trim = finite(track.get("trim_in_seconds", 0), "track trim_in_seconds", 0)
        gain = finite(track.get("gain_db", 0), "gain_db")
        path = local(root, track.get("path"))
        meta = probe(path)
        stream = next((s for s in meta["streams"] if s["codec_type"] == "audio"), None)
        if stream is None:
            raise ValueError("Audio track has no audio stream: " + str(path))
        available = duration(meta, stream) - trim
        length = finite(track.get("duration_seconds", available), "track duration_seconds", 0.00001)
        if available <= 0 or length > available + 1 / rate:
            raise ValueError("Audio trim extends beyond source: " + label)
        if at + length > timeline["duration_seconds"] + max(0.02, 1 / timeline["fps"]):
            raise ValueError("Audio extends past film; explicitly trim it: " + label)
        landmark = landmarks.get(label, {})
        if landmark.get("sync_offset_seconds", 0) >= length:
            raise ValueError("Sound's sync offset must lie inside the trimmed sound: " + label)
        measured.append({"id": label, "role": role, "path": str(path), "sha256": digest(path),
                         "at_seconds": at, "trim_in_seconds": trim, "duration_seconds": length, "gain_db": gain, **landmark})
    duck = settings.get("ducking", {})
    keys(duck, ("enabled", "db", "attack_seconds", "release_seconds"), "ducking")
    if not isinstance(duck.get("enabled", False), bool):
        raise ValueError("ducking.enabled must be boolean")
    duck = {"enabled": duck.get("enabled", False), "db": finite(duck.get("db", 10), "duck db", 0),
            "attack_seconds": finite(duck.get("attack_seconds", 0.08), "duck attack", 0.00001),
            "release_seconds": finite(duck.get("release_seconds", 0.25), "duck release", 0.00001)}
    norm = settings.get("normalization")
    if norm is not None:
        keys(norm, ("integrated_lufs", "true_peak_db", "lra"), "normalization")
        norm = {"integrated_lufs": finite(norm.get("integrated_lufs"), "integrated_lufs"),
                "true_peak_db": finite(norm.get("true_peak_db"), "true_peak_db"), "lra": finite(norm.get("lra", 11), "lra")}
        if not -70 <= norm["integrated_lufs"] <= -5 or not -9 <= norm["true_peak_db"] <= 0 or not 1 <= norm["lra"] <= 50:
            raise ValueError("Loudnorm targets are outside FFmpeg supported ranges")
    result = {"schema_version": 1, "timeline_fingerprint": timeline["fingerprint"], "sample_rate": rate,
              "duration_seconds": timeline["duration_seconds"], "tracks": measured, "ducking": duck, "normalization": norm,
              "mixer_sha256": digest(Path(__file__).with_name("mix_audio.py")), "core_sha256": digest(__file__)}
    result["fingerprint"] = identity(result)
    return result
