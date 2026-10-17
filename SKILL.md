---
name: ivanvideo-skill
description: Plan and produce editable code-driven videos from a brief and assets, with built-in explainer, UI, collage, chart, whiteboard, and typography animation. Use for product videos, Chinese technology news, technical education, reference-video analysis, narration-driven editing, review, and export.
---

# IvanVideo Skill

从需求、素材和参考片开始，完成可审核、可修改的视频工程。用户只需调用本 Skill；动画方法、八种参数化语法及检查工具已内置，无需另装或手动调用 huashu-art-motion。制作文件放在用户选定的工程目录。

## 制作流程

1. **整理简报与素材。** 确认主题、受众、目的、时长、语言、平台、画幅、旁白及已有素材；记录合理假设和缺口，素材不齐也可策划。用 `scripts/init_video_project.py` 建立独立工程，已有工程沿用配置。
2. **分析参考片。** 先用 `scripts/inspect_reference.py` 确认文件可读，取元数据和代表帧；另取关键转场前后帧，实际听过才描述声音。按时间戳区分直接观察与实现推测，提炼构图、关系、运动和节奏，不凭成片判断原作者所用 AI 工具。
3. **脚本与分镜。** 核实技术事实、参数、数据及产品实际功能。逐镜头写清表达目的、画面、运动、屏幕文字、完整旁白、音效、来源和起止时间。默认先请用户审核脚本与分镜；用户已明确授权连续制作时遵从已有授权。
4. **关键帧先行。** 确定字体、语义配色、布局、字幕安全区与节奏，先出代表静帧再动起来。按表达任务选择动画语法；每次只强调一个信息焦点，阅读停留从信息完整出现后计时。风格明确时不强制多个方向或增加审批节点。
5. **口播驱动样片。** 有配音时先取得真实的句级/词级时间；动作挂关键词或句界，生成对齐到帧的 cue。手工时间要注明为手工，缺配音可暂用草稿时间。默认制作 15–30 秒可播放样片，含运动、转场、必要字幕及可用的合法音频，等待风格确认。
6. **逐镜头完成。** 已确认分镜可直接用内置引擎产出片段，项目专属画面可写独立 Canvas/React/TypeScript 组件。真实产品录屏承载功能证据；AI 素材和代码可分层合成，文字保持可编辑。需要 Remotion 等工具时先查已有环境，由本 Skill 负责衔接。保持旁白、字幕和动作同步，音乐让位于人声。
7. **检查与修改。** 验证工程、片段和成片；检查首尾、转场边界及自动告警帧。按时间码局部修改，复验相邻镜头。静止比例、像素差等只是审阅线索，按画面目的判断；实际观看与试听另行记录。
8. **导出与留档。** 默认 MP4/H.264、1920×1080、30 fps，支持配置横屏、竖屏和方形。确认文件能解码且参数符合工程；保留源码、分镜、配音、字幕、素材引用及制作记录。批准版同时固定代码、时间线、混音和字幕，新版另存。项目经验记录证据，公共模板的新增需用户同意。

## 按当前步骤读取

- [references/production-workflow.md](references/production-workflow.md)：简报、参考分析、审核节点、修订与经验沉淀。
- [references/animation-production.md](references/animation-production.md)：内置动画的选型、口播 cue、关键帧与渲染命令。进入动画制作时读。
- [references/animation-grammars.md](references/animation-grammars.md)：八种语法的参数；只读选中的小节。
- [references/project-format.md](references/project-format.md)：项目、分镜、旁白时间与素材的格式。
- [references/quality-checks.md](references/quality-checks.md)：样片和交付前的自动检查、转场检查及人工审阅。

## 工具边界

Python 3 可做初始化与输入校验；内置渲染还需 FFmpeg、FFprobe、Playwright 和 Chromium，片段 QA 另需 NumPy/Pillow。先检查已有工具；涉及 Remotion 时优先复用已安装的官方 Skills 和现有组件，核实来源，不将普通本地 Skill 称为官方。缺项说明清楚，不自动安装大型框架或配置 API。配音、AI 生图/生视频依赖用户已有服务，按可用能力执行并标明来源。调用其他已安装工具的工作由本 Skill 编排，不要求用户切换 Skill。

内置片段引擎保留花叔的 MIT 署名和字体许可，来源见 `THIRD_PARTY_NOTICES.md`。它提供八种讲解动画的基础能力；复杂空间推导、特定品牌 UI 和真实角色表演仍需项目专属实现。
