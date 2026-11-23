"""
HTML → PNG renderer using Playwright (Chromium).
Renders each .slide at phone dimensions, 5x device pixel ratio.
"""
import asyncio
import re
from pathlib import Path

CHROMIUM = "/opt/pw-browsers/chromium"
SLIDE_CSS = ".slide"
PHONE_CSS = ".phone"


async def _render_slides_async(html_path: str, out_dir: str, prefix: str) -> list[str]:
    from playwright.async_api import async_playwright

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROMIUM,
            args=["--no-sandbox", "--disable-gpu"],
        )
        page = await browser.new_page(
            viewport={"width": 400, "height": 700},
            device_scale_factor=5,
        )
        await page.goto(f"file://{html_path}")
        await page.wait_for_timeout(500)

        slides = await page.query_selector_all(SLIDE_CSS)
        total = len(slides)

        for i in range(total):
            # activate slide i, deactivate others
            await page.evaluate(f"""
                (function() {{
                    var slides = document.querySelectorAll('.slide');
                    slides.forEach(function(s, j) {{
                        s.classList.remove('active', 'gone');
                        if (j === {i}) s.classList.add('active');
                    }});
                }})();
            """)
            await page.wait_for_timeout(800)

            fname = out / f"{prefix}_s{i+1}.png"
            phone = page.locator(PHONE_CSS)
            await phone.screenshot(path=str(fname), scale="device")
            paths.append(str(fname))

        await browser.close()

    return paths


def render_slides(html_path: str, out_dir: str, prefix: str) -> list[str]:
    return asyncio.run(_render_slides_async(html_path, out_dir, prefix))


async def _render_cards_async(html_path: str, out_dir: str, prefix: str) -> list[str]:
    """Render white card sections (multiple .card divs on a page)."""
    from playwright.async_api import async_playwright

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROMIUM,
            args=["--no-sandbox", "--disable-gpu"],
        )
        page = await browser.new_page(
            viewport={"width": 420, "height": 500},
            device_scale_factor=5,
        )
        await page.goto(f"file://{html_path}")
        await page.wait_for_timeout(500)

        cards = await page.query_selector_all(".card")
        for i, card in enumerate(cards):
            fname = out / f"{prefix}_c{i+1}.png"
            await card.screenshot(path=str(fname), scale="device")
            paths.append(str(fname))

        await browser.close()

    return paths


def render_cards(html_path: str, out_dir: str, prefix: str) -> list[str]:
    return asyncio.run(_render_cards_async(html_path, out_dir, prefix))
