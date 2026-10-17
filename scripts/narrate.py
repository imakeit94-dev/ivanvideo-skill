#!/usr/bin/env python3
"""Generate cached Chinese sentence audio with installed macOS voices or supplied audio."""
import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

from film_core import digest, finite, identity, keys, local, output_path, read, run, tool, write


def load_script(root, script_path):
    data = read(script_path)
    keys(data, ("provider", "voice", "rate_wpm", "segments"), "narration script")
    provider = data.get("provider", "macos")
    if provider not in ("macos", "provided"):
        raise ValueError("Narration provider must be macos or provided; no service is installed automatically")
    voice, rate = data.get("voice", "Tingting"), data.get("rate_wpm", 195)
    if not isinstance(voice, str) or not voice.strip() or not isinstance(rate, int) or isinstance(rate, bool) or rate <= 0:
        raise ValueError("voice must be a name and rate_wpm a positive integer")
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("Narration needs non-empty segments")
    seen = set()
    for item in segments:
        keys(item, ("id", "shot_id", "text", "speech_text", "audio_path", "trim_in_seconds", "duration_seconds"), "narration segment")
        for name in ("id", "shot_id"):
            value = item.get(name)
            if not isinstance(value, str) or not value or not all(c.isalnum() or c in "-_" for c in value):
                raise ValueError("Narration segment IDs must use letters/digits/hyphens/underscores")
        if item["id"] in seen:
            raise ValueError("Duplicate narration segment id: " + item["id"])
        seen.add(item["id"])
        if not isinstance(item.get("text"), str) or not item["text"].strip():
            raise ValueError("Each segment needs subtitle text")
        if not isinstance(item.get("speech_text", item["text"]), str) or not item.get("speech_text", item["text"]).strip():
            raise ValueError("speech_text must be non-empty")
        if provider == "provided" and not isinstance(item.get("audio_path"), str):
            raise ValueError("provided segments need audio_path")
        if provider == "macos" and any(k in item for k in ("audio_path", "trim_in_seconds", "duration_seconds")):
            raise ValueError("macos segments do not accept input audio/trim fields")
        finite(item.get("trim_in_seconds", 0), "trim_in_seconds", 0)
        if "duration_seconds" in item:
            finite(item["duration_seconds"], "duration_seconds", 0.01)
    return {"provider": provider, "voice": voice, "rate_wpm": rate, "segments": segments}


def wav_info(path):
    with wave.open(str(path), "rb") as handle:
        if handle.getframerate() != 48000 or handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            raise ValueError("Narration cache must be mono 48 kHz 16-bit PCM WAV")
        samples = handle.getnframes()
        if samples <= 0:
            raise ValueError("Narration audio is empty")
        # Read the payload as well; a valid header alone does not prove the file is complete.
        if len(handle.readframes(samples)) != samples * 2:
            raise ValueError("Narration audio payload is truncated")
        return {"samples": samples, "sample_rate": 48000, "duration_seconds": samples / 48000}


def verify_manifest(root, manifest_path, script_path):
    root, manifest_path, script_path = Path(root).resolve(), Path(manifest_path).resolve(), Path(script_path).resolve()
    script = load_script(root, script_path)
    manifest = read(manifest_path)
    if manifest.get("script_sha256") != digest(script_path):
        raise ValueError("Narration script changed; regenerate audio and schedule")
    parts = manifest.get("segments")
    if not isinstance(parts, list) or len(parts) != len(script["segments"]):
        raise ValueError("Narration manifest has the wrong segment count")
    for source, part in zip(script["segments"], parts):
        for key in ("id", "shot_id", "text"):
            if part.get(key) != source[key]:
                raise ValueError("Narration manifest no longer matches " + key)
        if script["provider"] == "provided" and digest(local(root, source["audio_path"])) != part.get("source_sha256"):
            raise ValueError("Provided narration source changed; regenerate audio and schedule")
        path = local(root, part["path"])
        if not path.is_file() or digest(path) != part.get("sha256") or wav_info(path) != part.get("audio"):
            raise ValueError("Narration audio is missing or changed: " + source["id"])
    return manifest


def generate(root, script_path, check=False):
    root, script_path = Path(root).resolve(), Path(script_path).resolve()
    script = load_script(root, script_path)
    ffmpeg = tool("ffmpeg")
    backend = {"provider": script["provider"], "generator_sha256": digest(__file__),
               "ffmpeg_version": run([ffmpeg, "-version"]).stdout.splitlines()[0]}
    if script["provider"] == "macos":
        say = tool("say")
        voices = run([say, "-v", "?"]).stdout
        if not any(line.startswith(script["voice"] + " ") for line in voices.splitlines()):
            raise ValueError("Voice is not installed; run narrate.py --voices and choose an existing voice")
        backend.update(voice=script["voice"], rate_wpm=script["rate_wpm"],
                       macos_version=platform.mac_ver()[0], say_sha256=digest(say))
    manifest = {"schema_version": 1, "script_sha256": digest(script_path), "backend": backend,
                "granularity": "sentence_clip", "listening_review": "pending", "segments": []}
    hits = 0
    for item in script["segments"]:
        recipe = {"backend": backend, "speech_text": item.get("speech_text", item["text"])}
        if script["provider"] == "provided":
            source = local(root, item["audio_path"])
            if not source.is_file():
                raise ValueError("Provided voice file is missing: " + str(source))
            recipe.update(source_sha256=digest(source), trim_in_seconds=item.get("trim_in_seconds", 0),
                          duration_seconds=item.get("duration_seconds"))
        key = identity(recipe)
        directory = output_path(root, "audio/tts/chunks/" + key)
        path = directory / "voice.wav"
        if check:
            continue
        if directory.exists():
            receipt = read(directory / "chunk.json")
            if receipt.get("recipe") != recipe or receipt.get("sha256") != digest(path) or wav_info(path) != receipt.get("audio"):
                raise ValueError("Cached narration changed; preserve it as provided audio or remove that generated cache")
            hits += 1
        else:
            directory.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".tts-", dir=directory.parent) as temporary:
                stage = Path(temporary)
                if script["provider"] == "macos":
                    raw = stage / "voice.aiff"
                    # stdin keeps text out of command parsing and supports literal punctuation safely.
                    result = subprocess.run([say, "-v", script["voice"], "-r", str(script["rate_wpm"]), "-o", str(raw)],
                                            input=recipe["speech_text"], capture_output=True, text=True)
                    if result.returncode:
                        raise ValueError("System TTS failed: " + result.stderr[-2000:])
                    command = [ffmpeg, "-v", "error", "-y", "-i", raw]
                else:
                    command = [ffmpeg, "-v", "error", "-y", "-ss", str(item.get("trim_in_seconds", 0)), "-i", source]
                    if item.get("duration_seconds") is not None:
                        command += ["-t", str(item["duration_seconds"])]
                run(command + ["-vn", "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", stage / "voice.wav"])
                audio = wav_info(stage / "voice.wav")
                if item.get("duration_seconds") and abs(audio["duration_seconds"] - item["duration_seconds"]) > 1 / 48000:
                    raise ValueError("Provided voice is shorter than the requested trim")
                receipt = {"recipe": recipe, "sha256": digest(stage / "voice.wav"), "audio": audio}
                write(stage / "chunk.json", receipt)
                if (stage / "voice.aiff").exists():
                    (stage / "voice.aiff").unlink()
                stage.rename(directory)
        manifest["segments"].append({"id": item["id"], "shot_id": item["shot_id"], "text": item["text"],
                                     "speech_text": recipe["speech_text"], "path": str(path.relative_to(root)),
                                     "cache_key": key, "sha256": receipt["sha256"], "audio": receipt["audio"]})
        if script["provider"] == "provided":
            manifest["segments"][-1]["source_sha256"] = recipe["source_sha256"]
    if check:
        return {"valid": True, "provider": script["provider"], "segments": len(script["segments"])}
    if digest(script_path) != manifest["script_sha256"]:
        raise ValueError("Narration script changed during generation; manifest was not published")
    manifest["fingerprint"] = identity(manifest)
    immutable = output_path(root, "audio/tts/manifests/" + manifest["fingerprint"] + ".json")
    write(immutable, manifest)
    write(output_path(root, "audio/tts/manifest.json"), manifest)
    return {"manifest": str(immutable.relative_to(root)), "segments": len(manifest["segments"]), "cache_hits": hits}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, nargs="?")
    parser.add_argument("--script", default="scripts/narration.json")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--voices", action="store_true", help="List installed macOS voices without creating files")
    args = parser.parse_args()
    if args.voices:
        print(run([tool("say"), "-v", "?"]).stdout)
        return 0
    if args.project is None:
        parser.error("project is required unless using --voices")
    root = args.project.expanduser().resolve()
    print(json.dumps(generate(root, local(root, args.script), args.check), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError, wave.Error) as error:
        print("IvanVideo: " + str(error), file=sys.stderr)
        raise SystemExit(2)
