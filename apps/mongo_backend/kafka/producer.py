"""Kafka producer for sending events to topics."""

import json
import logging
import uuid
from typing import Any, Optional

from confluent_kafka import Producer

from shared.kafka.config import KafkaConfig
from utils.datetime_utils import utc_now


logger = logging.getLogger(__name__)


class KafkaProducer:
    """
    Kafka producer for sending messages to topics.

    Usage:
        producer = KafkaProducer()
        producer.send("user", key="user_123", value={"event": "created", ...})
        producer.flush()
    """

    def __init__(self, config: Optional[KafkaConfig] = None):
        # TODO: Initialize config (use from_env if none provided) and create Producer
        pass

    def _delivery_callback(self, err, msg) -> None:
        """Callback for message delivery reports."""
        # TODO: Log error on failure, log debug on success
        pass

    def send(
        self,
        topic: str,
        value: dict[str, Any],
        key: Optional[str] = None,
    ) -> None:
        """
        Send a message to a Kafka topic.

        Args:
            topic: Target topic name
            value: Message payload (will be JSON serialized)
            key: Optional partition key
        """
        # TODO: Serialize value to JSON, encode key to utf-8, call producer.produce()
        pass

    def flush(self, timeout: float = 10.0) -> int:
        """
        Flush all pending messages.

        Args:
            timeout: Max time to wait in seconds

        Returns:
            Number of messages still in queue (0 if all delivered)
        """
        # TODO: Flush the producer
        pass

    def emit(
        self,
        event_type: str,
        entity_id: str,
        data: dict[str, Any],
    ) -> None:
        """
        Emit a domain event to Kafka.

        Args:
            event_type: Event type constant (e.g., EventType.USER_CREATED)
            entity_id: Primary entity ID (used as partition key)
            data: Event payload data
        """
        # TODO: Build event envelope and send to the correct topic
        pass


# Singleton instance
kafka_producer: Optional[KafkaProducer] = None


def get_kafka_producer() -> KafkaProducer:
    """Get or create the Kafka producer singleton."""
    # TODO: Implement singleton pattern
    pass
