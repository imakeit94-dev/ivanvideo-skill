---
name: ivanvideo-skill
description: Plan and produce editable videos with animation, Chinese narration, real UI capture, assets, covers, captions and mixing. Use for product videos, technology news, technical education, reference analysis, or SRT-based B-roll with audio-synced review and clip delivery.
---

# IvanVideo Skill

从需求、素材和参考片开始，完成可审核、可修改的视频工程。用户只需调用本 Skill；动画方法、八种参数化语法及检查工具已内置，无需另装或手动调用 huashu-art-motion。制作文件放在用户选定的工程目录。

已有母版与 SRT、只需要补充口播包装时，按 [broll-production.md](references/broll-production.md) 走导入/选段、声音同步预览、叠加检查和片段交付；保留原旁白及时间位置，镜头仍在 storyboard.json 中编辑。

## 制作流程

1. **整理简报与素材。** 确认主题、受众、目的、时长、语言、平台、画幅、旁白及已有素材；记录合理假设和缺口，素材不齐也可策划。用 `scripts/init_video_project.py` 建立独立工程，已有工程沿用配置。
2. **分析参考片。** 先用 `scripts/inspect_reference.py` 确认文件可读，取元数据和代表帧；另取关键转场前后帧，实际听过才描述声音。按时间戳区分直接观察与实现推测，提炼构图、关系、运动和节奏，不凭成片判断原作者所用 AI 工具。
3. **脚本与分镜。** 核实技术事实、参数、数据及产品实际功能；中文口播按 narration-editing.md 润色，产品展示按 product-evidence.md 留证。逐镜头写清表达目的、画面、运动、屏幕文字、完整旁白、音效、来源和起止时间。默认先请用户审核脚本与分镜；用户已明确授权连续制作时遵从已有授权。
4. **关键帧与素材。** 确定字体、语义配色、布局、字幕安全区与节奏，先出代表静帧再动起来。按表达任务选择动画语法；每次只强调一个信息焦点，阅读停留从信息完整出现后计时。需要配图或可选 AI 视频时按 asset-production.md 规划、调用实际可用服务并登记返回文件；不把提示词或任务 ID 当成品。风格明确时不强制多个方向或增加审批节点。
5. **口播驱动样片。** 按 narration-production.md 用已有本机声音或提供的音频生成句子清单，实测时长后预览/应用排时。句级时间用于字幕和句界 cue；关键词或嘴型需另有可靠对齐，不把实测片长说成词级精度。缺配音可用注明的草稿时间。默认制作 15–30 秒可播放样片，含运动、转场、必要字幕及合法音频，等待风格确认。
6. **逐镜头与整片完成。** 网页真实画面可按 software-capture.md 用明确操作与断言采集；其他软件使用可用的真实录屏方法或原组件并留证。内置引擎产出动画，专属组件先导出片段。用 render_film.py 沿用同一分镜合成动画、录屏、配图、字幕和混音。AI 素材与说明性重建明确来源。需要 Remotion 等复杂合成时先查已有环境，由本 Skill 衔接。
7. **检查与修改。** 验证工程、片段和成片；检查首尾、转场边界及自动告警帧。按时间码局部修改，复验相邻镜头。静止比例、像素差等只是审阅线索，按画面目的判断；实际观看与试听另行记录。
8. **导出与留档。** 默认 MP4/H.264、1920×1080、30 fps，支持配置横屏、竖屏和方形。确认文件能解码且参数符合工程；保留源码、分镜、配音、字幕、素材引用及制作记录。需要封面时按 cover-production.md 输出各画幅 PNG 和可编辑 HTML，标题与配图分层。批准版同时固定代码、时间线、混音和字幕，新版另存。项目经验记录证据，公共模板的新增需用户同意。

## 按当前步骤读取

- [references/production-workflow.md](references/production-workflow.md)：简报、参考分析、审核节点、修订与经验沉淀。
- [references/animation-production.md](references/animation-production.md)：内置动画的选型、口播 cue、关键帧与渲染命令。进入动画制作时读。
- [references/animation-grammars.md](references/animation-grammars.md)：八种语法的参数；只读选中的小节。
- [references/project-format.md](references/project-format.md)：项目、分镜、旁白时间与素材的格式。
- [references/quality-checks.md](references/quality-checks.md)：样片和交付前的自动检查、转场检查及人工审阅。
- [references/film-production.md](references/film-production.md)：多个镜头合成、媒体源、淡化、字幕与工程快照。进入样片或整片合成时读。
- [references/audio-production.md](references/audio-production.md)：已提供声音的分轨、音效落点、配乐压低、响度和过期混音检查。
- [references/narration-editing.md](references/narration-editing.md)：中文口播润色与事实保护。脚本需要中文配音时读。
- [references/product-evidence.md](references/product-evidence.md)：真实产品版本、功能与展示方式的证据。功能宣传时读。
- [references/narration-production.md](references/narration-production.md)：中文 TTS/导入声音、句子缓存、实测排时、修订备份及同步校验。进入配音时读。
- [references/software-capture.md](references/software-capture.md)：网页实际采集、操作断言、录屏与逐镜头来源绑定。需要真实网页素材时读。
- [references/asset-production.md](references/asset-production.md)：配图规划、可选 AI 视频服务、提示词、真实文件导入与逐镜头素材校验。
- [references/cover-production.md](references/cover-production.md)：三种画幅的封面、可编辑标题、字体与图像留档及检查。
- [references/broll-production.md](references/broll-production.md)：已有 SRT 和母版的口播包装、可拖动预览、头像/字幕区域和替换对照表。

## 工具边界

Python 3.9+ 可做初始化与输入校验；整片、混音及素材导入需 FFmpeg/FFprobe，字幕需 libass；内置动画、网页采集和封面 PNG 另需 Playwright/Chromium，片段 QA 另需 NumPy/Pillow。中文 TTS 支持已安装的 macOS say，其他服务音频用 provided 导入；不自动安装声音或接入云 API。配图优先使用已暴露的原生生图工具；AI 视频仅在实际服务可用时调用，没有内置云视频 SDK。导入不等于版权或事实审核通过。网页采集未覆盖所有原生桌面软件；没有词级强制对齐。整片支持 MP4/H.264、硬切与淡化。先检查工具，缺项明确说明，不自动安装大型框架。需要 Remotion 时优先复用确已安装的官方 Skills/组件，核实来源，不把普通本地 Skill 称为官方。

内置片段引擎保留花叔的 MIT 署名和字体许可，来源见 `THIRD_PARTY_NOTICES.md`。它提供八种讲解动画的基础能力；复杂空间推导、特定品牌 UI 和真实角色表演仍需项目专属实现。
