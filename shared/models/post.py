"""
Post Model - Social content created by users and leaders

Posts are social feed content that can appear in:
- Global feed (main page)
- Community feeds (specific communities)

Posts are referenced by feed_items for unified feed display.

Permissions:
- Any community member can create posts
- Only the leader can remove posts or post promotions
"""

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import Optional, List, Annotated
from datetime import datetime
from enum import Enum

from utils.datetime_utils import utc_now



class PostType(str, Enum):
    """Type of post content"""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    LINK = "link"
    POLL = "poll"


class AuthorType(str, Enum):
    """Who created the post"""
    USER = "user"
    LEADER = "leader"


# Embedded Schemas
class PostAuthor(BaseModel):
    """Post author information (denormalized)"""

    user_id: Annotated[PydanticObjectId, Field(description="Reference to User document")]
    display_name: Annotated[str, Field(description="Author display name")]
    avatar: Annotated[str, Field(description="Author avatar URL")]
    author_type: Annotated[AuthorType, Field(description="User or leader")]


class MediaAttachment(BaseModel):
    """Media attachment (image, video)"""

    media_type: Annotated[str, Field(description="image, video, gif")]
    media_url: Annotated[HttpUrl, Field(description="Media file URL")]
    thumbnail_url: Annotated[Optional[HttpUrl], Field(None, description="Thumbnail for videos")]
    width: Annotated[Optional[int], Field(None, ge=0, description="Media width in pixels")]
    height: Annotated[Optional[int], Field(None, ge=0, description="Media height in pixels")]
    duration_seconds: Annotated[Optional[int], Field(None, ge=0, description="Video duration")]
    size_bytes: Annotated[Optional[int], Field(None, ge=0, description="File size")]


class LinkPreview(BaseModel):
    """Preview for shared links"""

    url: Annotated[HttpUrl, Field(description="Shared URL")]
    title: Annotated[str, Field(max_length=200, description="Link title")]
    description: Annotated[Optional[str], Field(None, max_length=500, description="Link description")]
    image: Annotated[Optional[HttpUrl], Field(None, description="Preview image")]
    site_name: Annotated[Optional[str], Field(None, description="Site name")]




class PostStats(BaseModel):
    """Post engagement statistics"""

    view_count: Annotated[int, Field(default=0, ge=0, description="Total views")]
    like_count: Annotated[int, Field(default=0, ge=0, description="Total likes")]
    comment_count: Annotated[int, Field(default=0, ge=0, description="Total comments")]
    share_count: Annotated[int, Field(default=0, ge=0, description="Total shares")]
    save_count: Annotated[int, Field(default=0, ge=0, description="Times saved/bookmarked")]
    engagement_rate: Annotated[float, Field(default=0.0, ge=0.0, description="Engagement rate %")]
    last_comment_at: Annotated[Optional[datetime], Field(None, description="Last comment timestamp")]

# Main Post Document
class Post(Document):
    """
    Post model - social content for feeds

    Posts are the full content documents.
    They are referenced by feed_items for unified feed display.

    Permissions:
    - Any community member can post
    - Only the post author can edit their own post
    - Only the community leader can remove any post
    """

    # Post type
    post_type: Annotated[PostType, Field(description="Type of post")]

    # Author
    author: Annotated[PostAuthor, Field(description="Post author information")]

    # Content
    text_content: Annotated[str, Field(max_length=5000, description="Post text content")]

    # Media attachments (images, videos)
    media: Annotated[Optional[List[MediaAttachment]], Field(default_factory=list, description="Media attachments")]

    # Link preview (if sharing a link)
    link_preview: Annotated[Optional[LinkPreview], Field(None, description="Shared link preview")]

    # Poll data (if post is a poll)

   
    # Statistics
    stats: Annotated[PostStats, Field(default_factory=PostStats, description="Engagement stats")]

    # Status
    deleted_at: Annotated[Optional[datetime], Field(None, description="Soft delete timestamp")]

    # Global distribution

    # Published timestamp (different from created_at)
    published_at: Annotated[Optional[datetime], Field(None, description="Publication timestamp")]

   

    # Timestamps
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="Creation timestamp")]
    updated_at: Annotated[datetime, Field(default_factory=utc_now, description="Last update timestamp")]

    class Settings:
        name = "posts"

        indexes = [
            # Author's posts
            [("author.user_id", 1), ("status", 1), ("created_at", -1)],


            # Published posts
            [("status", 1), ("published_at", -1)],


            # Soft delete
            [("deleted_at", 1)],

        ]

 
    async def save(self, *args, **kwargs):
        """Override save to update timestamps"""
        self.updated_at = utc_now()
        return await super().save(*args, **kwargs)
