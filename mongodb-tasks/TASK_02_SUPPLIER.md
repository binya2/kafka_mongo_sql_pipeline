# TASK 02: Supplier Authentication Service

## 1. MISSION BRIEFING

Suppliers are the **commerce engine** of the platform. While Users browse, like, and share - Suppliers stock the shelves. They are business entities (LLCs, corporations, sole proprietors) that list products, manage inventory, and fulfill orders.

Suppliers are deliberately **separate from Users**. They cannot browse feeds or follow leaders. They have their own authentication system and their own set of capabilities.

### What You Will Build
The `SupplierAuthService` class - handling supplier registration, login, email verification, and password reset.

### What You Will Learn

| MongoDB Concept | Where You'll Use It |
|----------------|-------------------|
| Cross-collection queries | Checking email uniqueness across **both** `suppliers` AND `users` |
| Deep nested document construction | Building 3-level deep embedded objects |
| Multiple required embedded documents | Constructing `contact_info` + `company_info` + `business_info` |
| Array field validation in queries | Checking `contact_info.additional_emails` array |
| Compound index awareness | Understanding the location-based compound index |

### How This Differs From TASK_01 (User)

| Aspect | User (TASK_01) | Supplier (TASK_02) |
|--------|---------------|-------------------|
| Embedded types | 3 (`ContactInfo`, `BusinessAddress`, `UserProfile`) | **5** (`SupplierContactInfo`, `CompanyAddress`, `CompanyInfo`, `BusinessInfo`, `BankingInfo`) |
| Registration fields | 3 fields (email, password, name) | **~12 fields** across multiple embedded objects |
| Email check scope | Users only | **Suppliers + Users** (cross-collection) |
| Indexes | None | **1 compound index** (location) |
| Nesting depth | 2 levels | **3 levels** (company_info.business_address.city) |
| Token payload key | `user_id` | `supplier_id` |

---

## 2. BEFORE YOU START

### Prerequisites
- **TASK_01 (User) must be complete** - Supplier email check crosses into the Users collection
- MongoDB running locally
- Familiarity with Beanie ODM patterns from TASK_01

### Files You MUST Read Before Coding

#### Step 1: The Model (the data)
```
shared/models/supplier.py
```
This is a larger model than User. Pay attention to:
- 5 embedded document classes before the main `Supplier` class
- The `Supplier` class fields: `password_hash`, `contact_info`, `company_info`, `business_info`, `banking_info`, `product_ids`, `created_at`, `updated_at`
- The `Settings.indexes` - a compound index on business address location
- The `save()` override that auto-updates `updated_at`

#### Step 2: The Schema (the API contract)
```
apps/backend-service/src/schemas/supplier_auth.py
```
Notice the registration request has more fields than User's 3.

#### Step 3: The Route (who calls you)
```
apps/backend-service/src/routes/supplier_auth.py
```

#### Step 4: The Utilities (same as TASK_01)
```
apps/backend-service/src/utils/datetime_utils.py    → utc_now()
apps/backend-service/src/utils/serialization.py     → oid_to_str()
apps/backend-service/src/kafka/producer.py          → KafkaProducer.emit()
apps/backend-service/src/kafka/topics.py            → Topic.SUPPLIER
```

---

## 3. MODEL DEEP DIVE

### The Supplier Document Structure

A Supplier document in MongoDB is significantly larger than a User document. Here's the full shape:

```json
{
  "_id": ObjectId("..."),
  "password_hash": "$2b$12$...",

  "contact_info": {
    "primary_email": "supplier@acme.com",
    "additional_emails": ["orders@acme.com", "support@acme.com"],
    "primary_phone": "+1-555-0100",
    "contact_person_name": "John Doe",
    "contact_person_title": "Sales Director",
    "contact_person_email": "john@acme.com",
    "contact_person_phone": "+1-555-0102"
  },

  "company_info": {
    "legal_name": "Acme Corporation",
    "dba_name": "Acme Goods",
    "business_address": {
      "street_address_1": "100 Commerce Blvd",
      "street_address_2": "Suite 400",
      "city": "New York",
      "state": "NY",
      "zip_code": "10001",
      "country": "US"
    },
    "shipping_address": null
  },

  "business_info": {
    "facebook_url": null,
    "instagram_handle": null,
    "twitter_handle": null,
    "linkedin_url": null,
    "timezone": "America/New_York",
    "support_email": "help@acme.com",
    "support_phone": "+1-555-0199"
  },

  "banking_info": null,

  "product_ids": [],
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

### Embedded Documents Hierarchy

```
Supplier (Document → stored in "suppliers" collection)
├── password_hash (str)
├── contact_info (SupplierContactInfo)
│   ├── primary_email (EmailStr)              ← LOGIN KEY
│   ├── additional_emails (List[EmailStr])    ← CHECKED FOR EMAIL UNIQUENESS
│   ├── primary_phone (str)
│   ├── contact_person_name (Optional[str])   ← WHO TO REACH
│   ├── contact_person_title (Optional[str])
│   ├── contact_person_email (Optional[EmailStr])
│   └── contact_person_phone (Optional[str])
├── company_info (CompanyInfo)
│   ├── legal_name (str)                      ← OFFICIAL COMPANY NAME
│   ├── dba_name (Optional[str])              ← "DOING BUSINESS AS"
│   ├── business_address (CompanyAddress)      ← REQUIRED
│   │   ├── street_address_1 (str)
│   │   ├── street_address_2 (Optional[str])
│   │   ├── city, state, zip_code, country
│   └── shipping_address (Optional[CompanyAddress])
├── business_info (BusinessInfo)
│   ├── facebook_url, instagram_handle, twitter_handle, linkedin_url
│   ├── timezone (Optional[str])
│   └── support_email, support_phone
├── banking_info (Optional[BankingInfo])       ← ADDED LATER, NOT IN REGISTRATION
│   ├── bank_name (Optional[str])
│   ├── account_holder_name (Optional[str])
│   └── account_number_last4 (Optional[str])
├── product_ids (List[PydanticObjectId])       ← POPULATED BY PRODUCT SERVICE LATER
├── created_at (datetime)
└── updated_at (datetime)                      ← AUTO-UPDATED ON save()
```

### Index Analysis

The model defines one compound index:

| Index | Fields | Purpose |
|-------|--------|---------|
| Business location | `company_info.business_address.country` + `state` + `city` | Geo lookup for suppliers by location |

> **Key insight:** Notice `company_info.business_address.country` - that's a **3-level deep** nested field in an index. MongoDB supports dot notation at any nesting depth. This compound index follows the **left prefix rule** - you can query by country, country+state, or country+state+city, but NOT by city alone.

### Model Methods

The model provides one overridden method:

```python
await supplier.save()  # Automatically sets updated_at to utc_now() before saving
```

There are no other helper methods - your service layer will implement all business logic directly.

---

## 4. THE SERVICE CONTRACT

### Class Setup

```python
class SupplierAuthService:
    def __init__(self):
        self.password_min_length = 10          # Stricter: 10 vs User's 8
        self.password_max_length = 128
        self._kafka = get_kafka_producer()
        # Pattern now requires special char (!@#$%^&*) - User doesn't
        self.password_pattern = re.compile(
            r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*]).+$'
        )
```

### Method Signatures

| # | Method | MongoDB Operation | Returns |
|---|--------|------------------|---------|
| 1 | `generate_verification_token(supplier_id, email)` | None | `str` (JWT) |
| 2 | `generate_reset_token(supplier_id, email)` | None | `str` (JWT) |
| 3 | `verify_token(token, token_type)` | None | `Dict` (payload) |
| 4 | `hash_password(password)` | None | `str` |
| 5 | `verify_password(password, hash)` | None | `bool` |
| 6 | `validate_password(password, email)` | None | `None` (raises) |
| 7 | `is_email_available(email)` | `find_one` x3 (2 collections!) | `bool` |
| 8 | `register_supplier(~12 params)` | `insert` | `Dict` |
| 9 | `login(email, password)` | `find_one` + `save` | `Dict` |
| 10 | `verify_email(token)` | `get` + `save` | `Dict` |
| 11 | `request_password_reset(email)` | `find_one` | `Optional[str]` |
| 12 | `reset_password(token, new_password)` | `get` + `save` | `Dict` |

---

## 5. IMPLEMENTATION EXERCISES

---

### Exercise 5.1: Utility Foundation - Stricter Rules

**Concept:** Password validation with special character requirement + JWT tokens for supplier
**Difficulty:** Warm-up
**What's new from TASK_01:** Special character requirement in password, supplier-prefixed token types

#### Implement these 6 methods:

**5.1.1 through 5.1.3 - Token utilities (same pattern as TASK_01, different values)**

- `generate_verification_token(supplier_id, email)` → payload key is `"supplier_id"` (not `"user_id"`), type is `"supplier_email_verification"`, 6h expiry
- `generate_reset_token(supplier_id, email)` → type is `"supplier_password_reset"`, 1h expiry
- `verify_token(token, token_type)` → identical pattern to TASK_01

**5.1.4 through 5.1.6 - Password utilities (stricter than TASK_01)**

- `hash_password(password)` → identical to TASK_01
- `verify_password(password, hash)` → identical to TASK_01
- `validate_password(password, email)` → **DIFFERENT from TASK_01:**
  - Min length is `10` (not 8)
  - Pattern requires special character `(!@#$%^&*)` in addition to upper+lower+digit
  - Error message: `"Password must contain at least one uppercase letter, one lowercase letter, one digit, and one special character (!@#$%^&*)"`
  - Same email username check

#### Verify Exercise 5.1

```python
svc = SupplierAuthService()

# Password: must have special char
svc.validate_password("MyPass123!", "test@acme.com")  # OK
# svc.validate_password("MyPass123", "test@acme.com")  # Raises - no special char
# svc.validate_password("Short1!", "t@a.com")          # Raises - only 7 chars (need 10)
```

---

### Exercise 5.2: Cross-Collection Email Check

**Concept:** Querying TWO different collections in a single method
**Difficulty:** Easy-Medium
**What's new from TASK_01:** You now query **both** the `suppliers` collection AND the `users` collection. This is a cross-collection uniqueness check.

#### Implement: `is_email_available(self, email: str) -> bool`

**Business Rules:**
1. Normalize email (lowercase, strip)
2. Check suppliers - primary email: `Supplier.find_one({"contact_info.primary_email": email})`
3. Check suppliers - additional emails: `Supplier.find_one({"contact_info.additional_emails": email})`
4. Check users - primary email: `User.find_one({"contact_info.primary_email": email})`
5. Return `False` if ANY check finds a match, `True` otherwise

**The MongoDB Queries:**
```
Query 1: suppliers.findOne({"contact_info.primary_email": email})
Query 2: suppliers.findOne({"contact_info.additional_emails": email})
Query 3: users.findOne({"contact_info.primary_email": email})   ← CROSS-COLLECTION
```

> **Why cross-collection?** Imagine a supplier registers with `john@acme.com`, and a user also registers with `john@acme.com`. When `john@acme.com` tries to log in as a supplier, we find the supplier. When they try to log in as a user, we find the user. Same email, two accounts. This causes confusion and potential security issues. By checking both collections, we ensure global email uniqueness.

**Import required:**
```python
from shared.models.user import User  # Needed for cross-collection check
```

**Error handling:**
- Wrap in try/except
- Re-raise as `Exception(f"Failed to check email availability: {str(e)}")`

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

This is the same `find_one` pattern from TASK_01, just called three times on two different model classes. Beanie routes each query to the correct MongoDB collection based on the model's `Settings.name`.

`Supplier.find_one(...)` queries the `suppliers` collection.
`User.find_one(...)` queries the `users` collection.

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
async def is_email_available(self, email: str) -> bool:
    try:
        email = email.lower().strip()

        # Check suppliers (primary)
        supplier = await Supplier.find_one({"contact_info.primary_email": email})
        if supplier:
            return False

        # Check suppliers (additional)
        supplier = await Supplier.find_one({"contact_info.additional_emails": email})
        if supplier:
            return False

        # Check users (cross-collection)
        from shared.models.user import User
        user = await User.find_one({"contact_info.primary_email": email})
        if user:
            return False

        return True
    except Exception as e:
        raise Exception(f"Failed to check email availability: {str(e)}")
```

</details>

<details>
<summary><b>Hint Level 3</b> - Complete solution</summary>

The Hint Level 2 IS the complete solution for this method. The key learning point is the cross-collection pattern: using different Beanie model classes to query different MongoDB collections within the same method.

</details>

#### Verify Exercise 5.2

After completing TASK_01, you should have users in the `users` collection:
```bash
# This email was registered as a User in TASK_01
# Supplier email check should also catch it:
# await svc.is_email_available("consumer@example.com")  → False (found in users)
# await svc.is_email_available("brand-new@acme.com")    → True  (not in either)
```

#### Cross-Collection Checkpoint

**Question:** How does Beanie know which MongoDB collection to query?

<details>
<summary>Answer</summary>

Each Beanie `Document` class has an inner `Settings` class with a `name` attribute:
- `User` → queries the `users` collection (default name based on class)
- `Supplier.Settings.name = "suppliers"` → queries the `suppliers` collection

When you call `User.find_one(...)`, Beanie translates it to `db.users.findOne(...)`. When you call `Supplier.find_one(...)`, it becomes `db.suppliers.findOne(...)`. Same syntax, different collections.

</details>

---

### Exercise 5.3: Register Supplier - The Big Build

**Concept:** Constructing a document with multiple required embedded objects at multiple nesting depths
**Difficulty:** Medium-High
**What's new from TASK_01:** User registration took 3 parameters. Supplier registration takes many more. You must build multiple embedded objects and wire them together.

#### Implement: `register_supplier(self, primary_email, password, primary_phone, contact_person_name, contact_person_title, legal_name, street_address, city, state, zip_code, country, dba_name=None, support_email=None, timezone=None) -> Dict[str, Any]`

**Business Rules (implement in this exact order):**

1. **Normalize inputs:**
   - `primary_email.lower().strip()`
   - `contact_person_name.strip()`
   - `legal_name.strip()`

2. **Check email availability:**
   - Use `self.is_email_available(primary_email)`
   - If not available → `ValueError("Email already in use")`

3. **Validate password:**
   - `self.validate_password(password, primary_email)`

4. **Validate country code:**
   - `country` must be exactly 2 characters
   - If not → `ValueError("Country code must be a 2-letter ISO code")`

5. **Build the document** (inside → out):

```
Step A: Build CompanyAddress
    └── street_address_1, city, state (default "N/A"), zip_code, country

Step B: Build SupplierContactInfo
    └── primary_email, primary_phone, contact_person_name, title, email (defaults to primary_email)

Step C: Build CompanyInfo
    └── legal_name, dba_name, business_address (from A)

Step D: Build BusinessInfo
    └── timezone, support_email

Step E: Build Supplier
    └── password_hash, contact_info (B), company_info (C), business_info (D)
```

6. **Insert the document:**
   - `await supplier.insert()`

7. **Emit Kafka event:**
   - topic=`Topic.SUPPLIER`, action=`"registered"`, data=full supplier dump

8. **Generate verification token**

9. **Return result:**
```python
{
    "supplier": {
        "id": supplier_id,
        "email": supplier.contact_info.primary_email,
        "company_name": supplier.company_info.legal_name
    },
    "verification_token": verification_token
}
```

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

The construction pattern is the same as TASK_01's `register_consumer`, but with MORE embedded objects. Build each embedded object as a separate variable (address, contact_info, company_info, business_info), then assemble the Supplier from all of them.

Pay attention to `SupplierContactInfo` - it takes `contact_person_email=primary_email` (the contact person's email defaults to the supplier's primary email).

</details>

<details>
<summary><b>Hint Level 2</b> - The document construction</summary>

```python
supplier = Supplier(
    password_hash=self.hash_password(password),
    contact_info=SupplierContactInfo(
        primary_email=primary_email,
        primary_phone=primary_phone,
        contact_person_name=contact_person_name,
        contact_person_title=contact_person_title,
        contact_person_email=primary_email  # defaults to primary email
    ),
    company_info=CompanyInfo(
        legal_name=legal_name,
        dba_name=dba_name,
        business_address=CompanyAddress(
            street_address_1=street_address,
            city=city,
            state=state or "N/A",
            zip_code=zip_code,
            country=country
        )
    ),
    business_info=BusinessInfo(
        timezone=timezone,
        support_email=support_email
    )
)
```

</details>

#### Verify Exercise 5.3

```bash
curl -X POST http://localhost:8000/supplier/register \
  -H "Content-Type: application/json" \
  -d '{
    "primary_email": "sales@acme-electronics.com",
    "password": "SecurePass1!",
    "primary_phone": "+1-555-0100",
    "contact_person_name": "John Doe",
    "contact_person_title": "Sales Director",
    "legal_name": "Acme Electronics Inc",
    "street_address": "100 Commerce Blvd",
    "city": "New York",
    "state": "NY",
    "zip_code": "10001",
    "country": "US"
  }'
```

**Expected response (201 Created):**
```json
{
  "supplier": {
    "id": "<object-id>",
    "email": "sales@acme-electronics.com",
    "company_name": "Acme Electronics Inc"
  },
  "verification_token": "<jwt-token>"
}
```

**Test cross-collection email rejection (use an email from TASK_01):**
```bash
curl -X POST http://localhost:8000/supplier/register \
  -H "Content-Type: application/json" \
  -d '{
    "primary_email": "consumer@example.com",
    "password": "SecurePass1!",
    "primary_phone": "+1-555-0100",
    "contact_person_name": "Duplicate",
    "legal_name": "Dupe Corp",
    "street_address": "1 Main St",
    "city": "LA",
    "zip_code": "90001",
    "country": "US"
  }'
```
Should return 400: "Email already in use"

**Verify the nested structure in MongoDB shell:**
```javascript
db.suppliers.findOne(
  {"contact_info.primary_email": "sales@acme-electronics.com"},
  {
    "company_info.legal_name": 1,
    "company_info.business_address": 1,
    "contact_info.contact_person_name": 1
  }
)
```

---

### Exercise 5.4: The Login Flow

**Concept:** `find_one` + password verification + `save` for timestamp update
**Difficulty:** Medium
**What's new from TASK_01:** Querying the `Supplier` model instead of `User`, supplier-specific return format.

#### Implement: `login(self, email: str, password: str) -> Dict[str, Any]`

**Phases:**

#### Phase 1: Find the supplier
- Normalize email
- `Supplier.find_one({"contact_info.primary_email": email})`
- Not found → `ValueError("Invalid email or password")`

#### Phase 2: Verify password
- Use `self.verify_password(password, supplier.password_hash)`
- If wrong → `ValueError("Invalid email or password")`

#### Phase 3: Save and return
- Save the supplier (triggers `updated_at` update)
- Emit Kafka event: topic=`Topic.SUPPLIER`, action=`"login"`
- Return supplier data:

```python
{
    "id": supplier_id,
    "email": supplier.contact_info.primary_email,
    "company_name": supplier.company_info.legal_name
}
```

**Error handling:**
- `ValueError` → re-raise
- Any other → raise `Exception(f"Failed to login: {str(e)}")`

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

The login flow is nearly identical to TASK_01's login. The differences are:
1. Query `Supplier` instead of `User`
2. The returned dict includes a `company_name` field specific to suppliers
3. Use `Topic.SUPPLIER` for the Kafka event

</details>

#### Verify Exercise 5.4

```bash
curl -X POST http://localhost:8000/supplier/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "sales@acme-electronics.com",
    "password": "SecurePass1!"
  }'
```

**Expected (200 OK):**
```json
{
  "supplier": {
    "id": "<object-id>",
    "email": "sales@acme-electronics.com",
    "company_name": "Acme Electronics Inc"
  }
}
```

---

### Exercise 5.5: Email Verification

**Concept:** `Supplier.get(ObjectId)` + save
**Difficulty:** Easy-Medium
**What's reinforced:** The `get` by ID pattern from TASK_01, applied to a different collection.

#### Implement: `verify_email(self, token: str) -> Dict[str, Any]`

**Business Rules:**
1. Verify the token: `self.verify_token(token, "supplier_email_verification")`
   - Note: token type is `"supplier_email_verification"` (not `"email_verification"`)
   - Payload key is `"supplier_id"` (not `"user_id"`)
2. Get supplier by ID: `Supplier.get(ObjectId(supplier_id))`
   - Not found → `ValueError("Supplier not found")`
3. Save the supplier (to update `updated_at` timestamp)
4. Emit Kafka event: topic=`Topic.SUPPLIER`, action=`"email_verified"`
5. Return result:

```python
{
    "id": str(supplier.id),
    "email": supplier.contact_info.primary_email,
    "verified": True
}
```

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

This is the same pattern as TASK_01's verify_email. Just use `Supplier.get()` instead of `User.get()`, and extract `"supplier_id"` from the payload instead of `"user_id"`.

</details>

#### Verify Exercise 5.5

```bash
# Register a fresh supplier and capture the token, then verify:
curl -X POST http://localhost:8000/supplier/verify-email \
  -H "Content-Type: application/json" \
  -d '{"token": "<verification-token-from-registration>"}'
```

**Expected (200 OK):**
```json
{
  "id": "<object-id>",
  "email": "sales@acme-electronics.com",
  "verified": true
}
```

---

### Exercise 5.6: Password Reset Flow

**Concept:** Combining patterns from TASK_01, applied to the suppliers collection
**Difficulty:** Medium
**What's reinforced:** `find_one` → token → `get` by ID → field update → `save`

#### Implement TWO methods:

**5.6.1 - `request_password_reset(self, email: str) -> Optional[str]`**

Requirements:
1. Normalize email
2. `Supplier.find_one({"contact_info.primary_email": email})`
3. Not found → return `None`
4. Emit Kafka event: topic=`Topic.SUPPLIER`, action=`"password_reset_requested"`
5. Generate reset token using `self.generate_reset_token(str(supplier.id), email)`
6. Return the token

**5.6.2 - `reset_password(self, token: str, new_password: str) -> Dict[str, Any]`**

Requirements:
1. Verify token: `self.verify_token(token, "supplier_password_reset")`
2. Extract `supplier_id` and `email` from payload
3. Get supplier: `Supplier.get(ObjectId(supplier_id))`
   - Not found → `ValueError("Supplier not found")`
4. Validate new password: `self.validate_password(new_password, email)`
5. Update: `supplier.password_hash` = hash of new password
6. Save (triggers `updated_at` update)
7. Emit Kafka event: topic=`Topic.SUPPLIER`, action=`"password_reset"`
8. Return `{"message": "Password reset successful"}`

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

These are almost identical to TASK_01's password reset methods. The only differences: use `Supplier` instead of `User`, use `"supplier_password_reset"` as the token type, and extract `"supplier_id"` from the payload instead of `"user_id"`.

</details>

#### Verify Exercise 5.6

```bash
# Request reset
curl -X POST http://localhost:8000/supplier/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "sales@acme-electronics.com"}'

# Reset (you'd need to capture the token from direct service call)
curl -X POST http://localhost:8000/supplier/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "token": "<paste-reset-token>",
    "new_password": "NewSecure1Pass!"
  }'

# Login with new password
curl -X POST http://localhost:8000/supplier/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "sales@acme-electronics.com",
    "password": "NewSecure1Pass!"
  }'
```

---

## 6. VERIFICATION CHECKLIST

Before moving to the next task, verify:

### Functional Checks
- [ ] **Register supplier** - creates document with all embedded objects correctly nested (contact_info, company_info, business_info)
- [ ] **Cross-collection email check** - email registered as User (TASK_01) is rejected for supplier registration
- [ ] **Password validation** - rejects passwords without special characters, enforces 10-char minimum
- [ ] **Login success** - returns supplier data (id, email, company_name)
- [ ] **Login wrong password** - returns 401 with "Invalid email or password"
- [ ] **Email verification** - successfully retrieves supplier by ID from token
- [ ] **Password reset** - changes `password_hash`, old password no longer works

### Database Checks
- [ ] `db.suppliers.countDocuments()` - correct count
- [ ] `db.suppliers.getIndexes()` - shows the location compound index
- [ ] Supplier document has complete `company_info.business_address` nesting (3 levels deep)
- [ ] Supplier document has `contact_info.contact_person_name` populated
- [ ] After login: `updated_at` is refreshed

### Code Quality Checks
- [ ] Cross-collection import: `from shared.models.user import User`
- [ ] All token types use `"supplier_"` prefix
- [ ] All payload keys use `"supplier_id"` (not `"user_id"`)
- [ ] Kafka events use `Topic.SUPPLIER`
- [ ] Password min length is 10 (not 8)
- [ ] Password pattern requires `!@#$%^&*`

---

## 7. ADVANCED CHALLENGES

### Challenge A: Deep Index Analysis

Run this in MongoDB shell:
```javascript
// This query hits the 3-level deep business address compound index
db.suppliers.find({
  "company_info.business_address.country": "US",
  "company_info.business_address.state": "NY",
  "company_info.business_address.city": "New York"
}).explain("executionStats")
```

Questions:
1. Does it use the compound index? (Check `winningPlan.stage`)
2. What happens if you query ONLY by city (skipping country and state)?
```javascript
db.suppliers.find({
  "company_info.business_address.city": "New York"
}).explain("executionStats")
```
Does it still use the index?

<details>
<summary>Answer</summary>

No! Compound indexes follow the **left prefix rule**. The index is `(country, state, city)`. You can query:
- `country` alone - uses index
- `country + state` - uses index
- `country + state + city` - uses index
- `city` alone - full collection scan (can't skip the prefix)
- `state + city` - full collection scan (can't skip `country`)

This is one of the most important MongoDB index concepts. The field ORDER in a compound index matters.

</details>

### Challenge B: Supplier vs User - Why Two Collections?

The architecture uses separate collections for suppliers and users. Both have email, password, and login flows. Why not put them in the same collection with a `type` field?

Think about:
1. What happens to queries when you have mixed documents? (Hint: index selectivity)
2. What happens to validation when some fields are required for suppliers but don't exist for users?
3. How does the `product_ids` array on Supplier affect query patterns?

<details>
<summary>Answer</summary>

**Performance:** A single collection with mixed types means every query needs a `type` filter. With separate collections, each index is specialized.

**Schema flexibility:** MongoDB is schemaless, but Beanie enforces schemas per model. A single collection would need complex conditional validation: "if type=supplier, require company_info". Separate models keep validation clean.

**Operational independence:** Suppliers can be backed up, migrated, or sharded independently. Different read/write patterns can be optimized per collection.

**The trade-off:** Cross-collection email uniqueness requires multiple queries (as you implemented in Exercise 5.2). This is the cost of separation.

</details>

---

## 8. WHAT'S NEXT

You've now built authentication for both sides of the platform - Users and Suppliers. You understand:
- Cross-collection querying
- Complex nested document construction (3 levels deep)
- Why entities are separated into different collections

**TASK 04: Product Service** will build on these concepts with:
- Supplier-owned documents (products belong to suppliers via `supplier_id`)
- Product variants stored as a Dict of embedded objects
- Multi-location inventory tracking with embedded arrays
- Product status lifecycle (draft → active → discontinued)
- Three enums: `ProductStatus`, `ProductCategory`, `UnitType`

The patterns you learned here - find → validate → act → emit - will repeat in every service you build.
