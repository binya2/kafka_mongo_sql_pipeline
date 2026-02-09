"""Post Service - Business logic and DB operations."""

from typing import Optional

from beanie import PydanticObjectId

from shared.models.post import Post, PostType, MediaAttachment, LinkPreview
from shared.models.user import User
from shared.errors import NotFoundError, ValidationError
from utils.datetime_utils import utc_now
from utils.post_utils import build_post_author
from kafka.producer import get_kafka_producer
from shared.kafka.topics import EventType
from utils.serialization import oid_to_str


class PostService:
    """Handles post DB operations."""

    def __init__(self):
        self._kafka = get_kafka_producer()

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _build_media(media_list) -> list[MediaAttachment]:
        if not media_list:
            return []
        return [
            MediaAttachment(
                media_type=m.media_type,
                media_url=m.media_url,
                thumbnail_url=m.thumbnail_url,
                width=m.width,
                height=m.height,
                duration_seconds=m.duration_seconds,
                size_bytes=m.size_bytes,
            )
            for m in media_list
        ]

    @staticmethod
    def _build_link_preview(lp) -> Optional[LinkPreview]:
        if not lp:
            return None
        return LinkPreview(
            url=lp.url,
            title=lp.title,
            description=lp.description,
            image=lp.image,
            site_name=lp.site_name,
        )

    # ----------------------------------------------------------------
    # CRUD
    # ----------------------------------------------------------------

    async def create_post(self, user_id: str, body) -> Post:
        """Create a new post. `body` is a CreateCommunityPostRequest."""
        author = await build_post_author(user_id)

        post = Post(
            post_type=PostType(body.post_type),
            author=author,
            text_content=body.text_content,
            media=self._build_media(body.media),
            link_preview=self._build_link_preview(body.link_preview),
            published_at=None if body.is_draft else utc_now(),
        )
        await post.insert()

        self._kafka.emit(
            event_type=EventType.POST_CREATED,
            entity_id=oid_to_str(post.id),
            data=post.model_dump(mode="json"),
        )
        return post

    async def get_post(self, post_id: str) -> Post:
        try:
            post = await Post.get(PydanticObjectId(post_id))
        except Exception:
            raise NotFoundError("Post not found")
        if not post or post.deleted_at:
            raise NotFoundError("Post not found")
        return post

    async def list_posts(
        self,
        skip: int = 0,
        limit: int = 20,
        author_id: Optional[str] = None,
    ) -> list[Post]:
        query: dict = {"deleted_at": None, "published_at": {"$ne": None}}
        if author_id:
            query["author.user_id"] = author_id

        return (
            await Post.find(query)
            .sort("-published_at")
            .skip(skip)
            .limit(min(limit, 100))
            .to_list()
        )

    async def update_post(self, post_id: str, body) -> Post:
        """Partial update. `body` is an UpdatePostRequest."""
        post = await self.get_post(post_id)

        if body.text_content is not None:
            post.text_content = body.text_content
        if body.media is not None:
            post.media = self._build_media(body.media)
        if body.link_preview is not None:
            post.link_preview = self._build_link_preview(body.link_preview)

        await post.save()

        self._kafka.emit(
            event_type=EventType.POST_UPDATED,
            entity_id=oid_to_str(post.id),
            data=post.model_dump(mode="json"),
        )
        return post

    async def delete_post(self, post_id: str) -> None:
        post = await self.get_post(post_id)
        post.deleted_at = utc_now()
        await post.save()

        self._kafka.emit(
            event_type=EventType.POST_DELETED,
            entity_id=oid_to_str(post.id),
            data={"post_id": oid_to_str(post.id)},
        )

    async def publish_post(self, post_id: str) -> Post:
        post = await self.get_post(post_id)
        if post.published_at is not None:
            raise ValidationError("Post is already published")

        post.published_at = utc_now()
        await post.save()

        self._kafka.emit(
            event_type=EventType.POST_PUBLISHED,
            entity_id=oid_to_str(post.id),
            data=post.model_dump(mode="json"),
        )
        return post
