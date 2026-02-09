"""User & Supplier Routes"""

from fastapi import APIRouter, status

from schemas.user import (
    CreateUserRequest, UpdateUserRequest,
    CreateSupplierRequest, UpdateSupplierRequest,
)
from services.user import UserService
from utils.user_utils import user_response, supplier_response


router = APIRouter(prefix="/users", tags=["Users"])
supplier_router = APIRouter(prefix="/suppliers", tags=["Suppliers"])
user_service = UserService()


# ----------------------------------------------------------------
# User Endpoints
# ----------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(body: CreateUserRequest):
    user = await user_service.create_user(
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        phone=body.phone,
        bio=body.bio,
    )
    return user_response(user)


@router.get("/{user_id}")
async def get_user(user_id: str):
    return user_response(await user_service.get_user(user_id))


@router.get("")
async def list_users(limit: int = 20, skip: int = 0):
    users = await user_service.list_users(skip=skip, limit=limit)
    return [user_response(u) for u in users]


@router.patch("/{user_id}")
async def update_user(user_id: str, body: UpdateUserRequest):
    user = await user_service.update_user(
        user_id=user_id,
        display_name=body.display_name,
        phone=body.phone,
        bio=body.bio,
        avatar=body.avatar,
    )
    return user_response(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str):
    await user_service.delete_user(user_id)


# ----------------------------------------------------------------
# Supplier Endpoints
# ----------------------------------------------------------------

@supplier_router.post("", status_code=status.HTTP_201_CREATED)
async def create_supplier(body: CreateSupplierRequest):
    supplier = await user_service.create_supplier(body)
    return supplier_response(supplier)


@supplier_router.get("/{supplier_id}")
async def get_supplier(supplier_id: str):
    return supplier_response(await user_service.get_supplier(supplier_id))


@supplier_router.get("")
async def list_suppliers(limit: int = 20, skip: int = 0):
    suppliers = await user_service.list_suppliers(skip=skip, limit=limit)
    return [supplier_response(s) for s in suppliers]


@supplier_router.patch("/{supplier_id}")
async def update_supplier(supplier_id: str, body: UpdateSupplierRequest):
    supplier = await user_service.update_supplier(
        supplier_id=supplier_id,
        primary_phone=body.primary_phone,
        legal_name=body.legal_name,
        dba_name=body.dba_name,
        support_email=body.support_email,
        support_phone=body.support_phone,
    )
    return supplier_response(supplier)


@supplier_router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(supplier_id: str):
    await user_service.delete_supplier(supplier_id)
