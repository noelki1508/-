#!/usr/bin/env python3.13
"""
블랙스톤 일일 자동 포스팅 스크립트
매일 8AM KST에 실행됨 (cron: 0 23 * * *)

사용법:
  python3.13 daily_post.py              # 전체 실행 (텍스트 + 이미지)
  python3.13 daily_post.py --text-only  # 텍스트만
  python3.13 daily_post.py --dry-run    # 실제 게시 없이 테스트
"""
import argparse
import logging
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "post.log"),
    ],
)
logger = logging.getLogger(__name__)

THREADS_USERNAME = os.environ.get("THREADS_USERNAME", "blk_writer")
THREADS_PASSWORD = os.environ.get("THREADS_PASSWORD", "")
OUTPUT_DIR = Path(__file__).parent / "output"


def run(text_only: bool = False, dry_run: bool = False):
    logger.info(f"=== 블랙스톤 일일 포스팅 시작 {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")

    # 1. 콘텐츠 생성
    from content_generator import generate_content
    logger.info("콘텐츠 생성 중...")
    content = generate_content()
    text_post = content["text_post"]
    caption = content["caption"]
    slides = content["slides"]
    logger.info(f"텍스트 포스트: {text_post[:50]}...")

    if dry_run:
        logger.info("[DRY RUN] 텍스트 포스트:\n" + text_post)
        logger.info("[DRY RUN] 캡션: " + caption)
        logger.info("[DRY RUN] 슬라이드 수: " + str(len(slides)))
        return

    if not THREADS_PASSWORD:
        logger.error("THREADS_PASSWORD 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    # 2. Threads 클라이언트 로그인
    from threads_client import ThreadsClient
    client = ThreadsClient()
    logger.info("Threads 로그인 중...")
    client.login(THREADS_USERNAME, THREADS_PASSWORD)

    # 3. 텍스트 포스트 게시
    logger.info("텍스트 포스트 게시 중...")
    text_result = client.post_text(text_post)
    logger.info(f"텍스트 포스트 완료: {text_result.get('status')}")

    if text_only:
        logger.info("텍스트 전용 모드 완료")
        return

    # 4. 이미지 렌더링
    logger.info("이미지 렌더링 중...")
    from html_builder import build_slide_html
    from renderer import render_slides

    OUTPUT_DIR.mkdir(exist_ok=True)
    today_str = datetime.now().strftime("%Y%m%d")
    html_path = OUTPUT_DIR / f"slides_{today_str}.html"
    build_slide_html(slides, str(html_path))

    image_paths = render_slides(
        html_path=str(html_path),
        out_dir=str(OUTPUT_DIR),
        prefix=f"post_{today_str}",
    )
    logger.info(f"이미지 {len(image_paths)}장 렌더링 완료")

    # 5. 이미지 카드 포스트 게시 (캐러셀)
    logger.info("이미지 카드 포스트 게시 중...")
    if len(image_paths) == 1:
        img_result = client.post_image(image_paths[0], caption)
    else:
        img_result = client.post_carousel(image_paths, caption)
    logger.info(f"이미지 포스트 완료: {img_result.get('status')}")

    logger.info("=== 포스팅 완료 ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--text-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(text_only=args.text_only, dry_run=args.dry_run)
