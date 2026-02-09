"""Post Routes"""

from fastapi import APIRouter, Request, status, Query
from typing import Optional

from schemas.post import CreateCommunityPostRequest, UpdatePostRequest
from services.post import PostService
from shared.errors import ValidationError
from utils.post_utils import post_response


router = APIRouter(prefix="/posts", tags=["Posts"])
post_service = PostService()


def _get_user_id(request: Request) -> str:
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise ValidationError("X-User-ID header is required")
    return user_id


# ----------------------------------------------------------------
# CRUD
# ----------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_post(body: CreateCommunityPostRequest, request: Request):
    user_id = _get_user_id(request)
    post = await post_service.create_post(user_id, body)
    return post_response(post)


@router.get("/{post_id}")
async def get_post(post_id: str):
    return post_response(await post_service.get_post(post_id))


@router.get("")
async def list_posts(
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    author_id: Optional[str] = Query(None),
):
    posts = await post_service.list_posts(skip=skip, limit=limit, author_id=author_id)
    return [post_response(p) for p in posts]


@router.patch("/{post_id}")
async def update_post(post_id: str, body: UpdatePostRequest, request: Request):
    _get_user_id(request)
    post = await post_service.update_post(post_id, body)
    return post_response(post)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: str, request: Request):
    _get_user_id(request)
    await post_service.delete_post(post_id)


# ----------------------------------------------------------------
# Lifecycle
# ----------------------------------------------------------------

@router.post("/{post_id}/publish")
async def publish_post(post_id: str, request: Request):
    _get_user_id(request)
    return post_response(await post_service.publish_post(post_id))
