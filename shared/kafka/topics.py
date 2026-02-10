"""Kafka topic and event type definitions."""


class Topic:
    """Kafka topics."""
    # TODO: Define topic constants (USER, ORDER, POST, PRODUCT, SUPPLIER)
    pass

    @classmethod
    def all(cls) -> list[str]:
        """Return all topics."""
        # TODO: Return list of all topic strings
        pass


class EventType:
    """Event types (topic.action)."""
    # TODO: Define all event type constants in format "topic.action"
    pass
