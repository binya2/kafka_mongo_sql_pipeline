# TASK 01: User Service

## 1. MISSION BRIEFING

You are building the **user management backbone** of a Social Commerce Platform - a system where users discover products, engage with social content, and make purchases without ever leaving the ecosystem.

Every single action on the platform starts with a **User**. Creating accounts, updating profiles, browsing content - these are the foundation on which every other service is built.

### What You Will Build
The `UserService` class - the service layer that handles all user CRUD operations by writing MongoDB queries through Beanie ODM.

### What You Will Learn

| MongoDB Concept | Where You'll Use It |
|----------------|-------------------|
| `find_one()` with nested field match | Checking email uniqueness via `contact_info.primary_email` |
| `Document.get()` by ObjectId | Fetching a user by `_id` |
| `document.insert()` | Creating new user documents |
| `document.save()` | Updating existing documents |
| `find()` with filter + sort + skip/limit | Listing users with pagination |
| Embedded document construction | Building `ContactInfo`, `UserProfile` |
| Soft delete pattern | Setting `deleted_at` instead of removing documents |

---

## 2. BEFORE YOU START

### Prerequisites
- All 5 Docker containers running (`docker compose up -d`)
- Swagger UI accessible at `http://localhost:8000/docs`
- Basic understanding of Python async/await
- No previous tasks required (this is Task 01)

### Files You MUST Read Before Coding

Read these files in this exact order. **Do not skip any.** Understanding the data flow is critical.

#### Step 1: The Model (the data)
```
shared/models/user.py
```
This is your **data contract with MongoDB**. Every field, every embedded document - read it line by line. Pay special attention to:
- The embedded types: `ContactInfo`, `BusinessAddress`, `UserProfile` - these are the building blocks
- The `User` class - this is what gets stored in MongoDB
- The `save()` override - automatically updates `updated_at` on every save
- Note: There are no indexes or Settings class defined - the model is minimal

#### Step 2: The Schema (the API contract)
```
apps/mongo_backend/schemas/user.py
```
This defines **what the route sends you** (Request schemas). Focus on:
- `CreateUserRequest` - fields: `email`, `password`, `display_name`, `phone`, `bio`
- `UpdateUserRequest` - all fields optional: `display_name`, `phone`, `bio`, `avatar`

#### Step 3: The Route (who calls you)
```
apps/mongo_backend/routes/user.py
```
This is the HTTP layer. It receives requests, calls YOUR service methods, and formats responses. Notice:
- The route calls `user_service.create_user()` and expects a `User` document back
- The route wraps your return value with `user_response()` (strips `password_hash`, adds `id`)
- Errors are handled by the global `AppError` exception handlers in `server.py`

#### Step 4: The Utilities (your tools)
```
apps/mongo_backend/utils/password.py          → hash_password(password)
apps/mongo_backend/utils/datetime_utils.py    → utc_now()
apps/mongo_backend/utils/serialization.py     → oid_to_str(object_id)
apps/mongo_backend/kafka/producer.py          → KafkaProducer.emit()
shared/kafka/topics.py                        → EventType.USER_CREATED, etc.
shared/errors.py                              → DuplicateError, NotFoundError, etc.
```

### The Data Flow (understand this before writing any code)

```
HTTP Request
    │
    ▼
┌─────────┐   Validates input      ┌───────────┐
│  Route   │ ──────────────────────▶│  Schema   │
│ user.py  │   (Pydantic)          └───────────┘
│          │
│  Calls   │
│  your    │
│  service │
    │
    ▼
┌──────────────────────────────────────────────┐
│           UserService (YOU WRITE THIS)        │
│                                              │
│  1. Receives clean, validated data           │
│  2. Applies business rules                   │
│  3. Executes MongoDB queries via Beanie      │
│  4. Emits Kafka events                       │
│  5. Returns User document                    │
│                                              │
│  Throws DuplicateError → route returns 409   │
│  Throws NotFoundError  → route returns 404   │
│  Throws Exception      → route returns 500   │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────┐       ┌──────────────┐
│ MongoDB  │       │    Kafka     │
│  users   │       │ user topic   │
│collection│       │  (events)    │
└──────────┘       └──────────────┘
```

---

## 3. MODEL DEEP DIVE

### The User Document Structure

When a User is saved to MongoDB, it looks like this in the database:

```json
{
  "_id": ObjectId("507f1f77bcf86cd799439011"),
  "password_hash": "$2b$12$LJ3m4ys...",
  "contact_info": {
    "primary_email": "jane@example.com",
    "additional_emails": ["jane.work@company.com"],
    "phone": "+1234567890"
  },
  "profile": {
    "display_name": "Jane Smith",
    "avatar": "https://cdn.example.com/avatars/default.jpg",
    "bio": null,
    "date_of_birth": null
  },
  "deleted_at": null,
  "version": 1,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

### Embedded Documents Hierarchy

```
User (Document - stored in "users" collection)
├── password_hash (str)
├── contact_info (ContactInfo)
│   ├── primary_email (EmailStr)          ← UNIQUENESS KEY
│   ├── additional_emails (List[EmailStr])
│   └── phone (Optional[str])
├── profile (UserProfile)
│   ├── display_name (str)
│   ├── avatar (str, default provided)
│   ├── bio (Optional[str])
│   └── date_of_birth (Optional[datetime])
├── deleted_at (Optional[datetime])         ← SOFT DELETE MARKER
├── version (int, default=1)                ← OPTIMISTIC LOCKING
├── created_at (datetime)
└── updated_at (datetime)                   ← AUTO-UPDATED ON save()
```

> **Note:** The model also defines a `BusinessAddress` embedded type (street, city, state, zip_code, country) which is not currently used as a field on User, but is available for future use.

### Index Analysis

The User model does **not** define any custom indexes (no `Settings` class). This means:

- Queries use only the default `_id` index
- Queries on `contact_info.primary_email` will perform a **collection scan** until you add indexes
- This is intentional for learning - you'll see in the Advanced Challenges how to analyze query performance

> **Key insight:** Without indexes, queries like `{"contact_info.primary_email": "jane@example.com"}` do a full collection scan (O(n)). In production, you would add indexes for frequently queried fields. The `_id` lookup via `User.get()` is always fast because MongoDB creates a unique `_id` index automatically.

### Model Methods

The model provides one overridden method:

```python
await user.save()  # Automatically sets updated_at to utc_now() before saving
```

There are no other helper methods on the model - your service layer will implement all business logic directly.

---

## 4. THE SERVICE CONTRACT

Here is every method you must implement, with its complete contract.

### Class Setup

```python
class UserService:
    """Handles user and supplier DB operations."""

    def __init__(self):
        self._kafka = get_kafka_producer()
```

### Method Signatures

| # | Method | MongoDB Operation | Returns |
|---|--------|------------------|---------|
| 1 | `create_user(email, password, display_name, phone, bio)` | `find_one` + `insert` | `User` |
| 2 | `get_user(user_id)` | `get` by ObjectId | `User` |
| 3 | `list_users(skip, limit)` | `find` + filter + skip/limit | `list[User]` |
| 4 | `update_user(user_id, display_name, phone, bio, avatar)` | `get` + `save` | `User` |
| 5 | `delete_user(user_id)` | `get` + `save` (set deleted_at) | `None` |

---

## 5. IMPLEMENTATION EXERCISES

> **Rule:** Implement each exercise completely and verify it works before moving to the next. Each exercise builds on the previous one.

---

### Exercise 5.1: Your First Write - Create User

**Concept:** `find_one()` for uniqueness check + embedded document construction + `insert()`
**Difficulty:** Easy-Medium
**Why this matters:** This is how users enter the platform. You'll check uniqueness, build a complete `User` document from scratch, and persist it to MongoDB.

#### Implement: `create_user(self, email, password, display_name, phone=None, bio=None) -> User`

**Business Rules (implement in this order):**
1. Normalize the email: `email.lower().strip()`
2. Check email uniqueness by querying `contact_info.primary_email`
   - If a user exists with this email → raise `DuplicateError("Email already in use")`
3. Build the User document:
   - `password_hash`: use `hash_password(password)` from `utils/password.py`
   - `contact_info`: create `ContactInfo` with `primary_email=email` and `phone=phone`
   - `profile`: create `UserProfile` with `display_name=display_name` and `bio=bio`
   - All other fields use their defaults (`deleted_at=None`, `version=1`, timestamps auto-set)
4. Insert the document into MongoDB
5. Emit a Kafka event: `EventType.USER_CREATED`
6. Return the User document

**The MongoDB Operations:**

```
Operation 1: FIND_ONE → Check if email already exists
Operation 2: INSERT   → Persist the new User document
```

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

Beanie provides `ModelClass.find_one(filter_dict)` which maps directly to MongoDB's `findOne()`. For nested fields, use dot notation in the filter key. To insert, instantiate the model class and call `await document.insert()`.

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
# Uniqueness check (dot notation for nested field):
existing = await User.find_one({"contact_info.primary_email": email})

# Document construction:
user = User(
    password_hash=hash_password(password),
    contact_info=ContactInfo(primary_email=email, phone=phone),
    profile=UserProfile(display_name=display_name, bio=bio),
)

# Insert:
await user.insert()

# After insert, user.id is populated by MongoDB
```

</details>

<details>
<summary><b>Hint Level 3</b> - Near-complete solution</summary>

```python
async def create_user(self, email, password, display_name, phone=None, bio=None):
    email = email.lower().strip()
    existing = await User.find_one({"contact_info.primary_email": email})
    if existing:
        raise DuplicateError("Email already in use")

    user = User(
        password_hash=hash_password(password),
        contact_info=ContactInfo(primary_email=email, phone=phone),
        profile=UserProfile(display_name=display_name, bio=bio),
    )
    await user.insert()

    self._kafka.emit(
        event_type=EventType.USER_CREATED,
        entity_id=oid_to_str(user.id),
        data=user.model_dump(mode="json"),
    )
    return user
```

</details>

#### Verify Exercise 5.1

```bash
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "consumer@example.com",
    "password": "MySecure1Pass",
    "display_name": "Test Consumer"
  }'
```

**Expected response (201 Created):**
```json
{
  "id": "<some-object-id>",
  "contact_info": {
    "primary_email": "consumer@example.com",
    "additional_emails": [],
    "phone": null
  },
  "profile": {
    "display_name": "Test Consumer",
    "avatar": "https://cdn.example.com/avatars/default.jpg",
    "bio": null,
    "date_of_birth": null
  },
  "deleted_at": null,
  "version": 1,
  "created_at": "...",
  "updated_at": "..."
}
```

> Note: `password_hash` is stripped from the response by the `user_response()` utility in the route layer.

**Test duplicate email (409 Conflict):**
```bash
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "consumer@example.com",
    "password": "MySecure1Pass",
    "display_name": "Duplicate User"
  }'
```

**Verify in MongoDB shell:**
```javascript
db.users.findOne({"contact_info.primary_email": "consumer@example.com"})
```
You should see the full document with all default fields populated.

---

### Exercise 5.2: Get By ID - The Primary Key Lookup

**Concept:** `Document.get(ObjectId)` - fetching by `_id` + soft delete check
**Difficulty:** Easy
**Why this matters:** Every update and delete operation starts by fetching the user first. The `_id` lookup is the fastest possible query in MongoDB.

#### Implement: `get_user(self, user_id: str) -> User`

**Business Rules:**
1. Convert the string `user_id` to a `PydanticObjectId`
   - If invalid → raise `NotFoundError("User not found")`
2. Fetch the user by `_id` using `User.get()`
   - If not found → raise `NotFoundError("User not found")`
3. Check soft delete: if `user.deleted_at` is set → raise `NotFoundError("User not found")`
4. Return the User document

**The MongoDB Operation:**
```
GET by _id  →  User.get(PydanticObjectId("507f1f77bcf86cd799439011"))
```

**Key Distinction:**
```
find_one({"contact_info.primary_email": "x"})  ← Field query (collection scan without index)
User.get(PydanticObjectId("507f..."))           ← _id lookup (uses primary key, always fastest)
```

`User.get()` is Beanie's wrapper around `find_one({"_id": ObjectId(...)})`. The `_id` field has a unique index by default in every MongoDB collection.

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

Wrap the `User.get()` call in a try/except to catch invalid ObjectId strings. An invalid string like `"not-a-valid-id"` will throw an exception when converting to `PydanticObjectId`.

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
try:
    user = await User.get(PydanticObjectId(user_id))
except Exception:
    raise NotFoundError("User not found")
if not user or user.deleted_at:
    raise NotFoundError("User not found")
return user
```

</details>

#### Verify Exercise 5.2

Use the `id` from the user you created in Exercise 5.1:
```bash
curl http://localhost:8000/users/<user-id>
```

**Expected (200 OK):**
```json
{
  "id": "<user-id>",
  "contact_info": { ... },
  "profile": { ... },
  ...
}
```

**Non-existent user (404):**
```bash
curl http://localhost:8000/users/000000000000000000000000
```

---

### Exercise 5.3: List Users - Filtering and Pagination

**Concept:** `find()` with filter + `skip()` + `limit()` + `to_list()`
**Difficulty:** Easy
**Why this matters:** Every listing endpoint needs pagination. This teaches you the skip/limit pattern and how to filter soft-deleted documents at the database level.

#### Implement: `list_users(self, skip: int = 0, limit: int = 20) -> list[User]`

**Business Rules:**
1. Query all users where `deleted_at` is `None` (exclude soft-deleted users)
2. Apply `skip` for pagination offset
3. Cap `limit` at 100 maximum (prevent large queries)
4. Return the list

**The MongoDB Operation:**
```
FIND where deleted_at == null, SKIP n, LIMIT m → list of User documents
```

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

Beanie's `find()` returns a query builder. Chain `.skip()`, `.limit()`, and `.to_list()` to execute the query.

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
return (
    await User.find({"deleted_at": None})
    .skip(skip)
    .limit(min(limit, 100))
    .to_list()
)
```

</details>

#### Verify Exercise 5.3

```bash
curl "http://localhost:8000/users?limit=10&skip=0"
```

**Expected (200 OK):** Array of user objects.

---

### Exercise 5.4: Update User - Partial Field Updates

**Concept:** Fetch → modify only provided fields → `save()`
**Difficulty:** Easy-Medium
**Why this matters:** PATCH semantics mean only updating fields that were explicitly sent. You'll learn the "fetch → modify → save" pattern used throughout the codebase.

#### Implement: `update_user(self, user_id, display_name=None, phone=None, bio=None, avatar=None) -> User`

**Business Rules:**
1. Fetch the user using `self.get_user(user_id)` (reuses your Exercise 5.2 implementation)
2. For each parameter that is **not None**, update the corresponding field:
   - `display_name` → `user.profile.display_name`
   - `phone` → `user.contact_info.phone`
   - `bio` → `user.profile.bio`
   - `avatar` → `user.profile.avatar`
3. Save the user (the `save()` override auto-updates `updated_at`)
4. Emit `EventType.USER_UPDATED` Kafka event
5. Return the updated User document

**The MongoDB Operations:**
```
Operation 1: GET by _id (via get_user)
Operation 2: SAVE → replaces the document with updated fields
```

> **Important:** Only update fields that are explicitly provided (not None). If the request only sends `display_name`, don't touch `phone`, `bio`, or `avatar`.

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

Check each parameter with `if display_name is not None:` before assigning. This preserves the "partial update" semantics of PATCH requests.

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
user = await self.get_user(user_id)

if display_name is not None:
    user.profile.display_name = display_name
if phone is not None:
    user.contact_info.phone = phone
# ... same for bio, avatar

await user.save()  # auto-updates updated_at

self._kafka.emit(
    event_type=EventType.USER_UPDATED,
    entity_id=oid_to_str(user.id),
    data=user.model_dump(mode="json"),
)
return user
```

</details>

#### Verify Exercise 5.4

```bash
curl -X PATCH http://localhost:8000/users/<user-id> \
  -H "Content-Type: application/json" \
  -d '{
    "display_name": "Updated Name",
    "bio": "Hello, I am a test user!"
  }'
```

**Expected (200 OK):** User object with updated `display_name` and `bio`, but unchanged `phone` and `avatar`.

**Verify in MongoDB shell:**
```javascript
db.users.findOne({"_id": ObjectId("<user-id>")}, {"profile": 1, "updated_at": 1})
// profile.display_name should be "Updated Name"
// updated_at should be recent
```

---

### Exercise 5.5: Soft Delete - The Deletion Pattern

**Concept:** Fetch → set `deleted_at` → `save()` (instead of removing the document)
**Difficulty:** Easy
**Why this matters:** Soft delete preserves data for audit trails and recovery. Instead of removing the document, we timestamp when it was "deleted". All subsequent queries (get, list) must exclude these documents.

#### Implement: `delete_user(self, user_id: str) -> None`

**Business Rules:**
1. Fetch the user using `self.get_user(user_id)`
2. Set `user.deleted_at` to the current UTC time using `utc_now()`
3. Save the user
4. Emit `EventType.USER_DELETED` Kafka event
5. Return nothing (`None`)

**The MongoDB Operations:**
```
Operation 1: GET by _id (via get_user)
Operation 2: SAVE → sets deleted_at timestamp
```

> **Why not hard delete?** Soft delete lets you:
> - Recover accidentally deleted accounts
> - Maintain referential integrity (orders, posts still reference the user)
> - Comply with audit requirements
> - Support "undo" functionality

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

This is the same fetch-modify-save pattern as `update_user`, but you're setting `deleted_at` instead of profile fields.

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
user = await self.get_user(user_id)
user.deleted_at = utc_now()
await user.save()

self._kafka.emit(
    event_type=EventType.USER_DELETED,
    entity_id=oid_to_str(user.id),
    data={"user_id": oid_to_str(user.id)},
)
```

</details>

#### Verify Exercise 5.5

```bash
# Delete the user
curl -X DELETE http://localhost:8000/users/<user-id>
# Expected: 204 No Content

# Try to get the deleted user
curl http://localhost:8000/users/<user-id>
# Expected: 404 Not Found (because get_user checks deleted_at)

# List users - deleted user should not appear
curl http://localhost:8000/users
# Expected: Array without the deleted user
```

**Verify in MongoDB shell:**
```javascript
db.users.findOne({"_id": ObjectId("<user-id>")})
// Document still exists but deleted_at is set to a timestamp
```

---

## 6. VERIFICATION CHECKLIST

Before moving to TASK_02, verify that ALL of the following pass:

### Functional Checks
- [ ] **Create user** - creates document with correct defaults (`deleted_at=null`, `version=1`, timestamps set)
- [ ] **Duplicate email rejected** - second registration with same email fails with 409
- [ ] **Get user** - returns user data by ID
- [ ] **Get non-existent user** - returns 404
- [ ] **List users** - returns array, respects skip/limit
- [ ] **List users excludes deleted** - soft-deleted users don't appear in list
- [ ] **Update user** - updates only provided fields, leaves others unchanged
- [ ] **Delete user** - sets `deleted_at`, user no longer accessible via get/list

### Database Checks (MongoDB shell)
- [ ] `db.users.countDocuments()` - shows correct number of users created
- [ ] `db.users.getIndexes()` - shows only the default `_id` index
- [ ] Document has correct embedded structure: `contact_info` with `primary_email`, `additional_emails`, `phone`
- [ ] Document has `profile` with `display_name`, `avatar`, `bio`, `date_of_birth`
- [ ] After update: `updated_at` is refreshed
- [ ] After delete: `deleted_at` is set, document still exists

### Code Quality Checks
- [ ] `DuplicateError` used for email conflicts (not generic Exception)
- [ ] `NotFoundError` used for missing users
- [ ] Email normalized (lowercase, stripped) before uniqueness query
- [ ] Kafka events emitted for: USER_CREATED, USER_UPDATED, USER_DELETED
- [ ] All operations use Beanie ODM (no raw PyMongo queries)

---

## 7. ADVANCED CHALLENGES

These are optional exercises that deepen your understanding. Attempt them after completing the main exercises.

### Challenge A: Query Execution Analysis

The User model has no custom indexes. Let's see what that means for query performance.

Open the MongoDB shell and run:
```javascript
db.users.find({"contact_info.primary_email": "consumer@example.com"}).explain("executionStats")
```

Answer these questions:
1. What is the `winningPlan.stage`? (It will be `COLLSCAN` - full collection scan, because there's no index)
2. How many `totalDocsExamined`? (It will be ALL documents in the collection)

Now try the same after adding an index:
```javascript
db.users.createIndex({"contact_info.primary_email": 1}, {unique: true})
db.users.find({"contact_info.primary_email": "consumer@example.com"}).explain("executionStats")
```

Compare:
- What's the `winningPlan.stage` now? (Should be `IXSCAN` - index scan)
- How many `totalDocsExamined`? (Should be 1)

**Takeaway:** Indexes are the difference between O(log n) and O(n) queries. The User model intentionally has no indexes for simplicity - in production you'd add them.

### Challenge B: Unique Index Behavior

There is no unique index on `contact_info.primary_email`. What happens if two users somehow get the same primary email?

Try this in MongoDB shell:
```javascript
// Insert a document directly (bypassing application logic)
db.users.insertOne({
  "contact_info": {"primary_email": "duplicate@test.com", "additional_emails": []},
  "password_hash": "fake",
  "profile": {"display_name": "Dupe 1", "avatar": ""},
  "version": 1
})
// Insert another with the same email
db.users.insertOne({
  "contact_info": {"primary_email": "duplicate@test.com", "additional_emails": []},
  "password_hash": "fake",
  "profile": {"display_name": "Dupe 2", "avatar": ""},
  "version": 1
})
```

Does MongoDB reject the second insert? Why or why not?

**Reflection:** How does the application currently prevent duplicates? (Answer: via `find_one()` check before insert in `create_user()`). What's the weakness of this approach? (Answer: race condition - two requests could check simultaneously, both see the email is available, and both insert. A unique index would be the true safeguard.)

### Challenge C: The Soft Delete Filter

Look at `list_users`. It filters with `{"deleted_at": None}`. Now look at `get_user` - it fetches by `_id` first, then checks `deleted_at` in Python.

**Question:** Why not add `deleted_at: None` to the `get_user` query instead?

<details>
<summary>Answer</summary>

You could combine them:
```python
user = await User.find_one({"_id": PydanticObjectId(user_id), "deleted_at": None})
```

However, the current approach (fetch then check) works well for `_id` lookups because:
- The `_id` lookup is already the fastest query possible (unique index)
- Adding `deleted_at` filter doesn't improve performance for single-document lookups
- Separating the checks lets you potentially return different errors (e.g., "User was deleted" vs "User not found")

For `list_users`, filtering at the database level is essential because scanning and filtering many documents in Python would be wasteful.

</details>

---

## 8. WHAT'S NEXT

You've completed the foundation. You now understand:
- `find_one()` for field-based lookups (email uniqueness)
- `Document.get()` for `_id` lookups
- `document.insert()` for creating documents
- `document.save()` for updating documents
- `find()` with filter + skip/limit for pagination
- Embedded document construction (`ContactInfo`, `UserProfile`)
- Soft delete pattern (`deleted_at` timestamp)

**TASK 02: Supplier Service** will build on these concepts with:
- Deeper nesting (contact person info, company addresses, business info, banking info)
- More embedded document types (6 embedded types vs User's 3)
- Multi-level partial updates (updating fields across different nested objects)
- Hard delete (contrast with User's soft delete)

The patterns you learned here - find → validate → act → emit - will repeat in every service you build. Master them now.
