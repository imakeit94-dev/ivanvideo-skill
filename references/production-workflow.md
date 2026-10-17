# Production workflow

## Brief and setup

Capture topic, audience, purpose, duration, language, platform, aspect ratio, resolution, frame rate, narration and voice preference, reference media, existing assets, and delivery constraints. Ask only for details that materially affect the next step; otherwise record reasonable assumptions in `project.json`. Scan the provided asset location and record path, type, role, source/license if known, and whether it is approved. Keep missing assets visible in the manifest while planning continues.

Default delivery is MP4, H.264, 1920×1080, 30 fps, 16:9. Treat defaults as editable configuration. Platform requirements can change, so verify current specifications when platform-specific limits matter.

## Reference analysis

First confirm that the local file exists and is readable with FFprobe. Extract metadata and a small set of representative frames, then inspect the frames and audio as appropriate. Write observations with timestamps: shot boundaries, framing, movement, UI behavior, title/caption placement, transitions, pacing, music, voice, and sound effects. Label each note as **observed** or **inferred**. A finished video does not establish which model or production tool created it. Avoid reuse of third-party identity assets; translate visual mechanisms to original material.

Prefer key frames around scene changes and important transitions over uniform sampling alone. Use audio listening or transcription only when the available tools support it; do not claim audio content from metadata.

## Script and storyboard gate

Produce a content outline, complete script, narration, timed shot list, on-screen text, audio direction, and asset requirements. Every shot states its purpose, in/out time, image and movement, text, narration, audio cue, and asset source. Confirm durations add up to the requested runtime. Verify claims against primary sources or supplied product evidence; mark unresolved claims instead of inventing specifications. Product demonstrations must reflect actual behavior and be labeled if they use mock data.

Show the script and storyboard for review before rendering a full video. A short sample is the next review gate. Do not treat an outline or static storyboard as approval to produce the full video.

Honor explicit authorization already given for continuous production or a technical test; do not add a new approval gate to those tasks. For Chinese narration, use narration-editing.md before the existing script review. For real software promotion, use product-evidence.md to connect claims and shots to actual versions and behavior.

## Visual system and implementation

Choose a consistent design system appropriate to the brief: type, palette, spacing, corner radius, shadows, safe areas, caption treatment, transition vocabulary, and motion timing. Possible directions include technology business, real software UI, kinetic typography, keynote UI, editorial explainer, science animation, and corporate film. They are options, not presets to apply blindly.

Inspect the project and installed tooling before coding. Prefer existing components, real screen recordings for product behavior, and isolated reusable modules for new effects. Keep package changes scoped to the video project. Use generated image/video/audio only when available and record source and usage rights. If a skill or API is absent, report that accurately and continue with available methods.

## Sample, full edit, and changes

The sample should demonstrate the intended motion language, caption hierarchy, transitions, and sound treatment; use representative content rather than placeholder blocks wherever possible. Keep it short enough for a fast style decision. After approval, build the remaining shots against the approved storyboard. Synchronize narration, captions, and visual actions. Mix music so speech remains clear and avoid effects without an expressive purpose.

For multi-shot delivery, follow film-production.md and audio-production.md. Keep the existing authoring files as the source; compiled timing and mix bundles are derived artifacts. A rendered/decoded file establishes technical readability, while listening and product authenticity remain separate reviews.

For timestamped feedback, identify the affected shot and make the narrowest change that satisfies it. Keep prior approved shots and notes intact; record changed decisions in the project log.

## Frame-first and narration-led production

Set a representative keyframe before animating: composition, semantic colors, text hierarchy, subtitle region, and one clear focus. Select the animation grammar by what the narration is doing. Reuse the built-in runtime through animation-production.md; the user need not invoke another Skill. Choose purposeful continuous motion or deliberate holds according to the shot, without imposing a universal motion quota.

Use actual narration alignment to anchor visual cues to words or sentence boundaries. Mark manually timed and estimated segments honestly. Count reading time after the complete list/diagram is visible. Keep numbers, units, and semantic colors consistent across zooms, transitions, and labels.

When a revision repeats the same failure, log the timecode, root cause, attempted fix, and observed result. After repeated ineffective fixes, revisit the input assets, storyboard, or renderer capability instead of adding more visual rules. Freeze approved code, timeline, audio mix, and subtitles together. Private project feedback stays local to the project; only general methods with evidence belong in the public Skill.
