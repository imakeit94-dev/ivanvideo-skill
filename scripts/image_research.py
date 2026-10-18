#!/usr/bin/env python3
"""Optional read-only image research for IvanVideo; never installs or generates media."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

TAXONOMY = "oip-visual-v2"
SCHEMA = "ivanvideo-image-research-v1"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(value):
    return hashlib.sha256(value).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def local(root, path):
    result = (root / path).resolve()
    if not result.is_relative_to(root):
        raise ValueError("Research files must stay inside the project")
    return result


def save_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(encoded(value))


def archive_status(repo=None, python=None):
    """Explicit repo/engine failures do not trigger fallback downloads or retries."""
    repo = Path(repo or os.environ.get("OIP_REPO_ROOT") or
                Path.home() / ".local/share/open-image-prompts").expanduser().resolve()
    python = str(python or sys.executable)
    entry = repo / "skills/img-gen-prompts/scripts/oip.py"
    engine = {"repository": str(repo), "python": python, "commit": None, "dataset_version": None}
    try:
        if not entry.is_file() or not (repo / "scripts/prompt_library.py").is_file():
            raise ValueError("Optional Open Image Prompts checkout is unavailable")
        version = subprocess.run([python, "-c", "import sys; print(sys.version_info.major, sys.version_info.minor)"],
                                 capture_output=True, text=True, timeout=5, check=True)
        if tuple(map(int, version.stdout.split())) < (3, 10):
            raise ValueError("Archive requires an existing Python >=3.10; use --python or a compatible caller")
        # Use an explicit environment so an unrelated OIP_REPO_ROOT cannot override --repo.
        status = call_engine(engine, "status")
        if status.get("ready") is not True or status.get("active_taxonomy_version") != TAXONOMY:
            raise ValueError("Archive is not ready with " + TAXONOMY)
        manifest = repo / "data/dataset-manifest.json"
        if manifest.is_file():
            data = read(manifest)
            engine["dataset_version"] = data.get("dataset_version")
            engine["archive_sha256"] = data.get("db", {}).get("sha256")
        if shutil.which("git"):
            commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                                    capture_output=True, text=True, timeout=5, check=False)
            if not commit.returncode:
                engine["commit"] = commit.stdout.strip()
        return {"available": True, "engine": engine, "archive_status": status, "reason": None}
    except (ValueError, OSError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as error:
        return {"available": False, "engine": engine, "archive_status": None, "reason": str(error)}


def call_engine(engine, *arguments):
    # The upstream CLI consults OIP_REPO_ROOT; bind it only in this child process.
    environment = os.environ.copy()
    environment["OIP_REPO_ROOT"] = engine["repository"]
    command = [engine["python"], str(Path(engine["repository"]) / "skills/img-gen-prompts/scripts/oip.py"), *arguments]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                            env=environment, timeout=45, check=False)
    if result.returncode:
        raise ValueError("Archive command failed: " + result.stderr.strip()[-400:])
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError("Archive returned a non-object response")
    return value


def nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + " must be a non-empty string")
    return value


def strings(value, name):
    if not isinstance(value, list) or not all(isinstance(x, str) and x.strip() for x in value):
        raise ValueError(name + " must be an array of non-empty strings")
    return value


def http_url(value):
    return isinstance(value, str) and urlparse(value).scheme in ("https", "http") and bool(urlparse(value).netloc)


def records_from(payload, repository):
    if payload.get("taxonomy_version") != TAXONOMY or payload.get("schema_version") != "oip-retrieval-v1":
        raise ValueError("Unexpected retrieval taxonomy or schema")
    records, seen = [], set()
    for channel, kind in (("results", "exact"), ("related_results", "related")):
        values = payload.get(channel, [])
        if not isinstance(values, list):
            raise ValueError("Archive result channel must be an array")
        for item in values:
            if not isinstance(item, dict):
                raise ValueError("Archive record must be an object")
            label = nonempty(item.get("tweet_id"), "Reference ID")
            prompt = nonempty(item.get("source_prompt"), "Unchanged source prompt")
            author = nonempty(item.get("author"), "Author")
            source = nonempty(item.get("source_url"), "Source URL")
            if label in seen or not http_url(source):
                raise ValueError("Duplicate reference ID or invalid source URL")
            seen.add(label)
            missing = strings(item.get("missing_constraints", []), "missing_constraints")
            if item.get("match_kind") != kind or (kind == "exact" and missing) or (kind == "related" and len(missing) != 1):
                raise ValueError("Exact/related channels or missing constraints are inconsistent")
            image = item.get("images", {}).get("representative") or {}
            path = image.get("absolute_local_path") or image.get("local_path")
            candidate = (repository / path).resolve() if isinstance(path, str) and path else None
            if candidate and not candidate.is_relative_to((repository / "images").resolve()):
                candidate = None
            if not http_url(image.get("url")) and not (candidate and candidate.is_file()):
                raise ValueError("Reference has no usable image location")
            records.append({"id": label, "author": author, "source_url": source,
                            "source_prompt": prompt, "source_prompt_sha256": sha(prompt.encode()),
                            "match_kind": kind, "missing_constraints": missing,
                            "match_reasons": item.get("match_reasons", []),
                            "image": {"path": str(candidate) if candidate else None, "url": image.get("url"),
                                      "exists_at_search": bool(candidate and candidate.is_file())},
                            "selected": False, "prompt_kind": "unclassified",
                            "visual_review": {"status": "pending", "method": None, "notes": ""},
                            "reuse_notes": "", "avoid_copying": [], "rights_status": "unknown"})
    return records


def search(root, intent, out="references/image-research.json", repo=None, python=None, limit=5):
    root = Path(root).resolve()
    nonempty(intent, "Search intent")
    if not 1 <= limit <= 12:
        raise ValueError("limit must be 1..12")
    target = local(root, out)
    if not target.is_relative_to(root / "references"):
        raise ValueError("Research output must be in references/")
    if target.exists():
        raise ValueError("Research output exists; choose a new --out version")
    available = archive_status(repo, python)
    payload, records = None, []
    if available["available"]:
        try:
            payload = call_engine(available["engine"], "search", "--intent", intent, "--limit", str(limit))
            if payload.get("query") != intent:
                raise ValueError("Archive changed the original query")
            records = records_from(payload, Path(available["engine"]["repository"]))
        except (ValueError, OSError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as error:
            available.update(available=False, reason=str(error))
            payload, records = None, []
    source = {"query": intent, "engine": available["engine"], "archive_status": available["archive_status"], "response": payload}
    content = encoded(source)
    snapshot = local(root, "references/image-research-sources/" + sha(content) + ".json")
    if snapshot.exists():
        if snapshot.read_bytes() != content:
            raise ValueError("Existing research snapshot was modified")
    else:
        save_new(snapshot, source)
    report = {"schema_version": SCHEMA, "query": intent,
              "status": "unavailable" if not available["available"] else ("results" if records else "no_matches"),
              "reason": available["reason"], "engine": available["engine"],
              "source_snapshot": str(snapshot.relative_to(root)), "source_sha256": sha(content),
              "parsed_intent": payload.get("parsed_intent") if payload else None,
              "records": records, "derivations": []}
    save_new(target, report)
    # A project can re-check its archived evidence after moving, without the global Skill.
    script = Path(__file__).resolve()
    runtime = root / "scripts/ivanvideo_visual" / sha(script.read_bytes())[:16] / script.name
    runtime.parent.mkdir(parents=True, exist_ok=True)
    if runtime.exists() and runtime.read_bytes() != script.read_bytes():
        raise ValueError("Project visual runtime changed; preserve the edited version")
    if not runtime.exists():
        shutil.copyfile(script, runtime)
    return report


def check(root, report_path="references/image-research.json"):
    root = Path(root).resolve()
    direction = root / "references/visual-direction.json"
    if direction.is_file():
        spec = read(direction)["creative_spec"]
        fields = {"style_card_id", "subject", "use", "composition", "material_texture", "lighting", "palette", "mood", "invariants", "avoid", "aspect_ratio"}
        if set(spec) != fields:
            raise ValueError("creative_spec fields do not match the visual-direction contract")
        for name in fields - {"style_card_id", "invariants", "avoid"}:
            nonempty(spec[name], name)
        if spec["style_card_id"] is not None:
            nonempty(spec["style_card_id"], "style_card_id")
        strings(spec["invariants"], "invariants")
        strings(spec["avoid"], "avoid")
        if spec["aspect_ratio"] != "unspecified":
            try:
                a, b = map(int, spec["aspect_ratio"].split(":"))
                if a <= 0 or b <= 0:
                    raise ValueError()
            except ValueError:
                raise ValueError("Visual aspect_ratio must be positive integers like 16:9, or unspecified")
    path = local(root, report_path)
    if not path.is_file():
        return {"valid": True, "direction": direction.is_file(), "research": "not_configured", "selected": 0}
    report = read(path)
    if report.get("schema_version") != SCHEMA:
        raise ValueError("Unknown image research schema")
    source_path = local(root, report["source_snapshot"])
    if sha(source_path.read_bytes()) != report["source_sha256"]:
        raise ValueError("Research source snapshot changed")
    source = read(source_path)
    response = source["response"]
    if report["query"] != source["query"] or report["parsed_intent"] != (response.get("parsed_intent") if response else None):
        raise ValueError("Original query or parsed intent changed")
    expected = records_from(response, Path(source["engine"]["repository"])) if response is not None else []
    actual = report["records"]
    if [r["id"] for r in actual] != [r["id"] for r in expected] or report["engine"] != source["engine"]:
        raise ValueError("Reference IDs, order or engine provenance changed")
    expected_state = "results" if expected else ("no_matches" if response is not None else "unavailable")
    if report["status"] != expected_state or (response is not None and report["query"] != response["query"]):
        raise ValueError("Research status or original query changed")
    selected = set()
    for item, original in zip(actual, expected):
        # Review/selection and derived prompts are editable; archived source fields are not.
        for key in ("id", "author", "source_url", "source_prompt", "source_prompt_sha256", "match_kind", "missing_constraints", "match_reasons"):
            if item[key] != original[key]:
                raise ValueError("Archived source field changed: " + key)
        if item["image"].get("path") != original["image"]["path"] or item["image"].get("url") != original["image"]["url"]:
            raise ValueError("Archived representative image changed")
        if not isinstance(item["selected"], bool):
            raise ValueError("selected must be boolean")
        if item["prompt_kind"] not in ("unclassified", "generation_prompt", "commentary"):
            raise ValueError("Unknown source prompt kind")
        if item["selected"]:
            review = item["visual_review"]
            if review["status"] != "reviewed":
                raise ValueError("Selected references require actual visual review")
            for key in ("method", "notes"):
                nonempty(review[key], "Visual review " + key)
            nonempty(item["reuse_notes"], "Reusable visual decision")
            strings(item["avoid_copying"], "avoid_copying")
            selected.add(item["id"])
    seen_assets = set()
    for derived in report["derivations"]:
        label = nonempty(derived["asset_id"], "Derived asset ID")
        if label in seen_assets:
            raise ValueError("Duplicate derived asset ID")
        seen_assets.add(label)
        ids = strings(derived["source_ids"], "Derived source IDs")
        if not set(ids) <= selected:
            raise ValueError("Derived prompts may cite only visually reviewed, selected references")
        prompts = [nonempty(derived[k], k) for k in ("prompt_en", "prompt_zh")]
        nonempty(derived["rationale"], "Derivation rationale")
        plan = read(root / "references/asset-plan.json")
        matches = [x for x in plan["assets"] if x["id"] == label]
        if len(matches) != 1 or matches[0]["prompt"] not in prompts:
            raise ValueError("Derived prompt does not match the existing asset plan")
    return {"valid": True, "direction": direction.is_file(), "research": report["status"],
            "selected": len(selected), "derived_assets": len(seen_assets),
            "note": "Contract validation is not visual, factual or rights approval"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    status = commands.add_parser("status")
    search_parser = commands.add_parser("search")
    search_parser.add_argument("project", type=Path)
    search_parser.add_argument("--intent", required=True)
    search_parser.add_argument("--limit", type=int, default=5)
    search_parser.add_argument("--out", default="references/image-research.json")
    checker = commands.add_parser("check")
    checker.add_argument("project", type=Path)
    checker.add_argument("--report", default="references/image-research.json")
    for command in (status, search_parser):
        command.add_argument("--repo", type=Path, help="Existing optional checkout; never downloaded")
        command.add_argument("--python", help="Existing Python >=3.10 for the archive only")
    args = parser.parse_args()
    if args.command == "status":
        result = archive_status(args.repo, args.python)
    else:
        root = args.project.expanduser().resolve()
        if not (root / "project.json").is_file() or not (root / "storyboard.json").is_file():
            raise ValueError("Use an existing IvanVideo project")
        if args.command == "search":
            result = search(root, args.intent, args.out, args.repo, args.python, args.limit)
            result = {"report": args.out, "status": result["status"], "reason": result["reason"], "records": len(result["records"])}
        else:
            result = check(root, args.report)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as error:
        print("IvanVideo image research: " + str(error), file=sys.stderr)
        raise SystemExit(2)
