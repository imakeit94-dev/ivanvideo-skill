#!/usr/bin/env python3
"""Assemble editable animation/media shots, captions and checked audio into an H.264 film."""
import argparse
from fractions import Fraction
import json
import shutil
import sys
import tempfile
from pathlib import Path

from film_core import (audio_plan, build_timeline, digest, duration, engine_path, identity,
                       output_path, probe, read, run, subtitle_font, tool, write)
from mix_audio import create_mix, measure, verify_mix


def snapshot(root, captions):
    scripts = Path(__file__).parent
    names = ("film_core.py", "compile_timeline.py", "mix_audio.py", "render_film.py",
             "render_animation.py", "animation_spec.py", "validate_video_project.py", "check_video.py")
    version = identity({name: digest(scripts / name) for name in names})[:16]
    target = output_path(root, f"scripts/ivanvideo_film/{version}")
    target.mkdir(parents=True, exist_ok=True)
    for name in names:
        existing = target / name
        if existing.exists() and digest(existing) != digest(scripts / name):
            raise ValueError("Project runtime snapshot was edited; existing files were preserved")
        if not existing.exists():
            shutil.copy2(scripts / name, existing)
    if captions:
        settings = read(root / "project.json").get("subtitles", {})
        font = subtitle_font(root, settings)
        if not settings.get("font_path"):
            fonts = output_path(root, "src/film-fonts")
            fonts.mkdir(parents=True, exist_ok=True)
            for name in ("NotoSansSC-500.woff", "LICENSES.md", "OFL.txt"):
                if not (fonts / name).exists():
                    shutil.copy2(font.parent / name, fonts / name)
    return target


def ass_time(seconds):
    value = round(seconds * 100)
    return f"{value // 360000}:{value // 6000 % 60:02d}:{value // 100 % 60:02d}.{value % 100:02d}"


def subtitles(root, timeline, staging):
    config = read(root / "project.json")
    options = config.get("subtitles", {})
    safe = config.get("safe_area", {})
    bottom = round(max(safe.get("bottom", 0), options.get("margin_bottom", round(timeline["height"] * 0.05))))
    left, right = round(max(20, safe.get("left", 0))), round(max(20, safe.get("right", 0)))
    font = subtitle_font(root, options)
    (staging / "fonts").mkdir()
    shutil.copy2(font, staging / "fonts" / font.name)
    size = options.get("font_size", round(timeline["height"] * 0.038))
    family = options.get("font_name", "Noto Sans SC")
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {timeline['width']}
PlayResY: {timeline['height']}
WrapStyle: 0
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{family},{size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,{left},{right},{bottom},1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for cue in timeline["captions"]:
        # ASS controls are not accepted as caption markup; full-width variants are literal glyphs.
        text = cue["text"].replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\r\n", "\n").replace("\r", "\n").replace("\n", r"\N")
        lines.append(f"Dialogue: 0,{ass_time(cue['start_seconds'])},{ass_time(cue['end_seconds'])},Default,,0,0,0,,{text}")
    (staging / "subtitles.ass").write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


def animation_clip(root, shot):
    media = shot["media"]
    path = Path(media["path"])
    receipt = path.with_suffix(".cache.json")
    if path.is_file() and receipt.is_file():
        saved = read(receipt)
        if saved.get("cache_key") == media["cache_key"] and saved.get("sha256") == digest(path):
            return
        raise ValueError("Cached animation changed; preserve edits as media or remove the generated cache: " + str(path))
    if path.exists():
        raise ValueError("Unverified animation cache exists: " + str(path))
    engine = root / "src/animation-engine"
    if not engine.exists():
        shutil.copytree(engine_path(root), engine)
    run([sys.executable, Path(__file__).with_name("render_animation.py"), root, "--shot", shot["id"],
         "--out", str(path.relative_to(root))])
    write(receipt, {"cache_key": media["cache_key"], "sha256": digest(path)})


def inspect_media(shot, timeline):
    media, frames, fps = shot["media"], shot["frames"], timeline["fps"]
    path = Path(media["path"])
    metadata = probe(path)
    video = next((s for s in metadata["streams"] if s["codec_type"] == "video"), None)
    if not video:
        raise ValueError("Source has no readable video/image: " + str(path))
    if media["type"] != "image" and duration(metadata, video) - media["trim_in_seconds"] + 1 / fps < frames / fps:
        raise ValueError("Source is shorter than its shot; explicitly provide a hold/loop shot: " + shot["id"])


def normalize_clip(shot, timeline, target):
    media, frames, fps = shot["media"], shot["frames"], timeline["fps"]
    path = Path(media["path"])
    inspect_media(shot, timeline)
    trim = media["trim_in_seconds"]
    command = [tool("ffmpeg"), "-v", "error", "-y"]
    if media["type"] == "image":
        command += ["-loop", "1", "-framerate", str(fps)]
    else:
        command += ["-ss", str(trim)]
    command += ["-i", path]
    w, h = timeline["width"], timeline["height"]
    if media["fit"] == "cover":
        scale = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    else:
        scale = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"
    # At most one final frame is repeated to absorb source/target frame-grid rounding.
    filters = f"fps={fps},{scale},setsar=1,format=yuv420p,tpad=stop_mode=clone:stop_duration={1 / fps},trim=end_frame={frames},setpts=PTS-STARTPTS"
    run(command + ["-vf", filters, "-r", str(fps), "-frames:v", str(frames), "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "16", target])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--out", help="Project-relative MP4; defaults to project.output.path")
    parser.add_argument("--mix", help="Existing project-relative mix bundle; refuses stale input hashes")
    parser.add_argument("--check", action="store_true", help="Compile and validate audio without writing or rendering")
    parser.add_argument("--overwrite", action="store_true", help="Explicitly replace this film and its report")
    args = parser.parse_args()
    root = args.project.expanduser().resolve()
    timeline = build_timeline(root)
    plan = audio_plan(root, timeline)
    config = read(root / "project.json")
    output = output_path(root, args.out or config.get("output", {}).get("path", "outputs/final.mp4"))
    if output.suffix.lower() != ".mp4":
        raise ValueError("Film output must be an MP4")
    # Reject accidental overwrites of authoring inputs even when --overwrite is used.
    inputs = {root / "project.json", root / "storyboard.json"}
    inputs.update(Path(s["media"]["path"]) for s in timeline["shots"])
    inputs.update(Path(t["path"]) for t in plan["tracks"])
    if output in inputs:
        raise ValueError("Film output must not overwrite any input")
    if output.exists() and not args.overwrite and not args.check:
        raise ValueError("Output exists; choose a new version or explicitly use --overwrite")
    if args.mix:
        master, mix_report = verify_mix(root, timeline, output_path(root, args.mix))
        mix_dir = master.parent
    else:
        mix_dir = output_path(root, f"audio/mixes/{plan['fingerprint'][:16]}")
        master, mix_report = None, None
    for shot in timeline["shots"]:
        if shot["media"]["type"] != "animation":
            inspect_media(shot, timeline)
    if args.check:
        print(json.dumps({"valid": True, "frames": timeline["frames"], "audio_tracks": len(plan["tracks"]),
                          "captions": len(timeline["captions"]), "note": "No render or listening review performed"}, indent=2))
        return 0
    tool("ffmpeg")
    tool("ffprobe")
    runtime = snapshot(root, bool(timeline["captions"]))
    if master is None and plan["tracks"]:
        master, mix_report = create_mix(root, timeline, mix_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    write(output_path(root, "src/timeline.compiled.json"), timeline)
    with tempfile.TemporaryDirectory(prefix=".film-", dir=output.parent) as temp:
        staging = Path(temp)
        clips = []
        for index, shot in enumerate(timeline["shots"]):
            if shot["media"]["type"] == "animation":
                animation_clip(root, shot)
            clip = staging / f"clip-{index:04d}.mp4"
            normalize_clip(shot, timeline, clip)
            clips.append(clip)
        command = [tool("ffmpeg"), "-hide_banner", "-v", "error", "-y", "-filter_complex_threads", "1"]
        filters = []
        for i, clip in enumerate(clips):
            command += ["-i", clip]
            # setpts can clear frame-rate metadata; establish CFR after resetting timestamps.
            filters.append(f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS,fps={timeline['fps']}[v{i}]")
        current = "v0"
        for i, shot in enumerate(timeline["shots"][1:], 1):
            next_label = f"joined{i}"
            if shot["overlap_frames"]:
                filters.append(f"[{current}][v{i}]xfade=transition=fade:duration={shot['overlap_frames'] / timeline['fps']}:offset={shot['start_frame'] / timeline['fps']}[{next_label}]")
            else:
                filters.append(f"[{current}][v{i}]concat=n=2:v=1:a=0[{next_label}]")
            filters.append(f"[{next_label}]settb=AVTB,setpts=PTS-STARTPTS,fps={timeline['fps']}[ready{i}]")
            current = f"ready{i}"
        extra = ""
        if timeline["captions"]:
            subtitles(root, timeline, staging)
            extra = ",ass=filename=subtitles.ass:fontsdir=fonts"
        filters.append(f"[{current}]fps={timeline['fps']},trim=end_frame={timeline['frames']},setpts=PTS-STARTPTS{extra}[film]")
        if master:
            command += ["-i", master]
        command += ["-filter_complex", ";".join(filters), "-map", "[film]"]
        if master:
            command += ["-map", f"{len(clips)}:a:0", "-c:a", "aac", "-b:a", "192k"]
        else:
            command += ["-an"]
        candidate = staging / "film.mp4"
        command += ["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-r", str(timeline["fps"]), "-frames:v", str(timeline["frames"]), "-t", str(timeline["duration_seconds"]), "-movflags", "+faststart", candidate]
        run(command, cwd=staging)
        metadata = json.loads(run([tool("ffprobe"), "-v", "error", "-count_frames", "-show_streams", "-of", "json", candidate]).stdout)
        stream = next(s for s in metadata["streams"] if s["codec_type"] == "video")
        if (int(stream["nb_read_frames"]) != timeline["frames"] or [stream["width"], stream["height"]] != [timeline["width"], timeline["height"]]
                or stream["codec_name"] != "h264" or abs(float(Fraction(stream["avg_frame_rate"])) - timeline["fps"]) > 0.001):
            raise ValueError("Encoded film does not match the compiled frame count/dimensions/codec/fps")
        audio = [s for s in metadata["streams"] if s["codec_type"] == "audio"]
        if bool(audio) != bool(master) or any(abs(float(s["duration"]) - timeline["duration_seconds"]) > 0.1 for s in audio):
            raise ValueError("Encoded audio is missing or has the wrong duration")
        run([tool("ffmpeg"), "-v", "error", "-xerror", "-i", candidate, "-f", "null", "-"])
        encoded_loudness = measure(candidate) if master else None
        if encoded_loudness and float(encoded_loudness["input_tp"]) > 0:
            raise ValueError("AAC encoding introduced a peak above 0 dBTP; lower the mix level")
        if build_timeline(root)["fingerprint"] != timeline["fingerprint"] or audio_plan(root, timeline)["fingerprint"] != plan["fingerprint"]:
            raise ValueError("Inputs changed during rendering; film was not published")
        report = {"schema_version": 1, "timeline": timeline, "output_sha256": digest(candidate),
                  "mix": str(mix_dir.relative_to(root)) if master else None,
                  "master_sha256": digest(master) if master else None, "encoded_loudness": encoded_loudness,
                  "runtime": str(runtime.relative_to(root)), "ffmpeg_version": run([tool("ffmpeg"), "-version"]).stdout.splitlines()[0],
                  "checks": {"frame_count": True, "dimensions": True, "codec_fps": True, "full_decode": True, "audio_duration": True},
                  "manual_review": {"visual": "pending", "listening": "pending", "product_authenticity": "pending"}}
        candidate.replace(output)
        write(output.with_suffix(".film.json"), report)
        if timeline["captions"]:
            shutil.copy2(staging / "subtitles.ass", output.with_suffix(".ass"))
    print(json.dumps({"output": str(output), "report": str(output.with_suffix('.film.json')), "frames": timeline["frames"],
                      "runtime": str(runtime)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError, StopIteration) as error:
        print("IvanVideo: " + str(error), file=sys.stderr)
        raise SystemExit(2)
