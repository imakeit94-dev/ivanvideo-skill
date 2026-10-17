# 中文 TTS 与实测时间线

在审核后的口播需要转成声音、字幕和镜头时间时读取。保留脚本/样片的既有审核节点；技术测试或连续制作已获授权时按原授权执行。

## 配音输入

在工程 `scripts/narration.json` 保存按播放顺序排列的句子：

```json
{
  "provider":"macos",
  "voice":"Tingting",
  "rate_wpm":195,
  "segments":[
    {"id":"v1","shot_id":"S01","text":"先取得声音，再安排镜头。"},
    {"id":"v2","shot_id":"S02","text":"RTK 使用改正信息。","speech_text":"R T K 使用改正信息。"}
  ]
}
```

`text` 是正式旁白和字幕；`speech_text` 可选，仅用于发音，不能改变事实。相同镜头可有多句，segment ID 保持稳定；顺序必须与分镜一致。每镜 narration 应等于该镜各句 text 拼接（忽略空白），不一致时先统一审核文本。没有旁白的镜头可保留空 narration，不强制配音。

当前有两个输入模式：

- **macos**：使用本机已经安装的 `say` 声音，默认 Tingting；可离线工作，不自动下载声音。`--voices` 列出实际声音，不存在时明确报错。此模式不在 Linux/Windows 合成，但已产生的 WAV 可随工程继续使用。
- **provided**：将外部 TTS、录音或已提供声音归一到工程缓存。每句提供 `audio_path`，可选 `trim_in_seconds`、`duration_seconds`。音频必须真实存在；不能因文本存在就假定声音与文字一致。保留来源和服务使用条件。原音频路径仍被用于变更校验，工程迁移时也应携带原音频或处理对应路径。

```json
{"provider":"provided","segments":[{"id":"v1","shot_id":"S01","text":"已审核的句子。","audio_path":"audio/source-v1.wav"}]}
```

不自动安装云端 TTS SDK、寻找密钥或调用收费服务。用户已有其他提供方时，先生成合法音频再用 provided；当前没有通用云 API 适配器。

## 生成与缓存

```sh
python3 <skill>/scripts/narrate.py --voices
python3 <skill>/scripts/narrate.py <project> --check
python3 <skill>/scripts/narrate.py <project>
```

默认读取 scripts/narration.json；`--script` 可改为其他工程内输入。每句统一为单声道 48 kHz、16 位 PCM WAV，按真实采样数测量时长；不按字数估计，不自动削去停顿，以免截断声音。

缓存位于 `audio/tts/chunks/<哈希>/`，键包含提供方、声音/语速、发音文本、相关源音频、生成器及工具版本。修改一句可复用其余句子；更换影响声音的设置会重新生成对应缓存。被修改的缓存拒绝复用；要手工修音，应另存后作为 provided 输入。

`audio/tts/manifest.json` 指向最近生成结果，`audio/tts/manifests/` 保留按内容版本命名的清单。记录脚本文本哈希、每句音频、采样数、时长、来源与待试听状态。修改文字、发音或导入的原音频后，重新生成并排时。

## 排时预览与应用

分镜可增加可选设置：

```json
{"voice_timing":{"lead_seconds":0.3,"gap_seconds":0.18,"tail_seconds":0.5,"minimum_seconds":4}}
```

以上是本工具的默认引导/间隔/收尾起点，minimum 默认零；按内容调整。镜头时间由句子实测时长、间隔、读图停留和明确的转场重叠决定。音频保持采样精度，镜头边界对齐到帧。跨镜头人声重叠、失效的动作 cue 或三镜头转场会报错。

```sh
# 仅检查，无写入
python3 <skill>/scripts/schedule_narration.py <project> --check
# 默认生成候选文件，不改原分镜
python3 <skill>/scripts/schedule_narration.py <project>
# 按用户当前授权应用，并保留修改前副本
python3 <skill>/scripts/schedule_narration.py <project> --apply
```

候选文件位于 `src/narration-plans/<版本>/`。应用只更新镜头起止时间、必要的空旁白字段、工程时长、生成声音轨及字幕时间引用；保留媒体、视觉设计、已确认文字和其他音轨。`references/narration-revisions/` 保存修改前配置和事务状态，运行错误时尝试回滚；进程意外退出时据 applying 状态和 before 副本恢复。

已有未归本工具管理的旁白不会被静默替换。应用后的重复相同操作不产生内容修改。所有被重排的镜头都列出旧/新时间，后续镜头的移动是音频时长变化的直接结果。

工程时长为空时使用实测排时结果；固定时长足够则保留，余量留在末镜头。超时先调整文案或制作要求；只有明确允许调整时长时才使用 `--resize`。不会加速声音来凑时长。原音乐、音效及录屏长度不会被悄悄改写，重排后重新检查这些素材是否仍覆盖相应镜头。

## 句级字幕与同步检查

输出 `audio/narration-timing.json`，标记 `method: measured`、`granularity: sentence_clip`。这表示字幕覆盖相应声音片段的播放区间，包括片段里的停顿；不是词、音素或嘴型对齐。精确关键词动作需要另取可靠对齐结果；现在可用句界 anchor，加手工偏移时明确它是手工设计。

应用后同一组时间驱动 voice tracks、字幕和动画句界 anchor。渲染前会核对脚本、分镜旁白、音频哈希、生成轨起点及时间文件；过期时失败，不能用旧字幕配新声音。整片导出保留 ASS 和 SRT；ASS 为厘秒、SRT 为毫秒，取整不构成逐词精度。

如用户明确改用手工时间，应保存旧版本，再移除 narration.generated_timeline 的自动生成标记并维护对应音轨/字幕；不要修改哈希来绕过校验。

最后执行 `validate_video_project.py --delivery --film`、整片渲染和 check_video.py。试听发音、断句、停顿与可懂度；观看字幕断行、读速、遮挡与动作语义。成功合成声音和通过时长检查不等于已经听过。
