"""Post events consumer."""

import json
import logging
from datetime import datetime

from shared.kafka.topics import EventType
from src.dal.post_dal import PostDAL

logger = logging.getLogger(__name__)


class PostConsumer:

    def __init__(self):
        self._dal = PostDAL()

    def _parse_ts(self, ts):
        if not ts:
            return None
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def _handle_post_upsert(self, event: dict):
        """Shared handler for created and published (both send full model)."""
        data = event.get("data", {})
        author = data.get("author", {})
        stats = data.get("stats", {})
        link = data.get("link_preview") or {}
        media = data.get("media", [])

        self._dal.upsert_post(
            post_id=event.get("entity_id"),
            post_type=data.get("post_type"),
            author_user_id=author.get("user_id"),
            author_display_name=author.get("display_name"),
            author_avatar=author.get("avatar"),
            author_type=author.get("author_type"),
            text_content=data.get("text_content"),
            media_json=json.dumps(media) if media else None,
            link_url=link.get("url"),
            link_title=link.get("title"),
            link_description=link.get("description"),
            link_image=link.get("image"),
            link_site_name=link.get("site_name"),
            view_count=stats.get("view_count", 0),
            like_count=stats.get("like_count", 0),
            comment_count=stats.get("comment_count", 0),
            share_count=stats.get("share_count", 0),
            save_count=stats.get("save_count", 0),
            engagement_rate=stats.get("engagement_rate", 0.0),
            deleted_at=self._parse_ts(data.get("deleted_at")),
            published_at=self._parse_ts(data.get("published_at")),
            created_at=self._parse_ts(data.get("created_at")),
            updated_at=self._parse_ts(data.get("updated_at")),
            event_id=event.get("event_id"),
            event_timestamp=self._parse_ts(event.get("timestamp")),
        )

    def handle_post_created(self, event: dict):
        self._handle_post_upsert(event)
        logger.info(f"[POST_CREATED] {event['entity_id']}")

    def handle_post_published(self, event: dict):
        self._handle_post_upsert(event)
        logger.info(f"[POST_PUBLISHED] {event['entity_id']}")

    def handle_post_deleted(self, event: dict):
        data = event.get("data", {})
        self._dal.soft_delete_post(
            post_id=data.get("post_id") or event.get("entity_id"),
            event_id=event.get("event_id"),
            event_timestamp=self._parse_ts(event.get("timestamp")),
        )
        logger.info(f"[POST_DELETED] {event['entity_id']}")

    def get_handlers(self) -> dict:
        return {
            EventType.POST_CREATED: self.handle_post_created,
            EventType.POST_DELETED: self.handle_post_deleted,
            EventType.POST_PUBLISHED: self.handle_post_published,
        }
