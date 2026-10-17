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
- `narration` (`enabled`, `voice`, `notes`)
- `reference_videos`, `asset_roots`, `missing_items`, `assumptions`, `status`, `created_at`

Use `null` or an empty array for unknown values; preserve user supplied values. Do not pretend that a missing preference was specified.

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

## Asset manifest

`assets/manifest.json` is an array of items containing `path`, `media_type`, `role`, `source`, `license`, and `status` (`available`, `missing`, `needs_review`). Include references to externally located media without silently copying it.
