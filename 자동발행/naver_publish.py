"""네이버 블로그 자동발행 (글 1개)

사용법:
    pip install playwright
    python naver_publish.py ../포스트/001_매일_글을_쓴다는_것.md          # 실제 발행
    python naver_publish.py ../포스트/001_매일_글을_쓴다는_것.md --dry   # 발행 직전까지만

- 내 PC의 크롬을 띄웁니다. 비밀번호는 저장하지 않습니다.
- 처음 한 번은 열린 창에서 직접 로그인하세요. 로그인 상태는 ./chrome-profile 에 남아
  다음부터는 바로 글쓰기로 넘어갑니다. (자동 로그인은 네이버 캡차에 막힙니다)
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BLOG_ID = "mijin6729"
PROFILE_DIR = Path(__file__).parent / "chrome-profile"


def parse_post(path):
    text = Path(path).read_text(encoding="utf-8")
    title = re.search(r"^#\s+(.+)$", text, re.M).group(1).strip()
    tags = re.findall(r"#(\S+)", re.search(r"추천 태그\**:\s*(.+)", text).group(1)) if "추천 태그" in text else []
    # 헤더(제목~첫 구분선)는 본문에서 제외
    body = text.split("\n---\n", 1)[1] if "\n---\n" in text else text
    lines = []
    for line in body.strip().splitlines():
        line = line.rstrip()
        if line.strip() == "---":
            line = ""
        line = re.sub(r"^#{1,6}\s+", "", line)      # 소제목
        line = re.sub(r"^>\s?", "", line)           # 인용
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)  # 굵게
        lines.append(line)
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return title, body, tags[:30]


def click_if_visible(frame, selector, timeout=3000):
    try:
        frame.locator(selector).first.click(timeout=timeout)
    except PWTimeout:
        pass


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    title, body, tags = parse_post(sys.argv[1])
    dry = "--dry" in sys.argv
    print(f"제목: {title}\n태그: {tags}\n본문 {len(body)}자")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), channel="chrome", headless=False, viewport=None,
            args=["--start-maximized"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(f"https://blog.naver.com/{BLOG_ID}/postwrite")

        if "nid.naver.com" in page.url:
            print("크롬 창에서 로그인해 주세요. (최대 5분 대기)")
            page.wait_for_url(re.compile(r"blog\.naver\.com"), timeout=300_000)
            page.goto(f"https://blog.naver.com/{BLOG_ID}/postwrite")

        frame = page.frame_locator("#mainFrame")
        frame.locator(".se-content").first.wait_for(timeout=30_000)

        # 임시저장 복구 팝업 / 도움말 닫기
        click_if_visible(frame, ".se-popup-button-cancel")
        click_if_visible(frame, ".se-help-panel-close-button")

        # 제목
        frame.locator(".se-documentTitle .se-text-paragraph").first.click()
        page.keyboard.type(title)

        # 본문
        frame.locator(".se-component.se-text .se-text-paragraph").first.click()
        for i, line in enumerate(body.split("\n")):
            if i:
                page.keyboard.press("Enter")
            if line:
                page.keyboard.insert_text(line)
        page.wait_for_timeout(1000)

        # 발행 패널 열기
        frame.get_by_role("button", name="발행").first.click()
        page.wait_for_timeout(1000)

        tag_input = frame.locator("#tag-input")
        if tags and tag_input.count():
            for t in tags:
                tag_input.fill(t)
                page.keyboard.press("Enter")

        if dry:
            print("--dry: 발행 직전에서 멈췄습니다. 창을 확인한 뒤 Enter를 누르면 종료합니다.")
            input()
        else:
            # 패널 안의 최종 '발행' 버튼
            frame.locator("[class*='confirm_btn']").first.click()
            page.wait_for_url(re.compile(r"logNo=|/\d{9,}"), timeout=30_000)
            print("발행 완료:", page.url)
            page.wait_for_timeout(3000)
        ctx.close()


if __name__ == "__main__":
    main()
