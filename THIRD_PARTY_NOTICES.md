# Third-party notices

IvanVideo includes a selected, adapted snapshot of **huashu-art-motion** by **alchaincyf (花叔 · 花生)**, from https://github.com/alchaincyf/huashu-art-motion.

- `assets/animation-engine/`: the clip runtime, shared drawing libraries, eight parameterized grammars, and an adapted clip QA tool.
- `references/animation-grammars.md`: adapted grammar interface documentation.
- Keyframe-first design, narration cues, grammar selection, semantic colors, evidence-based review, and project-local feedback inform IvanVideo's production guidance.

The upstream software and documentation use the **MIT License, Copyright (c) 2026 alchaincyf (花叔 · 花生)**. The full notice is retained at `assets/animation-engine/LICENSE.huashu`.

The bundled fonts retain their separate **SIL Open Font License 1.1** notices in `assets/animation-engine/lib/fonts/LICENSES.md` and `OFL.txt`. Only the font families used by this clip runtime are included. The table also documents other fonts from the upstream distribution.

The local source distribution did not include a Git commit identifier. Its per-file source hashes and adaptation notes are recorded in `assets/animation-engine/PROVENANCE.json`. IvanVideo does not claim authorship of these upstream components. Project media, brand assets, private feedback, and reference-film character/audio assets are not part of this snapshot.

## Stage 1 production methods

The original IvanVideo film compiler, FFmpeg assembler and mixer, and supporting production references were informed by studying the locally installed `video-shotcraft` (shot and sound planning), `guizang-product-video-skill` (product evidence and audio review), and `humanizer-zh` (Chinese editing) workflows. No executable code, templates, audio, product assets or license text from those three packages is bundled in this stage. Their licenses do not replace the licenses of the separately retained Huashu runtime and fonts above.

The stage 2 narration/cache/scheduling and browser capture tools are also original IvanVideo implementations. They invoke separately installed macOS speech tools, FFmpeg and Playwright/Chromium; no system voices, browser binaries, third-party TTS SDKs or captured product media are redistributed with this Skill. Generated and captured media retain their project-specific provenance and usage conditions.
