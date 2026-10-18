# IvanVideo Skill

**AI 视频导演：从主题、要求和素材，逐步制作可审核、可编辑的视频工程。**

IvanVideo 是供 Codex 使用的个人视频制作 Skill，覆盖创意策划、参考视频分析、脚本分镜、动画、中文配音、真实软件展示、配图、剪辑混音、封面与导出。

统一调用入口：`$ivanvideo-skill`。日常制作无需分别调用被研究或融合的其他 Skill。实际视频项目保存在独立目录，Skill 仓库保存流程、工具和可复用资源。

## 适用场景

- 软件产品宣传、版本更新与功能演示。
- 企业与产品介绍。
- 中文 AI 科技新闻讲解。
- GNSS、RTK、SLAM 等技术科普。
- 视频号、YouTube 等平台的内容视频。

## 当前能力

| 环节 | 已具备的能力 |
| --- | --- |
| 项目初始化 | 整理主题、受众、时长、语言、画幅与素材，生成配置和素材清单，标记缺口 |
| 参考片分析 | 检查实际文件、时长、分辨率、帧率和音轨，提取代表帧，按时间戳区分观察与制作推测 |
| 脚本与分镜 | 内容结构、中文口播、逐镜头画面与动作、屏幕文字、旁白、音效和来源 |
| 内置动画 | 八种参数化讲解动画，支持关键帧预览、旁白句界 cue 和片段检查 |
| 整片合成 | 组合动画、录屏和静态配图，支持硬切、淡化、字幕烧录与导出 |
| 中文配音 | 使用已安装的 macOS 声音，或导入已有音频；逐句缓存并实测时长 |
| 时间线与字幕 | 根据配音时长安排镜头，字幕和句界动作共享时间来源，保存 ASS/SRT |
| 真实软件展示 | 实际网页操作、断言、截图、录屏及逐镜头证据绑定 |
| 声音制作 | 人声、音乐、音效分轨，动作落点、配乐压低、可选响度处理与过期混音检查 |
| 配图与可选 AI 视频 | 素材计划、提示词、实际可用服务编排、返回文件导入、来源和哈希记录 |
| 封面 | 横屏、竖屏、方形分别布局，输出 PNG 与保留独立文字的 HTML |
| 检查与留档 | 工程校验、完整解码、帧数与音轨检查、黑场/静音线索、项目工具快照 |
| 已有口播包装 | SRT 导入与选段，保留母版时间，声音同步拖动预览、头像/字幕叠加及带时间戳的意见 |
| 包装片段交付 | 干净 MP4、精确帧数、字幕 ID、母版替换对照表与过期交付校验 |

默认视频规格为 **MP4 / H.264 / 1920×1080 / 30 fps**，可通过项目配置修改尺寸与帧率，支持 16:9、9:16 和 1:1。封面尺寸独立配置，发布前需核实目标平台的实际要求。

## 安装与调用

将整个仓库放入个人 Skill 目录。当前项目使用的安装位置是 `~/.codex/skills/ivanvideo-skill`；若设置了 `CODEX_HOME`，按其实际路径选择目录。

首次安装示例（目标目录需不存在）：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/imakeit94-dev/ivanvideo-skill.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/ivanvideo-skill"
```

已有同名 Skill 时先检查内容和本地修改，避免覆盖。仓库本身不包含 FFmpeg、浏览器二进制或系统声音包；具体任务开始时检查所需工具。

在 Codex 对话中提供主题、要求、已有素材路径和项目目录：

```text
使用 $ivanvideo-skill 制作一条视频。
主题：……
受众：……
时长：……
语言与旁白：……
平台和画幅：……
已有素材：……
参考视频：……
工程目录：……
先整理需求并输出脚本与分镜，供我审核。
```

素材不齐也可以开始策划。默认先审核脚本与分镜，再制作 15–30 秒样片；样片风格确认后继续整片。用户已经明确授权连续制作时，沿用已有授权。

### A. 软件宣传视频

```text
使用 $ivanvideo-skill，为我的 GNSS 数据处理软件制作 60 秒中文宣传视频。
面向测绘工程师，16:9，1920×1080，科技商务风格。
产品资料和真实截图位于 ~/media/gnss-materials，工程保存到 ~/media/gnss-promo。
只展示有实际依据的功能，先给出完整脚本、分镜和待补素材清单。
```

### B. 根据参考视频学习表现风格

```text
使用 $ivanvideo-skill，分析 ~/media/references/demo.mp4。
按时间戳拆解构图、文字、运镜、转场和节奏，区分实际观察与实现推测。
为我的产品制作相近表现风格的 30 秒视频，不复制原片品牌资产。
工程保存到 ~/media/reference-inspired，先审核分镜，再制作 15 秒样片。
```

### C. 中文 AI 科技新闻

```text
使用 $ivanvideo-skill，制作一条约 90 秒的中文 AI 科技新闻讲解视频。
先检索并核实最近一周的官方发布，记录事件日期、来源和不确定性。
9:16，使用中文旁白、句级字幕和必要示意配图，不用生成画面冒充新闻实拍。
工程保存到 ~/media/ai-news，先输出选题、来源、脚本与分镜供我审核。
```

### D. 为已有口播补动画

```text
使用 $ivanvideo-skill，为 ~/media/tutorial.mp4 和 ~/media/tutorial.srt 补充动画包装。
先通读字幕，推荐开场、关键技术解释和总结的区间，保留真实操作段及原旁白时间。
在新的 ~/media/tutorial-broll 工程中制作可拖动、声音同步的预览，叠加我提供的头像和字幕区域。
审核后输出干净包装片段与替换对照表，并保留完整工程。
```

## 工作流程

**需求与素材 → 参考分析 → 脚本分镜 → 视觉与素材规划 → 配音及实测排时 → 样片 → 完整制作 → 检查修改 → 导出留档**

技术事实、产品参数与新闻数据需要核实来源；软件宣传以实际功能为依据。参考片用于学习表现方法，不能仅凭成片断言作者使用了某个 AI 工具。

配图用于概念、背景和视觉比喻；真实软件 UI 使用实际画面。精确文字、数值和技术图形优先保留为可编辑元素。生成素材记录实际提供方、提示词、文件与使用条件，提示词或任务 ID 不等于已完成的视频。

修改意见可按时间戳、镜头 ID 或截图提出。尽量保留已确认内容，复用未变镜头的缓存；最终合成仍可能需要重新编码。

## Skill 与视频工程

```text
ivanvideo-skill/                 # 个人 Skill / 本仓库
├── README.md                    # 使用概览
├── SKILL.md                     # Codex 工作入口
├── agents/openai.yaml           # 显示名称与调用元数据
├── references/                  # 详细流程、格式、检查与验证记录
├── scripts/                     # 初始化、渲染、声音、采集及素材工具
├── assets/animation-engine/     # 内置片段引擎及字体
├── tests/                       # 合成数据与回归测试
└── THIRD_PARTY_NOTICES.md        # 来源、署名与第三方许可说明

my-video-project/               # 用户指定的独立工程
├── project.json                # 制作规格、旁白、字幕、声音等配置
├── storyboard.json             # 镜头与时间线编辑源
├── scripts/                    # 简报、口播及制作工具快照
├── references/                 # 来源、分析、素材计划及封面配置
├── assets/                     # 素材清单、配图、录屏等
├── src/                        # 动画源码、引擎副本及编译时间线
├── audio/                      # 逐句声音、时间表与混音
├── previews/                   # 静帧、片段和样片
└── outputs/                    # 成片、字幕、封面与检查记录
```

`project.json` 和 `storyboard.json` 是编辑源，编译时间线可以重建。工程保留使用的素材、声音、工具和字体；引用外部绝对路径的素材，迁移时还需另行归档。

视频、录音、私有产品资料与测试样片保留在视频工程中，不写入公共 Skill 仓库。试验性组件先在项目内使用，新增公共模板需用户同意。

### 手动初始化第一个工程

也可以直接让 Codex 完成初始化。需要命令行操作时：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/ivanvideo-skill/scripts/init_video_project.py" \
  "$HOME/media/my-first-video" \
  --title "我的第一个视频" --topic "产品介绍" \
  --duration 60 --language zh-CN --aspect-ratio 16:9
```

初始化会拒绝非空目录。随后在 Codex 中指定这个工程，继续整理素材、生成脚本与分镜；空工程本身还不能直接渲染。

## 环境要求与边界

| 工具或服务 | 用途与边界 |
| --- | --- |
| Python 3.9+ | 初始化、JSON 配置与流程工具 |
| FFmpeg / FFprobe | 媒体处理、导入检查、整片合成和混音；字幕烧录需要 libass |
| Playwright / Chromium | 内置动画、真实网页采集及封面 PNG 输出 |
| NumPy / Pillow | 内置片段的部分 QA 检查 |
| macOS `say` 与已安装中文声音 | 当前自动 TTS 路径；其他服务通过已有音频导入，未内置云 TTS SDK |
| 当前会话可用的生图工具 | 按需生成配图；没有可用服务时接受已有图片 |
| 可选 AI 视频服务 | 按当前实际接口和授权调用，没有强制提供方或内置云视频 SDK |
| Remotion / React / TypeScript | 复杂组件或合成的可选路径，优先复用已有环境；基础流程不强制安装 |

中文同步目前为**句级音频片段时间**，不等于逐词、音素或嘴型对齐。真实网页采集使用独立浏览器上下文，不代表支持所有登录态或原生桌面软件。

机器检查不能替代完整观看与试听。字幕遮挡、对比度、发音、音效同步、产品真实性、生成伪影和使用权仍需人工审核；音乐音量以不掩盖人声为准。

## 融合进展与验证

以下为截至 2026-10-18 已保存的验证结果，详细记录包含环境与尚未验证项：

| 阶段 | 内容 | 已记录的验证 |
| --- | --- | --- |
| 动画基础 | 内置花叔八种参数化动画与检查工具 | [动画融合记录](references/integration-validation.md) |
| 第一批 | 整片合成、基础混音、中文口播编辑、真实产品证据流程 | 14 项回归与短样片；[第一批记录](references/stage1-validation.md) |
| 第二批 | 中文 TTS、实测时长排时、字幕同步、真实网页展示 | 累计 27 项回归、17 秒样片、迁移与单句修改；[第二批记录](references/stage2-validation.md) |
| 第三批 | 配图、可选视频素材、可编辑封面 | 累计 40 项回归、实际生图、三种画幅封面、18 秒样片与迁移重渲；[第三批记录](references/stage3-validation.md) |
| 第四批 | SRT 选段、声音同步预览、头像/字幕叠加检查、片段替换表 | 累计 56 项回归、实际浏览器拖动/播放、18 秒样片和两段干净交付；[第四批记录](references/stage4-validation.md) |

第三批验证时没有可用的 AI 视频生成服务，因此只验证了请求与提示词、实际编码视频导入及失败输入检查，**未验证 AI 视频提供方的实际生成与下载**。本机软件采集验证也不代表用户的商业产品已经验收。完整试听、跨系统与长片压力等未验证项见各批记录。

## 详细文档

- [完整制作流程](references/production-workflow.md) · [工程格式](references/project-format.md)
- [动画制作](references/animation-production.md) · [八种动画参数](references/animation-grammars.md)
- [整片合成](references/film-production.md) · [混音与声音](references/audio-production.md)
- [中文口播编辑](references/narration-editing.md) · [配音与排时](references/narration-production.md)
- [真实产品证据](references/product-evidence.md) · [网页采集](references/software-capture.md)
- [配图与可选 AI 视频](references/asset-production.md) · [封面制作](references/cover-production.md)
- [SRT 包装、同步预览与片段交付](references/broll-production.md)
- [质量检查](references/quality-checks.md)

## 来源与许可

内置片段引擎选取并改编自 [huashu-art-motion](https://github.com/alchaincyf/huashu-art-motion)，保留花叔的 MIT 署名与许可；随附字体保留 SIL Open Font License 说明。

其他 Skill 的研究与融合方式见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)：部分方法经过整理后由 IvanVideo 独立实现，没有把它们的代码、模板或品牌资产整体搬入。生成素材、产品截图、声音与服务条款按项目单独记录。
