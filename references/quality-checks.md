# Quality checks

Run machine checks when the tool can determine the result reliably; record command/result and separately list human review items.

## Commands

```sh
python3 <skill>/scripts/validate_video_project.py <project> --delivery
# When using the full-film pipeline:
python3 <skill>/scripts/validate_video_project.py <project> --delivery --film
python3 <skill>/scripts/render_film.py <project> --check
uv run --with playwright --with numpy --with pillow python <skill>/scripts/render_animation.py <project> --shot S01 --out previews/S01-v1.mp4 --qa
python3 <skill>/scripts/check_video.py <project> --video outputs/final.mp4 --detect --frames
```

Project validation checks JSON, aspect ratio, shot timing, documented overlaps, referenced assets, and built-in animation inputs. Clip QA checks same-environment determinism, rendering cost, frame changes, and text framing; inspect `*-qa/qa.json`, `qa.md`, and the contact sheet. The final-video checker fully decodes the media, compares export settings, flags black/silent intervals, and optionally extracts frames around storyboard boundaries. None of these commands replaces viewing and listening.

The bundled clip QA does not evaluate transitions between clips. Inspect both sides of every cut, transition midpoint, and the actual rendered first/last frames. Text tracking cannot reliably see occlusion by graphical objects, and graph/character intrusion into subtitle regions needs visual review. Motion thresholds are clues: a deliberate hold, subtle camera drift, or a story reaction can be correct even when static-frame percentages look unusual.

## Automated checks

- All storyboard-referenced assets resolve; no required items remain unmarked.
- Caption text fits the frame and safe-area policy where text bounds can be measured.
- Output video opens with FFprobe; expected width, height, frame rate, duration, and codec match project configuration.
- Expected audio stream exists; audio/video durations are close enough for the edit design.
- Detect black/frozen sections and silence/peak jumps where practical, then inspect flagged intervals. These detectors can produce false positives for intentional pauses, fades, dark scenes, or deliberate holds.
- Confirm final output exists, is non-empty, and can be decoded for representative frames.

## Human review

Watch the video at full size and listen through headphones/speakers. Check caption clipping, contrast, safe areas, spelling, reading time, unintentional black frames, transition collisions, movement smoothness, pacing, audio sync, unnatural silence or loudness changes, music under speech, and whether each visual actually supports the narration. Confirm product UI/functionality is faithful to a real capture or documented evidence. Recheck every frame/time range flagged by automation.

Provide timecodes or screenshots for issues. Fix the smallest relevant shot, rerender, and recheck adjacent transitions and audio sync. Record automated and human checks separately; never claim a visual or listening review that did not happen.

当前内置动画的实测范围与未验证项见 [integration-validation.md](integration-validation.md)。

整片流程见 [film-production.md](film-production.md)，声音流程见 [audio-production.md](audio-production.md)。第一批融合的回归与样片实测见 [stage1-validation.md](stage1-validation.md)。整片发布前的自动检查还包括准确帧数、全片解码、音轨时长、输入是否在渲染时变化、混音是否过期和编码后峰值；这些结果不代替产品真实性审阅或声音试听。

中文 TTS、实测排时、句级同步和真实网页采集的验证见 [stage2-validation.md](stage2-validation.md)。生成时间线会核对口播脚本、分镜文字、音频及字幕时间；capture_evidence 核对源规范与媒体哈希。两类检查都不等同于自动词级对齐、听感验收或整项产品功能认证。

配图、可选 AI 视频素材与封面按 [asset-production.md](asset-production.md)、[cover-production.md](cover-production.md) 检查。自动验证真实文件、来源哈希、图片/视频类型、完整解码和封面文字边界；人工审核生成伪影、技术事实、标题准确性、缩略图可读性和使用条件。任务 ID 或提示词不可当作完成的视频。第三批实测范围见 [stage3-validation.md](stage3-validation.md)。
