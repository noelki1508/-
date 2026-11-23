"""
Threads poster using instagrapi Instagram session.
"""
import json
import uuid
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SESSION_FILE = Path(__file__).parent / "ig_session.json"


class ThreadsClient:
    def __init__(self):
        self._cl = None

    def login(self, username: str, password: str):
        from instagrapi import Client
        cl = Client()

        if SESSION_FILE.exists():
            try:
                cl.load_settings(str(SESSION_FILE))
                cl.login(username, password)
                logger.info("Logged in using saved session")
            except Exception as e:
                logger.warning(f"Session reload failed ({e}), fresh login")
                cl = Client()
                cl.login(username, password)
        else:
            cl.login(username, password)
            logger.info("Logged in fresh")

        cl.dump_settings(str(SESSION_FILE))
        self._cl = cl
        self.user_id = cl.user_id
        logger.info(f"Logged in as user_id={self.user_id}")

    def post_text(self, text: str) -> dict:
        """Post a text-only Threads post."""
        assert self._cl, "Call login() first"
        data = self._cl.with_action_data({
            "text_post_app_info": json.dumps({"reply_control": 0}),
            "caption": text,
            "source_type": "4",
            "publish_mode": "text_post",
        })
        result = self._cl.private.post("v1/media/configure_text_only_post/", data=data)
        result.raise_for_status()
        resp = result.json()
        logger.info(f"Text post result: {resp.get('status')}")
        return resp

    def post_image(self, image_path: str, caption: str) -> dict:
        """Upload a single image post to Instagram feed (shows on Threads)."""
        assert self._cl, "Call login() first"
        from instagrapi.types import Location
        result = self._cl.photo_upload(
            path=image_path,
            caption=caption,
        )
        logger.info(f"Image post pk={result.pk}")
        return {"status": "ok", "pk": str(result.pk)}

    def post_carousel(self, image_paths: list[str], caption: str) -> dict:
        """Upload multiple images as a carousel post."""
        assert self._cl, "Call login() first"
        result = self._cl.album_upload(
            paths=image_paths,
            caption=caption,
        )
        logger.info(f"Carousel post pk={result.pk}")
        return {"status": "ok", "pk": str(result.pk)}
