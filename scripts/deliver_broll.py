#!/usr/bin/env python3
"""Render clean packaging clips and a verified source-time replacement table."""
import argparse
from fractions import Fraction
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

from broll import bound_segments
from film_core import build_timeline, digest, engine_path, identity, output_path, read, run, tool, tree_hash, write
from render_film import animation_clip, normalize_clip, snapshot


def stamp(frame, fps):
    ms = round(Fraction(frame * 1000, fps))
    return f"{ms//3600000:02d}-{ms//60000%60:02d}-{ms//1000%60:02d},{ms%1000:03d}"


def inputs(root):
    source, segments = bound_segments(root)
    timeline = build_timeline(root)
    return source, segments, timeline, {"timeline": timeline["fingerprint"], "source": identity(source), "engine": tree_hash(engine_path(root)),
                                       "renderer": digest(Path(__file__).with_name("render_animation.py")), "delivery": digest(__file__)}


def check_clip(path, frames, width, height, fps):
    metadata = json.loads(run([tool("ffprobe"), "-v", "error", "-count_frames", "-show_streams", "-of", "json", path]).stdout)
    video = next((s for s in metadata["streams"] if s.get("codec_type") == "video"), None)
    if not video or int(video["nb_read_frames"]) != frames or [video["width"], video["height"]] != [width, height] or video["codec_name"] != "h264" or Fraction(video["avg_frame_rate"]) != fps:
        raise ValueError("Packaging clip frame count/specification mismatch: " + str(path))
    if any(s.get("codec_type") == "audio" for s in metadata["streams"]):
        raise ValueError("Clean packaging delivery must not duplicate source narration")
    run([tool("ffmpeg"), "-v", "error", "-xerror", "-i", path, "-f", "null", "-"])
    return {"frame_count": True, "dimensions": True, "codec_fps": True, "full_decode": True, "no_audio": True}


def deliver(root, directory):
    root, directory = Path(root).resolve(), Path(directory).resolve()
    source, segments, timeline, signature = inputs(root)
    if directory.exists(): raise ValueError("Delivery directory exists; use a new version")
    runtime = snapshot(root, bool(timeline["captions"]))
    compiled = {s["id"]: s for s in timeline["shots"]}
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".broll-delivery-", dir=directory.parent) as temporary:
        stage, records = Path(temporary), []
        for index, (shot, segment) in enumerate(segments, 1):
            clean_title = re.sub(r'[\\/:*?"<>|\s]+', "", segment["title"])[:60] or segment["id"]
            first, last, fps = segment["start_frame"], segment["end_frame"], source["fps"]
            name = f"{index:02d}_{segment['id']}_{clean_title}_{stamp(first,fps)}~{stamp(last,fps)}.mp4"
            target = stage / name
            if "animation" in shot:
                # Share the full-film renderer's per-shot cache; unchanged shots stay untouched.
                animation_clip(root, compiled[shot["id"]])
                shutil.copy2(compiled[shot["id"]]["media"]["path"], target)
            else:
                normalize_clip(compiled[shot["id"]], timeline, target)
            checks = check_clip(target, last-first, source["width"], source["height"], fps)
            records.append({**segment, "file": name, "sha256": digest(target), "frames": last-first, "fps": fps,
                            "start_ms": round(Fraction(first*1000,fps)), "end_ms": round(Fraction(last*1000,fps)),
                            "interval": "[start_frame,end_frame)", "checks": checks})
        if inputs(root)[-1] != signature: raise ValueError("Delivery inputs changed while rendering")
        lines = ["# 包装片段替换对照表", "", "时间位置来自母版；区间左闭右开，终点帧属于下一段。", "",
                 f"源视频平均帧率：{source['master_rate']}；交付帧网格：{source['fps']} fps CFR。转换帧率时，下表帧号属于输出网格，不是源文件的原始帧编号。", "",
                 "片段为干净画面：不烧录审核头像/字幕，不含原旁白或其他声音。保留原剪辑音轨；声音另行按项目需求混合。", "",
                 "| 镜头 | 文件 | 母版入点 → 出点（毫秒） | 起帧 → 终帧 | 帧数 / fps | 字幕 ID | 句中切入 / 切出 |",
                 "| --- | --- | --- | --- | --- | --- | --- |"]
        for r in records:
            lines.append(f"| {r['id']} | {r['file']} | {r['start_ms']} → {r['end_ms']} | {r['start_frame']} → {r['end_frame']} | {r['frames']} / {r['fps']} | {', '.join(r['cue_ids'])} | {r['cut_start']} / {r['cut_end']} |")
        lines += ["", "毫秒为帧位置的显示取整值；以起止帧和 fps 为精确定位依据，不代表字幕或词级对齐精度。", "",
                  "自动检查了实际文件、帧数、规格、完整解码和无音轨。视觉、遮挡及回放听感仍需在原剪辑时间线上审核。"]
        (stage / "replacement-table.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
        write(stage / "delivery.json", {"schema_version": 1, "inputs": signature, "width": source["width"], "height": source["height"],
                                       "fps": source["fps"], "source_rate": source["master_rate"], "runtime": str(runtime.relative_to(root)), "segments": records,
                                       "table_sha256": digest(stage / "replacement-table.md"), "manual_review": "pending"})
        stage.rename(directory)
    return records


def verify(root, directory):
    report = read(directory / "delivery.json")
    if report["inputs"] != inputs(root)[-1]: raise ValueError("Packaging delivery is stale")
    if digest(directory / "replacement-table.md") != report["table_sha256"]: raise ValueError("Replacement table changed")
    for record in report["segments"]:
        path = output_path(directory, record["file"])
        if digest(path) != record["sha256"]: raise ValueError("Delivered clip changed")
        check_clip(path, record["frames"], report["width"], report["height"], report["fps"])
    return {"valid": True, "segments": len(report["segments"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path); parser.add_argument("--out", default="outputs/broll-v1")
    parser.add_argument("--check", action="store_true"); parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(); root = args.project.expanduser().resolve(); out = output_path(root, args.out)
    if args.verify: result = verify(root, out)
    elif args.check:
        _, segments, _, _ = inputs(root); result = {"valid": True, "segments": len(segments), "rendered": False}
    else: result = {"directory": str(out), "segments": len(deliver(root,out))}
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    try: main()
    except (ValueError, OSError, KeyError, TypeError) as error:
        print("IvanVideo: " + str(error), file=sys.stderr); raise SystemExit(2)
