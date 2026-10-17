---
name: ivanvideo-skill
description: Plan and produce editable code-driven videos from a brief and available assets, including reference analysis, scripts, storyboards, animation, voiceover, editing, quality checks, and export. Use for product explainers, technology news, technical education, and platform videos; route specialized animation or Remotion implementation to installed skills when useful.
---

# IvanVideo Skill

Guide a video from brief to a reviewable, editable project. Keep the Skill as workflow guidance and put every production artifact in the user’s chosen project directory.

## Workflow

1. Gather the brief and inspect the supplied asset directory. Record knowns, assumptions, missing items, and provenance; missing assets do not block planning. Initialize a project with `scripts/init_video_project.py` when requested or when starting production.
2. If a reference video is supplied, verify it is readable before analyzing it. Use `scripts/inspect_reference.py` to collect media metadata and representative frames; then write a timestamped report that separates visible evidence from inferred implementation. Learn techniques without copying logos, brand assets, or proprietary designs. Never infer the original creator’s AI tools from the finished video.
3. Verify technical, product, and numeric claims against trustworthy sources and real product behavior. Draft the structure, complete narration, timed storyboard, on-screen text, audio cues, and asset list. Use the project schemas in [references/project-format.md](references/project-format.md). Present the script and storyboard for review before rendering a full video.
4. Choose a visual direction that fits the audience, platform, and subject. Reuse available animation components and installed Skills; keep new components project-local and reusable. Check for installed Remotion capabilities and `huashu-art-motion` before implementing overlapping features. Do not install frameworks or APIs without need and user agreement.
5. Make a 15–30 second style sample by default (or the requested duration), with motion, transitions, readable captions, and available/licensable audio. Render a playable preview and wait for style approval before full production. If a required tool is unavailable, state the limitation and provide the best reviewable next artifact.
6. After approval, complete the timeline while keeping typography, color, motion, pacing, sound, captions, and narration coherent. Keep approved shots stable when revising; isolate changes by shot and timestamp.
7. Run automated checks where reliable and manually review visual, semantic, and audio issues. Export MP4/H.264 at 1920×1080, 30 fps by default, while honoring configured alternatives including 16:9, 9:16, and 1:1. Confirm the final file exists and is readable. Keep the editable project, configuration, script, storyboard, media references, and production notes.

## Routing and references

- Read [references/production-workflow.md](references/production-workflow.md) for phase details, review gates, and reference-video analysis.
- Read [references/project-format.md](references/project-format.md) for the project layout and JSON fields.
- Read [references/quality-checks.md](references/quality-checks.md) before sample or final delivery.
- Use the installed `remotion-video` Skill for Remotion-specific implementation, `huashu-art-motion` for suitable explainer/art animation, and `video-shotcraft` for its specialized shot recipes/templates. These are optional capabilities, not required dependencies.
- Use `scripts/inspect_reference.py` to probe reference metadata and extract review frames, `scripts/init_video_project.py` to create the project skeleton, and `scripts/validate_video_project.py` to check project JSON, shot timing, and asset paths. These require Python 3; reference analysis additionally requires FFmpeg/FFprobe.

Do not alter unrelated projects or global tool configuration. Do not add experimental components to a global template library without user agreement.
