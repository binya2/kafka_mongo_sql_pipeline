# TASK 05: Post Service - Social Content & Feed Operations

## 1. MISSION BRIEFING

Posts are the **social heartbeat** of the platform. They are the content that fills user feeds and the global timeline. Every post is authored by a user and can carry text, images, videos, links, or polls. Posts can be liked, shared, saved, and commented on.

This task introduces **denormalized author snapshots** and **cursor pagination with `$or` tiebreaker** - the most important query pattern for feed-style data.

### What You Will Build
The `PostService` class - ~10 methods covering post CRUD, feed generation with cursor pagination, user post listing, and engagement stat updates.

### What You Will Learn

| MongoDB Concept | Where You'll Use It |
|----------------|-------------------|
| **Cursor pagination with `$or` tiebreaker** | Feed listing: `published_at`/`_id` tiebreaker for deterministic ordering |
| **Base64-encoded cursors** | Using `encode_cursor`/`decode_cursor` utilities |
| **Nested field queries** | `author.user_id` for querying into denormalized embedded docs |
| **`$inc` for atomic counters** | Updating `stats.view_count`, `stats.like_count`, etc. |
| **Cross-collection reads** | User lookup for author denormalization |
| **Denormalized author data** | `PostAuthor` snapshot from User into Post |
| **Soft delete pattern** | Using `deleted_at` field instead of actual deletion |
| **Multiple embedded types** | 4 embedded types (PostAuthor, MediaAttachment, LinkPreview, PostStats) |
| **Anti-enumeration** | Always "Post not found" regardless of reason |

### How This Differs From Previous Tasks

| Aspect | Product (04) | Post (05) |
|--------|-------------|-----------|
| Collections touched | 2 (products + suppliers) | 2 (posts + users) |
| Cursor pagination | Simple `_id` cursor | **`published_at` + `_id` tiebreaker with base64** |
| Embedded doc queries | `supplier_id` (top-level) | **`author.user_id`** (nested field) |
| Denormalized data | `supplier_info` (Dict) | **`PostAuthor`** (typed embedded doc) |
| Atomic counters | `stats` fields set on creation | **`$inc` for incrementing stats** |
| Delete pattern | Status-based (DELETED) | **Soft delete with `deleted_at` timestamp** |

---

## 2. BEFORE YOU START

### Prerequisites
- **TASK_01 (User) must be complete** - Posts require an author (User)
- Have at least one user created from previous tasks

### Files You MUST Read Before Coding

| Order | File | Why |
|-------|------|-----|
| 1 | `shared/models/post.py` | 156 lines - 2 enums, 4 embedded types, 3 indexes |
| 2 | `apps/backend-service/src/schemas/post.py` | Request/response schemas |
| 3 | `apps/backend-service/src/routes/post.py` | Endpoints your service must support |
| 4 | `apps/backend-service/src/utils/post_utils.py` | `encode_cursor`, `decode_cursor`, response builders |

### The Data Flow

```
HTTP Request (User JWT)
    |
    v
+----------+   Extracts user_id from X-User-ID header
|  Route   |
|          |
|  Calls   |
|  your    |
|  service |
    |
    v
+----------------------------------------------------------+
|              PostService (YOU WRITE THIS)                  |
|                                                            |
|  Reads from TWO collections:                               |
|  +-- posts (main CRUD + feeds)                             |
|  +-- users (author validation + denormalization)           |
|                                                            |
|  Writes to ONE collection:                                 |
|  +-- posts (insert, update, soft delete)                   |
|                                                            |
|  Emits Kafka events:                                       |
|  +-- Topic.POST -> created, deleted                        |
+----------------------------------------------------------+
```

---

## 3. MODEL DEEP DIVE

### The Two Enums

```python
class PostType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    LINK = "link"
    POLL = "poll"

class AuthorType(str, Enum):
    USER = "user"
    LEADER = "leader"
```

### Embedded Document Hierarchy (4 types)

```
Post (Document)
|
+-- author: PostAuthor                       <- Denormalized from User
|   +-- user_id, display_name, avatar, author_type
|
+-- media: List[MediaAttachment]             <- Images, videos, GIFs
|   +-- media_type, media_url, thumbnail_url, width, height, duration_seconds, size_bytes
|
+-- link_preview: Optional[LinkPreview]      <- Shared link metadata
|   +-- url, title, description, image, site_name
|
+-- stats: PostStats                         <- Engagement counters
|   +-- view_count, like_count, comment_count, share_count, save_count,
|       engagement_rate, last_comment_at
|
+-- post_type: PostType                      <- text/image/video/link/poll
+-- text_content: str                        <- Post text (max 5000 chars)
+-- deleted_at: Optional[datetime]           <- Soft delete timestamp
+-- published_at: Optional[datetime]         <- Publication timestamp
+-- created_at: datetime                     <- Auto-set on creation
+-- updated_at: datetime                     <- Auto-set on save
```

### Index Analysis (3 indexes)

```python
indexes = [
    # Index 1: Author's posts (note: references "status" field for future use)
    [("author.user_id", 1), ("status", 1), ("created_at", -1)],
    # -> Querying into denormalized embedded doc!

    # Index 2: Published posts timeline
    [("status", 1), ("published_at", -1)],

    # Index 3: Soft delete
    [("deleted_at", 1)],
]
```

> **Note**: The indexes reference a `status` field that is defined in the index configuration but not as a document field. The `author.user_id` index is the key one - it demonstrates MongoDB's ability to index **nested fields** inside embedded documents.

### Key Model Observations

| Feature | Detail |
|---------|--------|
| **Collection name** | `posts` (set in `Settings.name`) |
| **Soft delete** | `deleted_at` field (None = active, timestamp = deleted) |
| **Timestamps** | `save()` override auto-updates `updated_at` |
| **No version field** | Unlike User, no optimistic locking built in |
| **No status field** | Use `deleted_at` and `published_at` to determine state |
| **PostStats defaults** | All counters default to 0, `engagement_rate` to 0.0 |

### Understanding PostStats

`PostStats` has 7 fields, all with defaults:

```python
class PostStats(BaseModel):
    view_count: int = 0          # Total views
    like_count: int = 0          # Total likes
    comment_count: int = 0       # Total comments
    share_count: int = 0         # Total shares
    save_count: int = 0          # Times saved/bookmarked
    engagement_rate: float = 0.0 # Engagement rate %
    last_comment_at: Optional[datetime] = None  # Last comment timestamp
```

These counters are updated using `$inc` - MongoDB's atomic increment operator. This is important because multiple users can like a post simultaneously, and `$inc` prevents race conditions.

---

## 4. THE SERVICE CONTRACT

Your service file: `apps/backend-service/src/services/post.py`

### Class Setup

```python
from shared.models.post import Post, PostType, AuthorType, PostAuthor, MediaAttachment, LinkPreview, PostStats
from shared.models.user import User

class PostService:
    def __init__(self, kafka_service=None):
        self._kafka = kafka_service
        self.max_page_size = 50
```

### Method Overview

| # | Method | MongoDB Concepts | Difficulty |
|---|--------|-----------------|-----------|
| 1 | `_get_user(user_id)` | `User.get()` + deleted check | Easy |
| 2 | `_get_post(post_id)` | `Post.get()` + deleted check | Easy |
| 3 | `_build_author(user)` | Denormalized snapshot from User | Easy |
| 4 | `_build_media_list(media_data)` | List construction | Easy |
| 5 | `_build_link_preview(preview_data)` | Optional construction | Easy |
| 6 | `create_post(...)` | Cross-collection + insert | Medium |
| 7 | `get_post(post_id)` | Simple get + deleted check | Easy |
| 8 | `list_posts(...)` | Cursor pagination + `$or` tiebreaker | **Hard** |
| 9 | `list_user_posts(...)` | Nested field query + cursor pagination | **Hard** |
| 10 | `update_post(...)` | Ownership check + partial update | Medium |
| 11 | `delete_post(...)` | Soft delete with `deleted_at` | Medium |
| 12 | `increment_stat(...)` | `$inc` atomic counter | Medium |

---

## 5. EXERCISES

---

### Exercise 5.1: Helper Methods Foundation

**Concept**: Cross-collection lookups with `get()`, denormalized data construction

#### 5.1a: Get Helpers - `_get_user`, `_get_post`

Both follow the same pattern:

```python
# Pattern:
# 1. Try to get by ID (wrapping in try/except for invalid ObjectId)
# 2. Check if found AND not soft-deleted
# 3. Raise ValueError if not found
```

```python
async def _get_user(self, user_id: str) -> User:
    try:
        user = await User.get(PydanticObjectId(user_id))
    except Exception:
        raise ValueError("Invalid user ID")

    if not user or user.deleted_at:
        raise ValueError("User not found")

    return user
```

> **Why wrap `User.get()` in try/except?** Because `PydanticObjectId("not-a-valid-id")` throws an exception. We catch it and return a clear error message instead of exposing internal details.

Implement `_get_post` following the same pattern. The only difference is the model class and error messages.

<details>
<summary>Full Implementation - Both Helpers</summary>

```python
async def _get_user(self, user_id: str) -> User:
    try:
        user = await User.get(PydanticObjectId(user_id))
    except Exception:
        raise ValueError("Invalid user ID")
    if not user or user.deleted_at:
        raise ValueError("User not found")
    return user

async def _get_post(self, post_id: str) -> Post:
    try:
        post = await Post.get(PydanticObjectId(post_id))
    except Exception:
        raise ValueError("Invalid post ID")
    if not post or post.deleted_at:
        raise ValueError("Post not found")
    return post
```
</details>

---

#### 5.1b: Builder Helpers

These pure Python methods construct embedded documents from request data. No MongoDB involved.

**`_build_author(user)`**: Create a denormalized `PostAuthor` from a `User` object.

```python
def _build_author(self, user: User, is_leader: bool = False) -> PostAuthor:
    return PostAuthor(
        user_id=user.id,
        display_name=user.profile.display_name,
        avatar=user.profile.avatar,
        author_type=AuthorType.LEADER if is_leader else AuthorType.USER
    )
```

> **Why denormalize?** Every time we display a post in a feed, we need the author's name and avatar. Without denormalization, we'd need a separate User query for every post in the feed (N+1 problem). By storing a snapshot in each post, the feed query returns everything in one go.

**`_build_media_list(media_data)`** and **`_build_link_preview(preview_data)`**: Build embedded objects from dict data.

<details>
<summary>Full Implementation - All Builders</summary>

```python
def _build_author(self, user: User, is_leader: bool = False) -> PostAuthor:
    return PostAuthor(
        user_id=user.id,
        display_name=user.profile.display_name,
        avatar=user.profile.avatar,
        author_type=AuthorType.LEADER if is_leader else AuthorType.USER
    )

def _build_media_list(self, media_data: Optional[List[Dict]]) -> List[MediaAttachment]:
    if not media_data:
        return []
    return [
        MediaAttachment(
            media_type=m.get("media_type"),
            media_url=m.get("media_url"),
            thumbnail_url=m.get("thumbnail_url"),
            width=m.get("width"),
            height=m.get("height"),
            duration_seconds=m.get("duration_seconds"),
            size_bytes=m.get("size_bytes")
        )
        for m in media_data
    ]

def _build_link_preview(self, preview_data: Optional[Dict]) -> Optional[LinkPreview]:
    if not preview_data:
        return None
    return LinkPreview(
        url=preview_data.get("url"),
        title=preview_data.get("title"),
        description=preview_data.get("description"),
        image=preview_data.get("image"),
        site_name=preview_data.get("site_name")
    )
```
</details>

---

### Exercise 5.2: Create Post

**Concept**: Cross-collection validation, embedded document construction, denormalized author snapshot

#### The Method Signature

```python
async def create_post(
    self,
    user_id: str,
    post_type: str,
    text_content: str,
    media: Optional[List[Dict]] = None,
    link_preview: Optional[Dict] = None,
    publish: bool = True
) -> Post:
```

#### Step-by-Step Algorithm

```
1. Validate user exists (cross-collection)
   +-- await self._get_user(user_id)

2. Validate post_type enum
   +-- PostType(post_type) - catch ValueError

3. Build Post document:
   +-- Use all _build_* helpers
   +-- Denormalize author from User -> PostAuthor

4. Set published_at if publishing immediately:
   +-- If publish -> set published_at = utc_now()

5. await post.insert()

6. Emit Kafka event (Topic.POST, action="created")

7. Return post
```

> **Think about it**: Why do we validate `post_type` with `PostType(post_type)` instead of just passing the string? Because MongoDB stores whatever you give it - if you store `"invalid_type"`, it will happily save it. The enum validation catches bad values BEFORE they reach the database.

> **Hint Level 1**: Follow the algorithm. The key insight is building the `PostAuthor` snapshot from the User document before inserting.

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def create_post(
    self, user_id: str, post_type: str, text_content: str,
    media=None, link_preview=None, publish: bool = True
) -> Post:
    user = await self._get_user(user_id)

    try:
        post_type_enum = PostType(post_type)
    except ValueError:
        raise ValueError(f"Invalid post type: {post_type}")

    post = Post(
        post_type=post_type_enum,
        author=self._build_author(user),
        text_content=text_content,
        media=self._build_media_list(media),
        link_preview=self._build_link_preview(link_preview),
        stats=PostStats(),
    )

    if publish:
        post.published_at = utc_now()

    await post.insert()

    if self._kafka:
        self._kafka.emit(
            topic=Topic.POST,
            action="created",
            entity_id=oid_to_str(post.id),
            data=post.model_dump(mode="json"),
        )
    return post
```
</details>

---

### Exercise 5.3: List Posts (Cursor Pagination with `$or` Tiebreaker)

**Concept**: Cursor pagination using `published_at` + `_id` tiebreaker, base64 cursor encoding

This is the **most important query pattern** in this task.

#### The Method Signature

```python
async def list_posts(
    self,
    cursor: Optional[str] = None,
    limit: int = 20
) -> Tuple[List[Post], bool]:
```

#### The `$or` Tiebreaker Pattern

```python
# Why $or tiebreaker?
# Multiple posts can have the same published_at (especially bulk imports).
# If we only paginate on published_at, we'd skip or duplicate posts.
#
# The $or says: give me posts where EITHER:
# - published_at is strictly BEFORE the cursor's timestamp, OR
# - published_at EQUALS the cursor's timestamp AND _id is less than cursor's id
#
# This ensures every post appears exactly once, even with identical timestamps.

query["$or"] = [
    {"published_at": {"$lt": cursor_published_at}},
    {
        "published_at": cursor_published_at,
        "_id": {"$lt": PydanticObjectId(cursor_id)}
    }
]
```

#### Base64 Cursor Encoding

Unlike TASK_04 where cursors were plain IDs, post cursors encode BOTH `published_at` and `id`:

```python
# Encoding (done by post_utils.py):
cursor_data = {"published_at": "2024-01-15T10:30:00", "id": "abc123"}
cursor = base64.urlsafe_b64encode(json.dumps(cursor_data).encode()).decode()
# -> "eyJwdWJsaXNoZWRfYXQiOiAiMjAyNC0wMS0xNVQxMDozMDowMCIsICJpZCI6ICJhYmMxMjMifQ=="

# Decoding:
cursor_data = decode_cursor(cursor)
# -> {"published_at": "2024-01-15T10:30:00", "id": "abc123"}
```

#### Building the Query

```
1. Base query: deleted_at = None, published_at != None (only published posts)
2. If cursor provided: decode and add $or tiebreaker
3. Sort by [("published_at", -1), ("_id", -1)]
4. Limit to limit + 1 (fetch one extra to check has_more)
5. If got more than limit: has_more = True, trim to limit
```

> **Hint Level 1**: Build the base query with `deleted_at: None` and `published_at: {"$ne": None}`. Decode cursor and add `$or` tiebreaker. Sort descending. Use the fetch+has-more pattern.

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def list_posts(
    self, cursor=None, limit=20
) -> Tuple[List[Post], bool]:
    query = {
        "deleted_at": None,
        "published_at": {"$ne": None}
    }

    if cursor:
        cursor_data = decode_cursor(cursor)
        cursor_published_at = datetime.fromisoformat(cursor_data["published_at"])
        cursor_id = PydanticObjectId(cursor_data["id"])
        query["$or"] = [
            {"published_at": {"$lt": cursor_published_at}},
            {
                "published_at": cursor_published_at,
                "_id": {"$lt": cursor_id}
            }
        ]

    limit = min(limit, self.max_page_size)
    posts = await Post.find(query).sort(
        [("published_at", -1), ("_id", -1)]
    ).limit(limit + 1).to_list()

    has_more = len(posts) > limit
    if has_more:
        posts = posts[:limit]

    return posts, has_more
```
</details>

---

### Exercise 5.4: List User Posts (Nested Field Query)

**Concept**: Querying into denormalized embedded documents using dot notation, combined with cursor pagination

#### The Method Signature

```python
async def list_user_posts(
    self,
    user_id: str,
    cursor: Optional[str] = None,
    limit: int = 20,
    include_unpublished: bool = False
) -> Tuple[List[Post], bool]:
```

#### Nested Field Queries

This is where the `author.user_id` index pays off:

```python
# MongoDB can query INSIDE embedded documents using dot notation
query = {
    "author.user_id": PydanticObjectId(user_id),
    "deleted_at": None
}
```

This is different from a top-level field query. MongoDB traverses into the `author` embedded document and matches on `user_id` within it. The compound index `[("author.user_id", 1), ("status", 1), ("created_at", -1)]` makes this efficient.

#### Published vs All Posts

```python
# If the requester is viewing their own posts, they can see unpublished ones
if not include_unpublished:
    query["published_at"] = {"$ne": None}
```

> **Hint Level 1**: Same cursor pagination pattern as `list_posts`, but add `author.user_id` to the base query. Use `created_at` instead of `published_at` for sort order (unpublished posts don't have `published_at`).

<details>
<summary>Full Implementation</summary>

```python
async def list_user_posts(
    self, user_id: str, cursor=None, limit=20, include_unpublished=False
) -> Tuple[List[Post], bool]:
    await self._get_user(user_id)

    query = {
        "author.user_id": PydanticObjectId(user_id),
        "deleted_at": None
    }

    if not include_unpublished:
        query["published_at"] = {"$ne": None}

    if cursor:
        cursor_data = decode_cursor(cursor)
        cursor_time = datetime.fromisoformat(cursor_data["published_at"])
        cursor_id = PydanticObjectId(cursor_data["id"])
        query["$or"] = [
            {"created_at": {"$lt": cursor_time}},
            {
                "created_at": cursor_time,
                "_id": {"$lt": cursor_id}
            }
        ]

    limit = min(limit, self.max_page_size)
    posts = await Post.find(query).sort(
        [("created_at", -1), ("_id", -1)]
    ).limit(limit + 1).to_list()

    has_more = len(posts) > limit
    if has_more:
        posts = posts[:limit]

    return posts, has_more
```
</details>

---

### Exercise 5.5: Single Post Operations (Get, Update, Delete)

**Concept**: Ownership checks, partial updates, soft delete pattern

#### 5.5a: `get_post(post_id)` - Simple Read

```python
async def get_post(self, post_id: str) -> Post:
    return await self._get_post(post_id)
```

That's it! The `_get_post` helper already handles the deleted check and anti-enumeration.

---

#### 5.5b: `update_post(...)` - Ownership + Partial Update

```
Algorithm:
1. Get post (with deleted check)
2. Check ownership: only author can edit
3. Apply partial updates (only non-None fields)
4. Save (save() override handles updated_at)
```

**The ownership check**:
```python
if str(post.author.user_id) != user_id:
    raise ValueError("Post not found")  # Anti-enumeration
```

> **Why "Post not found" instead of "Access denied"?** Anti-enumeration. If we said "Access denied", an attacker would know the post EXISTS but they can't access it. By saying "Not found", they can't distinguish between "doesn't exist" and "not yours".

**Partial updates**: Only update fields that are provided (not None):
```python
if text_content is not None:
    post.text_content = text_content
if media is not None:
    post.media = self._build_media_list(media)
if link_preview is not None:
    post.link_preview = self._build_link_preview(link_preview)
```

<details>
<summary>Full Implementation</summary>

```python
async def update_post(
    self, post_id: str, user_id: str,
    text_content=None, media=None, link_preview=None
) -> Post:
    post = await self._get_post(post_id)

    if str(post.author.user_id) != user_id:
        raise ValueError("Post not found")

    if text_content is not None:
        post.text_content = text_content
    if media is not None:
        post.media = self._build_media_list(media)
    if link_preview is not None:
        post.link_preview = self._build_link_preview(link_preview)

    await post.save()
    return post
```
</details>

---

#### 5.5c: `delete_post(...)` - Soft Delete

**What it does**: Sets `deleted_at` instead of actually removing the document.

```
Algorithm:
1. Get post (with deleted check)
2. Check ownership: only author can delete
3. Set deleted_at = utc_now()
4. Save
5. Emit Kafka event
```

> **Why soft delete?** Hard deletion (removing the document) is irreversible. Soft delete lets us:
> - Restore accidentally deleted posts
> - Keep data for analytics
> - Maintain referential integrity (comments still reference the post ID)
> - The `deleted_at` index makes it cheap to filter them out of queries.

<details>
<summary>Full Implementation</summary>

```python
async def delete_post(self, post_id: str, user_id: str) -> Post:
    post = await self._get_post(post_id)

    if str(post.author.user_id) != user_id:
        raise ValueError("Post not found")

    post.deleted_at = utc_now()
    await post.save()

    if self._kafka:
        self._kafka.emit(
            topic=Topic.POST,
            action="deleted",
            entity_id=oid_to_str(post.id),
            data={
                "author_id": oid_to_str(post.author.user_id),
                "deleted_by": user_id,
            },
        )

    return post
```
</details>

---

### Exercise 5.6: Increment Stats (`$inc` Atomic Counters)

**Concept**: Using MongoDB's `$inc` operator for atomic counter updates, avoiding read-modify-write race conditions

#### The Problem

When updating a counter like `stats.like_count`, the naive approach is:

```python
# WRONG - Race condition!
post = await Post.get(post_id)
post.stats.like_count += 1
await post.save()

# If two users like at the same time:
# Thread A: reads like_count = 5
# Thread B: reads like_count = 5
# Thread A: saves like_count = 6
# Thread B: saves like_count = 6  (should be 7!)
```

#### The Solution: `$inc`

MongoDB's `$inc` operator atomically increments a field at the database level:

```python
# CORRECT - Atomic!
from beanie.operators import Inc

await Post.find_one(
    Post.id == PydanticObjectId(post_id)
).update(Inc({Post.stats.view_count: 1}))
```

Or using raw update expression:

```python
await Post.find_one({"_id": PydanticObjectId(post_id)}).update(
    {"$inc": {"stats.view_count": 1}}
)
```

#### The Method Signature

```python
async def increment_stat(
    self,
    post_id: str,
    stat_field: str,
    amount: int = 1
) -> None:
```

#### Allowed Stats Fields

```python
ALLOWED_STAT_FIELDS = {
    "view_count", "like_count", "comment_count",
    "share_count", "save_count"
}
```

> **Why limit which fields can be incremented?** We don't want callers to increment `engagement_rate` (which should be calculated, not incremented) or arbitrary fields.

> **Hint Level 1**: Validate `stat_field` is in ALLOWED_STAT_FIELDS. Validate `post_id` is valid. Use `$inc` with dot notation: `f"stats.{stat_field}"`.

<details>
<summary>Full Implementation</summary>

```python
ALLOWED_STAT_FIELDS = {
    "view_count", "like_count", "comment_count",
    "share_count", "save_count"
}

async def increment_stat(self, post_id: str, stat_field: str, amount: int = 1) -> None:
    if stat_field not in self.ALLOWED_STAT_FIELDS:
        raise ValueError(f"Invalid stat field: {stat_field}")

    try:
        oid = PydanticObjectId(post_id)
    except Exception:
        raise ValueError("Invalid post ID")

    result = await Post.find_one(
        {"_id": oid, "deleted_at": None}
    ).update(
        {"$inc": {f"stats.{stat_field}": amount}}
    )

    if not result:
        raise ValueError("Post not found")
```
</details>

---

### Exercise 5.7: Update Last Comment Timestamp

**Concept**: Using `$set` on a nested field, combining with `$inc` in a single update

When a comment is added to a post, we need to:
1. Increment `stats.comment_count` by 1
2. Set `stats.last_comment_at` to the current time

Both can be done in a single atomic update:

```python
async def record_comment(self, post_id: str) -> None:
    try:
        oid = PydanticObjectId(post_id)
    except Exception:
        raise ValueError("Invalid post ID")

    result = await Post.find_one(
        {"_id": oid, "deleted_at": None}
    ).update({
        "$inc": {"stats.comment_count": 1},
        "$set": {"stats.last_comment_at": utc_now()}
    })

    if not result:
        raise ValueError("Post not found")
```

> **Why combine `$inc` and `$set` in one update?** Because MongoDB applies the entire update document atomically. If we did two separate updates, another operation could happen between them.

---

## 6. VERIFICATION CHECKLIST

| # | Test | What to Verify |
|---|------|---------------|
| 1 | Create a post (published) | Post has `published_at` set, `PostAuthor` has correct user data |
| 2 | Create a post (unpublished) | `published_at` is None |
| 3 | Get a post by ID | Returns the post with all embedded data |
| 4 | Get a deleted post | Returns "Post not found" |
| 5 | List posts | Pagination works, only published + non-deleted visible |
| 6 | List posts with cursor | Second page returns different posts, no duplicates |
| 7 | List user posts | Only that user's posts returned, `author.user_id` filter works |
| 8 | List user posts (include_unpublished) | Also shows unpublished posts |
| 9 | Update a post (as author) | Text changes, `updated_at` changes |
| 10 | Update a post (as non-author) | Returns "Post not found" |
| 11 | Delete a post (as author) | `deleted_at` is set, post no longer in feeds |
| 12 | Delete a post (as non-author) | Returns "Post not found" |
| 13 | Increment view_count | `stats.view_count` increases by 1 |
| 14 | Increment invalid stat | Returns error |
| 15 | Record comment | `stats.comment_count` increases, `stats.last_comment_at` set |

---

## 7. ADVANCED CHALLENGES

### Challenge 1: The `$or` Tiebreaker and Indexes

Run `.explain("executionStats")` on the list_posts query:

```javascript
db.posts.find({
  deleted_at: null,
  published_at: { $ne: null },
  $or: [
    { published_at: { $lt: ISODate("2024-01-15") } },
    { published_at: ISODate("2024-01-15"), _id: { $lt: ObjectId("...") } }
  ]
}).sort({ published_at: -1, _id: -1 }).limit(21)
```

**Questions**:
1. Which index does MongoDB choose for this query?
2. How many documents does it examine vs. return?
3. Would adding a compound index on `(published_at, _id)` help?
4. Does the `$or` force a collection scan, or can MongoDB use an index?

### Challenge 2: Denormalized Author Data Staleness

When a user changes their `display_name` or `avatar`, every post they've ever created still has the OLD values in `author.display_name` and `author.avatar`.

**Questions**:
1. How would you detect stale author data? (Hint: compare `post.author.display_name` to `user.profile.display_name`)
2. Design a background job that refreshes denormalized author data. What query would it use to find affected posts?
3. How would you use `updateMany` to batch-update all posts by a specific author?

```javascript
// Example batch update:
db.posts.updateMany(
  { "author.user_id": ObjectId("user123") },
  { $set: {
    "author.display_name": "New Name",
    "author.avatar": "https://new-avatar.png"
  }}
)
```

4. What index supports this `updateMany`? (Check Index #1: `author.user_id`)

### Challenge 3: Race Condition in Stat Counters

What happens if two users try to like a post at the exact same moment?

**With `$inc`** (our approach):
```
Thread A: $inc stats.like_count 1  -> MongoDB atomically: 5 -> 6
Thread B: $inc stats.like_count 1  -> MongoDB atomically: 6 -> 7
Result: 7 (correct!)
```

**Without `$inc`** (read-modify-write):
```
Thread A: read like_count = 5
Thread B: read like_count = 5
Thread A: save like_count = 6
Thread B: save like_count = 6
Result: 6 (WRONG - lost an update!)
```

**Questions**:
1. What other operations in MongoDB are atomic besides `$inc`? (Hint: `$set`, `$push`, `$addToSet`, `$pull`)
2. How does `$inc` with a negative number work? (It decrements - useful for "unlike")
3. Can you `$inc` multiple fields in one operation? (Yes! We did this in Exercise 5.7)

---

## 8. WHAT'S NEXT

Congratulations! You've built the **social content engine** of the platform.

**Concepts you mastered**:
- Cursor pagination with `$or` tiebreaker on `published_at`/`_id`
- Base64-encoded composite cursors
- Nested field queries (`author.user_id`)
- `$inc` for atomic counter updates
- `$set` + `$inc` in a single atomic update
- Cross-collection reads (users)
- Denormalized author data from User -> PostAuthor
- Soft delete pattern with `deleted_at`
- Anti-enumeration (always "Post not found")
- Multiple embedded document types (4 types)

**What comes next**:

**TASK_07: Order Service** - The e-commerce transaction engine. Orders connect Users to Products with status tracking, fulfillment, and payment workflows. You'll build:
- Order creation with product snapshot denormalization
- Multi-item orders with per-item fulfillment tracking
- Order status state machine (pending -> confirmed -> shipped -> delivered)
- Cross-collection validation (user must exist, products must exist)
- Order number generation
