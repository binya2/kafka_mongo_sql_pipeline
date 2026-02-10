# """Kafka configuration for producer and consumer."""
import os

from pydantic import Field
from pydantic_settings import BaseSettings


class KafkaConfig(BaseSettings):
    bootstrap_servers: str = Field(default="localhost:9092", validation_alias="KAFKA_BOOTSTRAP_SERVERS")
    client_id: str = Field(default="mysql-service", validation_alias="KAFKA_CLIENT_ID")


kafka_config = KafkaConfig()


def to_consumer_config(config, group_id: str) -> dict:
    return {
        "bootstrap.servers": config.bootstrap_servers,
        "group.id": group_id,
        "client.id": config.client_id,
        "auto.offset.reset": os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest"),
        "enable.auto.commit": True,
        "auto.commit.interval.ms": 5000,
    }
