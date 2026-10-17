# 整片合成

已有片段需要组合成样片或成片时读取。本模块使用现有 FFmpeg；不要求安装 Remotion，也不改变内置动画入口。

## 最小命令

```sh
python3 <skill>/scripts/validate_video_project.py <project> --delivery --film
python3 <skill>/scripts/compile_timeline.py <project> --check
python3 <skill>/scripts/render_film.py <project> --check
# 有内置动画时使用已具备 Playwright 的 Python 环境。
uv run --with playwright python <skill>/scripts/render_film.py <project> --out previews/sample-v1.mp4
python3 <skill>/scripts/check_video.py <project> --video previews/sample-v1.mp4 --detect --frames
```

`render_film.py` 可自动渲染动画、生成基础混音、烧录字幕和导出。`--mix audio/mixes/<id>` 可显式指定已存在的混音包；时间线、素材或设置过期时拒绝使用。无音频输入时可生成无声视频，但不虚构音轨，也不能把它称为完整的有声样片。默认输出 `project.output.path`；已存在的成片需另起版本名，或明确加 `--overwrite`。

## 镜头输入

保留已有 shot 的 `animation`。外部视频或静态图增加一个可选 `media`：

```json
{"media":{"type":"video","path":"assets/capture.mp4","trim_in_seconds":1.5,"fit":"contain"}}
```

`type` 为 `video` 或 `image`，路径相对工程，也可引用外部绝对路径。`fit` 可选 `contain`（默认，留黑边）或 `cover`（裁切填满，需审帧）。图片忽略原音轨并持续至镜头结束；动图请先明确转为视频，image 仅面向静态图片。视频内原音轨不会自动进入混音，需要时在音频配置中显式引用，避免意外带入原声。

每镜头必须明确选择 `media` 或 `animation`，不能同时填写。自定义 React/Canvas 画面先导出项目内片段，再作为 media 接入。文字 `visual` 和 `motion` 是制作描述，不能替代可渲染的输入。

视频源比镜头短时拒绝导出，不默认循环或用长时间定格填补。只允许在帧率换算时补至多一帧，若确需长停留，提供明确的静态图镜头。

## 时间和转场

分镜按时间顺序书写，完整覆盖从零开始的时间线。工程时长为空时从末镜头推导；不为空时必须一致。空隙用明确的静态图或视频表达。

相邻镜头没有重叠就是硬切。有重叠时，沿用已有字段：

```json
{"transition_in":{"from":"S01","duration_seconds":0.3,"type":"fade"}}
```

`type` 省略也表示淡化。重叠必须和秒数严格一致，并给两个镜头留下独立内容。第一版不支持三镜头同时重叠，也不支持其他转场类型；不静默降级。

全局起止边界统一取帧，再以相减得到镜头帧数，避免逐镜头取整累积漂移。源动画可能因独立片段的取整多/少一帧，合成时只校正该帧差；关键动作靠近镜头末尾时审阅实际末帧。最终帧数、编码、规格、音轨时长与全片解码均在发布输出前检查。

## 字幕

在 `project.json` 中启用：

```json
{"subtitles":{"enabled":true,"timing_path":"audio/timing.json","font_size":40,"margin_bottom":64}}
```

时间文件沿用 project-format.md 的全片秒数。缺 `timing_path` 时使用 `narration.timing_path`。字幕句子必须有唯一 ID、非空文字、有效且不重叠的区间。`method: draft` 始终是草稿，不表示语音对齐。

默认使用内置 OFL 字体 Noto Sans SC，可配置 `font_path`、`font_name`；建议提供 TTF/OTF，其他字体格式须确认本机 libass/FreeType 支持。字体复制到项目时保留许可。字幕遵从配置的下方及左右安全区，换行由 libass 布局；程序没有验证所有字形覆盖、遮挡或阅读速度。ASS 控制字符反斜线和花括号显示为全角字形，不作为排版指令执行。

导出 `.ass` 侧车文件保留可编辑字幕；正片为烧录字幕版本。字幕的边缘裁切、对比度与画面遮挡仍需实际审帧。

## 工程携带与局部修改

- `src/timeline.compiled.json`：生成结果；编辑源仍是 project.json 和 storyboard.json。
- `previews/film-clips/`：动画缓存；键包含分镜参数、时间输入、素材、引擎与渲染器哈希。未改镜头可复用缓存。缓存被外部编辑时拒绝复用；要保留的手工修改应另存并作为 media 引用。
- `scripts/ivanvideo_film/<版本哈希>/`：完整 Python 工具快照，避免覆盖已有工程工具。首次携带动画保留现有引擎副本；字幕字体保留于 `src/film-fonts/`。
- `.film.json`：编译时间线、混音及输出哈希、运行工具版本、机器检查结果与待人工审核项。

项目离开 Skill 后可运行快照内的 `render_film.py`，依赖仍为 FFmpeg/FFprobe，动画另需 Playwright/Chromium。外部绝对路径素材需用户自行携带或按要求归档，不宣称已经打包。

修改一个镜头可复用其他动画缓存；最终整片编码仍会重做，不宣称具备任意局部无损替换能力。批准版本保留原文件名，新版另存。
