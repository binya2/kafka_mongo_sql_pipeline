"""Kafka configuration for producer and consumer."""

import os

from pydantic import BaseModel, Field


class KafkaConfig(BaseModel):
    """Kafka configuration from environment variables."""

    bootstrap_servers: str = Field(default="localhost:9092")
    client_id: str = Field(default="service")

    @classmethod
    def from_env(cls, client_id: str = "service") -> "KafkaConfig":
        return cls(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            client_id=os.getenv("KAFKA_CLIENT_ID", client_id),
        )

    def to_producer_config(self) -> dict:
        return {
            "bootstrap.servers": self.bootstrap_servers,
            "client.id": self.client_id,
        }

    def to_consumer_config(self, group_id: str) -> dict:
        return {
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": group_id,
            "client.id": self.client_id,
            "auto.offset.reset": os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest"),
            "enable.auto.commit": True,
            "auto.commit.interval.ms": 5000,
        }
