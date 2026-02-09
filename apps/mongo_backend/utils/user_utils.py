"""User and Supplier helper utilities."""

from beanie import PydanticObjectId

from shared.models.user import User
from shared.models.supplier import Supplier
from shared.errors import NotFoundError


# ----------------------------------------------------------------
# User helpers
# ----------------------------------------------------------------

def user_response(user: User) -> dict:
    """Build a JSON-safe user response, stripping password_hash."""
    data = user.model_dump(mode="json")
    data.pop("password_hash", None)
    data["id"] = str(user.id)
    return data


async def get_user_or_404(user_id: str) -> User:
    """Fetch a user by ID or raise NotFoundError."""
    try:
        user = await User.get(PydanticObjectId(user_id))
    except Exception:
        raise NotFoundError("User not found")
    if not user or user.deleted_at:
        raise NotFoundError("User not found")
    return user


# ----------------------------------------------------------------
# Supplier helpers
# ----------------------------------------------------------------

def supplier_response(supplier: Supplier) -> dict:
    """Build a JSON-safe supplier response, stripping password_hash."""
    data = supplier.model_dump(mode="json")
    data.pop("password_hash", None)
    data["id"] = str(supplier.id)
    return data


async def get_supplier_or_404(supplier_id: str) -> Supplier:
    """Fetch a supplier by ID or raise NotFoundError."""
    try:
        supplier = await Supplier.get(PydanticObjectId(supplier_id))
    except Exception:
        raise NotFoundError("Supplier not found")
    if not supplier:
        raise NotFoundError("Supplier not found")
    return supplier
