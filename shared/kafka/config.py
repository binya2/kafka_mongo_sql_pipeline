"""Kafka configuration for producer and consumer."""

import os

from pydantic import BaseModel, Field


class KafkaConfig(BaseModel):
    """Kafka configuration from environment variables."""

    bootstrap_servers: str = Field(default="localhost:9092")
    client_id: str = Field(default="service")

    @classmethod
    def from_env(cls, client_id: str = "service") -> "KafkaConfig":
        """Create config from environment variables."""
        # TODO: Read KAFKA_BOOTSTRAP_SERVERS and KAFKA_CLIENT_ID from environment
        pass

    def to_producer_config(self) -> dict:
        """Return config dict for confluent_kafka.Producer."""
        # TODO: Return producer configuration dictionary
        pass

    def to_consumer_config(self, group_id: str) -> dict:
        """Return config dict for confluent_kafka.Consumer."""
        # TODO: Return consumer configuration dictionary
        pass
