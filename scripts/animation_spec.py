"""Strict, dependency-free input checks for IvanVideo's bundled animation clips."""
import copy
import json
import math
from pathlib import Path

KINDS = {
    "t1_3b1b": {"title", "equation", "point", "line", "highlight"},
    "t2_keynote_ui": {"title", "card", "step", "image", "highlight", "number"},
    "t3_finance_chart": {"title", "bar", "line", "candle", "highlight", "number"},
    "y1_kurzgesagt": {"title", "point", "highlight", "enter"},
    "y2_vox": {"title", "image", "clip", "point", "highlight"},
    "y3_whiteboard": {"title", "point", "draw", "image", "highlight"},
    "y4_storytime": {"title", "point", "highlight", "react", "insert"},
    "y5_kinetic_type": {"title", "point", "number", "highlight"},
}


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize(raw, base):
    """Resolve timestamp anchors and local media, reject silently ignored cues."""
    if not isinstance(raw, dict):
        raise ValueError("Animation spec must be a JSON object")
    def finite_tree(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Animation data must not contain NaN or Infinity")
        if isinstance(value, dict):
            for child in value.values():
                finite_tree(child)
        elif isinstance(value, list):
            for child in value:
                finite_tree(child)
    finite_tree(raw)
    spec = copy.deepcopy(raw)
    if spec.get("alpha"):
        raise ValueError("This delivery renderer exports opaque MP4; use a custom alpha-capable pipeline for transparency")
    grammar = spec.get("grammar")
    if not isinstance(grammar, str) or grammar not in KINDS:
        raise ValueError("Unknown grammar; choose one of: " + ", ".join(KINDS))
    duration = spec.get("duration")
    if not number(duration) or duration <= 0:
        raise ValueError("duration must be finite and greater than zero")
    for key, default in (("width", 1920), ("height", 1080), ("fps", 30)):
        spec.setdefault(key, default)
        if not isinstance(spec[key], int) or isinstance(spec[key], bool) or spec[key] <= 0:
            raise ValueError(f"{key} must be a positive integer")
    if spec["width"] % 2 or spec["height"] % 2:
        raise ValueError("H.264 yuv420p requires even width and height")
    frames = round(duration * spec["fps"])
    if frames < 1:
        raise ValueError("duration is shorter than one output frame")
    safe = spec.setdefault("safe", {})
    if not isinstance(safe, dict):
        raise ValueError("safe must be an object")
    for side in ("top", "bottom", "left", "right"):
        safe.setdefault(side, 0)
        if not number(safe[side]) or safe[side] < 0:
            raise ValueError(f"safe.{side} must be finite and non-negative")
    if safe["top"] + safe["bottom"] >= spec["height"]:
        raise ValueError("safe areas leave no content height")
    if safe["left"] or safe["right"]:
        raise ValueError("Bundled grammars do not reliably honor left/right safe margins; use a custom layout for this shot")
    if not isinstance(spec.setdefault("data", {}), dict):
        raise ValueError("data must be an object")
    cues = spec.get("cues")
    if not isinstance(cues, list) or not cues:
        raise ValueError("cues must be a non-empty array")
    timeline_start = spec.get("timeline_start_seconds", 0)
    if not number(timeline_start) or timeline_start < 0:
        raise ValueError("timeline_start_seconds must be finite and non-negative")
    timing = {}
    if spec.get("timing_file"):
        path = (base / spec["timing_file"]).resolve()
        timing_data = read_json(path)
        segments = timing_data.get("segments") if isinstance(timing_data, dict) else None
        if not isinstance(segments, list):
            raise ValueError("timing_file must contain a segments array")
        for item in segments:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
                raise ValueError("Each timing segment needs a non-empty string id")
            if item["id"] in timing:
                raise ValueError("Duplicate timing segment id: " + item["id"])
            if not number(item.get("start_seconds")) or not number(item.get("end_seconds")) or not 0 <= item["start_seconds"] < item["end_seconds"]:
                raise ValueError("Invalid timing segment interval: " + item["id"])
            timing[item["id"]] = item
    for index, cue in enumerate(cues):
        if not isinstance(cue, dict) or not isinstance(cue.get("kind"), str) or cue["kind"] not in KINDS[grammar]:
            raise ValueError(f"Unsupported cue kind at cues[{index}] for {grammar}")
        if "anchor" in cue:
            anchor = cue["anchor"]
            if not isinstance(anchor, dict) or not isinstance(anchor.get("id"), str) or anchor["id"] not in timing:
                raise ValueError(f"Missing timing segment for cues[{index}].anchor")
            edge = anchor.get("edge", "start")
            offset = anchor.get("offset_seconds", 0)
            if edge not in ("start", "end") or not number(offset):
                raise ValueError(f"Invalid timing anchor at cues[{index}]")
            cue["at"] = timing[anchor["id"]][edge + "_seconds"] + offset - timeline_start
        at = cue.get("at")
        if not number(at) or not 0 <= at < duration:
            raise ValueError(f"cues[{index}].at must lie within [0, duration)")
        frame = round(at * spec["fps"])
        if frame >= frames:
            raise ValueError(f"cues[{index}] rounds beyond the last visible frame")
        cue["at"] = frame / spec["fps"]
        if "dur" in cue and (not number(cue["dur"]) or cue["dur"] <= 0):
            raise ValueError(f"cues[{index}].dur must be finite and positive")
        if not isinstance(cue.get("data", {}), dict):
            raise ValueError(f"cues[{index}].data must be an object")
    for item in [spec["data"]] + cues:
        image = item.get("image")
        if image:
            if not isinstance(image, str):
                raise ValueError("image must be a local path or a data URL")
            if image.startswith("data:"):
                continue
            if "://" in image:
                raise ValueError("Download approved reference images to the project before rendering")
            path = (base / image).expanduser().resolve()
            if not path.is_file():
                raise ValueError("Image not found: " + str(path))
            item["image"] = str(path)
    for cue in cues:
        if cue["kind"] in ("image", "clip") and not cue.get("image"):
            raise ValueError("image/clip cues need an image path")
    spec["cues"] = sorted(cues, key=lambda q: q["at"])
    return spec
