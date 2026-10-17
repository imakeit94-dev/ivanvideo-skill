#!/usr/bin/env python3
"""Probe a reference video and extract representative frames for visual review."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def run_json(command: list[str]) -> dict:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("output", type=Path, help="Directory for report.json and frame images")
    parser.add_argument("--frames", type=int, default=6, help="Number of evenly distributed frames (2–20)")
    args = parser.parse_args()
    source = args.video.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not source.is_file() or not source.stat().st_size:
        print(f"Video is missing or empty: {source}", file=sys.stderr)
        return 2
    if not 2 <= args.frames <= 20:
        parser.error("--frames must be between 2 and 20")
    ffprobe, ffmpeg = shutil.which("ffprobe"), shutil.which("ffmpeg")
    if not ffprobe or not ffmpeg:
        print("FFmpeg and FFprobe are required. Install them or use another available media inspection tool.", file=sys.stderr)
        return 3
    try:
        data = run_json([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)])
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"Could not read media metadata: {exc}", file=sys.stderr)
        return 4
    video_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
    if not video_streams:
        print("No video stream found in the supplied file.", file=sys.stderr)
        return 4
    duration = float(data.get("format", {}).get("duration") or video_streams[0].get("duration") or 0)
    if duration <= 0:
        print("Video duration is unavailable or zero.", file=sys.stderr)
        return 4

    output.mkdir(parents=True, exist_ok=True)
    frames_dir = output / "frames"
    frames_dir.mkdir(exist_ok=True)
    timestamps = [duration * (i + 1) / (args.frames + 1) for i in range(args.frames)]
    extracted = []
    for index, seconds in enumerate(timestamps, 1):
        frame_path = frames_dir / f"frame_{index:02d}_{seconds:07.2f}s.jpg"
        result = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{seconds:.3f}", "-i", str(source), "-frames:v", "1", "-q:v", "2", "-y", str(frame_path)], capture_output=True, text=True)
        if result.returncode != 0 or not frame_path.is_file() or not frame_path.stat().st_size:
            print(f"Frame extraction failed at {seconds:.2f}s: {result.stderr.strip()}", file=sys.stderr)
            return 5
        extracted.append({"timestamp_seconds": round(seconds, 3), "path": str(frame_path)})
    report = {
        "source": str(source),
        "duration_seconds": duration,
        "format": data.get("format", {}),
        "streams": data.get("streams", []),
        "video_streams": video_streams,
        "audio_streams": [s for s in data.get("streams", []) if s.get("codec_type") == "audio"],
        "frames": extracted,
        "analysis_notes": {"observed": [], "inferred": []},
        "note": "Metadata and still frames only; listen to the media separately to assess sound content."
    }
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(report_path), "duration_seconds": duration, "resolution": [video_streams[0].get("width"), video_streams[0].get("height")], "frame_rate": video_streams[0].get("avg_frame_rate"), "audio_streams": len(report["audio_streams"]), "frames_extracted": len(extracted)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
