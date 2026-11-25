#!/usr/bin/env python3.13
"""
블랙 명조 카드 생성기 (Threads 첨부 이미지용)

사용법:
  python3.13 make_card.py "헤드라인" "본문 1줄|본문 2줄||새 문단 1줄" out.png
  - '|'  = 줄바꿈
  - '||' = 문단 띄우기
"""
import asyncio
import html
import sys
from pathlib import Path

CHROMIUM = "/opt/pw-browsers/chromium"
FONT_DIR = Path(__file__).parent / "fonts"

TEMPLATE = """<!doctype html><meta charset="utf-8">
<style>
@font-face {{ font-family:'Myeongjo'; font-weight:400; src:url('file://{font_dir}/NanumMyeongjo-Regular.ttf'); }}
@font-face {{ font-family:'Myeongjo'; font-weight:700; src:url('file://{font_dir}/NanumMyeongjo-Bold.ttf'); }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#000; }}
.card {{
  width:1080px; height:1080px; background:#000;
  display:flex; flex-direction:column; justify-content:center;
  padding:0 112px;
  font-family:'Myeongjo', serif;
}}
.headline {{
  font-size:50px; font-weight:700; color:#E9C04A;
  line-height:1.5; letter-spacing:0.01em; word-break:keep-all;
  margin-bottom:64px;
}}
.body {{
  font-size:44px; font-weight:400; color:#F2F2F2;
  line-height:2.25; letter-spacing:0.01em; word-break:keep-all;
}}
.gap {{ height:36px; }}
</style>
<div class="card">
  <div class="headline">{headline}</div>
  <div class="body">{body}</div>
</div>
"""


def _body_html(body: str) -> str:
    paras = [p.split("|") for p in body.split("||")]
    return '<div class="gap"></div>'.join(
        "<br>".join(html.escape(line) for line in lines) for lines in paras
    )


async def _render(headline: str, body: str, out: str):
    from playwright.async_api import async_playwright

    page_html = TEMPLATE.format(
        font_dir=FONT_DIR.resolve(),
        headline="<br>".join(html.escape(l) for l in headline.split("|")),
        body=_body_html(body),
    )
    tmp = Path(out).with_suffix(".html")
    tmp.write_text(page_html, encoding="utf-8")

    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1080, "height": 1080}, device_scale_factor=2)
        await page.goto(f"file://{tmp.resolve()}")
        await page.evaluate("document.fonts.ready")
        await page.wait_for_timeout(300)
        await page.locator(".card").screenshot(path=out, scale="device")
        await browser.close()
    tmp.unlink()


def make_card(headline: str, body: str, out: str) -> str:
    asyncio.run(_render(headline, body, out))
    return out


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    print(make_card(sys.argv[1], sys.argv[2], sys.argv[3]))
