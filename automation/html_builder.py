"""
Builds a complete HTML file from slide JSON data using the dark template.
"""
import json
from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent / "templates" / "shorts_dark.html"


def build_slide_html(slides: list[dict], output_path: str, font_size: int = 36) -> str:
    """Build a complete HTML slideshow from slide data."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    slide_html_parts = []
    for i, slide in enumerate(slides):
        idx = i + 1
        stype = slide.get("type", "generic")
        tag = slide.get("tag", "")
        main = slide.get("main", "").replace("\n", "<br>")
        sub = slide.get("sub", "").replace("\n", "<br>")

        inner = f'<div class="bg-num">{idx}</div>\n'
        inner += f'<div class="stag">{tag}</div>\n'

        if stype == "hook":
            inner += f'<div class="mtxt">{main}</div>\n'
            inner += f'<div class="stxt">{sub}</div>\n'

        elif stype == "pain":
            inner += '<div class="accent-line"></div>\n'
            inner += f'<div class="mtxt"><span class="r">{main}</span></div>\n' if "통장" in main or "못" in main else f'<div class="mtxt">{main}</div>\n'
            inner += f'<div class="stxt"><strong>{sub}</strong></div>\n'

        elif stype == "quote":
            inner += f'<div class="mtxt">{main}</div>\n'
            quote = slide.get("quote", "").replace("\n", "<br>")
            source = slide.get("source", "")
            inner += f'<div class="qbox"><p>{quote}</p><span class="src">{source}</span></div>\n'

        elif stype == "stats":
            inner += '<div class="accent-line"></div>\n'
            inner += f'<div class="mtxt"><em>{main}</em></div>\n'
            stats = slide.get("stats", [])
            cards = "".join(
                f'<div class="nc"><div class="nc-num">{s["num"]}</div><div class="nc-lbl">{s["label"]}</div></div>'
                for s in stats
            )
            inner += f'<div class="num-cards">{cards}</div>\n'

        elif stype == "scarcity":
            urgent = slide.get("urgent", "")
            if urgent:
                inner += f'<div class="urgent">{urgent}</div>\n'
            inner += f'<div class="mtxt">{main}</div>\n'
            inner += f'<div class="stxt">{sub}</div>\n'

        elif stype == "cta":
            inner += '<div class="accent-line"></div>\n'
            inner += f'<div class="mtxt">{main}</div>\n'
            inner += f'<div class="stxt">{sub}</div>\n'
            inner += '<div class="cta-btn">DM 줘 👇</div>\n'
            inner += '<div class="cta-sub">@blk_writer · 블랙스톤</div>\n'

        else:
            inner += f'<div class="mtxt">{main}</div>\n'
            if sub:
                inner += f'<div class="stxt">{sub}</div>\n'

        slide_html_parts.append(f'<div class="slide" id="s{idx}">\n{inner}</div>')

    slides_html = "\n".join(slide_html_parts)
    total = len(slides)

    html = template.replace("{{SLIDES}}", slides_html)
    html = html.replace("{{TOTAL}}", str(total))
    html = html.replace("{{FONT_SIZE}}", str(font_size))

    Path(output_path).write_text(html, encoding="utf-8")
    return output_path
