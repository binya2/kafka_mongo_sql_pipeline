"""Product Routes"""

from fastapi import APIRouter, Request, status, Query
from typing import Optional

from schemas.product import CreateProductRequest, UpdateProductRequest
from services.product import ProductService
from shared.errors import ValidationError
from utils.product_utils import product_response


router = APIRouter(prefix="/products", tags=["Products"])
svc = ProductService()


def _get_supplier_id(request: Request) -> str:
    supplier_id = request.headers.get("X-Supplier-ID")
    if not supplier_id:
        raise ValidationError("X-Supplier-ID header is required")
    return supplier_id


# ----------------------------------------------------------------
# CRUD
# ----------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_product(body: CreateProductRequest, request: Request):
    supplier_id = _get_supplier_id(request)
    product = await svc.create_product(supplier_id, body)
    return product_response(product)


@router.get("/{product_id}")
async def get_product(product_id: str):
    return product_response(await svc.get_product(product_id))


@router.get("")
async def list_products(
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = Query(None),
    supplier_id: Optional[str] = Query(None),
):
    products = await svc.list_products(
        skip=skip, limit=limit,
        status_filter=status_filter,
        category=category,
        supplier_id=supplier_id,
    )
    return [product_response(p) for p in products]


@router.patch("/{product_id}")
async def update_product(product_id: str, body: UpdateProductRequest, request: Request):
    _get_supplier_id(request)
    product = await svc.update_product(product_id, body)
    return product_response(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: str, request: Request):
    _get_supplier_id(request)
    await svc.delete_product(product_id)


# ----------------------------------------------------------------
# Lifecycle
# ----------------------------------------------------------------

@router.post("/{product_id}/publish")
async def publish_product(product_id: str, request: Request):
    _get_supplier_id(request)
    return product_response(await svc.publish_product(product_id))


@router.post("/{product_id}/discontinue")
async def discontinue_product(product_id: str, request: Request):
    _get_supplier_id(request)
    return product_response(await svc.discontinue_product(product_id))


@router.post("/{product_id}/mark-out-of-stock")
async def mark_out_of_stock(product_id: str, request: Request):
    _get_supplier_id(request)
    return product_response(await svc.mark_out_of_stock(product_id))


@router.post("/{product_id}/restore")
async def restore_product(product_id: str, request: Request):
    _get_supplier_id(request)
    return product_response(await svc.restore_product(product_id))
