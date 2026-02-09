# TASK 05: Post Service - Social Content & Feed Operations

## 1. MISSION BRIEFING

Posts are the **social heartbeat** of the platform. They are the content that fills user feeds and the global timeline. Every post is authored by a user and can carry text, images, videos, links, or polls. Posts can be created as drafts or published immediately.

This task introduces **denormalized author snapshots** - storing a copy of the author's data inside each post so feed queries don't need joins.

### What You Will Build
The `PostService` class in `apps/mongo_backend/services/post.py` - 7 methods covering post CRUD, a draft/publish lifecycle, and feed listing with author filtering.

### What You Will Learn

| MongoDB Concept | Where You'll Use It |
|----------------|-------------------|
| **Denormalized author snapshot** | `PostAuthor` embedded from User data at creation time |
| **Cross-collection reads** | User lookup for author denormalization (via utility function) |
| **Soft delete pattern** | Using `deleted_at` timestamp instead of actual deletion |
| **Draft/publish lifecycle** | `published_at` field gates whether a post appears in feeds |
| **Nested field queries** | `author.user_id` for filtering posts by author |
| **Skip/limit pagination** | Paginated post listing |
| **Multiple embedded types** | 4 embedded types (PostAuthor, MediaAttachment, LinkPreview, PostStats) |
| **Partial update pattern** | Updating only provided fields from `UpdatePostRequest` |

### How This Differs From Previous Tasks

| Aspect | Product (04) | Post (05) |
|--------|-------------|-----------|
| Collections touched | 2 (products + suppliers) | 2 (posts + users for author lookup) |
| Pagination | skip/limit with `$ne`/`$in` filters | skip/limit with `deleted_at`/`published_at` filters |
| Embedded doc queries | `supplier_id` (top-level) | **`author.user_id`** (nested field in embedded doc) |
| Denormalized data | `supplier_info` (plain Dict) | **`PostAuthor`** (typed embedded document) |
| Delete pattern | Status-based (`DELETED` enum) | **Soft delete with `deleted_at` timestamp** |
| Lifecycle | 5-state machine (DRAFT→ACTIVE→...) | **Simple draft/publish** (`published_at` = None or timestamp) |
| Author lookup | Service validates supplier directly | **Utility function** `build_post_author()` handles User lookup |

---

## 2. BEFORE YOU START

### Prerequisites
- **TASK_01 (User) must be complete** - Posts require an author (User)
- Have at least one user created from previous tasks

### Files You MUST Read Before Coding

| Order | File | Why |
|-------|------|-----|
| 1 | `shared/models/post.py` | The data model - 2 enums, 4 embedded types, 2 indexes |
| 2 | `apps/mongo_backend/schemas/post.py` | Request schemas - `CreateCommunityPostRequest`, `UpdatePostRequest` |
| 3 | `apps/mongo_backend/routes/post.py` | Endpoints: CRUD + publish lifecycle |
| 4 | `apps/mongo_backend/utils/post_utils.py` | `build_post_author()`, `post_response()`, `get_post_or_404()` |
| 5 | `shared/models/user.py` | User model - you'll read `user.profile.display_name` and `user.profile.avatar` for author snapshot |

### The Data Flow

```
HTTP Request
    │
    ▼
┌─────────┐   Extracts X-User-ID header
│  Route   │   (required for write operations)
│          │
│  Calls   │
│  your    │
│  service │
    │
    ▼
┌──────────────────────────────────────────────────────┐
│              PostService (YOU WRITE THIS)               │
│                                                          │
│  Reads from TWO collections (via utility function):      │
│  ├── posts (main CRUD + feeds)                           │
│  └── users (author validation + denormalization)         │
│                                                          │
│  Writes to ONE collection:                               │
│  └── posts (insert, update, soft delete)                 │
│                                                          │
│  Emits Kafka events:                                     │
│  └── EventType.POST_CREATED, POST_UPDATED,               │
│       POST_PUBLISHED, POST_DELETED                       │
└──────────────────────────────────────────────────────┘
    │
    ▼
┌─────────┐
│  Route   │   Wraps returned Post in post_response()
│          │   → JSON-safe dict via model_dump(mode="json")
└─────────┘
```

> **Key pattern**: The route layer calls `post_response(post)` to convert the returned `Post` document into a JSON dict. Your service returns `Post` documents (or `None` for delete).

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
│
├── post_type: PostType                    ← text/image/video/link/poll
│
├── author: PostAuthor                      ← Denormalized from User
│   ├── user_id: PydanticObjectId
│   ├── display_name: str
│   ├── avatar: str
│   └── author_type: AuthorType
│
├── text_content: str                       ← Post text (max 5000 chars)
│
├── media: List[MediaAttachment]            ← Images, videos, GIFs
│   ├── media_type: str
│   ├── media_url: HttpUrl
│   ├── thumbnail_url: Optional[HttpUrl]
│   ├── width, height: Optional[int]
│   ├── duration_seconds: Optional[int]
│   └── size_bytes: Optional[int]
│
├── link_preview: Optional[LinkPreview]     ← Shared link metadata
│   ├── url: HttpUrl
│   ├── title: str
│   ├── description: Optional[str]
│   ├── image: Optional[HttpUrl]
│   └── site_name: Optional[str]
│
├── stats: PostStats                        ← Engagement counters
│   ├── view_count, like_count, comment_count: int (default 0)
│   ├── share_count, save_count: int (default 0)
│   ├── engagement_rate: float (default 0.0)
│   └── last_comment_at: Optional[datetime]
│
├── deleted_at: Optional[datetime]          ← Soft delete timestamp
├── published_at: Optional[datetime]        ← Publication timestamp (None = draft)
├── created_at: datetime
└── updated_at: datetime                    ← AUTO-UPDATED ON save()
```

### Index Analysis (2 indexes)

```python
indexes = [
    # Index 1: Author's posts (for author_id filter)
    [("author.user_id", 1), ("deleted_at", 1), ("created_at", -1)],
    # → Used by: list_posts(author_id=...) - queries nested field!

    # Index 2: Published posts timeline
    [("deleted_at", 1), ("published_at", -1)],
    # → Used by: list_posts() - published feed sorted by date
]
```

> **Note on Index 1**: MongoDB can index fields **inside embedded documents** using dot notation. The `author.user_id` index means querying `{"author.user_id": some_id}` is efficient even though `author` is an embedded object.

### Key Model Observations

| Feature | Detail |
|---------|--------|
| **Collection name** | `posts` (set in `Settings.name`) |
| **Soft delete** | `deleted_at` field (None = active, timestamp = deleted) |
| **Draft/Publish** | `published_at` field (None = draft, timestamp = published) |
| **Timestamps** | `save()` override auto-updates `updated_at` |
| **PostStats defaults** | All counters default to 0, `engagement_rate` to 0.0 |

### Understanding the Draft/Publish Lifecycle

```
CREATE (is_draft=false)  →  published_at = utc_now()  →  Visible in feeds
CREATE (is_draft=true)   →  published_at = None       →  NOT visible in feeds
                              │
                              │  publish_post()
                              ▼
                         published_at = utc_now()       →  Now visible in feeds
```

The `list_posts` query filters `published_at: {"$ne": None}` to only show published posts.

---

## 4. THE SERVICE CONTRACT

Your service file: `apps/mongo_backend/services/post.py`

### Class Setup

```python
class PostService:
    """Handles post DB operations."""

    def __init__(self):
        self._kafka = get_kafka_producer()
```

### Method Overview

| # | Method | MongoDB Concepts | Difficulty |
|---|--------|-----------------|-----------|
| 1 | `_build_media(media_list)` | Static helper - convert request objects to model objects | Easy |
| 2 | `_build_link_preview(lp)` | Static helper - convert request object to model object | Easy |
| 3 | `create_post(user_id, body)` | Cross-collection author lookup + insert | Medium |
| 4 | `get_post(post_id)` | `Post.get()` + soft delete check | Easy |
| 5 | `list_posts(skip, limit, author_id)` | `find` with `deleted_at`/`published_at` filters + nested `author.user_id` | Medium |
| 6 | `update_post(post_id, body)` | Get + partial update + `.save()` | Easy |
| 7 | `delete_post(post_id)` | Soft delete with `deleted_at = utc_now()` | Easy |
| 8 | `publish_post(post_id)` | Draft gate + set `published_at` | Easy |

### Error Types

The service uses errors from `shared.errors`:
- **`NotFoundError`** - when post or user is not found
- **`ValidationError`** - when trying to publish an already-published post

### Important: `build_post_author()` Utility

The author denormalization logic lives in `apps/mongo_backend/utils/post_utils.py`, NOT in the service class:

```python
# From utils/post_utils.py:
async def build_post_author(user_id: str) -> PostAuthor:
    """Look up a User and build a PostAuthor snapshot."""
    user = await User.get(PydanticObjectId(user_id))
    # ... validates user exists and not deleted ...
    return PostAuthor(
        user_id=user.id,
        display_name=user.profile.display_name,
        avatar=user.profile.avatar,
        author_type=AuthorType.USER,
    )
```

Your service calls this function: `author = await build_post_author(user_id)`

### Return Type Convention

- `create_post`, `get_post`, `update_post`, `publish_post` → return `Post` document
- `delete_post` → returns `None`
- `list_posts` → returns `list[Post]`

The route layer formats via `post_response(post)`.

---

## 5. EXERCISES

---

### Exercise 5.1: Helper Methods - Building Embedded Documents

**Concept**: Converting typed request objects (from Pydantic schemas) into model embedded documents

#### 5.1a: `_build_media(media_list)` - Static Method

**What it does**: Converts a list of `MediaAttachmentRequest` objects into `MediaAttachment` model objects. Returns an empty list if input is falsy.

**Input**: `media_list` is a `list` of request objects with `.media_type`, `.media_url`, `.thumbnail_url`, `.width`, `.height`, `.duration_seconds`, `.size_bytes` attributes. Can also be `None`.
**Output**: `list[MediaAttachment]`

```python
# Each item has attributes accessed with dot notation:
# m.media_type, m.media_url, m.thumbnail_url, etc.
```

<details>
<summary>Hint Level 1 - Direction</summary>

Check for falsy input first (return empty list). Then use a list comprehension mapping each request field to the model constructor.
</details>

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
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
```
</details>

---

#### 5.1b: `_build_link_preview(lp)` - Static Method

**What it does**: Converts a `LinkPreviewRequest` object into a `LinkPreview` model object. Returns `None` if input is falsy.

**Input**: `lp` is a request object with `.url`, `.title`, `.description`, `.image`, `.site_name`. Can be `None`.
**Output**: `Optional[LinkPreview]`

<details>
<summary>Hint Level 1 - Direction</summary>

Check for falsy input (return None). Otherwise, build a `LinkPreview` from the request fields.
</details>

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
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
```
</details>

---

### Exercise 5.2: Create Post

**Concept**: Cross-collection author denormalization, embedded document construction, draft/publish logic

#### The Method Signature

```python
async def create_post(self, user_id: str, body) -> Post:
    """Create a new post. `body` is a CreateCommunityPostRequest."""
```

> **Important**: `body` is a `CreateCommunityPostRequest` Pydantic object - access fields with dot notation (`body.post_type`, `body.text_content`, `body.media`, `body.link_preview`, `body.is_draft`).

#### Step-by-Step Algorithm

```
1. Build PostAuthor snapshot from user (cross-collection)
   └── author = await build_post_author(user_id)
   └── This utility function fetches the User, validates they exist
       and aren't deleted, then returns a PostAuthor embedded doc

2. Build Post document:
   ├── post_type = PostType(body.post_type)
   ├── author = author (from step 1)
   ├── text_content = body.text_content
   ├── media = self._build_media(body.media)
   ├── link_preview = self._build_link_preview(body.link_preview)
   └── published_at = None if body.is_draft else utc_now()

3. await post.insert()

4. Emit Kafka event: EventType.POST_CREATED

5. Return the Post document
```

#### The Denormalized Author Pattern

```python
# Why denormalize author data?
# Every time we display a post in a feed, we need the author's name and avatar.
# Without denormalization, we'd need a separate User query for every post
# in the feed (N+1 problem).
# By storing a PostAuthor snapshot in each post, the feed query returns
# everything in one go.

# The build_post_author utility:
author = await build_post_author(user_id)
# → PostAuthor(user_id=..., display_name="Jane", avatar="https://...", author_type="user")
```

> **Trade-off**: If the user changes their name or avatar, existing posts still show the OLD values. This is usually acceptable for social platforms - a background job can refresh denormalized data if needed.

#### Draft vs Published

```python
# If body.is_draft is True → create as draft (won't appear in feeds)
# If body.is_draft is False → publish immediately
published_at = None if body.is_draft else utc_now()
```

<details>
<summary>Hint Level 1 - Direction</summary>

Call `build_post_author(user_id)` to get the author snapshot, then construct a `Post` with all the body fields and your helper methods. Set `published_at` based on `body.is_draft`. Insert, emit Kafka, return.
</details>

<details>
<summary>Hint Level 2 - Key Details</summary>

```python
# The author comes from a utility function, not built in-service:
from utils.post_utils import build_post_author
author = await build_post_author(user_id)

# Note: PostStats is auto-initialized with defaults via default_factory
# so you don't need to explicitly create it
```
</details>

<details>
<summary>Hint Level 3 - Full Implementation</summary>

```python
async def create_post(self, user_id: str, body) -> Post:
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
```
</details>

#### Verification

```bash
# Create a published post (replace USER_ID with an actual user ID):
curl -s -X POST http://localhost:8000/posts \
  -H "Content-Type: application/json" \
  -H "X-User-ID: USER_ID" \
  -d '{
    "community_id": "test-community",
    "post_type": "text",
    "text_content": "Hello world! My first post on this platform.",
    "is_draft": false
  }' | python3 -m json.tool

# Expected: Post with published_at set, author.display_name filled in

# Create a draft post:
curl -s -X POST http://localhost:8000/posts \
  -H "Content-Type: application/json" \
  -H "X-User-ID: USER_ID" \
  -d '{
    "community_id": "test-community",
    "post_type": "image",
    "text_content": "Check out this photo!",
    "media": [{"media_type": "image", "media_url": "https://example.com/photo.jpg"}],
    "is_draft": true
  }' | python3 -m json.tool

# Expected: Post with published_at = null (draft)
```

```javascript
// In MongoDB shell - verify the post was created:
db.posts.findOne({ text_content: "Hello world! My first post on this platform." })

// Check the denormalized author data:
db.posts.findOne(
  { text_content: /Hello world/ },
  { "author": 1, "published_at": 1, "post_type": 1 }
)
```

---

### Exercise 5.3: Get Post

**Concept**: `Document.get()` with `PydanticObjectId`, soft delete check

#### The Method Signature

```python
async def get_post(self, post_id: str) -> Post:
```

#### Algorithm

```
1. Fetch post by ID using Post.get(PydanticObjectId(post_id))
   └── Wrap in try/except for invalid ObjectIds
2. If post is None OR post.deleted_at is set → raise NotFoundError
3. Return the post
```

> **Anti-enumeration**: Whether the post doesn't exist or was soft-deleted, the same "Post not found" error is returned. An attacker can't distinguish between the two.

<details>
<summary>Hint Level 1 - Direction</summary>

Same pattern as `get_product` from TASK_04, but check `post.deleted_at` instead of `post.status == DELETED`.
</details>

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def get_post(self, post_id: str) -> Post:
    try:
        post = await Post.get(PydanticObjectId(post_id))
    except Exception:
        raise NotFoundError("Post not found")
    if not post or post.deleted_at:
        raise NotFoundError("Post not found")
    return post
```
</details>

#### Verification

```bash
# Get the post you created:
curl -s http://localhost:8000/posts/POST_ID | python3 -m json.tool

# Try a non-existent ID:
curl -s http://localhost:8000/posts/000000000000000000000000

# Expected: 404 "Post not found"
```

---

### Exercise 5.4: List Posts (Feed Query)

**Concept**: Multi-condition filter with `deleted_at`, `published_at`, optional `author.user_id` nested field query, skip/limit pagination

#### The Method Signature

```python
async def list_posts(
    self,
    skip: int = 0,
    limit: int = 20,
    author_id: Optional[str] = None,
) -> list[Post]:
```

#### Query Building

```python
# Base query: only show published, non-deleted posts
query = {
    "deleted_at": None,                # Not soft-deleted
    "published_at": {"$ne": None},     # Only published posts (not drafts)
}

# Optional author filter (nested field query!):
if author_id:
    query["author.user_id"] = author_id
```

> **Nested field query**: `author.user_id` uses dot notation to query into the `PostAuthor` embedded document. MongoDB traverses into the `author` object and matches on `user_id` within it. The compound index `[("author.user_id", 1), ("deleted_at", 1), ("created_at", -1)]` makes this efficient.

#### The Fetch Pattern

```python
return (
    await Post.find(query)
    .sort("-published_at")          # Most recent published first
    .skip(skip)
    .limit(min(limit, 100))         # Cap at 100 max
    .to_list()
)
```

<details>
<summary>Hint Level 1 - Direction</summary>

Build a query dict with `deleted_at: None` and `published_at: {"$ne": None}`. Optionally add `author.user_id` filter. Use Beanie's `find().sort().skip().limit().to_list()` chain.
</details>

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
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
```
</details>

#### Verification

```bash
# List all published posts:
curl -s "http://localhost:8000/posts" | python3 -m json.tool

# List posts by a specific author:
curl -s "http://localhost:8000/posts?author_id=USER_ID" | python3 -m json.tool

# Pagination:
curl -s "http://localhost:8000/posts?skip=0&limit=5" | python3 -m json.tool

# Note: draft posts should NOT appear in this listing
```

```javascript
// In MongoDB shell - verify the query:
db.posts.find({
    deleted_at: null,
    published_at: { $ne: null }
}).sort({ published_at: -1 }).limit(20)

// With author filter:
db.posts.find({
    deleted_at: null,
    published_at: { $ne: null },
    "author.user_id": ObjectId("USER_ID")
}).sort({ published_at: -1 })
```

---

### Exercise 5.5: Update Post (Partial Update)

**Concept**: Get-then-modify with field-by-field conditional update, calling helper methods for nested objects

#### The Method Signature

```python
async def update_post(self, post_id: str, body) -> Post:
    """Partial update. `body` is an UpdatePostRequest."""
```

#### Algorithm

```
1. Get post (reuse self.get_post - checks existence + not deleted)
2. For each field in UpdatePostRequest, if value is not None, update:
   ├── body.text_content → post.text_content
   ├── body.media → self._build_media(body.media) → post.media
   └── body.link_preview → self._build_link_preview(body.link_preview) → post.link_preview
3. await post.save()  (auto-updates updated_at)
4. Emit EventType.POST_UPDATED Kafka event
5. Return updated post
```

> **Note**: Unlike the old design, there is NO ownership check in the service. The route layer extracts `X-User-ID` header but the service trusts the caller.

<details>
<summary>Hint Level 1 - Direction</summary>

Fetch with `self.get_post()`, then check each body field for `is not None` and apply. Use `_build_media` and `_build_link_preview` for embedded objects. Save and emit Kafka event.
</details>

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def update_post(self, post_id: str, body) -> Post:
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
```
</details>

#### Verification

```bash
# Update the post text:
curl -s -X PATCH http://localhost:8000/posts/POST_ID \
  -H "Content-Type: application/json" \
  -H "X-User-ID: USER_ID" \
  -d '{"post_id": "POST_ID", "version": 1, "text_content": "Updated content!"}' | python3 -m json.tool

# Expected: Post with updated text_content, updated_at changed
```

---

### Exercise 5.6: Delete Post (Soft Delete)

**Concept**: Setting `deleted_at` timestamp instead of removing the document

#### The Method Signature

```python
async def delete_post(self, post_id: str) -> None:
```

#### Algorithm

```
1. Get post (self.get_post - checks existence + not already deleted)
2. Set post.deleted_at = utc_now()
3. await post.save()
4. Emit EventType.POST_DELETED Kafka event
```

> **Why soft delete?** Hard deletion (removing the document) is irreversible. Soft delete lets us:
> - Restore accidentally deleted posts
> - Keep data for analytics
> - Maintain referential integrity
> - The `deleted_at` index makes it cheap to filter them out of queries

> **Note**: The method returns `None` (not the post). The route returns HTTP 204 No Content.

<details>
<summary>Hint Level 1 - Direction</summary>

Fetch with `self.get_post()`, set `deleted_at` to current time, save, emit Kafka event with just the post ID.
</details>

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def delete_post(self, post_id: str) -> None:
    post = await self.get_post(post_id)
    post.deleted_at = utc_now()
    await post.save()

    self._kafka.emit(
        event_type=EventType.POST_DELETED,
        entity_id=oid_to_str(post.id),
        data={"post_id": oid_to_str(post.id)},
    )
```
</details>

#### Verification

```bash
# Delete a post:
curl -s -X DELETE http://localhost:8000/posts/POST_ID \
  -H "X-User-ID: USER_ID" -w "\nHTTP Status: %{http_code}\n"

# Expected: HTTP 204 No Content

# Verify it's gone from GET:
curl -s http://localhost:8000/posts/POST_ID

# Expected: 404 "Post not found"

# Verify it's gone from list:
curl -s "http://localhost:8000/posts" | python3 -m json.tool
# The deleted post should NOT appear
```

```javascript
// In MongoDB shell - the document still exists but has deleted_at set:
db.posts.findOne({ _id: ObjectId("POST_ID") }, { deleted_at: 1, text_content: 1 })
// → { deleted_at: ISODate("2025-..."), text_content: "..." }
```

---

### Exercise 5.7: Publish Post (Draft to Published)

**Concept**: Draft gate + setting `published_at`, `ValidationError` for already-published posts

#### The Method Signature

```python
async def publish_post(self, post_id: str) -> Post:
```

#### Algorithm

```
1. Get post (self.get_post - checks existence + not deleted)
2. Check if already published: if post.published_at is not None → raise ValidationError
3. Set post.published_at = utc_now()
4. await post.save()
5. Emit EventType.POST_PUBLISHED Kafka event
6. Return published post
```

> **Draft gate**: Only unpublished posts (where `published_at is None`) can be published. Trying to publish an already-published post is an error.

<details>
<summary>Hint Level 1 - Direction</summary>

Fetch with `self.get_post()`, check `published_at` is None (draft), set it to `utc_now()`, save, emit Kafka.
</details>

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
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
```
</details>

#### Verification

```bash
# First, create a draft post:
curl -s -X POST http://localhost:8000/posts \
  -H "Content-Type: application/json" \
  -H "X-User-ID: USER_ID" \
  -d '{
    "community_id": "test-community",
    "post_type": "text",
    "text_content": "This is a draft that I will publish later.",
    "is_draft": true
  }' | python3 -m json.tool

# Note the post ID and that published_at is null

# Publish the draft:
curl -s -X POST http://localhost:8000/posts/DRAFT_POST_ID/publish \
  -H "X-User-ID: USER_ID" | python3 -m json.tool

# Expected: Post with published_at now set

# Try to publish again (should fail):
curl -s -X POST http://localhost:8000/posts/DRAFT_POST_ID/publish \
  -H "X-User-ID: USER_ID" | python3 -m json.tool

# Expected: 422 error "Post is already published"

# Now it should appear in the feed:
curl -s "http://localhost:8000/posts" | python3 -m json.tool
# The published post should now be in the list
```

---

## 6. VERIFICATION CHECKLIST

After implementing all methods, verify each one works:

| # | Test | What to Verify |
|---|------|---------------|
| 1 | `_build_media` | Used by create/update - verify media list in response |
| 2 | `_build_link_preview` | Used by create/update - verify link_preview in response |
| 3 | Create a post (published) | `published_at` is set, `PostAuthor` has correct user data |
| 4 | Create a post (draft) | `published_at` is None |
| 5 | Create with media | `media` array populated correctly |
| 6 | Create with link preview | `link_preview` object populated |
| 7 | Get a post by ID | Returns the post with all embedded data |
| 8 | Get a deleted post | Returns "Post not found" |
| 9 | List posts | Only published + non-deleted posts visible |
| 10 | List posts with author_id | Only that author's published posts returned |
| 11 | List posts pagination | skip/limit works correctly |
| 12 | Draft post NOT in list | A draft post should not appear in `list_posts` |
| 13 | Update a post | Text changes, `updated_at` changes |
| 14 | Update media | Old media replaced with new list |
| 15 | Delete a post | `deleted_at` is set, post no longer in feeds |
| 16 | Delete a deleted post | Should fail with "Post not found" |
| 17 | Publish a draft post | `published_at` set, now visible in feeds |
| 18 | Publish an already-published post | Returns ValidationError |

---

## 7. ADVANCED CHALLENGES

### Challenge 1: Denormalized Author Data Staleness

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

### Challenge 2: Combining `$inc` and `$set` for Engagement Stats

The `PostStats` model has counters (view_count, like_count, etc.) that could be updated atomically using MongoDB's `$inc` operator:

```python
# Atomic increment of view count:
await Post.find_one({"_id": PydanticObjectId(post_id)}).update(
    {"$inc": {"stats.view_count": 1}}
)

# Atomic increment + set last_comment_at in one operation:
await Post.find_one({"_id": oid, "deleted_at": None}).update({
    "$inc": {"stats.comment_count": 1},
    "$set": {"stats.last_comment_at": utc_now()}
})
```

**Question**: Why is `$inc` better than the read-modify-write pattern for counters?

```python
# WRONG - Race condition:
post = await Post.get(post_id)
post.stats.view_count += 1
await post.save()
# Two simultaneous likes: both read 5, both save 6 (should be 7!)

# CORRECT - Atomic:
await Post.find_one({"_id": oid}).update({"$inc": {"stats.view_count": 1}})
# Two simultaneous likes: MongoDB atomically does 5→6, then 6→7
```

### Challenge 3: Feed Performance at Scale

With millions of posts, the `list_posts` query `{"deleted_at": None, "published_at": {"$ne": None}}` could become slow.

**Questions**:
1. How does the compound index `[("deleted_at", 1), ("published_at", -1)]` help?
2. Would cursor-based pagination (using `published_at` + `_id` as a tiebreaker) be more efficient than skip/limit at deep offsets? Why?
3. What happens to `skip(10000)` performance vs `{"published_at": {"$lt": last_seen_date}}`?

---

## 8. WHAT'S NEXT

You've built the **social content engine** of the platform.

**Concepts you mastered**:
- Denormalized author snapshot (`PostAuthor` from User data)
- Cross-collection reads (User lookup via utility function)
- Soft delete pattern with `deleted_at` timestamp
- Draft/publish lifecycle with `published_at` gating
- Nested field queries (`author.user_id`)
- Skip/limit pagination with multi-condition filters
- Media attachment and link preview construction
- Partial update pattern with `is not None` checks
- `ValidationError` for invalid state transitions

**TASK_07: Order Service** will introduce:
- Product snapshot denormalization (`ProductSnapshot` frozen at purchase time)
- Order number generation (human-readable `ORD-YYYYMMDD-XXXX` format)
- Multi-collection validation (User must exist + each Product must be ACTIVE)
- Per-item order building (`OrderItem` list with individual pricing)
- Status guard on cancel (only PENDING/CONFIRMED can be cancelled)
- Compound query filters (`customer.user_id` + optional status + sort)
