"""Serialization utilities for Kafka events."""

from beanie import PydanticObjectId


def oid_to_str(oid: PydanticObjectId) -> str:
    """Convert PydanticObjectId to string."""
    return str(oid)
