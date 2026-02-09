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
        # TODO: Implement _build_media
        # Convert a list of request objects into MediaAttachment embedded documents
        # Return empty list if media_list is falsy
        # Each item has: media_type, media_url, thumbnail_url, width, height,
        #   duration_seconds, size_bytes
        pass

    @staticmethod
    def _build_link_preview(lp) -> Optional[LinkPreview]:
        # TODO: Implement _build_link_preview
        # Convert a request object into a LinkPreview embedded document
        # Return None if lp is falsy
        # Fields: url, title, description, image, site_name
        pass

    # ----------------------------------------------------------------
    # CRUD
    # ----------------------------------------------------------------

    async def create_post(self, user_id: str, body) -> Post:
        """Create a new post. `body` is a CreateCommunityPostRequest."""
        # TODO: Implement create_post
        # 1. Build post author using build_post_author(user_id)
        # 2. Create Post document with:
        #    - post_type (PostType enum), author, text_content
        #    - media (use _build_media helper), link_preview (use _build_link_preview helper)
        #    - published_at: None if is_draft, else current UTC time
        # 3. Insert into MongoDB
        # 4. Emit POST_CREATED Kafka event
        # 5. Return the created post
        pass

    async def get_post(self, post_id: str) -> Post:
        # TODO: Implement get_post
        # 1. Fetch post by ID using Post.get()
        # 2. Handle invalid ObjectId (raise NotFoundError)
        # 3. Check post exists and is not soft-deleted
        # 4. Return the post
        pass

    async def list_posts(
        self,
        skip: int = 0,
        limit: int = 20,
        author_id: Optional[str] = None,
    ) -> list[Post]:
        # TODO: Implement list_posts
        # 1. Build query: deleted_at is None AND published_at is not None
        # 2. If author_id provided, filter by author.user_id
        # 3. Sort by -published_at, apply skip/limit (cap at 100)
        # 4. Return the list
        pass

    async def update_post(self, post_id: str, body) -> Post:
        """Partial update. `body` is an UpdatePostRequest."""
        # TODO: Implement update_post
        # 1. Fetch the post using get_post
        # 2. Update only the provided fields:
        #    text_content, media (use helper), link_preview (use helper)
        # 3. Save the updated document
        # 4. Emit POST_UPDATED Kafka event
        # 5. Return the updated post
        pass

    async def delete_post(self, post_id: str) -> None:
        # TODO: Implement delete_post (soft delete)
        # 1. Fetch the post using get_post
        # 2. Set deleted_at to current UTC time
        # 3. Save the document
        # 4. Emit POST_DELETED Kafka event
        pass

    async def publish_post(self, post_id: str) -> Post:
        # TODO: Implement publish_post
        # 1. Fetch the post using get_post
        # 2. Validate post is not already published (raise ValidationError)
        # 3. Set published_at to current UTC time
        # 4. Save the document
        # 5. Emit POST_PUBLISHED Kafka event
        # 6. Return the updated post
        pass
