#!/usr/bin/env python3
"""Create editable HTML and PNG covers from a registered image and approved copy."""
import argparse
import functools
import html
import http.server
import json
import re
import shutil
import sys
import tempfile
import threading
from pathlib import Path

from asset_workflow import asset_id, registered_asset
from film_core import digest, identity, keys, local, output_path, read, subtitle_font, write


def cover_input(root, path):
    spec = read(path)
    keys(spec, ("title", "subtitle", "eyebrow", "asset_id", "font_path", "palette", "variants"), "cover configuration")
    for name in ("title", "asset_id"):
        if not isinstance(spec.get(name), str) or not spec[name].strip():
            raise ValueError("Cover needs " + name)
    for name in ("subtitle", "eyebrow"):
        if not isinstance(spec.get(name, ""), str):
            raise ValueError(name + " must be a string")
    palette = spec.get("palette", {})
    keys(palette, ("background", "text", "accent"), "cover palette")
    for color in palette.values():
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError("Cover colors must be six-digit hex values")
    variants = spec.get("variants")
    if not isinstance(variants, list) or not variants:
        raise ValueError("Cover needs non-empty variants")
    seen = set()
    for variant in variants:
        keys(variant, ("id", "width", "height", "layout"), "cover variant")
        label = asset_id(variant.get("id"))
        if label in seen:
            raise ValueError("Duplicate cover variant ID")
        seen.add(label)
        if any(not isinstance(variant.get(k), int) or isinstance(variant[k], bool) or variant[k] <= 0 for k in ("width", "height")):
            raise ValueError("Cover dimensions must be positive integers")
        if variant.get("layout", "auto") not in ("auto", "split", "stack"):
            raise ValueError("Cover layout must be auto, split or stack")
    item = registered_asset(root, spec["asset_id"])
    if item["media_type"] != "image":
        raise ValueError("Select a registered still image; extract an approved video frame first if needed")
    font = local(root, spec["font_path"]) if spec.get("font_path") else subtitle_font(root, {})
    if not font.is_file() or font.suffix.lower() not in (".woff", ".woff2", ".ttf", ".otf"):
        raise ValueError("Provide a readable WOFF/TTF/OTF cover font")
    return spec, item, font


def cover_html(spec, variant, image_name, font_name):
    w, h = variant["width"], variant["height"]
    layout = variant.get("layout", "auto")
    if layout == "auto":
        layout = "split" if w / h >= 1.35 else "stack"
    colors = {"background": "#071527", "text": "#f5f7fc", "accent": "#72e2d2", **spec.get("palette", {})}
    size = min(90, w * 0.072, h * 0.14)
    padding = round(min(w, h) * 0.065)
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(spec['title'])}</title><style>
@font-face{{font-family:CoverFont;src:url('assets/{font_name}')}}
*{{box-sizing:border-box}}body{{margin:0;background:{colors['background']}}}
.poster{{width:{w}px;height:{h}px;padding:{padding}px;color:{colors['text']};background:{colors['background']};font-family:CoverFont,sans-serif;overflow:hidden}}
.layout{{width:100%;height:100%;display:grid;gap:4%;min-width:0;min-height:0}}
.split{{grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr)}}
.stack{{grid-template-rows:minmax(0,1.2fr) minmax(0,1fr);gap:4%}}
.copy{{display:flex;flex-direction:column;justify-content:center;min-width:0;min-height:0;gap:{round(min(w,h)*.025)}px}}
.stack .art{{grid-row:1}}.stack .copy{{grid-row:2;justify-content:flex-start}}
.title{{font-size:{size}px;font-weight:500;line-height:1.15;letter-spacing:-.025em;margin:0;white-space:pre-line;overflow-wrap:anywhere}}
.eyebrow{{font-size:{max(12,round(min(w,h)*.026))}px;letter-spacing:.12em;color:{colors['accent']};overflow-wrap:anywhere}}
.subtitle{{font-size:{max(14,round(min(w,h)*.032))}px;line-height:1.5;opacity:.82;white-space:pre-line;overflow-wrap:anywhere}}
.art{{min-width:0;min-height:0;display:flex;align-items:center;justify-content:center}}
.art img{{display:block;width:100%;height:100%;object-fit:contain}}
</style></head><body><main class="poster"><div class="layout {layout}">
<section class="copy">{('<div class="eyebrow">'+html.escape(spec['eyebrow'])+'</div>') if spec.get('eyebrow') else ''}
<h1 class="title">{html.escape(spec['title'])}</h1>
{('<div class="subtitle">'+html.escape(spec['subtitle'])+'</div>') if spec.get('subtitle') else ''}</section>
<figure class="art" style="margin:0"><img alt="" src="assets/{image_name}"></figure>
</div></main></body></html>"""


def render(root, spec_path, directory):
    root, spec_path, directory = (Path(p).resolve() for p in (root, spec_path, directory))
    spec, item, font = cover_input(root, spec_path)
    if directory.exists():
        raise ValueError("Cover output exists; use a new versioned directory")
    try:
        from playwright.sync_api import sync_playwright
        import importlib.metadata
    except ImportError as error:
        raise ValueError("Use an existing Playwright/Chromium environment; nothing was installed") from error
    source = local(root, item["path"])
    expected = {"config": digest(spec_path), "image": digest(source), "font": digest(font)}
    directory.parent.mkdir(parents=True, exist_ok=True)
    records = []
    with tempfile.TemporaryDirectory(prefix=".covers-", dir=directory.parent) as temporary:
        stage = Path(temporary)
        (stage / "assets").mkdir()
        image_name, font_name = "subject" + source.suffix.lower(), "cover-font" + font.suffix.lower()
        shutil.copy2(source, stage / "assets" / image_name)
        shutil.copy2(font, stage / "assets" / font_name)
        if not spec.get("font_path"):
            for name in ("LICENSES.md", "OFL.txt"):
                shutil.copy2(font.parent / name, stage / "assets" / name)
        write(stage / "cover.json", spec)
        for variant in spec["variants"]:
            (stage / (variant["id"] + ".html")).write_text(cover_html(spec, variant, image_name, font_name), encoding="utf-8")

        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(stage)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as playwright:
                with playwright.chromium.launch() as browser:
                    for variant in spec["variants"]:
                        page = browser.new_page(viewport={"width": variant["width"], "height": variant["height"]}, device_scale_factor=1)
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        page.goto(f"http://127.0.0.1:{server.server_port}/{variant['id']}.html", wait_until="load")
                        page.evaluate("document.fonts.ready")
                        page.wait_for_function("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
                        if not page.evaluate("document.fonts.check('16px CoverFont')"):
                            raise ValueError("Cover font did not load")
                        measurements = page.evaluate("""() => {
                          const copy=document.querySelector('.copy'), title=document.querySelector('.title');
                          const min=Math.max(16,Math.min(innerWidth,innerHeight)*.025);
                          let size=parseFloat(getComputedStyle(title).fontSize);
                          while((copy.scrollHeight>copy.clientHeight+1 || title.scrollWidth>title.clientWidth+1) && size>min){
                            size=Math.max(min,size-1);title.style.fontSize=size+'px';
                          }
                          const boxes=[...document.querySelectorAll('.title,.eyebrow,.subtitle')].map(e=>{
                            const b=e.getBoundingClientRect();return {text:e.textContent,x:b.x,y:b.y,width:b.width,height:b.height};
                          });
                          return {font_size:size, overflow:copy.scrollHeight>copy.clientHeight+1 || title.scrollWidth>title.clientWidth+1,
                            boxes, object_fit:getComputedStyle(document.querySelector('img')).objectFit};
                        }""")
                        if measurements["overflow"] or any(b["x"] < 0 or b["y"] < 0 or b["x"] + b["width"] > variant["width"] + 1 or b["y"] + b["height"] > variant["height"] + 1 for b in measurements["boxes"]):
                            raise ValueError("Cover text does not fit: " + variant["id"] + "; shorten copy or change layout")
                        if errors:
                            raise ValueError("Cover page errors: " + str(errors))
                        # Persist adjusted typography in the editable HTML too.
                        original = (stage / (variant["id"] + ".html")).read_text(encoding="utf-8")
                        original = original.replace("</style>", f".title{{font-size:{measurements['font_size']}px}}</style>")
                        (stage / (variant["id"] + ".html")).write_text(original, encoding="utf-8")
                        png = stage / (variant["id"] + ".png")
                        page.screenshot(path=str(png))
                        records.append({"id": variant["id"], "width": variant["width"], "height": variant["height"],
                                        "png": png.name, "sha256": digest(png), "html": variant["id"] + ".html", "measurements": measurements})
                        page.close()
                    browser_version = browser.version
        finally:
            server.shutdown()
            server.server_close()
        if digest(spec_path) != expected["config"] or digest(source) != expected["image"] or digest(font) != expected["font"]:
            raise ValueError("Cover inputs changed during rendering")
        report = {"schema_version": 1, "source_asset_id": item["id"], "source_sha256": item["sha256"],
                  "source_provenance": item["provenance"], "input_hashes": expected, "variants": records,
                  "runtime": {"chromium": browser_version, "playwright": importlib.metadata.version("playwright")},
                  "manual_review_pending": ["Composition and subject visibility", "Thumbnail readability and contrast", "Facts, generated artifacts, brand and usage conditions"],
                  "note": "HTML/CSS composes immutable source art and editable text; no automatic platform approval is implied."}
        write(stage / "covers.json", report)
        stage.rename(directory)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--spec", default="references/cover.json")
    parser.add_argument("--out", help="New project-relative cover bundle directory")
    parser.add_argument("--check", action="store_true", help="Validate inputs without launching a browser or rendering")
    args = parser.parse_args()
    root = args.project.expanduser().resolve()
    path = output_path(root, args.spec)
    spec, item, font = cover_input(root, path)
    if args.check:
        print(json.dumps({"valid": True, "variants": len(spec["variants"])}))
        return 0
    version = identity({"config": spec, "asset": item["sha256"], "font": digest(font), "renderer": digest(__file__)})[:16]
    directory = output_path(root, args.out or "outputs/covers/" + version)
    report = render(root, path, directory)
    print(json.dumps({"directory": str(directory), "variants": [v["png"] for v in report["variants"]]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print("IvanVideo: " + str(error), file=sys.stderr)
        raise SystemExit(2)
