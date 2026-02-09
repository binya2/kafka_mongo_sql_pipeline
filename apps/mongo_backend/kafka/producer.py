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
        self._config = config or KafkaConfig.from_env()
        self._producer = Producer(self._config.to_producer_config())
        logger.info(f"Kafka producer initialized: {self._config.bootstrap_servers}")

    def _delivery_callback(self, err, msg) -> None:
        """Callback for message delivery reports."""
        if err:
            logger.error(f"Delivery failed: {err}")
        else:
            logger.debug(f"Delivered to {msg.topic()}[{msg.partition()}]")

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
        self._producer.produce(
            topic=topic,
            key=key.encode("utf-8") if key else None,
            value=json.dumps(value).encode("utf-8"),
            callback=self._delivery_callback,
        )
        self._producer.poll(0)

    def flush(self, timeout: float = 10.0) -> int:
        """
        Flush all pending messages.

        Args:
            timeout: Max time to wait in seconds

        Returns:
            Number of messages still in queue (0 if all delivered)
        """
        return self._producer.flush(timeout)

    def emit(
        self,
        topic: str,
        action: str,
        entity_id: str,
        data: dict[str, Any],
    ) -> None:
        """
        Emit a domain event to Kafka.

        Args:
            topic: Target topic (e.g., Topic.USER)
            action: Event action (e.g., "registered", "login")
            entity_id: Primary entity ID (used as partition key)
            data: Event payload data
        """
        event = {
            "event_type": f"{topic}.{action}",
            "event_id": str(uuid.uuid4()),
            "timestamp": utc_now().isoformat(),
            "entity_id": entity_id,
            "data": data,
        }
        self.send(topic=topic, key=entity_id, value=event)


# Singleton instance
kafka_producer: Optional[KafkaProducer] = None


def get_kafka_producer() -> KafkaProducer:
    """Get or create the Kafka producer singleton."""
    global kafka_producer
    if kafka_producer is None:
        kafka_producer = KafkaProducer()
    return kafka_producer
