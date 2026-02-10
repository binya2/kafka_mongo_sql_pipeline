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
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"

    # Supplier
    SUPPLIER_CREATED = "supplier.created"
    SUPPLIER_UPDATED = "supplier.updated"
    SUPPLIER_DELETED = "supplier.deleted"

    # Product
    PRODUCT_CREATED = "product.created"
    PRODUCT_UPDATED = "product.updated"
    PRODUCT_PUBLISHED = "product.published"
    PRODUCT_DISCONTINUED = "product.discontinued"
    PRODUCT_OUT_OF_STOCK = "product.out_of_stock"
    PRODUCT_RESTORED = "product.restored"
    PRODUCT_DELETED = "product.deleted"

    # Order
    ORDER_CREATED = "order.created"
    ORDER_CANCELLED = "order.cancelled"

    # Post
    POST_CREATED = "post.created"
    POST_UPDATED = "post.updated"
    POST_PUBLISHED = "post.published"
    POST_DELETED = "post.deleted"
