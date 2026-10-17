#!/usr/bin/env python3
"""Mix supplied voice/music/SFX with repeatable timing, optional ducking and loudnorm."""
import argparse
import json
import math
import re
import sys
import tempfile
from pathlib import Path

from film_core import audio_plan, build_timeline, digest, output_path, read, run, tool, write


def measure(path, normalization=None):
    target = normalization or {"integrated_lufs": -23, "true_peak_db": -1, "lra": 11}
    expression = (f"loudnorm=I={target['integrated_lufs']}:TP={target['true_peak_db']}:"
                  f"LRA={target['lra']}:print_format=json")
    result = run([tool("ffmpeg"), "-hide_banner", "-i", path, "-af", expression, "-f", "null", "-"])
    matches = re.findall(r'\{\s*"input_i".*?\}', result.stderr, re.S)
    if not matches:
        raise ValueError("FFmpeg did not return loudness measurements")
    return json.loads(matches[-1])


def verify_mix(root, timeline, directory):
    plan = audio_plan(root, timeline)
    report = read(directory / "mix.json")
    if report.get("plan", {}).get("fingerprint") != plan["fingerprint"]:
        raise ValueError("Mix is stale: storyboard, configuration, sources or mixer changed; rebuild the mix")
    master = directory / "master.wav"
    if not master.is_file() or digest(master) != report.get("master_sha256"):
        raise ValueError("Mix master is missing or changed")
    return master, report


def duck_expression(plan):
    duck = plan["ducking"]
    if not duck["enabled"]:
        return "1"
    weights = []
    for track in plan["tracks"]:
        if track["role"] != "voice":
            continue
        s, e = track["at_seconds"], track["at_seconds"] + track["duration_seconds"]
        a, r = duck["attack_seconds"], duck["release_seconds"]
        weights.append(f"if(lt(t,{s}),clip((t-({s}-{a}))/{a},0,1),if(lte(t,{e}),1,clip((({e}+{r})-t)/{r},0,1)))")
    weight = "0"
    for item in weights:
        weight = f"max({weight},{item})"
    return f"pow(10,-{duck['db']}*({weight})/20)"


def create_mix(root, timeline, directory):
    plan = audio_plan(root, timeline)
    if not plan["tracks"]:
        raise ValueError("No audio supplied; no mix was fabricated")
    if directory.exists():
        return verify_mix(root, timeline, directory)
    directory.parent.mkdir(parents=True, exist_ok=True)
    rate = plan["sample_rate"]
    samples = round(plan["duration_seconds"] * rate)
    with tempfile.TemporaryDirectory(prefix=".mix-", dir=directory.parent) as temp:
        staging = Path(temp)
        for role in ("voice", "music", "sfx"):
            tracks = [t for t in plan["tracks"] if t["role"] == role]
            command = [tool("ffmpeg"), "-hide_banner", "-v", "error", "-y"]
            filters, labels = [], []
            if not tracks:
                command += ["-f", "lavfi", "-i", f"anullsrc=r={rate}:cl=stereo"]
                filters.append(f"[0:a]atrim=end_sample={samples}[stem]")
            else:
                for i, track in enumerate(tracks):
                    command += ["-i", track["path"]]
                    offset = round(track["at_seconds"] * rate)
                    trim = round(track["trim_in_seconds"] * rate)
                    length = round(track["duration_seconds"] * rate)
                    label = f"t{i}"
                    filters.append(f"[{i}:a]aresample={rate},aformat=sample_fmts=fltp:channel_layouts=stereo,"
                                   f"atrim=start_sample={trim}:end_sample={trim + length},asetpts=PTS-STARTPTS,"
                                   f"volume={track['gain_db']}dB,adelay={offset}S:all=1,apad,atrim=end_sample={samples}[{label}]")
                    labels.append(f"[{label}]")
                filters.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:dropout_transition=0[raw]")
                filters.append(f"[raw]volume='{duck_expression(plan) if role == 'music' else '1'}':eval=frame[stem]")
            command += ["-filter_complex", ";".join(filters), "-map", "[stem]", "-c:a", "pcm_f32le", staging / f"{role}.wav"]
            run(command)
        raw = staging / "premaster.wav"
        run([tool("ffmpeg"), "-v", "error", "-y", "-i", staging / "voice.wav", "-i", staging / "music.wav",
             "-i", staging / "sfx.wav", "-filter_complex", "[0:a][1:a][2:a]amix=inputs=3:normalize=0:dropout_transition=0[m]",
             "-map", "[m]", "-c:a", "pcm_f32le", raw])
        before = measure(raw, plan["normalization"])
        norm = plan["normalization"]
        applied = None
        command = [tool("ffmpeg"), "-hide_banner", "-y", "-i", raw]
        if norm:
            values = [before[k] for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")]
            if not all(math.isfinite(float(v)) for v in values):
                raise ValueError("Silent/non-finite mix cannot be loudness-normalized")
            expression = (f"loudnorm=I={norm['integrated_lufs']}:TP={norm['true_peak_db']}:LRA={norm['lra']}:"
                          f"measured_I={before['input_i']}:measured_TP={before['input_tp']}:"
                          f"measured_LRA={before['input_lra']}:measured_thresh={before['input_thresh']}:"
                          f"offset={before['target_offset']}:linear=true:print_format=json,"
                          f"aresample={rate},apad,atrim=end_sample={samples}")
            command += ["-af", expression]
        elif float(before["input_tp"]) > 0:
            raise ValueError("Mix would clip; reduce gain_db or configure normalization")
        command += ["-ar", str(rate), "-c:a", "pcm_s24le", staging / "master.wav"]
        result = run(command)
        if norm:
            applied = json.loads(re.findall(r'\{\s*"input_i".*?\}', result.stderr, re.S)[-1])
        after = measure(staging / "master.wav", norm)
        if float(after["input_tp"]) > 0:
            raise ValueError("Master true peak exceeds 0 dBTP; reduce levels")
        raw.unlink()
        if audio_plan(root, timeline)["fingerprint"] != plan["fingerprint"]:
            raise ValueError("Audio inputs changed while mixing; master was not published")
        write(staging / "mix.json", {"plan": plan, "before": before, "normalization_result": applied,
                                     "after": after, "master_sha256": digest(staging / "master.wav"),
                                     "ffmpeg_version": run([tool("ffmpeg"), "-version"]).stdout.splitlines()[0],
                                     "manual_listening": "pending", "ducking_basis": "supplied voice clip intervals, not detected words"})
        # Publish the complete bundle only after all processing succeeds.
        staging.rename(directory)
    return directory / "master.wav", read(directory / "mix.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--out", help="Project-relative mix directory; existing valid mixes are reused, never overwritten")
    parser.add_argument("--check", action="store_true", help="Validate inputs and measure source durations without writing")
    args = parser.parse_args()
    root = args.project.expanduser().resolve()
    timeline = build_timeline(root)
    plan = audio_plan(root, timeline)
    directory = output_path(root, args.out or f"audio/mixes/{plan['fingerprint'][:16]}")
    if args.check:
        print(json.dumps({"valid": True, "tracks": len(plan["tracks"]), "fingerprint": plan["fingerprint"]}, indent=2))
    else:
        master, _ = create_mix(root, timeline, directory)
        print(json.dumps({"master": str(master), "report": str(directory / "mix.json")}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError, StopIteration) as error:
        print("IvanVideo: " + str(error), file=sys.stderr)
        raise SystemExit(2)
