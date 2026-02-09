"""Supplier events consumer."""

import logging
from datetime import datetime

from shared.kafka.topics import EventType
from src.dal.supplier_dal import SupplierDAL

logger = logging.getLogger(__name__)


class SupplierConsumer:

    def __init__(self):
        self._dal = SupplierDAL()

    def _parse_ts(self, ts):
        if not ts:
            return None
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def handle_supplier_created(self, event: dict):
        data = event.get("data", {})
        contact = data.get("contact_info", {})
        company = data.get("company_info", {})
        address = company.get("business_address", {})
        biz = data.get("business_info", {})

        self._dal.insert_supplier(
            supplier_id=event.get("entity_id"),
            email=contact.get("primary_email"),
            primary_phone=contact.get("primary_phone"),
            contact_person_name=contact.get("contact_person_name"),
            contact_person_title=contact.get("contact_person_title"),
            contact_person_email=contact.get("contact_person_email"),
            contact_person_phone=contact.get("contact_person_phone"),
            legal_name=company.get("legal_name"),
            dba_name=company.get("dba_name"),
            street_address_1=address.get("street_address_1"),
            street_address_2=address.get("street_address_2"),
            city=address.get("city"),
            state=address.get("state"),
            zip_code=address.get("zip_code"),
            country=address.get("country"),
            support_email=biz.get("support_email"),
            support_phone=biz.get("support_phone"),
            facebook_url=biz.get("facebook_url"),
            instagram_handle=biz.get("instagram_handle"),
            twitter_handle=biz.get("twitter_handle"),
            linkedin_url=biz.get("linkedin_url"),
            timezone=biz.get("timezone"),
            created_at=self._parse_ts(data.get("created_at")),
            updated_at=self._parse_ts(data.get("updated_at")),
            event_id=event.get("event_id"),
            event_timestamp=self._parse_ts(event.get("timestamp")),
        )
        logger.info(f"[SUPPLIER_CREATED] {event['entity_id']}")

    def handle_supplier_deleted(self, event: dict):
        data = event.get("data", {})
        self._dal.delete_supplier(
            supplier_id=data.get("supplier_id") or event.get("entity_id"),
        )
        logger.info(f"[SUPPLIER_DELETED] {event['entity_id']}")

    def get_handlers(self) -> dict:
        return {
            EventType.SUPPLIER_CREATED: self.handle_supplier_created,
            EventType.SUPPLIER_DELETED: self.handle_supplier_deleted,
        }
