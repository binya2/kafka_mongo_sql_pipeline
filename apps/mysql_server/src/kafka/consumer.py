"""Kafka consumer for subscribing to domain events."""

import json
import logging
import signal
from typing import Callable, Optional

from confluent_kafka import Consumer, KafkaError

from shared.kafka.config import KafkaConfig
from shared.kafka.topics import Topic


logger = logging.getLogger(__name__)


class KafkaConsumer:
    """Kafka consumer for subscribing to domain events."""

    def __init__(self, group_id: str = "mysql-analytics-service"):
        # TODO: Initialize config, create Consumer, set up handlers dict and running flag
        pass

    def register_handler(self, event_type: str, handler: Callable) -> None:
        """Register a handler for a specific event type."""
        # TODO: Store handler in handlers dict
        pass

    def subscribe(self, topics: Optional[list[str]] = None) -> None:
        """Subscribe to topics."""
        # TODO: Subscribe consumer to topics (default to Topic.all())
        pass

    def _process_message(self, msg) -> None:
        """Process a single message."""
        # TODO: JSON decode message, extract event_type, lookup and call handler
        pass

    def start(self) -> None:
        """Start consuming messages."""
        # TODO: Poll loop with timeout=1.0, handle errors (_PARTITION_EOF, UNKNOWN_TOPIC_OR_PART)
        pass

    def stop(self) -> None:
        """Stop the consumer."""
        # TODO: Set running=False and close consumer
        pass

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        # TODO: Handle SIGINT and SIGTERM for graceful shutdown
        pass
