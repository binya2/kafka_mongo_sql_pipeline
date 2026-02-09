"""Order Routes"""

from fastapi import APIRouter, Request, status, Query
from typing import Optional

from schemas.order import CreateOrderRequest, CancelOrderRequest
from services.order import OrderService
from shared.errors import ValidationError
from utils.order_utils import order_response


router = APIRouter(prefix="/orders", tags=["Orders"])
svc = OrderService()


def _get_user_id(request: Request) -> str:
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise ValidationError("X-User-ID header is required")
    return user_id


# ----------------------------------------------------------------
# CRUD
# ----------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_order(body: CreateOrderRequest, request: Request):
    user_id = _get_user_id(request)
    order = await svc.create_order(user_id, body)
    return order_response(order)


@router.get("/{order_id}")
async def get_order(order_id: str):
    return order_response(await svc.get_order(order_id))


@router.get("")
async def list_orders(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    user_id = _get_user_id(request)
    orders = await svc.list_orders(
        user_id=user_id, skip=skip, limit=limit,
        status_filter=status_filter,
    )
    return [order_response(o) for o in orders]


@router.post("/{order_id}/cancel")
async def cancel_order(order_id: str, body: CancelOrderRequest, request: Request):
    _get_user_id(request)
    order = await svc.cancel_order(order_id, body.reason)
    return order_response(order)
