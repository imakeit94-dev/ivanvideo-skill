# 配图与可选 AI 视频素材

先读已确认脚本，逐镜头判断表达任务：真实功能用真实 UI；精确结构、坐标、数值和技术推导用可编辑代码图形；情境、隐喻、背景才适合生成式素材。新闻中的事件影像不得用生成画面冒充，示意图要标注。把拟用素材、缺口和用途记入工程，不要求服务或参考图齐全才开始策划。

## 1. 规划与提示词

工程 `references/asset-plan.json` 示例：

```json
{
  "style": "深蓝与青绿，柔和摄影棚光，统一材质",
  "assets": [{
    "id": "A01", "media_type": "image", "role": "illustration",
    "purpose": "解释从素材到视频的概念，不是产品截图",
    "shot_ids": ["S01"], "aspect_ratio": "1:1",
    "prompt": "居中的透明胶片与空白分镜卡片，主体四周留白，不生成文字或标志。",
    "avoid": ["虚构 UI", "可读文字"], "reference_images": [],
    "provider": null, "model": null
  }]
}
```

`role` 为 illustration/background/b_roll/cover_subject；视频用 `media_type:video`，另需正数 `duration_seconds`。参考图填实际文件路径；缺图会记为 missing、ready=false。`shot_ids` 可空（例如仅封面），非空时必须已存在。`provider/model` 是期望值，不证明服务已执行。

```bash
python "$SKILL/scripts/asset_workflow.py" "$PROJECT" prepare --check
python "$SKILL/scripts/asset_workflow.py" "$PROJECT" prepare
```

输出版本化 `references/asset-requests/<hash>/<id>.json` 和提示词 MD，状态恒为 planned。`--check` 不写文件。修改计划或参考图形成新请求，保留生成时的旧请求。

提示词围绕主体、信息目的、构图、镜头、光线、材质、画幅、留白和限制。统一一套视觉语言，参考只提炼构图与表现方法；不得复制专有品牌资产。精确标题、中文标签、参数和数据在 HTML/React/字幕中排版，避免依靠模型把事实画对。编辑图像时保留原始图，另存变体。

## 2. 按需调用已有服务

- 先检查当前可调用的原生工具、已安装 CLI、已有服务连接及能力。调用工具前阅读其说明；涉及第三方当前模型、尺寸、费用或 API 参数时查当前官方资料。不要凭记忆声称支持某分辨率、时长或参考模式。
- 配图优先用当前原生 imagegen（有其 Skill 时遵从其操作规则）。把实际提交的提示词与原始返回文件存入工程。不要因为旧示例出现某 API 就安装 SDK、要求密钥或使用另一付费服务。
- AI 视频是可选分支：先明确该镜头需要运动还是静图运镜即可。服务实际可用并在用户预算/授权范围内时，按当前接口组织分段动作、相机、主体一致性、参考文件、时长与音频要求；不固定某风格、15 秒或字数门槛。
- 异步服务需保存实际提供方/模型（未暴露填 null）、请求参数、任务 ID、完成状态与错误。任务接受、排队、生成成功、下载完成是不同状态；下载并验证文件前不称为可用视频。失败保留记录，可改用现有素材或代码动画。
- 服务不可用时提供请求与提示词，明确“未生成”，接受用户提供的成品。无需为本工作流安装 Dreamina、视频框架或全局服务。不得静默重试收费任务或购买额度。
- 此 Skill 的 CLI 准备请求、导入和检查文件；模型调用由当前工具编排。无需用户再调用其他制作 Skill。语音/配乐不从未知视频音轨自动启用。

## 3. 登记真实返回文件

先写 `references/A01-result.json`：

```json
{
  "origin": "ai_generated", "provider": "实际工具名", "model": null,
  "source": "实际调用与日期", "license": "提供方条款；使用权待审核",
  "job_id": null, "prompt_used": "实际提交的完整提示词", "notes": "概念示意图"
}
```

提供素材用 `origin:user_provided`；程序生成的测试夹具只能用 `synthetic_test`。source/license 必填，未确定可写 unknown，绝不自动视为可商用。AI 输出必须记录实际 provider 和 prompt_used；不猜模型。

```bash
python "$SKILL/scripts/asset_workflow.py" "$PROJECT" register \
  --request references/asset-requests/HASH/A01.json \
  --file /actual/returned-image.png --metadata references/A01-result.json
python "$SKILL/scripts/asset_workflow.py" "$PROJECT" verify --id A01
```

导入读取并完整解码文件，检查静态 PNG/JPEG/WebP 或实际 MP4/MOV/WebM/MKV 视频，测量尺寸、帧数、时长及音轨数。输出复制到工程 `assets/media/`，追加现有 `assets/manifest.json` 数组，保留旧条目；重复 ID 拒绝覆盖。音频仅登记，合成中需显式音轨。媒体不足镜头时长由成片检查拒绝，不自动拉伸。比较请求与实测画幅/时长；偏差应调整镜头或重新生成，不冒称请求精确满足。

生成来源、请求哈希、参考图哈希、成品哈希与人工审核状态保存在清单。生成图不得只留在工具缓存。镜头绑定：

```json
{"media":{"type":"image","path":"assets/media/A01-HASH.png","fit":"contain"},"asset_evidence":{"id":"A01"}}
```

编译时验证路径、媒体类型、内容与原请求，混用文件或修改旧请求会失败；没有新字段的旧工程继续可用。修改素材用新 ID 与分镜局部替换，避免影响已确认镜头。

## 审核与保留

自动解码不能判断模型伪影、技术正确性、商标、人物肖像授权或商用权。逐项检查主体形态、手部/文字、事实、产品真实性、来源条款及视觉一致性。最终保留计划、提示词、服务记录、原文件与所用版本；测试夹具、任务 ID 或单帧改扩展名不算 AI 视频服务验证。
