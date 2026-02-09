"""
Post Schemas - Request and Response models for Post API
"""

from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============================================================
# Embedded Schema Requests
# ============================================================

class MediaAttachmentRequest(BaseModel):
    """Media attachment for post"""
    media_type: str = Field(..., description="Media type: image, video, gif")
    media_url: HttpUrl = Field(..., description="Media file URL")
    thumbnail_url: Optional[HttpUrl] = Field(None, description="Thumbnail URL for videos")
    width: Optional[int] = Field(None, ge=0, description="Width in pixels")
    height: Optional[int] = Field(None, ge=0, description="Height in pixels")
    duration_seconds: Optional[int] = Field(None, ge=0, description="Duration for videos")
    size_bytes: Optional[int] = Field(None, ge=0, description="File size")


class LinkPreviewRequest(BaseModel):
    """Link preview for post"""
    url: HttpUrl = Field(..., description="Shared URL")
    title: str = Field(..., max_length=200, description="Link title")
    description: Optional[str] = Field(None, max_length=500, description="Link description")
    image: Optional[HttpUrl] = Field(None, description="Preview image URL")
    site_name: Optional[str] = Field(None, description="Site name")


class PollOptionRequest(BaseModel):
    """Poll option"""
    option_id: str = Field(..., description="Unique option ID")
    option_text: str = Field(..., max_length=100, description="Option text")


class PollDataRequest(BaseModel):
    """Poll data for poll-type posts"""
    question: str = Field(..., max_length=300, description="Poll question")
    options: List[PollOptionRequest] = Field(..., min_length=2, max_length=6, description="Poll options")
    allows_multiple_votes: bool = Field(default=False, description="Allow multiple selections")
    ends_at: Optional[datetime] = Field(None, description="Poll end datetime")


class MentionRequest(BaseModel):
    """User mention"""
    user_id: str = Field(..., description="Mentioned user ID")
    display_name: str = Field(..., description="Mentioned user display name")


# ============================================================
# Community Post Requests
# ============================================================

class CreateCommunityPostRequest(BaseModel):
    """Create a post in a community"""
    community_id: str = Field(..., description="Community ID")
    post_type: str = Field(..., description="Post type: text, image, video, link, poll")
    text_content: str = Field(..., min_length=1, max_length=5000, description="Post text content")
    media: Optional[List[MediaAttachmentRequest]] = Field(None, max_length=10, description="Media attachments")
    link_preview: Optional[LinkPreviewRequest] = Field(None, description="Link preview")
    poll: Optional[PollDataRequest] = Field(None, description="Poll data for poll posts")
    tags: Optional[List[str]] = Field(None, max_length=10, description="Hashtags")
    mentions: Optional[List[MentionRequest]] = Field(None, description="User mentions")
    is_draft: bool = Field(default=False, description="Create as draft instead of publishing")
    request_global_distribution: bool = Field(default=False, description="Request global distribution on publish")

    @field_validator("post_type")
    @classmethod
    def validate_post_type(cls, v: str) -> str:
        valid_types = {"text", "image", "video", "link", "poll"}
        if v not in valid_types:
            raise ValueError(f"Invalid post type. Must be one of: {', '.join(valid_types)}")
        return v


class ListCommunityPostsRequest(BaseModel):
    """List posts in a community"""
    community_id: str = Field(..., description="Community ID")
    cursor: Optional[str] = Field(None, description="Pagination cursor")
    limit: int = Field(default=20, ge=1, le=100, description="Number of posts to return")
    include_hidden: bool = Field(default=False, description="Include hidden posts (leader/admin only)")


# ============================================================
# Home Feed Request
# ============================================================

class GetHomeFeedRequest(BaseModel):
    """Get personalized home feed"""
    cursor: Optional[str] = Field(None, description="Pagination cursor")
    limit: int = Field(default=20, ge=1, le=100, description="Number of posts to return")


# ============================================================
# Single Post Requests
# ============================================================

class GetPostRequest(BaseModel):
    """Get post by ID"""
    post_id: str = Field(..., description="Post ID")


class UpdatePostRequest(BaseModel):
    """Update a post (only for non-globally-tagged posts)"""
    post_id: str = Field(..., description="Post ID")
    version: int = Field(..., ge=1, description="Current version for optimistic locking")
    text_content: Optional[str] = Field(None, min_length=1, max_length=5000, description="Updated text content")
    media: Optional[List[MediaAttachmentRequest]] = Field(None, max_length=10, description="Updated media")
    link_preview: Optional[LinkPreviewRequest] = Field(None, description="Updated link preview")
    tags: Optional[List[str]] = Field(None, max_length=10, description="Updated tags")


class DeletePostRequest(BaseModel):
    """Soft delete a post"""
    post_id: str = Field(..., description="Post ID")
    version: int = Field(..., ge=1, description="Current version for optimistic locking")


class PublishPostRequest(BaseModel):
    """Publish a draft post"""
    post_id: str = Field(..., description="Post ID")
    version: int = Field(..., ge=1, description="Current version for optimistic locking")
    request_global_distribution: bool = Field(default=False, description="Request global distribution on publish")


# ============================================================
# Global Distribution Requests
# ============================================================

class RequestGlobalDistributionRequest(BaseModel):
    """Request global distribution for a post"""
    post_id: str = Field(..., description="Post ID")
    version: int = Field(..., ge=1, description="Current version for optimistic locking")


# ============================================================
# Change Request Requests
# ============================================================

class CreateChangeRequestRequest(BaseModel):
    """Create a change request for a globally-tagged post"""
    post_id: str = Field(..., description="Post ID")
    requested_changes: Dict[str, Any] = Field(..., description="Dict of field -> new value")
    reason: str = Field(..., min_length=5, max_length=500, description="Reason for the change")


class ListChangeRequestsRequest(BaseModel):
    """List change requests for a post"""
    post_id: str = Field(..., description="Post ID")
    cursor: Optional[str] = Field(None, description="Pagination cursor")
    limit: int = Field(default=20, ge=1, le=100, description="Number of requests to return")
    status: Optional[str] = Field(None, description="Filter by status: pending, approved, rejected")


# ============================================================
# Moderation Requests (Leader/Admin)
# ============================================================

class HidePostRequest(BaseModel):
    """Hide a post (leader/admin only)"""
    post_id: str = Field(..., description="Post ID")
    version: int = Field(..., ge=1, description="Current version for optimistic locking")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for hiding")


class UnhidePostRequest(BaseModel):
    """Unhide a hidden post (leader/admin only)"""
    post_id: str = Field(..., description="Post ID")
    version: int = Field(..., ge=1, description="Current version for optimistic locking")


class PinPostRequest(BaseModel):
    """Pin a post in community (leader only)"""
    post_id: str = Field(..., description="Post ID")
    version: int = Field(..., ge=1, description="Current version for optimistic locking")


class UnpinPostRequest(BaseModel):
    """Unpin a post (leader only)"""
    post_id: str = Field(..., description="Post ID")
    version: int = Field(..., ge=1, description="Current version for optimistic locking")


# ============================================================
# Admin Requests
# ============================================================

class CreateGlobalPostRequest(BaseModel):
    """Create a global-only post (admin only)"""
    post_type: str = Field(..., description="Post type: text, image, video, link, poll")
    text_content: str = Field(..., min_length=1, max_length=5000, description="Post text content")
    media: Optional[List[MediaAttachmentRequest]] = Field(None, max_length=10, description="Media attachments")
    link_preview: Optional[LinkPreviewRequest] = Field(None, description="Link preview")
    poll: Optional[PollDataRequest] = Field(None, description="Poll data for poll posts")
    tags: Optional[List[str]] = Field(None, max_length=10, description="Hashtags")
    mentions: Optional[List[MentionRequest]] = Field(None, description="User mentions")

    @field_validator("post_type")
    @classmethod
    def validate_post_type(cls, v: str) -> str:
        valid_types = {"text", "image", "video", "link", "poll"}
        if v not in valid_types:
            raise ValueError(f"Invalid post type. Must be one of: {', '.join(valid_types)}")
        return v


class ApproveGlobalDistributionRequest(BaseModel):
    """Approve global distribution (admin only)"""
    post_id: str = Field(..., description="Post ID")


class RejectGlobalDistributionRequest(BaseModel):
    """Reject global distribution (admin only)"""
    post_id: str = Field(..., description="Post ID")
    reason: str = Field(..., min_length=5, max_length=1000, description="Rejection reason")


class RevokeGlobalDistributionRequest(BaseModel):
    """Revoke approved global distribution (admin only)"""
    post_id: str = Field(..., description="Post ID")
    reason: str = Field(..., min_length=5, max_length=1000, description="Revocation reason")


class ApproveChangeRequestRequest(BaseModel):
    """Approve a change request (admin only)"""
    request_id: str = Field(..., description="Change request ID")
    notes: Optional[str] = Field(None, max_length=1000, description="Admin notes")


class RejectChangeRequestRequest(BaseModel):
    """Reject a change request (admin only)"""
    request_id: str = Field(..., description="Change request ID")
    notes: str = Field(..., min_length=5, max_length=1000, description="Rejection reason/notes")


# ============================================================
# Response Schemas
# ============================================================

class AuthorResponse(BaseModel):
    """Author information in response"""
    user_id: str
    display_name: str
    avatar: str
    author_type: str


class MediaResponse(BaseModel):
    """Media attachment in response"""
    media_type: str
    media_url: str
    thumbnail_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class LinkPreviewResponse(BaseModel):
    """Link preview in response"""
    url: str
    title: str
    description: Optional[str] = None
    image: Optional[str] = None


class PollOptionResponse(BaseModel):
    """Poll option in response"""
    option_id: str
    option_text: str
    vote_count: int
    percentage: float


class PollResponse(BaseModel):
    """Poll data in response"""
    question: str
    options: List[PollOptionResponse]
    total_votes: int
    ends_at: Optional[str] = None
    allows_multiple_votes: bool


class StatsResponse(BaseModel):
    """Post statistics in response"""
    view_count: int
    like_count: int
    comment_count: int
    share_count: int
    save_count: int
    engagement_rate: float


class GlobalDistributionResponse(BaseModel):
    """Global distribution info in response"""
    requested: bool
    status: str
    requested_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    rejection_reason: Optional[str] = None


class CommunityResponse(BaseModel):
    """Community info in response"""
    community_id: str
    community_name: str


class PostResponse(BaseModel):
    """Full post response"""
    id: str
    post_type: str
    author: AuthorResponse
    text_content: str
    media: List[MediaResponse]
    link_preview: Optional[LinkPreviewResponse] = None
    poll: Optional[PollResponse] = None
    community: Optional[CommunityResponse] = None
    tags: List[str]
    stats: StatsResponse
    status: str
    global_distribution: GlobalDistributionResponse
    is_pinned: bool
    version: int
    published_at: Optional[str] = None
    created_at: str
    updated_at: str


class PostListItemResponse(BaseModel):
    """Post item in list response"""
    id: str
    post_type: str
    author: AuthorResponse
    text_preview: str
    primary_image: Optional[str] = None
    community: Optional[CommunityResponse] = None
    stats: StatsResponse
    status: str
    global_distribution_status: str
    is_pinned: bool
    published_at: Optional[str] = None
    created_at: str


class PaginatedPostsResponse(BaseModel):
    """Paginated list of posts"""
    posts: List[PostListItemResponse]
    next_cursor: Optional[str] = None
    has_more: bool


class ChangeRequestResponse(BaseModel):
    """Change request response"""
    id: str
    post_id: str
    author_id: str
    requested_changes: Dict[str, Any]
    reason: str
    status: str
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    applied_at: Optional[str] = None
    created_at: str


class PaginatedChangeRequestsResponse(BaseModel):
    """Paginated list of change requests"""
    change_requests: List[ChangeRequestResponse]
    next_cursor: Optional[str] = None
    has_more: bool
