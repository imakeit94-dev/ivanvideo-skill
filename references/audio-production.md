# 基础混音与声音检查

本模块处理已提供或已合法生成的音频，不包含 TTS 服务、自动逐词对齐或音乐下载。整片合成时按需读取。

## 配置

在 `project.json` 增加可选 `audio`；旧项目缺少本字段仍可使用：

```json
{
  "audio": {
    "sample_rate": 48000,
    "tracks": [
      {"id":"voice-1","role":"voice","path":"audio/sentence-1.wav","at_seconds":0.5},
      {"id":"music","role":"music","path":"audio/music.wav","at_seconds":0,"duration_seconds":15,"gain_db":-14}
    ],
    "ducking":{"enabled":true,"db":8,"attack_seconds":0.08,"release_seconds":0.25},
    "normalization":null
  }
}
```

每轨唯一 `id`；`role` 为 voice/music/sfx；`at_seconds` 是全片绝对起点。可选 `trim_in_seconds`、`duration_seconds`、`gain_db`；默认从头播放到源结束。源时长用 FFprobe 实测。音频超出片长会报错，需显式裁短或调整分镜，不静默切掉结尾。

`narration.audio_path` 提供整条旁白且 enabled 不是 false 时自动作为 voice；不要又写一条相同的 voice track。若显式使用分句 voice tracks，则不再同时提供 narration.audio_path。旁白启用但无 voice 会失败。

镜头内的动作音效写入原有 `audio_cues`：

```json
{"id":"open-panel","path":"audio/click.wav","offset_seconds":1.2,"sync_offset_seconds":0.03,"gain_db":-4}
```

`offset_seconds` 是镜头内的动作时刻；`sync_offset_seconds` 是裁切后素材内部的听觉落点，默认零。播放从 `镜头开始 + offset - sync_offset` 开始。可选 trim_in_seconds、duration_seconds；落点需实际测量或试听，不能假定文件第一采样就是动作点。负起点报错，需修改素材或时机。

## 执行和产物

```sh
python3 <skill>/scripts/mix_audio.py <project> --check
python3 <skill>/scripts/mix_audio.py <project>
```

默认生成 `audio/mixes/<计划哈希>/voice.wav`、`music.wav`、`sfx.wav`、`master.wav`、`mix.json`。缺少的分轨补等长静音；完全没有提供音频时不伪造混音。分轨使用浮点 WAV 保留叠加余量；master 为 24 位 PCM。每轨按采样点定位，并补静音至整片长度。

ducking 只压低 music。第一版根据 voice 素材的区间生成音量包络，并不识别句内停顿或词；长旁白有大量停顿时可提供分句轨道，或另做精细音量自动化。重叠语音区间取当前最大衰减，避免反复相乘。数值是项目起点，最终以人声可懂、音乐自然为准。

可选双遍 loudnorm：

```json
{"normalization":{"integrated_lufs":-20,"true_peak_db":-2,"lra":11}}
```

以上为配置示例，不是所有平台的标准。未配置时不自动改变总响度；发现超过 0 dBTP 的混音拒绝导出，降低 gain_db 或配置处理后再试。配置后记录实测输入、第二遍实际 linear/dynamic 模式和输出测量；完全静音不能正常标准化。

旧混音只有在计划、素材哈希、主文件哈希和混音器版本均一致时才能复用。新计划默认另存目录。导出 MP4 后再次测量编码后的峰值，超过 0 dBTP 时拒绝发布；峰值正常不能证明声音好听。

FFmpeg 测量记录中的 `input_i`、`input_tp`、`input_lra` 表示被测文件的实际响度/峰值/响度范围；同一段日志的 output_* 是测量滤镜模拟处理的结果，不能当作原文件的值。

## 审核

按次序试听 voice、music、sfx、master 和实际导出的 MP4。核对发音、语义、动作同步、配乐遮盖、突响、异常静音及收尾。机器测量与试听分别记录；不能从波形、分轨文件存在或编码成功推断“已经听过”。

方法参考了 video-shotcraft 的动作/音乐关系和 guizang-product-video-skill 的声音检查实践；本批脚本为 IvanVideo 独立实现，未移植其脚本、模板或音频文件。
