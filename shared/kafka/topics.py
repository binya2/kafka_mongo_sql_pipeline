"""Kafka topic and event type definitions."""


class Topic:
    """Kafka topics."""
    USER = "user"
    ORDER = "order"
    POST = "post"
    PRODUCT = "product"
    SUPPLIER = "supplier"

    @classmethod
    def all(cls) -> list[str]:
        """Return all topics."""
        return [
            cls.USER,
            cls.ORDER,
            cls.POST,
            cls.PRODUCT,
            cls.SUPPLIER,
        ]


class EventType:
    """Event types (topic.action)."""

    # User
    USER_CREATED = "user.created"
    USER_DELETED = "user.deleted"

    # Supplier
    SUPPLIER_CREATED = "supplier.created"
    SUPPLIER_DELETED = "supplier.deleted"

    # Product
    PRODUCT_CREATED = "product.created"
    PRODUCT_DELETED = "product.deleted"
    PRODUCT_PUBLISHED = "product.published"

    # Order
    ORDER_CREATED = "order.created"
    ORDER_CANCELLED = "order.cancelled"

    # Post
    POST_CREATED = "post.created"
    POST_DELETED = "post.deleted"
    POST_PUBLISHED = "post.published"
