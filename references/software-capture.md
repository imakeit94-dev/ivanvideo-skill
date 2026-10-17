# 真实软件画面采集

用户需要网页功能演示、已有本地应用预览或真实 UI 素材时读取。先确认目标、版本、可访问入口和已授权的操作范围；使用用户选择的目标。采集工具不会自动登录或复用其他浏览器的会话。

## 网页采集规范

在工程 scripts/capture.json 中写出实际入口和操作：

```json
{
  "url":"http://127.0.0.1:8000/",
  "product":"实际产品名",
  "version":"实际版本或 unknown",
  "platform":"实际平台",
  "feature":"本次需要展示的功能",
  "sources":["实际产品资料或源码入口"],
  "viewport":{"width":1280,"height":720},
  "record_video":true,
  "steps":[
    {"id":"before","action":"capture","assert_text":"开始状态"},
    {"id":"after","action":"click","selector":"button[data-action='open']","seconds":0.5,"assert_text":"预期结果"}
  ]
}
```

工具支持 capture、click、fill、wait_for、hold。click/fill/wait_for 使用实际 selector；fill 另填 value。seconds 为操作后停留，默认 0.2 秒、单次最多 30 秒。可用 assert_text、assert_url_contains 验证所需状态，断言失败不发布捕获包。选择已授权且可逆的演示步骤；发送、购买、删除等操作不能仅因出现在示例里就获得授权。

步骤 ID 保持唯一，开启录屏时保留 recording 给录屏资产，不将它用作步骤 ID。

```sh
python3 <skill>/scripts/capture_web.py <project> --spec scripts/capture.json --check
uv run --with playwright python <skill>/scripts/capture_web.py <project> --spec scripts/capture.json --out assets/captures/feature-v1
```

使用已有 Playwright/Chromium；不自动安装浏览器或大型框架。新开独立上下文，不读取已有 cookie、密码或登录资料。当前只处理单页网页；新窗口、登录流程和原生桌面软件应使用合适的已有采集工具，明确记录实际方法。

## 捕获包与证据

捕获包保存每步 PNG、可选原始 WebM 与 H.264 录屏、capture.json。报告记录来源 URL、产品/版本、规格、操作和断言、页面异常、素材哈希及运行环境。记录中的 wall_seconds 是观察时间，不是严格对齐到录屏首帧的时间码；需要按动作配音时，检查实际编码片段后再取剪辑点。

不得修改捕获页的 DOM、文字或功能状态来冒充实际软件。宣传框架、取景、外层放大可在视频里制作；模拟数据、原组件受控运行、说明性重建分别留证，不能混称真实运行结果。桌面原生 UI 并未被此网页工具自动覆盖。

分镜使用捕获素材时，仍用已有 media，并可绑定报告：

```json
{
  "media":{"type":"image","path":"assets/captures/feature-v1/after.png","fit":"contain"},
  "capture_evidence":{"report":"assets/captures/feature-v1/capture.json","asset_id":"after"}
}
```

录屏素材的 asset_id 为 recording，media.type 为 video。渲染检查报告中的素材哈希、路径和类型；采集规范被修改或媒体被替换时拒绝绑定。需要改版时保留原规范与捕获包，另存新版本。报告校验只证明引用一致，不能证明产品的所有宣传主张。

实际观看录屏和导出帧，对照版本、资料与断言结果，按 product-evidence.md 建立逐镜头证据记录。review_status 默认 pending；自动脚本不会代替用户把功能真实性改为通过。素材和具体目标记录留在视频项目，公共 Skill 只保存通用工具与说明。
