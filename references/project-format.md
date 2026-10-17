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
- `safe_area` (`top`, `bottom`, `left`, `right` in pixels); bundled clip layout supports top/bottom only
- `visual_system` (`palette`, `fonts`, `concept_colors`, `motion_notes`)
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

Times are global seconds from the start of the video. `method` records `manual`, `aligned`, or `draft`; draft estimates are not verified audio alignment. Segment ids are unique, allowing cue anchors to survive a text or timing revision. Retain the original narration file and alignment provenance.

## Editable animation snapshot

The first animation render adds `src/animation-engine/` (including license notices), `src/clips/`, and `scripts/ivanvideo_runtime/`. Store sample MP4/PNG and `.render.json` records in `previews/`; keep release exports in `outputs/`. The engine snapshot stays with the project and is not overwritten when the global Skill changes.

When the user approves a version, record the matching code revision, storyboard, narration, subtitle file and mix settings together. Keep private feedback and exploratory notes in the project. Promote reusable methods only after demonstrated success, and obtain agreement before changing a shared template library.

## Asset manifest

`assets/manifest.json` is an array of items containing `path`, `media_type`, `role`, `source`, `license`, and `status` (`available`, `missing`, `needs_review`). Include references to externally located media without silently copying it.
