# 内置动画制作

## 根据内容选画法

| 表达任务 | 内置 grammar | 制作要点 |
|---|---|---|
| 机制、公式、关系变化 | `t1_3b1b` | 颜色对应固定概念；让旧对象变成新对象，动作后留阅读停顿 |
| 产品发布、功能步骤、真实 UI 截图 | `t2_keynote_ui` | 一屏一件事，截图等比放入，强调真实操作区域 |
| 数值、趋势、对比 | `t3_finance_chart` | 坐标系→数据→标注；来源、单位、统计口径一致；示意数据明确标记 |
| 尺度、层级、系统科普 | `y1_kurzgesagt` | 当前参数化组件以节点/尺度穿行为主，专属设备与空间机制另写模块 |
| 新闻、事件、证据链 | `y2_vox` | 先放真实材料与关系，再加纸纹装饰；截图不裁掉关键证据 |
| 逐步论证、流程推导 | `y3_whiteboard` | 说一句写一句，画面逐步累计；完整内容出现后才计算阅读停留 |
| 经历、反应、幽默故事 | `y4_storytime` | 通用几何角色，反应特写与停顿承担节奏；嘴型默认是示意，不能当作精确音素同步 |
| 开场、关键词、清单、章节 | `y5_kinetic_type` | 字是主体，一次一个焦点；长文先精简再排版 |

同一片段保持一种语法；分段换语法时用统一色板、字体和字幕串联。不要强制每镜持续微动或给每镜堆动作：推导可以停住，故事可以快切后定住。表中风格名表示表现手法，成片使用自己的内容与身份资产。

## 一帧先行、再做样片

先确认构图、信息焦点与字幕空间。可选纯代码、AI 分层素材加代码、生成视频素材或混合路线；需精确同步和可编辑文字的部分由代码控制。有参考片时提取构图和运动规律，设计属于本项目的画面。静帧通过后，制作代表性动态样片；不把参数示范片的快节奏直接当作实际旁白节奏。

## 统一入口

`<skill>` 表示本 Skill 的安装目录，命令中的工程和文件路径按实际位置替换。用户只调用 `$ivanvideo-skill`，Codex 在内部运行这些工具。

```sh
python3 <skill>/scripts/init_video_project.py <project> --aspect-ratio 9:16
python3 <skill>/scripts/validate_video_project.py <project>
python3 <skill>/scripts/render_animation.py <project> --shot S01 --check
# 使用已有的、具备 Playwright 的环境；uv 是可选的隔离依赖方式，不改变全局 Python。
uv run --with playwright --with numpy --with pillow python <skill>/scripts/render_animation.py <project> --shot S01 --stills 0.5,2,4
uv run --with playwright --with numpy --with pillow python <skill>/scripts/render_animation.py <project> --shot S01 --out previews/S01-v1.mp4 --qa
```

`--spec src/clips/S01.json` 可直接渲染手写片段，与 `--shot` 二选一。`--shot` 从分镜生成 `src/clips/S01.json`，分镜是源；改生成的 JSON 后应使用 `--spec`。首次渲染将引擎和所需字体复制到 `src/animation-engine/`，将工具复制到 `scripts/ivanvideo_runtime/`，后续保留本工程已修改的副本。项目离开本 Skill 后，也能在具备相同依赖的环境中用复制的工具重渲。

输出 MP4 或 PNG、逐次 `.render.json` 参数记录及可选 `*-qa/` 报告。`--audio audio/voice.wav` 可以加入已经提供/合法生成的声音，短音轨补静音，不以截短画面掩盖时长问题。默认不覆盖已有输出；改版优先新文件名，明确覆盖时加 `--overwrite`。

## 分镜中的动画对象

```json
{
  "grammar": "t2_keynote_ui",
  "data": {"title": "一次看清流程"},
  "cues": [
    {"at": 0, "kind": "title"},
    {"anchor": {"id": "voice-feature", "edge": "start", "offset_seconds": 0},
     "kind": "card", "text": "真实功能", "image": "assets/product-screen.png"}
  ]
}
```

将这个对象放入某个 shot 的 `animation` 字段。字段 `duration`、`fps`、宽高和镜头全局起点由分镜及工程配置决定。这里的图片路径相对工程根目录。对应时间文件由 `project.json` 的 `narration.timing_path` 指定。

独立 clip JSON 则使用 `duration`、`fps`、`width`、`height`、`grammar`、`data`、`cues`，图片和 `timing_file` 路径相对该 JSON。具体参数见 animation-grammars.md。

## 旁白时间与 cue

先使用真实配音的对齐结果。没有自动对齐工具时可实际听音后手工标注，标明 `method: manual`；试稿时间标为 `draft`。不能把从文字估算的时间称为真实对齐。

时间文件格式见 project-format.md。`anchor.id` 对应其中一个句子或关键词，`edge` 取 `start` 或 `end`，偏移单位为秒；换算成片段局部秒数后对齐到输出帧。无 anchor 的 `at` 也是片段局部时间。数字 cue 的 `at` 在上游语法中表示数字落定时刻，需留出此前的计数动作时间。

配音、脚本或语速变化后重新对齐相关 cue，并复核字幕、动作和相邻镜头。落定后的阅读时间要实际留够，不能把动画展开时间算作完整内容的可读时间。

## 已明确的限制

- 标准入口提前拒绝未知 grammar/kind、越界 cue、缺图片和无效时间，避免底层静默忽略指令。
- 内置语法支持 top/bottom 安全区。left/right 的行为不一致，标准入口会拒绝非零值；有平台右侧按钮区等需求时应为该镜头实现专属布局，不宣称已经自动适配。
- `y4_storytime` 的角色等图形仍可能进入下方安全区；QA 和人工审帧需分别核对文字与图形。
- 内置导出入口为不透明 H.264 MP4 和 PNG 静帧。透明、3D 物理场景或精确技术示意使用项目专属渲染模块。
- 固定代码随机种子、字体和依赖；同一环境同一时刻可检查确定性，跨平台像素一致不能仅凭配置保证。
