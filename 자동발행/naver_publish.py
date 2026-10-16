"""
네이버 블로그 자동발행 (Chrome + Playwright)

사용법:
    pip install playwright
    python naver_publish.py ../포스트/001_매일_글을_쓴다는_것.md --blog-id 내블로그아이디

- 처음 실행 시 크롬 창이 뜨면 네이버에 직접 로그인하세요 (로그인 정보는 ./chrome_profile 에 저장되어 다음부터 생략).
- --draft 를 주면 발행 대신 임시저장만 합니다 (테스트용 추천).
"""
import argparse
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

PROFILE_DIR = Path(__file__).parent / "chrome_profile"


def parse_post(path: Path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title = lines[0].lstrip("# ").strip()
    tags_match = re.search(r"\*\*추천 태그\*\*:\s*(.+)", text)
    tags = re.findall(r"#(\S+)", tags_match.group(1)) if tags_match else []

    # 메타 정보(카테고리/태그) 블록 이후를 본문으로 사용
    body_start = 1
    for i, line in enumerate(lines):
        if line.strip() == "---":
            body_start = i + 1
            break
    body = []
    for line in lines[body_start:]:
        s = line.strip()
        if s == "---":
            continue  # 구분선은 생략
        s = re.sub(r"^#{1,6}\s*", "", s)   # 소제목 기호 제거
        s = re.sub(r"^>\s*", "", s)        # 인용 기호 제거
        s = s.replace("**", "")            # 굵게 기호 제거
        body.append(s)
    # 연속 빈 줄 정리
    cleaned = []
    for s in body:
        if s == "" and cleaned and cleaned[-1] == "":
            continue
        cleaned.append(s)
    return title, "\n".join(cleaned).strip(), tags[:10]


def close_popups(frame):
    for sel in [".se-popup-button-cancel",       # '작성 중인 글이 있습니다' → 취소
                ".se-help-panel-close-button"]:   # 도움말 패널 닫기
        try:
            frame.locator(sel).first.click(timeout=2000)
        except PWTimeout:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("post", type=Path)
    ap.add_argument("--blog-id", required=True)
    ap.add_argument("--draft", action="store_true", help="발행하지 않고 임시저장만")
    args = ap.parse_args()

    title, body, tags = parse_post(args.post)
    print(f"제목: {title}\n태그: {tags}\n본문 {len(body)}자")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), channel="chrome", headless=False,
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        page.goto("https://nid.naver.com/nidlogin.login")
        if "nidlogin" in page.url:
            print(">> 크롬 창에서 네이버 로그인을 완료하세요 (최대 5분 대기)")
            page.wait_for_url(lambda u: "nidlogin" not in u, timeout=300_000)

        page.goto(f"https://blog.naver.com/{args.blog_id}?Redirect=Write")
        frame = page.frame_locator("#mainFrame")
        frame.locator(".se-documentTitle").wait_for(timeout=30_000)
        close_popups(frame)

        # 제목
        frame.locator(".se-documentTitle .se-text-paragraph").first.click()
        page.keyboard.insert_text(title)

        # 본문
        frame.locator(".se-component.se-text .se-text-paragraph").first.click()
        for i, line in enumerate(body.split("\n")):
            if line:
                page.keyboard.insert_text(line)
            page.keyboard.press("Enter")
            page.wait_for_timeout(30)

        if args.draft:
            frame.locator("button[class*='save_btn']").first.click()
            print("임시저장 완료")
        else:
            frame.locator("button[class*='publish_btn']").first.click()
            page.wait_for_timeout(1000)
            if tags:
                tag_input = frame.locator("input[class*='tag_input'], #tag-input").first
                for t in tags:
                    tag_input.click()
                    page.keyboard.insert_text(t)
                    page.keyboard.press("Enter")
            frame.locator("button[class*='confirm_btn']").first.click()
            page.wait_for_url(re.compile(r"(PostView|logNo=|/\d{9,})"), timeout=30_000)
            print(f"발행 완료: {page.url}")

        page.wait_for_timeout(3000)
        ctx.close()


if __name__ == "__main__":
    sys.exit(main())
