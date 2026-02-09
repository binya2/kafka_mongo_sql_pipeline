# TASK 02: Supplier Service

## 1. MISSION BRIEFING

Suppliers are the **commerce engine** of the platform. While Users browse, like, and share - Suppliers stock the shelves. They are business entities (LLCs, corporations, sole proprietors) that list products, manage inventory, and fulfill orders.

Suppliers are deliberately **separate from Users**. They have their own collection, their own authentication, and their own set of capabilities.

### What You Will Build
The supplier methods inside the `UserService` class - handling supplier CRUD operations (create, read, update, delete) by writing MongoDB queries through Beanie ODM.

### What You Will Learn

| MongoDB Concept | Where You'll Use It |
|----------------|-------------------|
| Deep nested document construction | Building 3-level deep embedded objects (company_info.business_address.city) |
| Multiple required embedded documents | Constructing `contact_info` + `company_info` + `business_info` + `banking_info` |
| Multi-level partial updates | Updating fields across different nested objects |
| Compound index awareness | Understanding the location-based compound index |
| Hard delete pattern | Using `document.delete()` (contrast with User's soft delete) |

### How This Differs From TASK_01 (User)

| Aspect | User (TASK_01) | Supplier (TASK_02) |
|--------|---------------|-------------------|
| Embedded types | 3 (`ContactInfo`, `BusinessAddress`, `UserProfile`) | **6** (`SupplierContactInfo`, `CompanyAddress`, `CompanyInfo`, `BusinessInfo`, `BankingInfo`) |
| Registration input | 5 flat fields (email, password, name, phone, bio) | **Structured body** with nested objects (`CreateSupplierRequest`) |
| Indexes | None | **1 compound index** (location) |
| Nesting depth | 2 levels | **3 levels** (company_info.business_address.city) |
| Deletion | Soft delete (`deleted_at` timestamp) | **Hard delete** (document removed) |
| Partial update | 4 flat fields | **5 fields across 3 nested objects** |

---

## 2. BEFORE YOU START

### Prerequisites
- **TASK_01 (User) must be complete** - Supplier methods live in the same `UserService` class
- All 5 Docker containers running
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
apps/mongo_backend/schemas/user.py
```
The supplier schemas are in the same file as user schemas. Focus on:
- `CreateSupplierRequest` - structured body with nested `ContactInfoRequest`, `CompanyInfoRequest`, `BusinessInfoRequest`, `BankingInfoRequest`
- `UpdateSupplierRequest` - flat partial update fields: `primary_phone`, `legal_name`, `dba_name`, `support_email`, `support_phone`

#### Step 3: The Route (who calls you)
```
apps/mongo_backend/routes/user.py
```
The supplier routes are in the same file as user routes, using a separate `supplier_router` with prefix `/suppliers`. Notice:
- The route calls `user_service.create_supplier(body)` passing the full request body
- The route wraps returns with `supplier_response()` (strips `password_hash`, adds `id`)
- Update route destructures the body into individual keyword arguments

#### Step 4: The Utilities
```
apps/mongo_backend/utils/password.py          → hash_password(password)
apps/mongo_backend/utils/datetime_utils.py    → utc_now()
apps/mongo_backend/utils/serialization.py     → oid_to_str()
apps/mongo_backend/kafka/producer.py          → KafkaProducer.emit()
shared/kafka/topics.py                        → EventType.SUPPLIER_CREATED, etc.
shared/errors.py                              → DuplicateError, NotFoundError
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
│   ├── primary_email (EmailStr)              ← UNIQUENESS KEY
│   ├── additional_emails (List[EmailStr])
│   ├── primary_phone (str)
│   ├── contact_person_name (Optional[str])   ← WHO TO REACH
│   ├── contact_person_title (Optional[str])
│   ├── contact_person_email (Optional[EmailStr])
│   └── contact_person_phone (Optional[str])
├── company_info (CompanyInfo)
│   ├── legal_name (str)                      ← OFFICIAL COMPANY NAME
│   ├── dba_name (Optional[str])              ← "DOING BUSINESS AS"
│   ├── business_address (CompanyAddress)      ← REQUIRED, 3 LEVELS DEEP
│   │   ├── street_address_1 (str)
│   │   ├── street_address_2 (Optional[str])
│   │   ├── city, state, zip_code, country
│   └── shipping_address (Optional[CompanyAddress])
├── business_info (BusinessInfo)
│   ├── facebook_url, instagram_handle, twitter_handle, linkedin_url
│   ├── timezone (Optional[str])
│   └── support_email, support_phone
├── banking_info (Optional[BankingInfo])       ← CAN BE NULL
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

---

## 4. THE SERVICE CONTRACT

The supplier methods live in the same `UserService` class as user methods. Here is every supplier method you must implement.

### Method Signatures

| # | Method | MongoDB Operation | Returns |
|---|--------|------------------|---------|
| 1 | `create_supplier(body)` | `find_one` + `insert` | `Supplier` |
| 2 | `get_supplier(supplier_id)` | `get` by ObjectId | `Supplier` |
| 3 | `list_suppliers(skip, limit)` | `find_all` + skip/limit | `list[Supplier]` |
| 4 | `update_supplier(supplier_id, primary_phone, legal_name, dba_name, support_email, support_phone)` | `get` + `save` | `Supplier` |
| 5 | `delete_supplier(supplier_id)` | `get` + `delete` | `None` |

---

## 5. IMPLEMENTATION EXERCISES

---

### Exercise 5.1: Create Supplier - The Big Build

**Concept:** Constructing a document with multiple required embedded objects at multiple nesting depths
**Difficulty:** Medium-High
**What's new from TASK_01:** User creation took 5 flat parameters. Supplier creation receives a structured `CreateSupplierRequest` body with nested objects. You must map each request object to its corresponding model object.

#### Implement: `create_supplier(self, body) -> Supplier`

The `body` parameter is a `CreateSupplierRequest` with this structure:
```
body.password                              → str
body.contact_info                          → ContactInfoRequest
body.contact_info.primary_email            → EmailStr
body.contact_info.additional_emails        → List[EmailStr]
body.contact_info.primary_phone            → str
body.contact_info.contact_person_name      → Optional[str]
body.contact_info.contact_person_title     → Optional[str]
body.contact_info.contact_person_email     → Optional[EmailStr]
body.contact_info.contact_person_phone     → Optional[str]
body.company_info                          → CompanyInfoRequest
body.company_info.legal_name              → str
body.company_info.dba_name               → Optional[str]
body.company_info.business_address        → CompanyAddressRequest
body.company_info.shipping_address        → Optional[CompanyAddressRequest]
body.business_info                        → BusinessInfoRequest
body.banking_info                         → Optional[BankingInfoRequest]
```

**Business Rules (implement in this order):**

1. **Normalize email:** `body.contact_info.primary_email.lower().strip()`
2. **Check email uniqueness:**
   - Query `Supplier.find_one({"contact_info.primary_email": email})`
   - If found → raise `DuplicateError("Email already in use")`
3. **Build embedded objects (inside → out):**

```
Step A: Build SupplierContactInfo from body.contact_info
Step B: Build CompanyAddress from body.company_info.business_address
Step C: (Optional) Build shipping CompanyAddress from body.company_info.shipping_address
Step D: Build CompanyInfo from body.company_info + address(es)
Step E: Build BusinessInfo from body.business_info
Step F: (Optional) Build BankingInfo from body.banking_info
Step G: Build Supplier from all of the above
```

4. **Insert the document:** `await supplier.insert()`
5. **Emit Kafka event:** `EventType.SUPPLIER_CREATED`
6. **Return the Supplier document**

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

The construction pattern is the same as TASK_01's `create_user`, but with MORE embedded objects. Build each embedded object as a separate variable, then assemble the Supplier from all of them. Access nested request fields with dot notation: `body.contact_info.primary_email`.

</details>

<details>
<summary><b>Hint Level 2</b> - The document construction</summary>

```python
# Build contact info
ci = body.contact_info
contact_info = SupplierContactInfo(
    primary_email=email,
    additional_emails=ci.additional_emails,
    primary_phone=ci.primary_phone,
    contact_person_name=ci.contact_person_name,
    contact_person_title=ci.contact_person_title,
    contact_person_email=ci.contact_person_email,
    contact_person_phone=ci.contact_person_phone,
)

# Build address
addr = body.company_info.business_address
business_address = CompanyAddress(
    street_address_1=addr.street_address_1,
    street_address_2=addr.street_address_2,
    city=addr.city,
    state=addr.state,
    zip_code=addr.zip_code,
    country=addr.country,
)

# Build company info
company_info = CompanyInfo(
    legal_name=body.company_info.legal_name,
    dba_name=body.company_info.dba_name,
    business_address=business_address,
    shipping_address=...,  # same pattern if provided
)
```

</details>

<details>
<summary><b>Hint Level 3</b> - Near-complete solution</summary>

```python
async def create_supplier(self, body):
    email = body.contact_info.primary_email.lower().strip()
    existing = await Supplier.find_one({"contact_info.primary_email": email})
    if existing:
        raise DuplicateError("Email already in use")

    ci = body.contact_info
    contact_info = SupplierContactInfo(
        primary_email=email,
        additional_emails=ci.additional_emails,
        primary_phone=ci.primary_phone,
        contact_person_name=ci.contact_person_name,
        contact_person_title=ci.contact_person_title,
        contact_person_email=ci.contact_person_email,
        contact_person_phone=ci.contact_person_phone,
    )

    addr = body.company_info.business_address
    business_address = CompanyAddress(
        street_address_1=addr.street_address_1,
        street_address_2=addr.street_address_2,
        city=addr.city, state=addr.state,
        zip_code=addr.zip_code, country=addr.country,
    )

    shipping_address = None
    if body.company_info.shipping_address:
        sa = body.company_info.shipping_address
        shipping_address = CompanyAddress(
            street_address_1=sa.street_address_1,
            street_address_2=sa.street_address_2,
            city=sa.city, state=sa.state,
            zip_code=sa.zip_code, country=sa.country,
        )

    company_info = CompanyInfo(
        legal_name=body.company_info.legal_name,
        dba_name=body.company_info.dba_name,
        business_address=business_address,
        shipping_address=shipping_address,
    )

    bi = body.business_info
    business_info = BusinessInfo(
        facebook_url=bi.facebook_url, instagram_handle=bi.instagram_handle,
        twitter_handle=bi.twitter_handle, linkedin_url=bi.linkedin_url,
        timezone=bi.timezone, support_email=bi.support_email,
        support_phone=bi.support_phone,
    )

    banking_info = None
    if body.banking_info:
        banking_info = BankingInfo(
            bank_name=body.banking_info.bank_name,
            account_holder_name=body.banking_info.account_holder_name,
            account_number_last4=body.banking_info.account_number_last4,
        )

    supplier = Supplier(
        password_hash=hash_password(body.password),
        contact_info=contact_info,
        company_info=company_info,
        business_info=business_info,
        banking_info=banking_info,
    )
    await supplier.insert()

    self._kafka.emit(
        event_type=EventType.SUPPLIER_CREATED,
        entity_id=oid_to_str(supplier.id),
        data=supplier.model_dump(mode="json"),
    )
    return supplier
```

</details>

#### Verify Exercise 5.1

```bash
curl -X POST http://localhost:8000/suppliers \
  -H "Content-Type: application/json" \
  -d '{
    "password": "SecurePass1!",
    "contact_info": {
      "primary_email": "sales@acme-electronics.com",
      "primary_phone": "+1-555-0100",
      "contact_person_name": "John Doe",
      "contact_person_title": "Sales Director"
    },
    "company_info": {
      "legal_name": "Acme Electronics Inc",
      "business_address": {
        "street_address_1": "100 Commerce Blvd",
        "city": "New York",
        "state": "NY",
        "zip_code": "10001",
        "country": "US"
      }
    }
  }'
```

**Expected response (201 Created):**
```json
{
  "id": "<object-id>",
  "contact_info": {
    "primary_email": "sales@acme-electronics.com",
    "additional_emails": [],
    "primary_phone": "+1-555-0100",
    "contact_person_name": "John Doe",
    "contact_person_title": "Sales Director",
    ...
  },
  "company_info": {
    "legal_name": "Acme Electronics Inc",
    "business_address": {
      "street_address_1": "100 Commerce Blvd",
      "city": "New York",
      "state": "NY",
      ...
    }
  },
  ...
}
```

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

### Exercise 5.2: Get Supplier - ID Lookup

**Concept:** `Supplier.get(PydanticObjectId)` - same pattern as User, different collection
**Difficulty:** Easy
**What's reinforced:** The `get` by ID pattern from TASK_01.

#### Implement: `get_supplier(self, supplier_id: str) -> Supplier`

**Business Rules:**
1. Convert string `supplier_id` to `PydanticObjectId`
   - If invalid → raise `NotFoundError("Supplier not found")`
2. Fetch the supplier by `_id`
   - If not found → raise `NotFoundError("Supplier not found")`
3. Return the Supplier document

> **Note:** Unlike User, Supplier does NOT have soft delete. No `deleted_at` check needed.

<details>
<summary><b>Hint Level 1</b> - Pattern</summary>

```python
try:
    supplier = await Supplier.get(PydanticObjectId(supplier_id))
except Exception:
    raise NotFoundError("Supplier not found")
if not supplier:
    raise NotFoundError("Supplier not found")
return supplier
```

</details>

#### Verify Exercise 5.2

```bash
curl http://localhost:8000/suppliers/<supplier-id>
```

---

### Exercise 5.3: List Suppliers - Pagination

**Concept:** `find_all()` + skip/limit (no filter needed - no soft delete)
**Difficulty:** Easy
**What's different from TASK_01:** No `deleted_at` filter needed since suppliers use hard delete.

#### Implement: `list_suppliers(self, skip: int = 0, limit: int = 20) -> list[Supplier]`

**Business Rules:**
1. Query all suppliers (no filter needed)
2. Apply `skip` and `limit` (cap at 100)
3. Return the list

<details>
<summary><b>Hint Level 1</b> - Pattern</summary>

```python
return (
    await Supplier.find_all()
    .skip(skip)
    .limit(min(limit, 100))
    .to_list()
)
```

</details>

#### Verify Exercise 5.3

```bash
curl "http://localhost:8000/suppliers?limit=10&skip=0"
```

---

### Exercise 5.4: Update Supplier - Multi-Level Partial Update

**Concept:** Updating fields across different nested objects in a single save
**Difficulty:** Medium
**What's new from TASK_01:** In TASK_01, all updatable fields lived in two objects (`profile` and `contact_info`). Here, updatable fields are spread across THREE nested objects: `contact_info.primary_phone`, `company_info.legal_name`, `company_info.dba_name`, `business_info.support_email`, `business_info.support_phone`.

#### Implement: `update_supplier(self, supplier_id, primary_phone=None, legal_name=None, dba_name=None, support_email=None, support_phone=None) -> Supplier`

**Business Rules:**
1. Fetch the supplier using `self.get_supplier(supplier_id)`
2. For each parameter that is **not None**, update the corresponding nested field:
   - `primary_phone` → `supplier.contact_info.primary_phone`
   - `legal_name` → `supplier.company_info.legal_name`
   - `dba_name` → `supplier.company_info.dba_name`
   - `support_email` → `supplier.business_info.support_email`
   - `support_phone` → `supplier.business_info.support_phone`
3. Save the supplier (auto-updates `updated_at`)
4. Emit `EventType.SUPPLIER_UPDATED` Kafka event
5. Return the updated Supplier document

**Key learning:** Notice how a single `save()` call updates fields across three different embedded objects. Beanie replaces the entire document in MongoDB - it doesn't send partial updates. This is the "fetch → modify → replace" pattern.

<details>
<summary><b>Hint Level 1</b> - Direction</summary>

Same pattern as TASK_01's `update_user` - check each param for `is not None`, then assign. The difference is which nested object each field belongs to.

</details>

<details>
<summary><b>Hint Level 2</b> - Pattern</summary>

```python
supplier = await self.get_supplier(supplier_id)

if primary_phone is not None:
    supplier.contact_info.primary_phone = primary_phone
if legal_name is not None:
    supplier.company_info.legal_name = legal_name
if dba_name is not None:
    supplier.company_info.dba_name = dba_name
if support_email is not None:
    supplier.business_info.support_email = support_email
if support_phone is not None:
    supplier.business_info.support_phone = support_phone

await supplier.save()

self._kafka.emit(
    event_type=EventType.SUPPLIER_UPDATED,
    entity_id=oid_to_str(supplier.id),
    data=supplier.model_dump(mode="json"),
)
return supplier
```

</details>

#### Verify Exercise 5.4

```bash
curl -X PATCH http://localhost:8000/suppliers/<supplier-id> \
  -H "Content-Type: application/json" \
  -d '{
    "legal_name": "Acme Electronics LLC",
    "support_email": "help@acme-electronics.com"
  }'
```

**Expected:** Supplier with updated `company_info.legal_name` and `business_info.support_email`, all other fields unchanged.

**Verify in MongoDB shell:**
```javascript
db.suppliers.findOne(
  {"_id": ObjectId("<supplier-id>")},
  {"company_info.legal_name": 1, "business_info.support_email": 1, "updated_at": 1}
)
```

---

### Exercise 5.5: Delete Supplier - Hard Delete

**Concept:** `document.delete()` - permanent removal (contrast with User's soft delete)
**Difficulty:** Easy
**What's new from TASK_01:** In TASK_01, you set `deleted_at` and saved. Here, you permanently remove the document from the collection.

#### Implement: `delete_supplier(self, supplier_id: str) -> None`

**Business Rules:**
1. Fetch the supplier using `self.get_supplier(supplier_id)`
2. Delete the document permanently: `await supplier.delete()`
3. Emit `EventType.SUPPLIER_DELETED` Kafka event
4. Return nothing

**Why hard delete here but soft delete for Users?**
- Users have relationships (orders, posts) that reference them. Soft delete preserves referential integrity.
- Suppliers can also have products, but the system design chooses permanent removal. Products would become orphaned - this is a deliberate simplification.

<details>
<summary><b>Hint Level 1</b> - Pattern</summary>

```python
supplier = await self.get_supplier(supplier_id)
await supplier.delete()

self._kafka.emit(
    event_type=EventType.SUPPLIER_DELETED,
    entity_id=oid_to_str(supplier.id),
    data={"supplier_id": oid_to_str(supplier.id)},
)
```

</details>

#### Verify Exercise 5.5

```bash
# Delete the supplier
curl -X DELETE http://localhost:8000/suppliers/<supplier-id>
# Expected: 204 No Content

# Try to get the deleted supplier
curl http://localhost:8000/suppliers/<supplier-id>
# Expected: 404 Not Found

# Verify in MongoDB shell - document should be GONE
db.suppliers.findOne({"_id": ObjectId("<supplier-id>")})
# Returns null (document permanently removed)
```

---

## 6. VERIFICATION CHECKLIST

Before moving to the next task, verify:

### Functional Checks
- [ ] **Create supplier** - creates document with all embedded objects correctly nested (contact_info, company_info, business_info)
- [ ] **Duplicate email rejected** - same email for two suppliers fails with 409
- [ ] **Optional fields** - `banking_info: null`, `shipping_address: null` when not provided
- [ ] **Get supplier** - returns full supplier document by ID
- [ ] **Get non-existent supplier** - returns 404
- [ ] **List suppliers** - returns array, respects skip/limit
- [ ] **Update supplier** - updates fields across `contact_info`, `company_info`, and `business_info`
- [ ] **Delete supplier** - permanently removes document from collection

### Database Checks
- [ ] `db.suppliers.countDocuments()` - correct count
- [ ] `db.suppliers.getIndexes()` - shows the location compound index
- [ ] Supplier document has complete `company_info.business_address` nesting (3 levels deep)
- [ ] Supplier document has `contact_info.contact_person_name` populated
- [ ] After update: `updated_at` is refreshed
- [ ] After delete: document is completely gone (not soft-deleted)

### Code Quality Checks
- [ ] `DuplicateError` used for email conflicts
- [ ] `NotFoundError` used for missing suppliers
- [ ] Kafka events emitted: `SUPPLIER_CREATED`, `SUPPLIER_UPDATED`, `SUPPLIER_DELETED`
- [ ] All operations use Beanie ODM

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

### Challenge B: Soft Delete vs Hard Delete

The architecture uses soft delete for Users and hard delete for Suppliers. Think about:

1. What happens to a supplier's products when the supplier is hard deleted? (They become orphaned - `product.supplier_id` points to a non-existent supplier)
2. How would you change the design to handle this? (Options: cascade delete products, soft delete supplier instead, or check for products before allowing delete)
3. What are the trade-offs of each approach?

<details>
<summary>Answer</summary>

**Cascade delete:** Delete all supplier's products too. Clean but destructive - loses product data.

**Soft delete:** Add `deleted_at` to Supplier like User has. Preserves data but requires filtering in all supplier queries.

**Pre-check:** In `delete_supplier`, check `supplier.product_ids` - if non-empty, reject the delete. Safe but frustrating for users.

The current design prioritizes simplicity. In production, you'd likely use soft delete for suppliers too, or cascade delete their products.

</details>

### Challenge C: Supplier vs User - Why Two Collections?

The architecture uses separate collections for suppliers and users. Both have email, password, and similar patterns. Why not put them in the same collection with a `type` field?

<details>
<summary>Answer</summary>

**Performance:** A single collection with mixed types means every query needs a `type` filter. With separate collections, each index is specialized.

**Schema flexibility:** Beanie enforces schemas per model. A single collection would need conditional validation. Separate models keep validation clean.

**Operational independence:** Suppliers can be backed up, migrated, or sharded independently.

**The trade-off:** If you wanted cross-collection email uniqueness, you'd need to check both collections (adding a query to `create_supplier`). The current design only checks within the supplier collection.

</details>

---

## 8. WHAT'S NEXT

You've now built CRUD operations for both Users and Suppliers. You understand:
- Complex nested document construction (3 levels deep)
- Multi-level partial updates across nested objects
- Hard delete vs soft delete trade-offs
- Compound index behavior (left prefix rule)

**TASK 04: Product Service** will build on these concepts with:
- Supplier-owned documents (products belong to suppliers via `supplier_id`)
- Product variants stored as a Dict of embedded objects
- Multi-location inventory tracking with embedded arrays
- Product status lifecycle (DRAFT → ACTIVE → DISCONTINUED / OUT_OF_STOCK)
- Back-reference management (adding/removing product_ids from supplier.product_ids)
- Three enums: `ProductStatus`, `ProductCategory`, `UnitType`

The patterns you learned here - fetch → validate → build → persist → emit - will repeat in every service you build.
