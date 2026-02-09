"""User events consumer."""

import logging
from datetime import datetime

from shared.kafka.topics import EventType
from src.dal.user_dal import UserDAL

logger = logging.getLogger(__name__)


class UserConsumer:

    def __init__(self):
        self._dal = UserDAL()

    def _parse_ts(self, ts):
        if not ts:
            return None
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def handle_user_created(self, event: dict):
        data = event.get("data", {})
        contact = data.get("contact_info", {})
        profile = data.get("profile", {})

        self._dal.insert_user(
            user_id=event.get("entity_id"),
            email=contact.get("primary_email"),
            phone=contact.get("phone"),
            display_name=profile.get("display_name"),
            avatar=profile.get("avatar"),
            bio=profile.get("bio"),
            version=data.get("version", 1),
            deleted_at=self._parse_ts(data.get("deleted_at")),
            created_at=self._parse_ts(data.get("created_at")),
            updated_at=self._parse_ts(data.get("updated_at")),
            event_id=event.get("event_id"),
            event_timestamp=self._parse_ts(event.get("timestamp")),
        )
        logger.info(f"[USER_CREATED] {event['entity_id']}")

    def handle_user_deleted(self, event: dict):
        data = event.get("data", {})
        self._dal.soft_delete_user(
            user_id=data.get("user_id") or event.get("entity_id"),
            event_id=event.get("event_id"),
            event_timestamp=self._parse_ts(event.get("timestamp")),
        )
        logger.info(f"[USER_DELETED] {event['entity_id']}")

    def get_handlers(self) -> dict:
        return {
            EventType.USER_CREATED: self.handle_user_created,
            EventType.USER_DELETED: self.handle_user_deleted,
        }
