# Quality checks

Run machine checks when the tool can determine the result reliably; record command/result and separately list human review items.

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
