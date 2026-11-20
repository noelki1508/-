#!/usr/bin/env python3
"""네이버 블로그 임시저장 자동화.

포스트 파일(.md 또는 .txt)을 읽어서 네이버 블로그 글쓰기 화면(스마트에디터 ONE)에
제목과 본문을 입력하고 '저장'(임시저장) 버튼까지 눌러 줍니다. 발행은 하지 않으니
사진을 넣고 확인한 뒤 직접 발행하시면 돼요.

사용법:
    python naver_draft.py                      # ../포스트 폴더의 글을 전부 임시저장
    python naver_draft.py 파일1.md 파일2.txt    # 지정한 파일만
    python naver_draft.py --dry-run            # 네이버에 넣지 않고 읽은 내용만 확인

지원하는 파일 형식:
  .md  - '# 제목', '**카테고리**: ...', '**추천 태그**: #... ', '---' 다음부터 본문
  .txt - [제목] / [본문] / [해시태그] 구역으로 나눈 메모장 파일
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_POSTS_DIR = HERE.parent / "포스트"
PROFILE_DIR = HERE / "naver_profile"  # 로그인 정보가 저장되는 곳 (절대 공유·업로드 금지)
LOG_FILE = HERE / "저장기록.txt"

WRITE_URL = "https://blog.naver.com/GoBlogWrite.naver"
LOGIN_URL = "https://nid.naver.com/nidlogin.login"

# 스마트에디터 ONE 화면 요소. 네이버가 화면을 바꾸면 이 부분만 고치면 돼요.
SEL_TITLE = ".se-documentTitle .se-text-paragraph"
SEL_BODY = ".se-component.se-text .se-text-paragraph"
SEL_POPUP_CANCEL = ".se-popup-button-cancel"  # "작성 중인 글이 있습니다" 팝업의 취소
SEL_HELP_CLOSE = ".se-help-panel-close-button"
SEL_SAVE_BUTTON = "button[class*='save_btn']"
SAVE_BUTTON_TEXT = re.compile(r"^\s*저장")
SAVED_MESSAGE = re.compile(r"저장\s*(되었|됐|완료)")

LOGIN_WAIT_SEC = 300
EDITOR_WAIT_SEC = 40
LINE_PAUSE_MS = 40

Segment = tuple[str, bool]  # (글자, 굵게 여부)
Paragraph = list[Segment]  # 빈 리스트 = 빈 줄


@dataclass
class Post:
    path: Path
    title: str
    paragraphs: list[Paragraph]
    tags: list[str] = field(default_factory=list)
    category: str = ""

    def char_count(self) -> tuple[int, int]:
        text = "\n".join("".join(t for t, _ in p) for p in self.paragraphs)
        return len(text), len("".join(text.split()))


# ---------------------------------------------------------------- 파일 읽기

def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError(f"{path.name}: 글자 인코딩을 읽을 수 없어요. UTF-8로 저장해 주세요.")


def find_tags(lines: list[str]) -> list[str]:
    tags = re.findall(r"#[^\s#,]+", " ".join(lines))
    return list(dict.fromkeys(tags))


def tidy(paragraphs: list[Paragraph]) -> list[Paragraph]:
    """앞뒤 빈 줄을 없애고, 빈 줄은 최대 2줄까지만 남겨요."""
    out: list[Paragraph] = []
    blanks = 0
    for p in paragraphs:
        if p:
            blanks = 0
            out.append(p)
        elif out and blanks < 2:
            blanks += 1
            out.append(p)
    while out and not out[-1]:
        out.pop()
    return out


LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
ITALIC = re.compile(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)")


def inline_segments(text: str) -> Paragraph:
    text = LINK.sub(r"\1 (\2)", text)
    segments = []
    for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
        part = ITALIC.sub(r"\1", part)
        if part:
            segments.append((part, i % 2 == 1))
    return segments


def markdown_line(line: str) -> Paragraph:
    s = line.strip()
    if not s or re.fullmatch(r"-{3,}|\*{3,}|_{3,}", s):
        return []
    heading = re.match(r"#{1,6}\s+(.*)", s)
    if heading:  # 소제목은 굵게
        return [("".join(t for t, _ in inline_segments(heading.group(1))), True)]
    s = re.sub(r"^>\s?", "", s)
    s = re.sub(r"^[-*+]\s+", "• ", s)
    return inline_segments(s)


META = re.compile(r"\*\*(.+?)\*\*\s*[:：]\s*(.*)")


def parse_markdown(path: Path, text: str) -> Post:
    lines = text.splitlines()
    title, category, tags = "", "", []
    body_start = len(lines)
    for i, line in enumerate(lines):
        s = line.strip()
        if not title:
            if s.startswith("# "):
                title = s[2:].strip()
            continue
        meta = META.fullmatch(s)
        if meta:
            key, value = meta.groups()
            if "카테고리" in key:
                category = value.strip()
            elif "태그" in key:
                tags = find_tags([value])
            continue
        if re.fullmatch(r"-{3,}", s):  # 머리말 끝
            body_start = i + 1
            break
        if s:  # 머리말 없이 바로 본문이 시작되는 경우
            body_start = i
            break
    paragraphs = tidy([markdown_line(l) for l in lines[body_start:]])
    return Post(path, title, paragraphs, tags, category)


SECTION = re.compile(r"\s*\[(제목|본문|해시태그|태그)\]\s*")


def parse_txt(path: Path, text: str) -> Post:
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        m = SECTION.fullmatch(line)
        if m:
            current = m.group(1)
            sections.setdefault(current, [])
        elif current:
            sections[current].append(line)
    title = " ".join(l.strip() for l in sections.get("제목", []) if l.strip())
    body = sections.get("본문", [])
    paragraphs = tidy([[(l.rstrip(), False)] if l.strip() else [] for l in body])
    tags = find_tags(sections.get("해시태그", []) + sections.get("태그", []))
    return Post(path, title, paragraphs, tags)


def load_post(path: Path) -> Post:
    text = read_text(path)
    post = parse_markdown(path, text) if path.suffix.lower() == ".md" else parse_txt(path, text)
    if not post.title:
        raise ValueError(f"{path.name}: 제목을 찾지 못했어요.")
    if not post.paragraphs:
        raise ValueError(f"{path.name}: 본문을 찾지 못했어요.")
    return post


def collect_files(args_paths: list[str]) -> list[Path]:
    targets = [Path(p) for p in args_paths] or [DEFAULT_POSTS_DIR]
    files: list[Path] = []
    for target in targets:
        if target.is_dir():
            files += sorted(p for p in target.iterdir() if p.suffix.lower() in (".md", ".txt"))
        elif target.is_file():
            files.append(target)
        else:
            print(f"⚠️  찾을 수 없어요: {target}")
    return files


def load_log() -> set[str]:
    if not LOG_FILE.exists():
        return set()
    return {line.split("\t")[-1] for line in read_text(LOG_FILE).splitlines() if line.strip()}


def append_log(post: Post) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M')}\t{post.path.name}\n")


# ---------------------------------------------------------------- 브라우저

def launch(p):
    PROFILE_DIR.mkdir(exist_ok=True)
    errors = []
    for channel in ("chrome", "msedge", None):  # 크롬 → 엣지 → 플레이라이트 기본 브라우저
        options = dict(user_data_dir=str(PROFILE_DIR), headless=False, no_viewport=True,
                       args=["--start-maximized"])
        if channel:
            options["channel"] = channel
        try:
            return p.chromium.launch_persistent_context(**options)
        except Exception as e:  # 설치 안 된 브라우저는 건너뜀
            errors.append(f"  - {channel or 'chromium'}: {str(e).splitlines()[0]}")
    sys.exit("브라우저를 열 수 없어요. 크롬을 설치하거나 "
             "'python -m playwright install chromium'을 실행해 주세요.\n" + "\n".join(errors))


def is_logged_in(context) -> bool:
    return any(c["name"] == "NID_AUT" for c in context.cookies("https://www.naver.com"))


def ensure_login(page) -> None:
    if is_logged_in(page.context):
        return
    page.goto(LOGIN_URL)
    print("👉 열린 브라우저 창에서 네이버에 로그인해 주세요.")
    print("   ('로그인 상태 유지'를 체크하면 다음부터는 로그인 없이 바로 진행돼요.)")
    deadline = time.time() + LOGIN_WAIT_SEC
    while time.time() < deadline:
        if is_logged_in(page.context):
            print("✅ 로그인 확인!")
            return
        page.wait_for_timeout(1000)
    sys.exit("로그인을 기다리다 시간이 지났어요. 다시 실행해 주세요.")


def find_editor_frame(page):
    deadline = time.time() + EDITOR_WAIT_SEC
    while time.time() < deadline:
        for frame in page.frames:
            try:
                if frame.locator(SEL_TITLE).count():
                    return frame
            except Exception:  # 로딩 중에 사라진 프레임
                pass
        page.wait_for_timeout(500)
    raise RuntimeError("글쓰기 화면을 찾지 못했어요. 네이버 화면 구성이 바뀌었을 수 있어요.")


def dismiss_popups(page, frame) -> None:
    page.wait_for_timeout(1500)  # 팝업이 뜰 시간
    for selector, message in ((SEL_POPUP_CANCEL, "이전에 작성 중이던 글 이어쓰기 팝업을 닫았어요."),
                              (SEL_HELP_CLOSE, None)):
        button = frame.locator(selector).first
        if button.count() and button.is_visible():
            button.click()
            if message:
                print(f"   ℹ️  {message}")
            page.wait_for_timeout(500)


def open_editor(page, blog_id: str | None):
    url = f"https://blog.naver.com/{blog_id}?Redirect=Write" if blog_id else WRITE_URL
    page.goto(url, wait_until="domcontentloaded")
    frame = find_editor_frame(page)
    dismiss_popups(page, frame)
    return frame


def type_paragraphs(page, paragraphs: list[Paragraph], bold: bool) -> None:
    for i, segments in enumerate(paragraphs):
        for text, is_bold in segments:
            toggle = bold and is_bold
            if toggle:
                page.keyboard.press("ControlOrMeta+b")
            page.keyboard.insert_text(text)
            if toggle:
                page.keyboard.press("ControlOrMeta+b")
        if i < len(paragraphs) - 1:
            page.keyboard.press("Enter")
        page.wait_for_timeout(LINE_PAUSE_MS)


def write_post(page, frame, post: Post, bold: bool, with_tags: bool) -> None:
    frame.locator(SEL_TITLE).first.click()
    page.keyboard.insert_text(post.title)

    paragraphs = list(post.paragraphs)
    body_text = " ".join(t for p in paragraphs for t, _ in p)
    tags = [t for t in post.tags if t not in body_text]
    if with_tags and tags:  # 본문 맨 아래 해시태그 (발행할 때 태그로 등록돼요)
        paragraphs += [[], [(" ".join(tags), False)]]

    frame.locator(SEL_BODY).first.click()
    type_paragraphs(page, paragraphs, bold)

    typed_title = frame.locator(SEL_TITLE).first.inner_text().strip()
    if post.title not in typed_title:
        print(f"   ⚠️  제목이 제대로 들어갔는지 확인해 주세요. (화면: {typed_title!r})")


def find_save_button(page, frame):
    for scope in (frame, page.main_frame):
        for button in (scope.locator(SEL_SAVE_BUTTON).first,
                       scope.get_by_role("button", name=SAVE_BUTTON_TEXT).first):
            try:
                if button.count() and button.is_visible():
                    return button
            except Exception:
                pass
    return None


def save_draft(page, frame) -> bool:
    button = find_save_button(page, frame)
    if button is None:
        raise RuntimeError("'저장' 버튼을 찾지 못했어요.")
    button.click()
    deadline = time.time() + 8
    while time.time() < deadline:
        for scope in (frame, page.main_frame):
            try:
                if scope.get_by_text(SAVED_MESSAGE).first.is_visible():
                    return True
            except Exception:
                pass
        page.wait_for_timeout(300)
    return False


# ---------------------------------------------------------------- 실행

def preview(post: Post) -> None:
    with_space, without_space = post.char_count()
    print(f"📄 {post.path.name}")
    print(f"   제목: {post.title}")
    if post.category:
        print(f"   카테고리: {post.category} (발행할 때 직접 선택해 주세요)")
    print(f"   태그 {len(post.tags)}개: {' '.join(post.tags)}")
    print(f"   본문: {len(post.paragraphs)}줄, 공백 포함 {with_space}자 / 공백 제외 {without_space}자")


def main() -> None:
    parser = argparse.ArgumentParser(description="네이버 블로그 임시저장 자동화")
    parser.add_argument("paths", nargs="*", help="포스트 파일이나 폴더 (기본: ../포스트)")
    parser.add_argument("--dry-run", action="store_true", help="네이버에 넣지 않고 읽은 내용만 보여주기")
    parser.add_argument("--blog-id", help="네이버 블로그 아이디 (자동으로 못 찾을 때만)")
    parser.add_argument("--force", action="store_true", help="이미 임시저장한 파일도 다시 저장")
    parser.add_argument("--plain", action="store_true", help="굵은 글씨 없이 입력")
    parser.add_argument("--no-tags", action="store_true", help="본문 끝에 해시태그를 넣지 않기")
    args = parser.parse_args()

    posts = []
    for path in collect_files(args.paths):
        try:
            posts.append(load_post(path))
        except ValueError as e:
            print(f"⚠️  건너뜀 - {e}")

    if args.dry_run:
        for post in posts:
            preview(post)
        return

    done = set() if args.force else load_log()
    skipped = [p for p in posts if p.path.name in done]
    posts = [p for p in posts if p.path.name not in done]
    for post in skipped:
        print(f"⏭️  이미 저장함: {post.path.name} (다시 저장하려면 --force)")
    if not posts:
        print("임시저장할 글이 없어요.")
        return

    from playwright.sync_api import sync_playwright

    results = []
    with sync_playwright() as p:
        context = launch(p)
        page = context.pages[0] if context.pages else context.new_page()
        page.on("dialog", lambda dialog: dialog.accept())
        ensure_login(page)

        for post in posts:
            print()
            preview(post)
            try:
                frame = open_editor(page, args.blog_id)
                write_post(page, frame, post, bold=not args.plain, with_tags=not args.no_tags)
                if save_draft(page, frame):
                    append_log(post)
                    results.append(f"✅ {post.title}")
                else:
                    results.append(f"❓ {post.title} - 저장 버튼은 눌렀는데 완료 메시지를 못 봤어요. 임시저장 목록에서 확인해 주세요.")
            except Exception as e:
                results.append(f"❌ {post.title} - {e}")
            print("   " + results[-1])

        print("\n===== 결과 =====")
        print("\n".join(results))
        input("\n브라우저에서 임시저장 글을 확인한 뒤 엔터를 누르면 창이 닫혀요...")
        context.close()


if __name__ == "__main__":
    main()
