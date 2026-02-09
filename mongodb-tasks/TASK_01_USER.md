# TASK 01: User Authentication Service

## 1. MISSION BRIEFING

You are building the **authentication backbone** of a Social Commerce Platform - a system where celebrities create branded communities and consumers discover and buy products without leaving the ecosystem.

Every single action on the platform starts with a **User**. Registration, login, email verification, password reset - these are the gates through which every consumer and leader enters.

### What You Will Build
The `AuthService` class - the service layer that handles all user authentication operations by writing MongoDB queries through Beanie ODM.

### What You Will Learn

| MongoDB Concept | Where You'll Use It |
|----------------|-------------------|
| `find_one()` with nested field match | Querying `contact_info.primary_email` |
| `find_one()` with array field match | Checking `contact_info.additional_emails` |
| `Document.get()` by ObjectId | Fetching user by `_id` |
| `document.insert()` | Creating new user documents |
| `document.save()` | Updating existing documents |
| Embedded document construction | Building `ContactInfo`, `UserProfile` |

---

## 2. BEFORE YOU START

### Prerequisites
- MongoDB running locally (via Docker)
- Project dependencies installed
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
- The `User` class (line 64) - this is what gets stored in MongoDB
- The `save()` override - automatically updates `updated_at` on every save
- Note: There are no indexes or helper methods defined yet - the model is minimal

#### Step 2: The Schema (the API contract)
```
apps/backend-service/src/schemas/auth.py
```
This defines **what the route sends you** (Request schemas) and **what you must return** (Response schemas). Your service sits between the route and the database.

#### Step 3: The Route (who calls you)
```
apps/backend-service/src/routes/auth.py
```
This is the HTTP layer. It receives requests, calls YOUR service methods, and formats responses. Notice:
- Line 28-33: The route calls `auth_service.register_consumer()` and expects a dict back
- Line 115-118: The route calls `auth_service.login()` with email, password, and ip_address
- The route handles HTTP status codes - **your service throws ValueError for business errors**

#### Step 4: The Utilities (your tools)
```
apps/backend-service/src/utils/datetime_utils.py    → utc_now()
apps/backend-service/src/utils/serialization.py     → oid_to_str()
apps/backend-service/src/kafka/producer.py          → KafkaProducer.emit()
apps/backend-service/src/kafka/topics.py            → Topic.USER
```

### The Data Flow (understand this before writing any code)

```
HTTP Request
    │
    ▼
┌─────────┐   Validates input      ┌───────────┐
│  Route   │ ──────────────────────▶│  Schema   │
│ auth.py  │   (Pydantic)          └───────────┘
│          │
│  Calls   │
│  your    │
│  service │
    │
    ▼
┌──────────────────────────────────────────────┐
│              AuthService (YOU WRITE THIS)     │
│                                              │
│  1. Receives clean, validated data           │
│  2. Applies business rules                   │
│  3. Executes MongoDB queries via Beanie      │
│  4. Emits Kafka events                       │
│  5. Returns dict (route formats response)    │
│                                              │
│  Throws ValueError → route returns 400/401   │
│  Throws Exception  → route returns 500       │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────┐
│ MongoDB  │  (via Beanie ODM)
│  users   │
│collection│
└──────────┘
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
│   ├── primary_email (EmailStr)          ← LOGIN KEY
│   ├── additional_emails (List[EmailStr]) ← ALSO CHECKED FOR UNIQUENESS
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
class AuthService:
    def __init__(self):
        self.password_min_length = 8
        self.password_max_length = 128
        self._kafka = get_kafka_producer()
        self.password_pattern = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$')
```

### Method Signatures

| # | Method | MongoDB Operation | Returns |
|---|--------|------------------|---------|
| 1 | `generate_verification_token(user_id, email)` | None | `str` (JWT) |
| 2 | `generate_reset_token(user_id, email)` | None | `str` (JWT) |
| 3 | `verify_token(token, token_type)` | None | `Dict` (payload) |
| 4 | `hash_password(password)` | None | `str` (bcrypt hash) |
| 5 | `verify_password(password, password_hash)` | None | `bool` |
| 6 | `validate_password(password, email)` | None | `None` (raises ValueError) |
| 7 | `is_email_available(email)` | `find_one` x2 | `bool` |
| 8 | `register_consumer(email, password, display_name)` | `insert` | `Dict` |
| 9 | `login(email, password)` | `find_one` + `save` | `Dict` |
| 10 | `verify_email(token)` | `get` + `save` | `Dict` |
| 11 | `request_password_reset(email)` | `find_one` | `Optional[str]` |
| 12 | `reset_password(token, new_password)` | `get` + `save` | `Dict` |

---

## 5. IMPLEMENTATION EXERCISES

> **Rule:** Implement each exercise completely and verify it works before moving to the next. Each exercise builds on the previous one.

---

### Exercise 5.1: Utility Foundation (No MongoDB)

**Concept:** Pure Python logic - bcrypt hashing, JWT tokens, regex validation
**Difficulty:** Warm-up
**Why this matters:** Every authentication flow depends on these utilities. Get them right first.

#### Implement these 6 methods:

**5.1.1 - `generate_verification_token(self, user_id: str, email: str) -> str`**

Create a JWT token for email verification.

Requirements:
- Payload must contain: `user_id`, `email`, `type` (set to `"email_verification"`), `exp` (6 hours from now)
- Use `JWT_SECRET` and `JWT_ALGORITHM` constants defined at module level
- Use `utc_now()` from datetime_utils for the current time

**5.1.2 - `generate_reset_token(self, user_id: str, email: str) -> str`**

Create a JWT token for password reset.

Requirements:
- Same as verification token but: `type` = `"password_reset"`, `exp` = 1 hour from now

**5.1.3 - `verify_token(self, token: str, token_type: str) -> Dict[str, Any]`**

Decode and validate a JWT token.

Requirements:
- Decode the token using `jwt.decode()` with `JWT_SECRET` and `[JWT_ALGORITHM]`
- Verify the `type` field in the payload matches `token_type` parameter
- Return the decoded payload dict
- Raise `ValueError("Invalid token type")` if type doesn't match
- Raise `ValueError("Token has expired")` for `jwt.ExpiredSignatureError`
- Raise `ValueError("Invalid token")` for `jwt.InvalidTokenError`

**5.1.4 - `hash_password(self, password: str) -> str`**

Hash a password using bcrypt.

Requirements:
- Generate a salt with `bcrypt.gensalt(rounds=12)`
- Hash using `bcrypt.hashpw()` - encode password to UTF-8 before hashing
- Return the hash as a string (decode from bytes)

**5.1.5 - `verify_password(self, password: str, password_hash: str) -> bool`**

Verify a password against its hash.

Requirements:
- Use `bcrypt.checkpw()` - encode both password and hash to UTF-8
- Return the boolean result

**5.1.6 - `validate_password(self, password: str, email: str) -> None`**

Validate password meets security requirements.

Requirements:
- Check length: must be between `self.password_min_length` (8) and `self.password_max_length` (128)
- Check pattern: must match `self.password_pattern` (at least 1 uppercase, 1 lowercase, 1 digit)
- Check email leak: password cannot contain the email username (part before `@`, case-insensitive)
- Raise `ValueError` with descriptive message for each failure
- Return `None` if password is valid (no return value needed)

#### Verify Exercise 5.1

Test in Python shell:
```python
auth = AuthService()

# Test password hashing
hashed = auth.hash_password("MyPass123")
assert auth.verify_password("MyPass123", hashed) == True
assert auth.verify_password("WrongPass", hashed) == False

# Test password validation
auth.validate_password("MyPass123", "user@example.com")  # Should pass
# auth.validate_password("short", "user@example.com")    # Should raise ValueError
# auth.validate_password("nouppercase1", "u@e.com")      # Should raise ValueError

# Test token generation
token = auth.generate_verification_token("user123", "test@example.com")
payload = auth.verify_token(token, "email_verification")
assert payload["user_id"] == "user123"
assert payload["email"] == "test@example.com"
```

---

### Exercise 5.2: Your First MongoDB Query - Email Availability

**Concept:** `find_one()` with nested field match + array field match
**Difficulty:** Easy
**Why this matters:** Before creating any user, we must ensure email uniqueness. This is your first real MongoDB query.

#### Implement: `is_email_available(self, email: str) -> bool`

**Business Rules:**
1. Normalize the email: lowercase and strip whitespace
2. Check if the email is used as ANY user's **primary email**
3. Check if the email is used as ANY user's **additional email**
4. Return `True` only if neither check finds a match

**The MongoDB Queries You Need:**

Query 1 - Check primary email:
```
Find ONE document in the users collection where
the nested field contact_info.primary_email equals the given email
```

Query 2 - Check additional emails:
```
Find ONE document in the users collection where
the array field contact_info.additional_emails contains the given email
```

**Error handling:**
- Wrap in try/except
- Re-raise any exception as `Exception(f"Failed to check email availability: {str(e)}")`

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

Beanie provides `ModelClass.find_one(filter_dict)` which maps directly to MongoDB's `findOne()`. For nested fields, use dot notation in the filter key. For array fields, MongoDB automatically checks if the value exists anywhere in the array.

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
# Nested field query (dot notation):
user = await User.find_one({"contact_info.primary_email": email})

# Array field query (automatic $in-like behavior):
user = await User.find_one({"contact_info.additional_emails": email})
```

MongoDB automatically searches arrays when you query a field that contains an array. You don't need `$in` or `$elemMatch` for simple equality matches.

</details>

<details>
<summary><b>Hint Level 3</b> - Near-complete solution</summary>

```python
async def is_email_available(self, email: str) -> bool:
    try:
        email = email.lower().strip()

        # Check primary email (uses index: contact_info.primary_email)
        user = await User.find_one({"contact_info.primary_email": email})
        if user:
            return False

        # Check additional emails (uses index: contact_info.additional_emails)
        user = await User.find_one({"contact_info.additional_emails": email})
        if user:
            return False

        return True
    except Exception as e:
        raise Exception(f"Failed to check email availability: {str(e)}")
```

</details>

#### Verify Exercise 5.2

With an empty database, this should return `True`:
```bash
# You can test this via the register endpoint later,
# or test directly in a Python shell:
# await auth_service.is_email_available("new@example.com")  → True
```

#### Index Checkpoint

**Question:** The User model does not define any custom indexes. What does this mean for the two queries in this method?

<details>
<summary>Answer</summary>

Without custom indexes, both queries perform a **collection scan** (COLLSCAN) - MongoDB checks every document. This is fine for development and small datasets, but in production you'd want to add indexes on `contact_info.primary_email` and `contact_info.additional_emails` to make these O(log n) instead of O(n).

</details>

---

### Exercise 5.3: Your First Write - Register Consumer

**Concept:** Document construction with embedded objects + `insert()`
**Difficulty:** Easy-Medium
**Why this matters:** This is how users enter the platform. You'll build a complete `User` document from scratch and persist it to MongoDB.

#### Implement: `register_consumer(self, email: str, password: str, display_name: str) -> Dict[str, Any]`

**Business Rules (implement in this order):**
1. Normalize inputs: `email.lower().strip()`, `display_name.strip()`
2. Check email availability using your `is_email_available()` method
   - If not available → raise `ValueError("Email already in use")`
3. Validate password using your `validate_password()` method
   - It raises ValueError internally if invalid
4. Build the User document:
   - `password_hash`: hash the password
   - `contact_info`: create `ContactInfo` with `primary_email=email`
   - `profile`: create `UserProfile` with `display_name=display_name`
   - All other fields use their defaults (`deleted_at=None`, `version=1`, timestamps auto-set)
5. Insert the document into MongoDB
6. Emit a Kafka event (topic: `Topic.USER`, action: `"registered"`)
7. Generate a verification token
8. Return the result dict

**The MongoDB Operation:**

```
INSERT a new User document into the "users" collection
```

**Return format** (the route expects exactly this structure):
```python
{
    "user": {
        "id": "string (the MongoDB ObjectId as string)",
        "email": "the primary email",
        "display_name": "the display name"
    },
    "verification_token": "the JWT token string"
}
```

**Error handling:**
- `ValueError` → re-raise as-is
- Any other exception → raise `Exception(f"Failed to register consumer: {str(e)}")`

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

In Beanie, you construct a document by instantiating the model class, then call `await document.insert()` to persist it. The `id` field is auto-generated by MongoDB after insert.

Use `oid_to_str(user.id)` to convert the ObjectId to a string for the response.

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
# Document construction:
user = User(
    password_hash=self.hash_password(password),
    contact_info=ContactInfo(primary_email=email),
    profile=UserProfile(display_name=display_name)
    # deleted_at, version, created_at, updated_at all use defaults from the model
)

# Insert:
await user.insert()

# After insert, user.id is populated by MongoDB
user_id = oid_to_str(user.id)  # "507f1f77bcf86cd799439011"
```

</details>

<details>
<summary><b>Hint Level 3</b> - Near-complete solution</summary>

```python
async def register_consumer(self, email, password, display_name):
    try:
        email = email.lower().strip()
        display_name = display_name.strip()

        if not await self.is_email_available(email):
            raise ValueError("Email already in use")

        self.validate_password(password, email)

        user = User(
            password_hash=self.hash_password(password),
            contact_info=ContactInfo(primary_email=email),
            profile=UserProfile(display_name=display_name)
        )
        await user.insert()

        user_id = oid_to_str(user.id)

        self._kafka.emit(
            topic=Topic.USER,
            action="registered",
            entity_id=user_id,
            data=user.model_dump(mode="json"),
        )

        verification_token = self.generate_verification_token(user_id, email)

        return {
            "user": {
                "id": user_id,
                "email": user.contact_info.primary_email,
                "display_name": user.profile.display_name
            },
            "verification_token": verification_token
        }
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to register consumer: {str(e)}")
```

</details>

#### Verify Exercise 5.3

```bash
curl -X POST http://localhost:8000/auth/register \
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
  "user": {
    "id": "<some-object-id>",
    "email": "consumer@example.com",
    "display_name": "Test Consumer"
  },
  "message": "Registration successful. Verification email sent to consumer@example.com",
  "verification_token": "<jwt-token>"
}
```

**Test duplicate email (400 Bad Request):**
```bash
curl -X POST http://localhost:8000/auth/register \
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

### Exercise 5.4: The Login Flow - Find, Validate, Update

**Concept:** `find_one()` with conditional reads + `save()` for updating
**Difficulty:** Medium
**Why this matters:** Login is the most important authentication operation. It combines reading, validating, and conditionally writing back to the database - all in a single method. This is the "find → check → act" pattern you'll use everywhere.

#### Implement: `login(self, email: str, password: str) -> Dict[str, Any]`

**This is the most important method in this task.** It has 4 distinct phases:

#### Phase 1: Find the user
- Normalize email (lowercase, strip)
- Query: find one user by `contact_info.primary_email`
- If not found → raise `ValueError("Invalid email or password")`

> **Security note:** We say "Invalid email or password" (not "Email not found") to prevent email enumeration attacks.

#### Phase 2: Check soft delete
- If `user.deleted_at is not None` → raise `ValueError("Account no longer exists")`

#### Phase 3: Verify password
- Use `self.verify_password(password, user.password_hash)`
- If password is WRONG → raise `ValueError("Invalid email or password")`

#### Phase 4: Return user data
- Save the user (triggers `updated_at` timestamp update via the save override)
- Emit Kafka event: topic=`Topic.USER`, action=`"login"`

```python
{
    "id": user_id,
    "email": user.contact_info.primary_email,
    "display_name": user.profile.display_name,
    "avatar": user.profile.avatar
}
```

**Error handling:**
- `ValueError` → re-raise
- Any other → raise `Exception(f"Failed to login: {str(e)}")`

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

The key MongoDB operation is the initial `find_one`. Everything after that is Python logic operating on the returned document object. When you call `save()`, Beanie sends an update to MongoDB replacing the document (and the save override updates `updated_at`).

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
# Phase 1: Find
user = await User.find_one({"contact_info.primary_email": email})
if not user:
    raise ValueError("Invalid email or password")

# Phase 2: Soft delete check
if user.deleted_at is not None:
    raise ValueError("Account no longer exists")

# Phase 3: Verify password
if not self.verify_password(password, user.password_hash):
    raise ValueError("Invalid email or password")

# Phase 4: Save (updates updated_at) and return
await user.save()
```

</details>

#### Verify Exercise 5.4

**Successful login** (use the consumer you registered in 5.3):
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "consumer@example.com",
    "password": "MySecure1Pass"
  }'
```

**Expected (200 OK):**
```json
{
  "user": {
    "id": "<object-id>",
    "email": "consumer@example.com",
    "display_name": "Test Consumer",
    "avatar": "https://cdn.example.com/avatars/default.jpg"
  }
}
```

**Wrong password (401):**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "consumer@example.com",
    "password": "WrongPassword1"
  }'
```

---

### Exercise 5.5: Get By ID - Email Verification

**Concept:** `Document.get(ObjectId)` - fetching by `_id` vs querying by field
**Difficulty:** Medium
**Why this matters:** Login finds users by email (field query). Verification finds users by their ID embedded in the JWT token. These are fundamentally different MongoDB operations.

#### Implement: `verify_email(self, token: str) -> Dict[str, Any]`

**Business Rules:**
1. Verify the token using `self.verify_token(token, "email_verification")`
   - This returns a payload dict with `user_id` and `email`
2. Get the user by ID using `User.get(ObjectId(user_id))`
   - If not found → raise `ValueError("User not found")`
3. Save the user (triggers `updated_at` update)
4. Emit Kafka event: topic=`Topic.USER`, action=`"email_verified"`
5. Return result dict

> **Note:** The User model does not have an `email_verified` field. This exercise focuses on the `User.get(ObjectId)` pattern - fetching a document by its `_id`. In a production system, you would add an `email_verified` field to the model.

**The MongoDB Operations:**

```
Operation 1: GET by _id  →  User.get(ObjectId("507f1f77bcf86cd799439011"))
Operation 2: SAVE        →  Updates the document in place
```

**Return format:**
```python
{
    "id": "string",
    "email": "string",
    "verified": True
}
```

**Key Distinction:**
```
find_one({"contact_info.primary_email": "x"})  ← Field query (collection scan without index)
User.get(ObjectId("507f..."))                   ← _id lookup (uses primary key, always fastest)
```

`User.get()` is Beanie's wrapper around `find_one({"_id": ObjectId(...)})`. The `_id` field has a unique index by default in every MongoDB collection - you never need to define it.

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

You need `from bson import ObjectId` to convert the string user_id from the token payload into a proper ObjectId for the query. `User.get()` expects an ObjectId, not a string.

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
payload = self.verify_token(token, "email_verification")
user_id = payload.get("user_id")

user = await User.get(ObjectId(user_id))
if not user:
    raise ValueError("User not found")

await user.save()
```

</details>

#### Verify Exercise 5.5

Use the verification token from registration (Exercise 5.3):
```bash
# First, register a fresh user and capture the token:
RESPONSE=$(curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "verify.me@example.com",
    "password": "VerifyMe1Pass",
    "display_name": "Verify Test"
  }')

TOKEN=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['verification_token'])")

# Now verify:
curl -X POST http://localhost:8000/auth/verify-email \
  -H "Content-Type: application/json" \
  -d "{\"token\": \"$TOKEN\"}"
```

**Expected (200 OK):**
```json
{
  "id": "<object-id>",
  "email": "verify.me@example.com",
  "verified": true
}
```

**Verify in MongoDB shell:**
```javascript
db.users.findOne(
  {"contact_info.primary_email": "verify.me@example.com"},
  {"updated_at": 1}
)
// updated_at should be recent (confirming the save worked)
```

---

### Exercise 5.6: Complete the Flow - Password Reset

**Concept:** Combining `find_one` + token generation + `get` by ID + field update + `save`
**Difficulty:** Medium
**Why this matters:** Password reset touches every concept from previous exercises. It's your integration test.

#### Implement TWO methods:

**5.6.1 - `request_password_reset(self, email: str) -> Optional[str]`**

Request a password reset. Returns a reset token if the user exists, `None` otherwise.

**Business Rules:**
1. Normalize email (lowercase, strip)
2. Find user by primary email
3. If not found → return `None` (don't reveal whether email exists)
4. Emit Kafka event: topic=`Topic.USER`, action=`"password_reset_requested"`
5. Generate and return a reset token

**Security note:** The route always returns "If the email exists, a reset link has been sent" regardless of whether we found a user. This prevents email enumeration.

**5.6.2 - `reset_password(self, token: str, new_password: str) -> Dict[str, Any]`**

Complete the password reset using the token.

**Business Rules:**
1. Verify the token: `self.verify_token(token, "password_reset")`
2. Extract `user_id` and `email` from payload
3. Get user by ID: `User.get(ObjectId(user_id))`
   - If not found → raise `ValueError("User not found")`
4. Validate the new password: `self.validate_password(new_password, email)`
5. Update the password:
   - `user.password_hash` = hash of new password
6. Save the user (triggers `updated_at` update)
7. Emit Kafka event: topic=`Topic.USER`, action=`"password_reset"`
8. Return `{"message": "Password reset successful"}`

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

`request_password_reset` is essentially: find_one → if found, generate token. `reset_password` is: verify token → get by id → update field → save. Both are combinations of patterns you've already implemented.

</details>

#### Verify Exercise 5.6

```bash
# Step 1: Request reset
curl -X POST http://localhost:8000/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "consumer@example.com"}'
# Response: {"message": "If the email exists, a password reset link has been sent"}

# Step 2: Use the token (in production this comes from email)
# For testing, call request_password_reset directly and use the token:

# Step 3: Reset with new password
curl -X POST http://localhost:8000/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "token": "<paste-reset-token-here>",
    "new_password": "MyNewSecure1Pass"
  }'
# Response: {"message": "Password reset successful"}

# Step 4: Login with new password should work
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "consumer@example.com",
    "password": "MyNewSecure1Pass"
  }'
# Response: 200 OK with user data
```

---

## 6. VERIFICATION CHECKLIST

Before moving to TASK_02, verify that ALL of the following pass:

### Functional Checks
- [ ] **Register consumer** - creates document with correct defaults (`deleted_at=null`, `version=1`, timestamps set)
- [ ] **Duplicate email rejected** - second registration with same email fails with 400
- [ ] **Login success** - returns user data (id, email, display_name, avatar)
- [ ] **Login wrong password** - returns 401 with "Invalid email or password"
- [ ] **Login soft-deleted user** - returns error "Account no longer exists"
- [ ] **Email verification** - successfully retrieves user by ID from token, saves user
- [ ] **Password reset request** - returns token for existing user, `None` for non-existent
- [ ] **Password reset complete** - changes `password_hash`, old password no longer works

### Database Checks (MongoDB shell)
- [ ] `db.users.countDocuments()` - shows correct number of users created
- [ ] `db.users.getIndexes()` - shows only the default `_id` index (no custom indexes in model)
- [ ] Document has correct embedded structure: `contact_info` with `primary_email`, `additional_emails`, `phone`
- [ ] Document has `profile` with `display_name`, `avatar`, `bio`, `date_of_birth`
- [ ] After login: `updated_at` is refreshed

### Code Quality Checks
- [ ] All methods have try/except error handling
- [ ] ValueError used for business logic errors (not generic Exception)
- [ ] Email normalized (lowercase, stripped) before every query
- [ ] Kafka events emitted for: register, login, email_verified, password_reset_requested, password_reset
- [ ] No raw MongoDB queries - all operations use Beanie ODM

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

**Reflection:** How does the application currently prevent duplicates? (Answer: via `is_email_available()` check before insert). What's the weakness of this approach? (Answer: race condition - two requests could check simultaneously, both see the email is available, and both insert. A unique index would be the true safeguard.)

### Challenge C: The Soft Delete Gap

Look at the login method. When a user is soft-deleted (`deleted_at is not None`), we reject the login. But we find the user first with:
```python
User.find_one({"contact_info.primary_email": email})
```

This query does NOT filter by `deleted_at`. So we find deleted users, then check in Python. Is this efficient?

How would you change the query to filter deleted users at the database level?

<details>
<summary>Answer</summary>

```python
user = await User.find_one({
    "contact_info.primary_email": email,
    "deleted_at": None
})
```

This uses the `deleted_at` index and prevents loading deleted user documents into memory. However, the current approach has a UX benefit: we can show the specific error "Account no longer exists" instead of the generic "Invalid email or password". It's a tradeoff between efficiency and user experience.

</details>

---

## 8. WHAT'S NEXT

You've completed the foundation. You now understand:
- `find_one()` for field-based lookups
- `Document.get()` for `_id` lookups
- `document.insert()` for creating documents
- `document.save()` for updating documents
- Embedded document construction
- Which indexes support which queries

**TASK 02: Supplier Authentication** will build on these concepts with:
- Deeper nesting (contact person info, company addresses, business info, banking info)
- Cross-collection email uniqueness (checking both User and Supplier collections)
- More embedded document types (5 embedded types vs User's 3)
- Compound index usage (location-based supplier lookup)

The patterns you learned here - find → validate → act → emit - will repeat in every service you build. Master them now.
