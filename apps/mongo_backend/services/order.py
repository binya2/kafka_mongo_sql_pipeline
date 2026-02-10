"""Order Service - Business logic and DB operations."""

from typing import Optional

from beanie import PydanticObjectId

from shared.models.order import Order, OrderStatus, ShippingAddress
from shared.models.product import Product, ProductStatus
from shared.models.user import User
from shared.errors import NotFoundError, ValidationError
from utils.datetime_utils import utc_now
from utils.order_utils import generate_order_number, build_order_customer, build_order_item
from kafka.producer import get_kafka_producer
from shared.kafka.topics import EventType
from utils.serialization import oid_to_str


class OrderService:
    """Handles order DB operations."""

    def __init__(self):
        self._kafka = get_kafka_producer()

    async def create_order(self, user_id: str, body) -> Order:
        """Create a new order. `body` is a CreateOrderRequest."""
        # TODO: Implement create_order
        # 1. Build customer snapshot using build_order_customer(user_id)
        # 2. Loop through body.items:
        #    a. Fetch each product using Product.get()
        #    b. Validate product exists and status is ACTIVE
        #    c. Build order item using build_order_item(index, product, variant_name, quantity)
        # 3. Build ShippingAddress from body.shipping_address
        # 4. Create Order document with:
        #    - order_number (use generate_order_number())
        #    - customer, items, shipping_address
        # 5. Insert into MongoDB
        # 6. Emit ORDER_CREATED Kafka event
        # 7. Return the created order
        pass

    async def get_order(self, order_id: str) -> Order:
        # TODO: Implement get_order
        # 1. Fetch order by ID using Order.get()
        # 2. Handle invalid ObjectId (raise NotFoundError)
        # 3. Check order exists
        # 4. Return the order
        pass

    async def list_orders(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        status_filter: Optional[str] = None,
    ) -> list[Order]:
        # TODO: Implement list_orders
        # 1. Build query: filter by customer.user_id (convert to PydanticObjectId)
        # 2. If status_filter provided, parse comma-separated statuses into $in query
        # 3. Sort by -created_at, apply skip/limit (cap at 100)
        # 4. Return the list
        pass

    async def cancel_order(self, order_id: str, reason: str) -> Order:
        # TODO: Implement cancel_order
        # 1. Fetch the order using get_order
        # 2. Validate status is PENDING or CONFIRMED (raise ValidationError otherwise)
        # 3. Set status to CANCELLED
        # 4. Save the document
        # 5. Emit ORDER_CANCELLED Kafka event
        # 6. Return the updated order
        pass
