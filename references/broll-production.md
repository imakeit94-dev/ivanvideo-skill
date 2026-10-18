# 已有口播视频的 SRT 包装

适用于已有母版和字幕、只补充部分动画画面的任务。先确认哪些段落需要包装，哪些实际操作应保留；不要求重新配音或重做整片。用户只需调用 `$ivanvideo-skill`，以下命令由 Codex 编排。`SKILL` 是安装目录，`PROJECT` 是独立包装工程。

## 1. 导入与选段

新建独立工程，避免替换已有分镜：

```sh
python "$SKILL/scripts/init_video_project.py" "$PROJECT" --title "口播包装"
python "$SKILL/scripts/broll.py" "$PROJECT" import --srt /path/input.srt --master /path/master.mp4 --check
python "$SKILL/scripts/broll.py" "$PROJECT" import --srt /path/input.srt --master /path/master.mp4
```

导入保留 UTF-8/BOM SRT 快照、实际媒体参数与哈希，输出 `source_path`，形如 `references/broll-sources/HASH/source.json`。`--check` 不写文件。要求真实视频文件，自动读取画幅、平均帧率、时长和音轨；不猜同名母版，也不默认 4K。源视频仍在原位置；需要迁移时应归档外部文件并重新处理路径。

内置引擎使用整数输出帧率。遇到非整数或可能变帧率输入时必须明确选用 `--fps 30` 等整数转换目标；转换维持秒时间，不能把输出帧号说成源文件原始帧编号。此分支不是 VFR/丢帧时间码的完整编辑器。先核实交付需求再转换，不默认将 29.97 当 30。

```sh
python "$SKILL/scripts/broll.py" "$PROJECT" list --source references/broll-sources/HASH/source.json
```

先通读字幕，列出建议区间及原因：开场、章节结论、清晰的对比、总结；观众要看具体操作时保留真实录屏。新闻、技术及产品事实仍需核实。屏幕文案提炼原意，保留条件和确定程度；字幕纠错要查证，不因模板需要编造数据。

保存 `references/selection.json`：

```json
{
  "segments": [
    {"id":"B01","title":"三个功能","from_cue":"srt-1","to_cue":"srt-4"},
    {"id":"B02","title":"结论","start_ms":12000,"end_ms":16000,"snap":"exact"}
  ]
}
```

每段选择 cue ID 或毫秒，不能混用。`srt-N` 来自原字幕编号，不按字幕文字搜索。相同编号下的文字修改不会改变 ID；新 SRT 若重新编号，需要重新核对映射，不承诺跨任意版本自动识别同一句话。

- `snap:exact` 默认保留指定区间，换算到输出帧边界，并提示是否在句中切入/切出。
- `snap:expand` 明确允许扩到相交字幕的外边界；保留原始请求毫秒。
- 越界、重叠、重复 ID、未知 cue 和取整后零帧会失败。

```sh
# 只输出候选选段，不改工程
python "$SKILL/scripts/broll.py" "$PROJECT" select --source references/broll-sources/HASH/source.json --selection references/selection.json
# 按现有授权应用到空工程，并保留原配置副本
python "$SKILL/scripts/broll.py" "$PROJECT" select --source references/broll-sources/HASH/source.json --selection references/selection.json --apply
```

应用生成完整母版时间线：所选段为可编辑 `animation` 起步镜头，未选段为 `GAP-*` 的原视频镜头；不会把选段前移拼在一起。镜头编辑仍使用 `storyboard.json`，不维护另一套手工时间线。初始动画只是占位草稿，需要按真实内容完善后审核。

首次应用只接受空分镜，拒绝覆盖现有工程。范围重选在新版本工程中应用；已选镜头的画面、动作和文字可以局部修改。原始音轨第一轨被提取为 PCM，可能已经含音乐，不宣称分离出纯净人声。原音频不会因选段被重新合成或加速。导入字幕标记为手工/导入来源，不是自动语音或词级对齐。

`project.broll` 保存原导入快照，shot.broll_segment 保存唯一的选段位置及请求信息。derived `audio/broll-subtitles.json` 用于句界 anchor，不手改其文本/时间；修改字幕需导入新源版本并复核选段。支持基本 SRT 多行文本，样式标签按文字处理；重叠字幕可在预览合并显示，若最终烧录字幕仍须满足整片字幕的非重叠约束。

## 2. 头像与字幕叠加

按母版实际测量填写 `references/broll-overlay.json`；没有配置时不假设任何作者的头像位置：

```json
{"regions":[
  {"id":"host","kind":"avatar","shape":"circle","x":0.8,"y":0.04,"width":0.15,"height":0.266666667,"label":"头像占位"},
  {"id":"captions","kind":"subtitle","x":0.1,"y":0.84,"width":0.8,"height":0.13,"font_size":40}
]}
```

坐标为画布 0–1 比例，字号为画布像素；示例圆适合 16:9，其他画幅需重新测量，圆的像素宽高必须相同。`protected` 可标产品关键操作区域。头像为明确标注的占位形状，不生成或冒用真人；字幕取母版 SRT，用户可开关叠加。

自动提示部分 Canvas 文字与区域的相交、画布边缘及字幕区域溢出，均是人工审阅线索。缓存画布里的字、图形、遮罩和物体遮挡未被完整检测。字幕叠加是构图检查标尺，不承诺与最终 libass 字形和换行完全相同。区域配置不代表动画已自动绕开它，也不取消既有语法的安全区限制。

## 3. 可拖动的声音同步预览

```sh
# 使用已有 Playwright 环境；QA 可选，但交付前应实际运行
python "$SKILL/scripts/build_broll_preview.py" "$PROJECT" --out previews/review-v1 --check
python "$SKILL/scripts/build_broll_preview.py" "$PROJECT" --out previews/review-v1 --qa
# 输出同时提供项目自带脚本的启动命令
python "$SKILL/scripts/build_broll_preview.py" "$PROJECT" --out previews/review-v1 --serve --port 8765
```

用浏览器打开输出的 `http://127.0.0.1:8765/`。使用此服务器的媒体字节 Range 支持，普通静态服务器可能使浏览器声音无法正确跳转。仅绑定本机回环地址，不自动发布到互联网。

预览复用项目的 clip.html / renderFrame 与归一化 spec，不重写动画。声音作为播放时钟，画面采样到相同帧网格；拖动先等音频定位再更新画面，跨镜头动画提前加载字体与图片。可导航镜头、拖动、播放、切换叠加、记录当前时间意见，并下载 review-notes.json。它不直接修改源工程，按意见回到分镜局部修改。

预览包含真实声音混音副本、媒体浏览器兼容衍生文件、引擎、字体、规格、SRT 和输入哈希。目录包含项目声音与素材，只用于有权限的审核对象。它支持当前包装的硬切时间线；重叠淡化会明确拒绝，应改用已有成片预览。长片多镜头性能仍需另测，不承诺实时预览在所有设备上流畅。

新预览使用新目录，旧版本不覆盖。项目保留 UI 与引擎副本，更新全局 Skill 不会静默替换项目已有副本。修改已固定的 UI 源时先留版本，再重新构建；不要直接改审核包并声称仍匹配旧输入。

## 4. 干净片段与对照表

```sh
python "$SKILL/scripts/deliver_broll.py" "$PROJECT" --out outputs/broll-v1 --check
python "$SKILL/scripts/deliver_broll.py" "$PROJECT" --out outputs/broll-v1
python "$SKILL/scripts/deliver_broll.py" "$PROJECT" --out outputs/broll-v1 --verify
```

所选镜头复用 render_animation.py，专属预渲染媒体沿用现有 normalize_clip。输出默认 H.264、所选区间的精确帧数和配置尺寸：

- 每个 MP4 带镜头 ID、标题与起止毫秒文件名。
- `replacement-table.md`：母版位置、输出帧网格、区间帧数、字幕 ID、句中切口提示。
- `delivery.json`：来源/时间线/引擎/成品哈希及实际检查结果。

区间左闭右开。毫秒只是帧位置的显示取整，以起止帧和 fps 精确定位。包装片段不含声音、不烧录审核头像或字幕；放回原视频轨并保留原音轨，避免重复旁白。需要配乐/音效时使用既有声音流程另行制作，不从母版自动重复混入。

验证文件存在、内容哈希、帧数、编码、分辨率、帧率、完整解码和无音轨；源、分镜或成品被改动时拒绝旧交付。保留完整项目、源码与声音，不采用“只留 MP4”的限制。最终全片样片仍可通过 render_film.py 生成，整体字幕烧录与片段干净交付相互独立。

## 审核节点与边界

保留脚本/视觉审核规则；已有口播包装可集中审核选段、文字及动态预览，获确认后按既有授权完成，不反复增加审批。机器 QA 不代表听过声音，交付应分别记录拖动/播放检查、同引擎帧比较、遮挡线索、实际视觉查看与完整试听。

本批是对阿江口播包装方法的独立适配，沿用 IvanVideo 引擎、工程和混音；没有引入其十套主题、Node/Remotion 强制依赖、固定响度差或第三方品牌素材。实测记录见 [stage4-validation.md](stage4-validation.md)。
