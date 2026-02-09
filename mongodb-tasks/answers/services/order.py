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
        customer = await build_order_customer(user_id)

        # Build order items from product lookups
        items = []
        for i, item_req in enumerate(body.items):
            try:
                product = await Product.get(PydanticObjectId(item_req.product_id))
            except Exception:
                raise NotFoundError(f"Product not found: {item_req.product_id}")
            if not product or product.status != ProductStatus.ACTIVE:
                raise ValidationError(f"Product not available: {item_req.product_id}")

            items.append(build_order_item(i, product, item_req.variant_name, item_req.quantity))

        addr = body.shipping_address
        shipping_address = ShippingAddress(
            recipient_name=addr.recipient_name,
            phone=addr.phone,
            street_address_1=addr.street_address_1,
            street_address_2=addr.street_address_2,
            city=addr.city,
            state=addr.state,
            zip_code=addr.zip_code,
            country=addr.country,
        )

        order = Order(
            order_number=generate_order_number(),
            customer=customer,
            items=items,
            shipping_address=shipping_address,
        )
        await order.insert()

        self._kafka.emit(
            event_type=EventType.ORDER_CREATED,
            entity_id=oid_to_str(order.id),
            data=order.model_dump(mode="json"),
        )
        return order

    async def get_order(self, order_id: str) -> Order:
        try:
            order = await Order.get(PydanticObjectId(order_id))
        except Exception:
            raise NotFoundError("Order not found")
        if not order:
            raise NotFoundError("Order not found")
        return order

    async def list_orders(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        status_filter: Optional[str] = None,
    ) -> list[Order]:
        query: dict = {"customer.user_id": PydanticObjectId(user_id)}
        if status_filter:
            statuses = [s.strip() for s in status_filter.split(",")]
            query["status"] = {"$in": statuses}

        return (
            await Order.find(query)
            .sort("-created_at")
            .skip(skip)
            .limit(min(limit, 100))
            .to_list()
        )

    async def cancel_order(self, order_id: str, reason: str) -> Order:
        order = await self.get_order(order_id)
        if order.status not in (OrderStatus.PENDING, OrderStatus.CONFIRMED):
            raise ValidationError("Only pending or confirmed orders can be cancelled")

        order.status = OrderStatus.CANCELLED
        await order.save()

        self._kafka.emit(
            event_type=EventType.ORDER_CANCELLED,
            entity_id=oid_to_str(order.id),
            data={"order_number": order.order_number},
        )
        return order
