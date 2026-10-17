# 封面制作

从已确认的影片主旨中选一个标题与一个视觉主体。标题应准确，不夸大产品功能或新闻确定性。优先沿用片中的配图、品牌色和字体；也可从已确认视频提取实际帧，按 asset-production.md 登记为图片并记录原视频与时间码。封面不是必须重新调用模型的步骤。

## 配置与渲染

`references/cover.json`：

```json
{
  "title": "从素材\n到成片", "subtitle": "配图与可编辑视频", "eyebrow": "IVANVIDEO",
  "asset_id": "A01",
  "palette": {"background":"#071527","text":"#f5f7fc","accent":"#72e2d2"},
  "variants": [
    {"id":"landscape","width":1280,"height":720,"layout":"auto"},
    {"id":"portrait","width":1080,"height":1920,"layout":"auto"},
    {"id":"square","width":1080,"height":1080,"layout":"auto"}
  ]
}
```

```bash
python "$SKILL/scripts/render_covers.py" "$PROJECT" --check
python "$SKILL/scripts/render_covers.py" "$PROJECT" --out outputs/covers-v1
```

使用已有 Playwright/Chromium 环境；若项目用 uv 缓存，可在其环境中运行，不自动安装。`asset_id` 指向已登记的静态图片。默认字体为随 Skill 提供的 Noto Sans SC，输出携带 OFL 与字体说明；`font_path` 可选，使用自备字体时要另保留其授权说明。

宽画幅 auto 使用左右分栏，竖屏/方形上下排布；可显式指定 split/stack。主体图片 contain，不拉伸或裁掉图中内容。字数过多时按画布有限缩小标题，仍溢出即失败，不截断凑成封面。比例变化后分别布局，不直接裁剪成品。上述尺寸是示例，可修改；并不代表某平台当前上传规格，发布前应核实平台要求。

输出每个画幅的 PNG、HTML，以及 `assets/` 图像、字体和配置与 `covers.json`。HTML 保留独立文字，换标题可修改原 cover.json 再生成新目录；也可编辑 HTML 另存预览。不要覆盖已确认版本。工程的合成脚本快照包含封面工具，离开全局 Skill 仍可使用项目自带工具重新生成。

## 检查与交付

自动检查登记来源与输入哈希、字体/图像实际加载、页面错误、文字布局溢出与画布边界；输出实际尺寸与标题字号记录。不能据此宣称所有字形、对比度或平台审核通过。

人工查看每种画幅，缩小到缩略图再看：标题是否易读，主体是否过小，主次是否明确，配图与标题是否一致，有无生成伪影与误导标识。检查真实字体授权、来源条款；如需独立控制图中文字或精确图形，应回到可编辑图形，不能靠封面工具拆开生成图的像素。交付 PNG 与 HTML 源文件及用到的图像，全部留在工程目录。
