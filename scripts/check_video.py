#!/usr/bin/env python3
"""Decode a video, compare project delivery settings, and flag intervals for review."""
import argparse
from fractions import Fraction
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--video", default="outputs/final.mp4", help="Project-relative video file")
    parser.add_argument("--detect", action="store_true", help="Flag black/silent intervals; these need human interpretation")
    parser.add_argument("--frames", action="store_true", help="Extract frames around planned shot boundaries")
    args = parser.parse_args()
    root = args.project.expanduser().resolve()
    path = (root / args.video).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Video must be inside the video project")
    if not path.is_file() or not path.stat().st_size:
        raise ValueError("Video is missing or empty: " + str(path))
    ffprobe, ffmpeg = shutil.which("ffprobe"), shutil.which("ffmpeg")
    if not ffprobe or not ffmpeg:
        raise ValueError("FFmpeg and FFprobe are required")
    config = json.loads((root / "project.json").read_text(encoding="utf-8"))
    meta = json.loads(subprocess.check_output([ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)]))
    video = next(s for s in meta["streams"] if s["codec_type"] == "video")
    audio = [s for s in meta["streams"] if s["codec_type"] == "audio"]
    fps = float(Fraction(video["avg_frame_rate"]))
    duration = float(video.get("duration") or meta["format"]["duration"])
    errors = []
    if [video["width"], video["height"]] != [config["width"], config["height"]]:
        errors.append("Resolution differs from project.json")
    if abs(fps - config["fps"]) > 0.01:
        errors.append("Frame rate differs from project.json")
    if video["codec_name"] != config.get("output", {}).get("video_codec", "h264"):
        errors.append("Video codec differs from project.json")
    expected = config.get("duration_seconds")
    if expected is not None and abs(duration - expected) > max(1 / fps, 0.05):
        errors.append("Video duration differs from project.json")
    if config.get("narration", {}).get("enabled") and not audio:
        errors.append("Narration is enabled but no audio stream exists")
    for stream in audio:
        if stream.get("duration") and abs(float(stream["duration"]) - duration) > max(1 / fps, 0.1):
            errors.append("Audio/video durations differ; inspect the track ending")
    command = [ffmpeg, "-hide_banner", "-v", "info" if args.detect else "error", "-i", str(path)]
    if args.detect:
        command += ["-vf", "blackdetect=d=0.1:pix_th=0.10"]
        if audio:
            command += ["-af", "silencedetect=noise=-45dB:d=0.25"]
    command += ["-f", "null", "-"]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        errors.append("Full media decode failed: " + result.stderr[-2000:])
    events = [line.strip() for line in result.stderr.splitlines() if re.search(r"black_start:|silence_start:|silence_end:", line)]
    times = {0, max(0, duration - 1 / fps)}
    board = root / "storyboard.json"
    if board.is_file():
        for shot in json.loads(board.read_text(encoding="utf-8")).get("shots", []):
            for edge in (shot["start_seconds"], shot["end_seconds"]):
                times.update(t for t in (edge - 1 / fps, edge, edge + 1 / fps) if 0 <= t < duration)
            transition = shot.get("transition_in", {})
            if transition.get("duration_seconds"):
                times.add(shot["start_seconds"] + transition["duration_seconds"] / 2)
    times = sorted({round(t, 6) for t in times if 0 <= t < duration})
    frame_dir = path.parent / (path.stem + "-review")
    if args.frames:
        frame_dir.mkdir(parents=True, exist_ok=True)
        for index, t in enumerate(times):
            subprocess.run([ffmpeg, "-v", "error", "-ss", str(t), "-i", str(path), "-frames:v", "1", "-vf", "scale=640:-2", "-y", str(frame_dir / f"{index:03d}_{t:.3f}.jpg")], check=True)
    report = {
        "video": str(path.relative_to(root)), "codec": video["codec_name"], "fps": fps,
        "resolution": [video["width"], video["height"]], "duration_seconds": duration,
        "audio_streams": len(audio), "errors": errors, "review_events": events,
        "review_times_seconds": times, "review_frames": str(frame_dir.relative_to(root)) if args.frames else None,
        "manual_review_pending": ["Subtitle clipping, contrast, reading time and safe areas", "Narration/visual meaning and factual accuracy", "Real product behavior and UI authenticity", "Transition collisions, audio sync, music/voice balance and volume changes"],
        "note": "Black/silence detections are review clues, not automatic failures. No viewing or listening review is implied."
    }
    report_path = path.with_suffix(".qa.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(report_path), "errors": errors, "review_events": len(events)}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, StopIteration, subprocess.SubprocessError) as error:
        print("IvanVideo: " + str(error), file=sys.stderr)
        raise SystemExit(2)
