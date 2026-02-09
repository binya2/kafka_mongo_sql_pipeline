"""Post helper utilities."""

from beanie import PydanticObjectId

from shared.models.post import Post, PostAuthor, AuthorType
from shared.models.user import User
from shared.errors import NotFoundError, ValidationError
from utils.datetime_utils import utc_now


def post_response(post: Post) -> dict:
    """Build a JSON-safe post response."""
    data = post.model_dump(mode="json")
    data["id"] = str(post.id)
    return data


async def get_post_or_404(post_id: str) -> Post:
    """Fetch a post by ID or raise NotFoundError. Excludes deleted."""
    try:
        post = await Post.get(PydanticObjectId(post_id))
    except Exception:
        raise NotFoundError("Post not found")
    if not post or post.deleted_at:
        raise NotFoundError("Post not found")
    return post


async def build_post_author(user_id: str) -> PostAuthor:
    """Look up a User and build a PostAuthor snapshot."""
    try:
        user = await User.get(PydanticObjectId(user_id))
    except Exception:
        raise ValidationError("Invalid user ID")
    if not user or user.deleted_at:
        raise NotFoundError("User not found")

    return PostAuthor(
        user_id=user.id,
        display_name=user.profile.display_name,
        avatar=user.profile.avatar,
        author_type=AuthorType.USER,
    )
