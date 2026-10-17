# Video project format

## Layout

`init_video_project.py` creates this editable project skeleton:

```text
project.json
storyboard.json
scripts/brief.md
references/README.md
assets/manifest.json
src/
audio/
previews/
outputs/
```

The video project belongs in a user-selected location and must not be stored under the Skill directory. Preserve original media in place when practical; record paths and copy only when required by the editing tool or requested by the user.

## `project.json`

Top-level fields:

- `title`, `topic`, `audience`, `purpose`
- `duration_seconds`, `language`, `platform`
- `aspect_ratio` (`16:9`, `9:16`, or `1:1`), `width`, `height`, `fps`
- `output` (`container`, `video_codec`, `path`)
- `narration` (`enabled`, `voice`, `notes`, `audio_path`, `timing_path`)
- Optional `narration.generated_timeline` is owned by the measured narration scheduler; it records script/manifest references, timing hash and generated track IDs. Do not forge hashes or manually move generated tracks; regenerate timing or explicitly adopt a manual workflow.
- `safe_area` (`top`, `bottom`, `left`, `right` in pixels); bundled clip layout supports top/bottom only
- `visual_system` (`palette`, `fonts`, `concept_colors`, `motion_notes`)
- Optional `audio` (tracks, ducking, normalization, sample rate) and `subtitles`; missing fields preserve old behavior. Details: [audio-production.md](audio-production.md) and [film-production.md](film-production.md).
- `reference_videos`, `asset_roots`, `missing_items`, `assumptions`, `status`, `created_at`

Use `null` or an empty array for unknown values; preserve user supplied values. Do not pretend that a missing preference was specified.

Aspect ratio and actual dimensions must agree. Initialization selects 1920×1080 for 16:9, 1080×1920 for 9:16, and 1080×1080 for 1:1. Custom dimensions must be supplied as a width/height pair; the ratio is inferred when omitted. Conflicting ratio/dimensions are rejected before files are written.

## `storyboard.json`

Use `{ "shots": [] }` until a storyboard exists. A shot should include:

```json
{
  "id": "S01",
  "start_seconds": 0,
  "end_seconds": 5,
  "purpose": "",
  "visual": "",
  "motion": "",
  "on_screen_text": [],
  "narration": "",
  "audio_cues": [],
  "assets": [],
  "source_notes": []
}
```

Shot intervals use seconds from the start of the program and should not overlap unless an intentional overlap is documented. Include a source for each external factual claim and a provenance note for each non-original asset.

For intentional overlap, put `transition_in: {"from": "S01", "duration_seconds": 0.3}` on the incoming shot; the overlap must equal the transition duration. An explicit pause or black shot can cover a deliberate gap.

An optional `animation` object selects the built-in grammar, data, and cues. Its media paths are relative to the project root. Details are in [animation-production.md](animation-production.md). Shots without this object may use screen recordings, custom components, or other renderers. `assets` lists file paths; they must resolve or be marked missing in the manifest during planning. `validate_video_project.py --delivery` requires all referenced assets and a complete timeline.

For the full-film renderer, each shot chooses exactly one `animation` or `media: {type, path, trim_in_seconds, fit}`. Media type is video or image. Custom components enter as rendered video. `audio_cues` can contain structured shot-local sound events, described in audio-production.md. `--film` adds the stricter renderability, subtitle and measured audio checks without changing planning-only validation.

Optional `voice_timing` controls lead/gap/tail/reading-hold time during narration scheduling. Optional `capture_evidence: {report, asset_id}` binds a media shot to its actual capture report. Formats and commands: [narration-production.md](narration-production.md), [software-capture.md](software-capture.md).

## Narration timing

`narration.timing_path` points to a JSON file such as `audio/timing.json`:

```json
{
  "method": "manual",
  "audio_path": "audio/voice.wav",
  "segments": [
    {"id": "voice-feature", "text": "相关关键词或句子", "start_seconds": 1.2, "end_seconds": 2.8}
  ]
}
```

Times are global seconds from the start of the video. `method` records `manual`, `aligned`, `draft`, or `measured`. The scheduler's measured method has `granularity: sentence_clip`, meaning measured audio-clip intervals including pauses, never word/phoneme alignment. Draft estimates are not verified alignment. Segment IDs are unique, allowing cue anchors to survive a text or timing revision. Retain original narration and timing provenance.

## Editable animation snapshot

The first animation render adds `src/animation-engine/` (including license notices), `src/clips/`, and `scripts/ivanvideo_runtime/`. Store sample MP4/PNG and `.render.json` records in `previews/`; keep release exports in `outputs/`. The engine snapshot stays with the project and is not overwritten when the global Skill changes.

Full-film rendering additionally saves a versioned tool snapshot under `scripts/ivanvideo_film/`, optional subtitle fonts under `src/film-fonts/`, cached animation clips under `previews/film-clips/`, and reconstructible `src/timeline.compiled.json`. Authoring sources stay project.json/storyboard.json. Audio bundles include stems, master and hash/measurement records. The film's `.film.json` retains compiled timing, output/mix hashes, runtime version and pending manual review; `.ass` retains editable burned-in caption text/timing.

When the user approves a version, record the matching code revision, storyboard, narration, subtitle file and mix settings together. Keep private feedback and exploratory notes in the project. Promote reusable methods only after demonstrated success, and obtain agreement before changing a shared template library.

## Asset manifest

`assets/manifest.json` is an array of items containing `path`, `media_type`, `role`, `source`, `license`, and `status` (`available`, `missing`, `needs_review`). Include references to externally located media without silently copying it.
