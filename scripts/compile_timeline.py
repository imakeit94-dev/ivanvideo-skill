#!/usr/bin/env python3
"""Compile the existing storyboard to a reproducible frame timeline (not an editing source)."""
import argparse
import json
import sys
from pathlib import Path

from film_core import build_timeline, output_path, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--check", action="store_true", help="Validate without writing")
    args = parser.parse_args()
    root = args.project.expanduser().resolve()
    timeline = build_timeline(root)
    if not args.check:
        write(output_path(root, "src/timeline.compiled.json"), timeline)
    print(json.dumps({"valid": True, "shots": len(timeline["shots"]), "frames": timeline["frames"],
                      "duration_seconds": timeline["duration_seconds"], "fingerprint": timeline["fingerprint"]}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print("IvanVideo: " + str(error), file=sys.stderr)
        raise SystemExit(2)
