"""Kafka consumer for subscribing to domain events."""
import json
import logging
import signal
from typing import Callable, Optional

from confluent_kafka import Consumer

from shared.kafka.config import kafka_config, to_consumer_config
from shared.kafka.topics import Topic

logger = logging.getLogger(__name__)


class KafkaConsumer:
    """Kafka consumer for subscribing to domain events."""

    def __init__(self, group_id: str = "mysql-analytics-service"):
        """Initialize Kafka consumer."""
        self._config = kafka_config
        self._consumer = Consumer(to_consumer_config(self._config, group_id))
        self._handlers = {}
        self._running = False
        logger.info(f"Kafka Consumer {group_id} initialized")

    def register_handler(self, event_type: str, handler: Callable) -> None:
        """Register a handler for a specific event type."""
        self._handlers[event_type] = handler
        logger.info(f"Registered handler for {event_type}")

    def subscribe(self, topics: Optional[list[str]] = None) -> None:
        """Subscribe to topics."""
        if topics is None:
            topics = Topic.all()
        self._consumer.subscribe(topics)
        logger.info(f"Subscribed to topics: {topics}")

    def _process_message(self, msg) -> None:
        """Process a single message."""
        try:
            value = json.loads(msg.value().decode("utf-8"))
            event_type = value.get("event_type")
            if event_type not in self._handlers:
                logger.warning(f"Received message with unregistered event type: {event_type}")
                return
            handler = self._handlers.get(event_type)
            if handler:
                handler(value)
            else:
                logger.warning(f"No handler registered for event type: {event_type}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def start(self) -> None:
        """Start consuming messages."""
        self._running = True
        logger.info("Kafka Consumer started")
        self._setup_signal_handlers()
        try:
            while self._running:
                msg = self._consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error(f"Consumer error: {msg.error()}")
                    continue
                self._process_message(msg)
        except Exception as e:
            logger.error(f"Error in consumer loop: {e}")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the consumer."""
        self._running = False
        self._consumer.close()
        logger.info("Kafka Consumer stopped")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, shutting down consumer...")
            self.stop()
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

