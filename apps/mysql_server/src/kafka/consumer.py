"""Kafka consumer for subscribing to domain events."""

import json
import logging
import signal
from typing import Callable, Optional

from confluent_kafka import Consumer, KafkaError, KafkaException

from shared.kafka.config import KafkaConfig
from shared.kafka.topics import Topic


logger = logging.getLogger(__name__)


class KafkaConsumer:
    """Kafka consumer for subscribing to domain events."""

    def __init__(self, group_id: str = "mysql-analytics-service"):
        self._config = KafkaConfig.from_env(client_id="mysql-service")
        self._consumer = Consumer(self._config.to_consumer_config(group_id))
        self._handlers: dict[str, Callable] = {}
        self._running = False

        logger.info(f"Kafka consumer initialized: {self._config.bootstrap_servers}")

    def register_handler(self, event_type: str, handler: Callable) -> None:
        """Register a handler for a specific event type."""
        self._handlers[event_type] = handler
        logger.info(f"Registered handler for: {event_type}")

    def subscribe(self, topics: Optional[list[str]] = None) -> None:
        """Subscribe to topics."""
        topics = topics or Topic.all()
        self._consumer.subscribe(topics)
        logger.info(f"Subscribed to topics: {topics}")

    def _process_message(self, msg) -> None:
        """Process a single message."""
        try:
            value = json.loads(msg.value().decode("utf-8"))
            event_type = value.get("event_type")

            if not event_type:
                logger.warning(f"Message missing event_type")
                return

            handler = self._handlers.get(event_type)
            if handler:
                handler(value)
                logger.info(f"Processed: {event_type}")
            else:
                logger.debug(f"No handler for: {event_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def start(self) -> None:
        """Start consuming messages."""
        self._running = True
        self._setup_signal_handlers()

        logger.info("Consumer started, waiting for messages...")

        try:
            while self._running:
                msg = self._consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    elif msg.error().code() == KafkaError.UNKNOWN_TOPIC_OR_PART:
                        logger.warning(f"Unknown topic or partition, waiting...")
                        continue
                    else:
                        logger.error(f"Kafka error: {msg.error()}")
                        continue
                else:
                    self._process_message(msg)

        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the consumer."""
        self._running = False
        self._consumer.close()
        logger.info("Consumer stopped")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def handler(signum, frame):
            self._running = False

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)
