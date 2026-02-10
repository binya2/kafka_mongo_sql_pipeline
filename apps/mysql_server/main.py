"""MySQL Analytics Service - Kafka Consumer Entry Point."""

import logging

from src.db.connection import get_database
from src.kafka.consumer import KafkaConsumer
from src.consumers.user_consumer import UserConsumer
from src.consumers.supplier_consumer import SupplierConsumer
from src.consumers.product_consumer import ProductConsumer
from src.consumers.order_consumer import OrderConsumer
from src.consumers.post_consumer import PostConsumer
from shared.kafka.topics import Topic

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Start the MySQL analytics consumer."""
    logger.info("MySQL Analytics Service starting...")

    # Initialize database
    db = get_database()
    db.connect()
    db.init_tables()

    # Create Kafka consumer
    # consumer = KafkaConsumer(group_id="mysql-analytics-service")

    # Register all domain consumers
    # domain_consumers = [
    #     UserConsumer(),
    #     SupplierConsumer(),
    #     ProductConsumer(),
    #     OrderConsumer(),
    #     PostConsumer(),
    # ]

    # for dc in domain_consumers:
    #     for event_type, handler in dc.get_handlers().items():
    #         consumer.register_handler(event_type, handler)
    #
    # # Subscribe to all topics and start
    # consumer.subscribe(Topic.all())
    # consumer.start()


if __name__ == "__main__":
    main()
