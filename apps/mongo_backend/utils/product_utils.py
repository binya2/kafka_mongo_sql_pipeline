"""Product helper utilities."""

from beanie import PydanticObjectId

from shared.models.product import Product, ProductStatus
from shared.errors import NotFoundError


def product_response(product: Product) -> dict:
    """Build a JSON-safe product response."""
    data = product.model_dump(mode="json")
    data["id"] = str(product.id)
    return data


async def get_product_or_404(product_id: str) -> Product:
    """Fetch a product by ID or raise NotFoundError. Excludes deleted."""
    try:
        product = await Product.get(PydanticObjectId(product_id))
    except Exception:
        raise NotFoundError("Product not found")
    if not product or product.status == ProductStatus.DELETED:
        raise NotFoundError("Product not found")
    return product
