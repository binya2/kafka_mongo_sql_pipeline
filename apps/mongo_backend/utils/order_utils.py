"""Order helper utilities."""

import secrets

from beanie import PydanticObjectId

from shared.models.order import (
    Order, OrderCustomer, OrderItem, ProductSnapshot, FulfillmentStatus,
)
from shared.models.product import Product
from shared.models.user import User
from shared.errors import NotFoundError, ValidationError
from utils.datetime_utils import utc_now


def order_response(order: Order) -> dict:
    """Build a JSON-safe order response."""
    data = order.model_dump(mode="json")
    data["id"] = str(order.id)
    return data


async def get_order_or_404(order_id: str) -> Order:
    """Fetch an order by ID or raise NotFoundError."""
    try:
        order = await Order.get(PydanticObjectId(order_id))
    except Exception:
        raise NotFoundError("Order not found")
    if not order:
        raise NotFoundError("Order not found")
    return order


def generate_order_number() -> str:
    """Generate a human-readable order number: ORD-YYYYMMDD-XXXX."""
    date_part = utc_now().strftime("%Y%m%d")
    random_part = secrets.token_hex(2).upper()
    return f"ORD-{date_part}-{random_part}"


async def build_order_customer(user_id: str) -> OrderCustomer:
    """Look up a User and build an OrderCustomer snapshot."""
    try:
        user = await User.get(PydanticObjectId(user_id))
    except Exception:
        raise ValidationError("Invalid user ID")
    if not user or user.deleted_at:
        raise NotFoundError("User not found")

    return OrderCustomer(
        user_id=user.id,
        display_name=user.profile.display_name,
        email=user.contact_info.primary_email,
        phone=user.contact_info.phone,
    )


def build_product_snapshot(product: Product, variant_name: str | None) -> ProductSnapshot:
    """Build an immutable ProductSnapshot from a Product document."""
    variant_attributes: dict[str, str] = {}
    image_url = "https://placeholder.com/default.jpg"
    supplier_name = product.supplier_info.get("name", "Unknown")

    if variant_name and variant_name in product.variants:
        variant = product.variants[variant_name]
        variant_attributes = {
            a.attribute_name: a.attribute_value for a in variant.attributes
        }
        if variant.image_url:
            image_url = str(variant.image_url)

    return ProductSnapshot(
        product_id=product.id,
        supplier_id=product.supplier_id,
        product_name=product.name,
        variant_name=variant_name,
        variant_attributes=variant_attributes,
        image_url=image_url,
        supplier_name=supplier_name,
    )


def build_order_item(
    index: int,
    product: Product,
    variant_name: str | None,
    quantity: int,
) -> OrderItem:
    """Build a single OrderItem from a product lookup."""
    if variant_name and variant_name in product.variants:
        unit_price = product.variants[variant_name].price_cents
    else:
        unit_price = product.base_price_cents

    total = unit_price * quantity

    return OrderItem(
        item_id=f"item_{index + 1}",
        product_snapshot=build_product_snapshot(product, variant_name),
        quantity=quantity,
        unit_price_cents=unit_price,
        final_price_cents=total,
        fulfillment_status=FulfillmentStatus.PENDING,
        total_cents=total,
    )
