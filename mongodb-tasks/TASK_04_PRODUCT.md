# TASK 04: Product Catalog Service

## 1. MISSION BRIEFING

Products are the **commerce core** of the platform. While Users socialize, Products are what actually get bought and sold. Every product is owned by a Supplier and goes through a lifecycle from draft to active to eventually discontinued or deleted.

This is the **most structurally complex entity** you've built so far. The Product model has 7 different embedded document types, a `Dict[str, ProductVariant]` map field (not just a list!), multi-location inventory tracking, and a 5-state lifecycle machine.

### What You Will Build
The `ProductService` class - methods covering CRUD, a 5-state lifecycle machine, cross-collection supplier validation, public product discovery with advanced filtering, and inventory-aware operations.

### What You Will Learn

| MongoDB Concept | Where You'll Use It |
|----------------|-------------------|
| **`Dict` (Map) field queries** | Variants stored as `Dict[str, ProductVariant]` - querying nested dict values |
| **`$gte` / `$lte` range queries** | Price range filtering on `base_price_cents` |
| **`$in` operator** | Multi-status filtering (`status in ["active", "draft"]`) |
| **`$ne` with compound queries** | Name uniqueness excluding current doc + SKU uniqueness per supplier |
| **`$addToSet` atomic update** | Adding product ID to supplier's `product_ids` array |
| **Cross-collection validation** | Supplier must exist before creating products |
| **Denormalized data** | Caching `supplier_info` dict on product document |
| **State machine transitions** | 5-status lifecycle with guarded transitions |
| **Complex document construction** | Building 7+ embedded sub-documents from flat request data |
| **Cursor pagination** | Both supplier listing and public discovery |

### How This Differs From Previous Tasks

| Aspect | Auth (01/02) | Product (04) |
|--------|-------------|-------------|
| Embedded docs | 2-5 types | **7 types** |
| Data structure | Lists + flat fields | **Dict/Map** (variants) + Lists |
| Query operators | basic `find_one` | **`$gte`/`$lte`, `$in`, `$ne`** |
| Enums | None | **3 enums** (ProductStatus, ProductCategory, UnitType) |
| Collections touched | 1 | **2** (products + suppliers for validation) |
| Write pattern | Insert + update | **Insert + partial + lifecycle transitions** |
| Inventory | N/A | **Multi-location + variant inventory** |

---

## 2. BEFORE YOU START

### Prerequisites
- **TASK_01 (User) must be complete** - You need users in the database
- **TASK_02 (Supplier) must be complete** - Products require a supplier
- Have at least one registered supplier from TASK_02

### Files You MUST Read Before Coding

| Order | File | Why |
|-------|------|-----|
| 1 | `shared/models/product.py` | The data model - 239 lines, 3 enums, 7 embedded types, 3 indexes, Dict-based variants |
| 2 | `apps/backend-service/src/schemas/product.py` | Request/response schemas including nested variant/location requests |
| 3 | `apps/backend-service/src/routes/product.py` | Endpoints: CRUD + lifecycle + public access |
| 4 | `shared/models/supplier.py` | Cross-collection reference - you'll read supplier data |
| 5 | `apps/backend-service/src/kafka/topics.py` | `Topic.PRODUCT` for event emission |

### The Data Flow

```
HTTP Request (Supplier JWT)
    │
    ▼
┌─────────┐   Extracts supplier_id from
│  Route   │   X-Supplier-ID header
│          │
│  Calls   │
│  your    │
│  service │
    │
    ▼
┌──────────────────────────────────────────────────────┐
│              ProductService (YOU WRITE THIS)           │
│                                                        │
│  Reads from TWO collections:                           │
│  ├── products (main CRUD + lifecycle)                  │
│  └── suppliers (validation: exists?)                   │
│                                                        │
│  Writes to TWO collections:                            │
│  ├── products (insert, update, status changes)         │
│  └── suppliers ($addToSet product_id to supplier)      │
│                                                        │
│  Also emits Kafka events:                              │
│  └── Topic.PRODUCT → created, deleted, published,      │
│       discontinued, out_of_stock                       │
└──────────────────────────────────────────────────────┘
```

### The Product Lifecycle State Machine

```
                 ┌───────────────┐
                 │    DRAFT      │  ← Created here
                 └───────┬───────┘
                         │ publish_product()
                         ▼
                 ┌───────────────┐
                 │    ACTIVE     │
                 └──┬─────────┬──┘
                    │         │
               mark_out_of    │ discontinue_product()
               _stock()       │
                    ▼         ▼
              ┌──────────┐ ┌──────────────┐
              │OUT_OF_   │ │DISCONTINUED  │
              │STOCK     │ │              │
              └──────────┘ └──────────────┘
                    │
                    │ discontinue_product() (also valid)
                    ▼
              ┌──────────────┐
              │DISCONTINUED  │
              └──────────────┘

              ┌───────────────┐
              │   DELETED     │  ← set status from any non-deleted state
              └───────────────┘
```

---

## 3. MODEL DEEP DIVE

### Embedded Document Hierarchy (7 types)

```
Product (Document)
│
├── supplier_id: PydanticObjectId         ← Reference to Supplier
├── supplier_info: Dict[str, str]          ← Denormalized supplier snapshot
│
├── name: str                              ← Product name
├── short_description: Optional[str]       ← Brief summary
│
├── topic_descriptions: List[TopicDescription]
│   └── topic (str), description (str), display_order (int)
│
├── category: ProductCategory              ← One of 11 categories
├── unit_type: UnitType                    ← piece, pair, set, kg, etc.
│
├── metadata: ProductMetadata
│   ├── base_sku: str                      ← Product-level SKU
│   └── brand: Optional[str]
│
├── stock_locations: List[StockLocation]   ← Multi-warehouse inventory
│   └── location_name, street_address, city, state, zip_code, country, quantity
│
├── variants: Dict[str, ProductVariant]    ← THE BIG ONE: Map of variants
│   └── Each variant has:
│       ├── variant_id (str)
│       ├── variant_name (str)
│       ├── attributes: List[VariantAttribute]  ← Color: Red, Size: L
│       ├── price_cents (int), cost_cents (Optional[int])
│       ├── quantity (int)
│       ├── package_dimensions: PackageDimensions
│       │   └── width_cm, height_cm, depth_cm
│       └── image_url (Optional[HttpUrl])
│
├── base_price_cents: int                  ← Base price in cents
│
├── stats: ProductStats                    ← Denormalized counters
│   └── view_count, favorite_count, purchase_count, total_reviews
│
├── status: ProductStatus                  ← draft/active/out_of_stock/discontinued/deleted
├── published_at: Optional[datetime]       ← First published timestamp
├── created_at: datetime
└── updated_at: datetime                   ← AUTO-UPDATED ON save()
```

### Enums

```python
class ProductStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"
    DELETED = "deleted"

class ProductCategory(str, Enum):
    ELECTRONICS = "electronics"
    FASHION = "fashion"
    BEAUTY = "beauty"
    HOME_GARDEN = "home_garden"
    # ... 11 total values

class UnitType(str, Enum):
    PIECE = "piece"
    PAIR = "pair"
    SET = "set"
    # ... 12 total values
```

### Why `variants` is a `Dict` Not a `List`

```python
# Model definition:
variants: Dict[str, ProductVariant]  # Keyed by variant name

# In MongoDB, stored as:
{
  "variants": {
    "Red-Large": { "variant_id": "v1", "price_cents": 9999, ... },
    "Blue-Small": { "variant_id": "v2", "price_cents": 8999, ... }
  }
}
```

A Dict/Map gives you:
- **O(1) lookup by name** (`variants.get("Red-Large")`)
- **Unique keys enforced** by Python dict
- **But**: you can't use `$in` on dict keys, and querying deep into dict values requires dot-notation on dynamic keys

### Index Analysis (3 indexes)

```python
indexes = [
    # Index 1: Supplier's products
    [("supplier_id", 1)],
    # → Used by: list_products(), get_product() ownership check

    # Index 2: Status-based filtering
    [("status", 1)],
    # → Used by: list_public_products(), lifecycle queries

    # Index 3: Recent products
    [("created_at", -1)],
    # → Used by: sorting in list queries
]
```

> **Note:** Unlike the Supplier model's compound index, these are simple single-field indexes. For a compound query like `{supplier_id: X, status: "active"}`, MongoDB will use the `supplier_id` index and post-filter for status.

### Model Methods

```python
await product.save()  # Automatically sets updated_at to utc_now() before saving
```

There are no other helper methods - your service layer will implement all business logic directly.

---

## 4. THE SERVICE CONTRACT

Your service file: `apps/backend-service/src/services/product.py`

### Method Overview

| # | Method | MongoDB Concepts | Difficulty |
|---|--------|-----------------|-----------|
| 1 | `_check_name_uniqueness(name, exclude_id)` | `find_one` + `$ne` | Medium |
| 2 | `_check_sku_uniqueness(supplier_id, sku, exclude_id)` | Compound `find_one` + `$ne` | Medium |
| 3 | `_add_product_to_supplier(supplier, product_id)` | `$addToSet` atomic update | Medium |
| 4 | `create_product(supplier_id, product_data)` | Cross-collection get + complex insert | Hard |
| 5 | `get_product(product_id, supplier_id)` | Compound `find_one` (anti-enumeration) | Easy |
| 6 | `list_products(supplier_id, ...)` | `$in`, cursor pagination | Hard |
| 7 | `update_product(product_id, supplier_id, updates)` | Get + uniqueness checks + partial update | Medium |
| 8 | `delete_product(product_id, supplier_id)` | Get + set status to DELETED | Easy |
| 9 | `publish_product(product_id, supplier_id)` | Status gate + transition | Medium |
| 10 | `discontinue_product(product_id, supplier_id)` | Status gate + transition | Easy |
| 11 | `mark_out_of_stock(product_id, supplier_id)` | Status gate + transition | Easy |
| 12 | `get_public_product(product_id)` | Multi-condition `find_one` | Medium |
| 13 | `list_public_products(...)` | `$gte`/`$lte`, cursor pagination | Hard |

---

## 5. EXERCISES

---

### Exercise 5.1: Helper Methods Foundation

**Concept**: Basic MongoDB queries with `$ne` and `$addToSet`

These helper methods are called by every other method in the service. Get them right first.

#### 5.1a: `_check_name_uniqueness(name, exclude_id=None)`

**What it does**: Checks if a product name is already taken. When updating, excludes the current product from the check.

**MongoDB Pattern**: `find_one` with optional `$ne` on `_id`

```
Query when CREATING:
  { "name": "Cool Headphones" }

Query when UPDATING (exclude current product):
  { "name": "Cool Headphones", "_id": { "$ne": ObjectId("abc123") } }
```

> **Why `$ne` instead of two separate queries?** A single atomic query is both faster and race-condition-safe.

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def _check_name_uniqueness(self, name: str, exclude_id: Optional[str] = None) -> None:
    query = {"name": name}
    if exclude_id:
        query["_id"] = {"$ne": ObjectId(exclude_id)}

    existing = await Product.find_one(query)
    if existing:
        raise ValueError(f"Product name '{name}' already exists")
```
</details>

---

#### 5.1b: `_check_sku_uniqueness(supplier_id, base_sku, exclude_id=None)`

**What it does**: Checks if a base SKU already exists **for this specific supplier**. Different suppliers can have the same SKU.

**MongoDB Pattern**: Compound query on `supplier_id` + nested field `metadata.base_sku`

```
Query: {
  "supplier_id": PydanticObjectId("..."),
  "metadata.base_sku": "HDPH-001",    ← Dot-notation into embedded doc!
  "_id": { "$ne": ObjectId("...") }    ← Optional: exclude current
}
```

> **Think about it**: Why is SKU uniqueness per-supplier but name uniqueness is global? Because the SKU is an internal identifier that only the supplier sees, while the product name is the public-facing name.

<details>
<summary>Full Implementation</summary>

```python
async def _check_sku_uniqueness(self, supplier_id: str, base_sku: str, exclude_id: Optional[str] = None) -> None:
    query = {
        "supplier_id": PydanticObjectId(supplier_id),
        "metadata.base_sku": base_sku.upper()
    }
    if exclude_id:
        query["_id"] = {"$ne": ObjectId(exclude_id)}

    existing = await Product.find_one(query)
    if existing:
        raise ValueError(f"SKU '{base_sku}' already exists for this supplier")
```
</details>

---

#### 5.1c: `_add_product_to_supplier(supplier, product_id)`

**What it does**: Adds the new product's ID to the supplier's `product_ids` array using `$addToSet`.

**MongoDB Pattern**: `$addToSet` - adds an element to an array ONLY if it doesn't already exist (idempotent).

```python
# $addToSet vs $push:
# $push:     Always adds → can create duplicates
# $addToSet: Only adds if not present → idempotent (safe to retry)
```

**Error handling**: Wrap in try/except, print a warning but don't fail.

<details>
<summary>Full Implementation</summary>

```python
async def _add_product_to_supplier(self, supplier: Supplier, product_id: PydanticObjectId) -> None:
    try:
        await supplier.update({"$addToSet": {"product_ids": product_id}})
    except Exception as e:
        print(f"Warning: Failed to update supplier array: {e}")
```
</details>

---

### Exercise 5.2: Create Product - The Construction Challenge

**Concept**: Building a complex document with 7+ embedded types from flat request data, cross-collection validation, denormalized snapshot, and `$addToSet`

#### The Method Signature

```python
async def create_product(
    self,
    supplier_id: str,
    product_data: Dict[str, Any]
) -> Dict[str, Any]:
```

#### Step-by-Step Algorithm

```
1. Get supplier by ID (cross-collection)
   └── Supplier.get(PydanticObjectId(supplier_id))
   └── Raise "Supplier not found" if None

2. Check name uniqueness (global)
   └── await self._check_name_uniqueness(product_data["name"])

3. Check SKU uniqueness (per supplier)
   └── await self._check_sku_uniqueness(supplier_id, product_data["base_sku"])

4. Build ProductMetadata
   └── ProductMetadata(base_sku=..., brand=...)

5. Build variants Dict[str, ProductVariant]
   └── For each (variant_name, variant_data) in product_data["variants"]:
       ├── Build List[VariantAttribute] from variant_data["attributes"]
       ├── Build PackageDimensions from variant_data["package_dimensions"]
       └── Build ProductVariant with all fields

6. Build List[StockLocation]
   └── For each loc in product_data["stock_locations"]:
       └── StockLocation(location_name=..., city=..., quantity=..., ...)

7. Build List[TopicDescription]
   └── For each td in product_data["topic_descriptions"]:
       └── TopicDescription(topic=..., description=..., display_order=...)

8. Build denormalized supplier_info
   └── {"id": str(supplier.id), "name": supplier.company_info.legal_name}

9. Construct Product document with ALL embedded objects
   └── Product(supplier_id=..., name=..., metadata=..., variants=..., ...)
   └── Status = DRAFT

10. await product.insert()

11. Emit Kafka event (Topic.PRODUCT, action="created")

12. await self._add_product_to_supplier(supplier, product.id)

13. Return summary dict
```

#### The Denormalized `supplier_info` Pattern

```python
# Why store supplier data ON the product?
# Because when displaying a product, you don't want to JOIN to the suppliers collection.
# MongoDB doesn't have JOINs - instead, you embed frequently-read data.

supplier_info = {
    "id": str(supplier.id),
    "name": supplier.company_info.legal_name
}
```

> **Trade-off**: If the supplier changes their name, the product still shows the old name. This is acceptable because business names rarely change, and a background job can refresh denormalized data.

#### Building the Variants Dict (the tricky part)

```python
# product_data["variants"] arrives as:
# {
#   "Red-Large": {
#     "variant_id": "v1",
#     "attributes": [{"attribute_name": "Color", "attribute_value": "Red"}, ...],
#     "package_dimensions": {"width_cm": 30, "height_cm": 15, "depth_cm": 10},
#     "price_cents": 9999,
#     ...
#   }
# }

variants_dict = {}
for variant_name, variant_data in product_data.get("variants", {}).items():
    attributes = [VariantAttribute(...) for attr in variant_data["attributes"]]
    package_dimensions = PackageDimensions(...)
    variants_dict[variant_name] = ProductVariant(
        variant_id=variant_data["variant_id"],
        variant_name=variant_name,
        attributes=attributes,
        price_cents=variant_data["price_cents"],
        # ... more fields
    )
```

<details>
<summary>Hint Level 3 - Full Implementation</summary>

```python
async def create_product(self, supplier_id: str, product_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # 1. Get supplier
        supplier = await Supplier.get(PydanticObjectId(supplier_id))
        if not supplier:
            raise ValueError("Supplier not found")

        # 2-3. Uniqueness checks
        await self._check_name_uniqueness(product_data["name"])
        await self._check_sku_uniqueness(supplier_id, product_data["base_sku"])

        # 4. Build metadata
        metadata = ProductMetadata(
            base_sku=product_data["base_sku"],
            brand=product_data.get("brand")
        )

        # 5. Build variants
        variants_dict = {}
        for variant_name, variant_data in product_data.get("variants", {}).items():
            attributes = [
                VariantAttribute(
                    attribute_name=attr["attribute_name"],
                    attribute_value=attr["attribute_value"]
                )
                for attr in variant_data.get("attributes", [])
            ]
            pkg_dims = variant_data["package_dimensions"]
            package_dimensions = PackageDimensions(
                width_cm=pkg_dims["width_cm"],
                height_cm=pkg_dims["height_cm"],
                depth_cm=pkg_dims["depth_cm"]
            )
            variants_dict[variant_name] = ProductVariant(
                variant_id=variant_data["variant_id"],
                variant_name=variant_name,
                attributes=attributes,
                price_cents=variant_data["price_cents"],
                cost_cents=variant_data.get("cost_cents"),
                quantity=variant_data.get("quantity", 0),
                package_dimensions=package_dimensions,
                image_url=variant_data.get("image_url")
            )

        # 6. Build stock locations
        stock_locations = [
            StockLocation(
                location_name=loc["location_name"],
                street_address=loc.get("street_address"),
                city=loc["city"],
                state=loc.get("state"),
                zip_code=loc["zip_code"],
                country=loc["country"],
                quantity=loc.get("quantity", 0)
            )
            for loc in product_data.get("stock_locations", [])
        ]

        # 7. Build topic descriptions
        topic_descriptions = [
            TopicDescription(
                topic=td["topic"],
                description=td["description"],
                display_order=td.get("display_order", 0)
            )
            for td in product_data.get("topic_descriptions", [])
        ]

        # 8. Denormalized supplier info
        supplier_info = {
            "id": str(supplier.id),
            "name": supplier.company_info.legal_name
        }

        # 9. Construct product
        product = Product(
            supplier_id=PydanticObjectId(supplier_id),
            supplier_info=supplier_info,
            name=product_data["name"],
            short_description=product_data.get("short_description"),
            topic_descriptions=topic_descriptions,
            category=ProductCategory(product_data["category"]),
            unit_type=UnitType(product_data.get("unit_type", "piece")),
            metadata=metadata,
            stock_locations=stock_locations,
            variants=variants_dict,
            base_price_cents=product_data["base_price_cents"],
            status=ProductStatus.DRAFT
        )

        # 10. Insert
        await product.insert()

        # 11. Kafka event
        product_id = oid_to_str(product.id)
        self._kafka.emit(
            topic=Topic.PRODUCT,
            action="created",
            entity_id=product_id,
            data=product.model_dump(mode="json"),
        )

        # 12. Update supplier's product array
        await self._add_product_to_supplier(supplier, product.id)

        # 13. Return summary
        return {
            "id": product_id,
            "supplier_id": str(product.supplier_id),
            "name": product.name,
            "status": product.status.value,
            "created_at": product.created_at.isoformat(),
            "updated_at": product.updated_at.isoformat()
        }
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to create product: {str(e)}")
```
</details>

#### Verification

```javascript
// In MongoDB shell - verify the product was created correctly:
db.products.findOne({ name: "Your Product Name" })

// Check all embedded objects are present:
db.products.findOne(
  { name: "Your Product Name" },
  {
    "supplier_info": 1,
    "metadata.base_sku": 1,
    "variants": 1,
    "stock_locations": 1,
    "status": 1
  }
)

// Verify supplier's product_ids was updated:
db.suppliers.findOne(
  { _id: ObjectId("your_supplier_id") },
  { product_ids: 1 }
)
```

---

### Exercise 5.3: Get Product (Ownership-Scoped)

**Concept**: Compound `find_one` query for access control (anti-enumeration)

#### The Security Pattern

```python
# WRONG - Information leak:
product = await Product.get(PydanticObjectId(product_id))
if product.supplier_id != supplier_id:
    raise ValueError("Forbidden")  # ← Attacker now knows product EXISTS

# RIGHT - Anti-enumeration:
product = await Product.find_one({
    "_id": PydanticObjectId(product_id),
    "supplier_id": PydanticObjectId(supplier_id)
})
if not product:
    raise ValueError("Product not found")  # ← Same error whether it doesn't exist or wrong owner
```

<details>
<summary>Full Implementation</summary>

```python
async def get_product(self, product_id: str, supplier_id: str) -> Optional[Product]:
    try:
        product = await Product.find_one({
            "_id": PydanticObjectId(product_id),
            "supplier_id": PydanticObjectId(supplier_id)
        })
        if not product:
            raise ValueError("Product not found")
        return product
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to get product: {str(e)}")
```
</details>

---

### Exercise 5.4: List Supplier's Products (Filtered + Paginated)

**Concept**: Dynamic query building with `$in`, cursor pagination, and `find().sort().limit().to_list()`

#### The Method Signature

```python
async def list_products(
    self,
    supplier_id: str,
    page_size: int = 20,
    cursor: Optional[str] = None,
    status_filter: Optional[List[str]] = None,
    category_filter: Optional[str] = None
) -> Dict[str, Any]:
```

#### Query Building (Dynamic Filters)

```python
# Start with the base query (always filter by supplier)
query = {"supplier_id": PydanticObjectId(supplier_id)}

# Add optional filters:
if status_filter:      query["status"] = {"$in": status_filter}
if category_filter:    query["category"] = category_filter

# Cursor pagination:
if cursor:             query["_id"] = {"$gt": PydanticObjectId(cursor)}
```

#### New Operator: `$in`

```python
# $in: Match ANY value in the provided array
{"status": {"$in": ["active", "draft"]}}
# Matches products where status is "active" OR "draft"
```

#### The Fetch + Has-More Pattern

```python
# Fetch page_size + 1 to check if there are more results
products = await Product.find(query).sort("-created_at").limit(page_size + 1).to_list()

has_more = len(products) > page_size
if has_more:
    products = products[:-1]  # Remove the extra item

next_cursor = str(products[-1].id) if has_more and products else None
```

#### Response Building

Build a list of product summaries:

```python
product_list = [
    {
        "id": str(p.id),
        "name": p.name,
        "status": p.status.value,
        "category": p.category.value,
        "base_price_cents": p.base_price_cents,
        "variant_count": len(p.variants),
        "created_at": p.created_at,
        "updated_at": p.updated_at
    }
    for p in products
]
```

<details>
<summary>Full Implementation</summary>

```python
async def list_products(
    self, supplier_id: str, page_size: int = 20, cursor: Optional[str] = None,
    status_filter: Optional[List[str]] = None, category_filter: Optional[str] = None
) -> Dict[str, Any]:
    try:
        query = {"supplier_id": PydanticObjectId(supplier_id)}

        if status_filter:
            query["status"] = {"$in": status_filter}
        if category_filter:
            query["category"] = category_filter
        if cursor:
            query["_id"] = {"$gt": PydanticObjectId(cursor)}

        page_size = min(page_size, 50)

        products = await Product.find(query).sort("-created_at").limit(page_size + 1).to_list()

        has_more = len(products) > page_size
        if has_more:
            products = products[:-1]

        product_list = [
            {
                "id": str(p.id),
                "name": p.name,
                "status": p.status.value,
                "category": p.category.value,
                "base_price_cents": p.base_price_cents,
                "variant_count": len(p.variants),
                "created_at": p.created_at,
                "updated_at": p.updated_at
            }
            for p in products
        ]

        next_cursor = str(products[-1].id) if has_more and products else None

        return {
            "products": product_list,
            "pagination": {
                "next_cursor": next_cursor,
                "has_more": has_more,
                "page_size": page_size
            }
        }
    except Exception as e:
        raise Exception(f"Failed to list products: {str(e)}")
```
</details>

---

### Exercise 5.5: Update Product (Partial Update)

**Concept**: Get-then-modify with uniqueness validation and status gate

#### Algorithm

```
1. Get product (reuse self.get_product - ownership check included)
2. Status gate: cannot update DELETED products
3. If "name" changed → check name uniqueness (exclude current product!)
4. If "base_sku" changed → check SKU uniqueness (exclude current product!)
5. Apply each update field to the product object
6. await product.save()
7. Return updated product
```

#### The `exclude_id` Pattern in Action

```python
# When CREATING: no exclude
await self._check_name_uniqueness("Cool Headphones")

# When UPDATING: exclude THIS product's ID
await self._check_name_uniqueness(updates["name"], product_id)
# ↑ Without this, updating ANY field on a product named "Cool Headphones"
#   would fail because it finds ITSELF
```

#### Partial Update Application

```python
# Only apply fields that are present in the updates dict:
if "name" in updates:
    product.name = updates["name"]
if "short_description" in updates:
    product.short_description = updates["short_description"]
if "category" in updates:
    product.category = ProductCategory(updates["category"])
if "base_price_cents" in updates:
    product.base_price_cents = updates["base_price_cents"]
```

<details>
<summary>Full Implementation</summary>

```python
async def update_product(self, product_id: str, supplier_id: str, updates: Dict[str, Any]) -> Product:
    try:
        product = await self.get_product(product_id, supplier_id)

        if product.status == ProductStatus.DELETED:
            raise ValueError("Cannot update deleted product")

        if "name" in updates and updates["name"] != product.name:
            await self._check_name_uniqueness(updates["name"], product_id)

        if "base_sku" in updates and updates["base_sku"] != product.metadata.base_sku:
            await self._check_sku_uniqueness(supplier_id, updates["base_sku"], product_id)

        if "name" in updates:
            product.name = updates["name"]
        if "short_description" in updates:
            product.short_description = updates["short_description"]
        if "category" in updates:
            product.category = ProductCategory(updates["category"])
        if "base_price_cents" in updates:
            product.base_price_cents = updates["base_price_cents"]

        await product.save()
        return product
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to update product: {str(e)}")
```
</details>

---

### Exercise 5.6: Product Lifecycle - State Machine Transitions

**Concept**: Status gates, cross-collection validation, and the state machine pattern

This exercise covers lifecycle methods. Each one checks the current status, validates the transition is allowed, and updates the product.

#### 5.6a: `delete_product(product_id, supplier_id)` - Set to DELETED (Idempotent)

```python
# Algorithm:
# 1. Get product (ownership check)
# 2. If already DELETED → return (idempotent, don't error!)
# 3. Set status to DELETED
# 4. Save
# 5. Emit Kafka event
```

**The Idempotent Pattern**: DELETE should always return success. If the product is already deleted, that's fine.

<details>
<summary>Full Implementation</summary>

```python
async def delete_product(self, product_id: str, supplier_id: str) -> None:
    try:
        product = await self.get_product(product_id, supplier_id)

        if product.status == ProductStatus.DELETED:
            return  # Idempotent

        product.status = ProductStatus.DELETED
        await product.save()

        self._kafka.emit(
            topic=Topic.PRODUCT,
            action="deleted",
            entity_id=oid_to_str(product.id),
            data={
                "name": product.name,
                "supplier_id": oid_to_str(product.supplier_id),
            },
        )
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to delete product: {str(e)}")
```
</details>

---

#### 5.6b: `publish_product(product_id, supplier_id)` - Draft to Active

```python
# Algorithm:
# 1. Get product (ownership check)
# 2. Status gate: must be DRAFT
# 3. Validate: must have a short description
# 4. Set status to ACTIVE, published_at to utc_now()
# 5. Save
# 6. Emit Kafka event
```

<details>
<summary>Full Implementation</summary>

```python
async def publish_product(self, product_id: str, supplier_id: str) -> Product:
    try:
        product = await self.get_product(product_id, supplier_id)

        if product.status != ProductStatus.DRAFT:
            raise ValueError(f"Cannot publish product with status '{product.status.value}'")

        if not product.short_description:
            raise ValueError("Short description is required to publish")

        product.status = ProductStatus.ACTIVE
        product.published_at = utc_now()
        await product.save()

        self._kafka.emit(
            topic=Topic.PRODUCT,
            action="published",
            entity_id=oid_to_str(product.id),
            data={
                "name": product.name,
                "supplier_id": oid_to_str(product.supplier_id),
                "category": product.category.value,
                "base_price_cents": product.base_price_cents,
            },
        )
        return product
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to publish product: {str(e)}")
```
</details>

---

#### 5.6c: `discontinue_product(product_id, supplier_id)`

**Status gate**: Only ACTIVE or OUT_OF_STOCK can be discontinued.

```python
if product.status not in [ProductStatus.ACTIVE, ProductStatus.OUT_OF_STOCK]:
    raise ValueError(f"Cannot discontinue product with status '{product.status.value}'")
```

**Update**: Set status to DISCONTINUED, save.

<details>
<summary>Full Implementation</summary>

```python
async def discontinue_product(self, product_id: str, supplier_id: str) -> Product:
    try:
        product = await self.get_product(product_id, supplier_id)

        if product.status not in [ProductStatus.ACTIVE, ProductStatus.OUT_OF_STOCK]:
            raise ValueError(f"Cannot discontinue product with status '{product.status.value}'")

        product.status = ProductStatus.DISCONTINUED
        await product.save()

        self._kafka.emit(
            topic=Topic.PRODUCT,
            action="discontinued",
            entity_id=oid_to_str(product.id),
            data={
                "name": product.name,
                "supplier_id": oid_to_str(product.supplier_id),
            },
        )
        return product
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to discontinue product: {str(e)}")
```
</details>

---

#### 5.6d: `mark_out_of_stock(product_id, supplier_id)`

**Status gate**: Only ACTIVE can be marked out of stock.

<details>
<summary>Full Implementation</summary>

```python
async def mark_out_of_stock(self, product_id: str, supplier_id: str) -> Product:
    try:
        product = await self.get_product(product_id, supplier_id)

        if product.status != ProductStatus.ACTIVE:
            raise ValueError(f"Cannot mark product with status '{product.status.value}' as out of stock")

        product.status = ProductStatus.OUT_OF_STOCK
        await product.save()

        self._kafka.emit(
            topic=Topic.PRODUCT,
            action="out_of_stock",
            entity_id=oid_to_str(product.id),
            data={
                "name": product.name,
                "supplier_id": oid_to_str(product.supplier_id),
            },
        )
        return product
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to mark product out of stock: {str(e)}")
```
</details>

---

### Exercise 5.7: Public Product Endpoints - Discovery

**Concept**: Multi-condition `find_one`, `$gte`/`$lte` for price ranges, cursor pagination

These endpoints serve the **public storefront** - no supplier authentication needed.

#### 5.7a: `get_public_product(product_id)`

**What it does**: Get a product for public viewing. Only returns ACTIVE products.

```python
product = await Product.find_one({
    "_id": PydanticObjectId(product_id),
    "status": ProductStatus.ACTIVE
})
```

<details>
<summary>Full Implementation</summary>

```python
async def get_public_product(self, product_id: str) -> Optional[Product]:
    try:
        product = await Product.find_one({
            "_id": PydanticObjectId(product_id),
            "status": ProductStatus.ACTIVE
        })
        if not product:
            raise ValueError("Product not found")
        return product
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Failed to get public product: {str(e)}")
```
</details>

---

#### 5.7b: `list_public_products(...)` - Public Discovery

#### The Method Signature

```python
async def list_public_products(
    self,
    page_size: int = 20,
    cursor: Optional[str] = None,
    category_filter: Optional[str] = None,
    min_price_cents: Optional[int] = None,
    max_price_cents: Optional[int] = None
) -> Dict[str, Any]:
```

#### Query Building - Filter Layers

```python
# Layer 1: Base filter (always applied)
query = {"status": ProductStatus.ACTIVE}

# Layer 2: Category (optional)
if category_filter:
    query["category"] = category_filter

# Layer 3: Price range with $gte/$lte (optional)
if min_price_cents is not None or max_price_cents is not None:
    price_filter = {}
    if min_price_cents is not None:
        price_filter["$gte"] = min_price_cents
    if max_price_cents is not None:
        price_filter["$lte"] = max_price_cents
    query["base_price_cents"] = price_filter

# Cursor pagination
if cursor:
    query["_id"] = {"$gt": PydanticObjectId(cursor)}
```

#### New Operators: `$gte` / `$lte`

```python
# Range query on numeric fields:
{"base_price_cents": {"$gte": 1000, "$lte": 5000}}
# Matches products priced between $10.00 and $50.00

# You can use one or both:
{"base_price_cents": {"$gte": 1000}}                      # Min $10.00, no max
{"base_price_cents": {"$lte": 5000}}                      # No min, max $50.00
{"base_price_cents": {"$gte": 1000, "$lte": 5000}}        # Both bounds
```

<details>
<summary>Full Implementation</summary>

```python
async def list_public_products(
    self, page_size: int = 20, cursor: Optional[str] = None,
    category_filter: Optional[str] = None,
    min_price_cents: Optional[int] = None, max_price_cents: Optional[int] = None
) -> Dict[str, Any]:
    try:
        query = {"status": ProductStatus.ACTIVE}

        if category_filter:
            query["category"] = category_filter

        if min_price_cents is not None or max_price_cents is not None:
            price_filter = {}
            if min_price_cents is not None:
                price_filter["$gte"] = min_price_cents
            if max_price_cents is not None:
                price_filter["$lte"] = max_price_cents
            query["base_price_cents"] = price_filter

        if cursor:
            query["_id"] = {"$gt": PydanticObjectId(cursor)}

        page_size = min(page_size, 50)

        products = await Product.find(query).sort("-created_at").limit(page_size + 1).to_list()

        has_more = len(products) > page_size
        if has_more:
            products = products[:-1]

        product_list = [
            {
                "id": str(p.id),
                "name": p.name,
                "category": p.category.value,
                "base_price_cents": p.base_price_cents,
                "supplier_info": p.supplier_info,
                "variant_count": len(p.variants),
                "stats": {
                    "view_count": p.stats.view_count,
                    "purchase_count": p.stats.purchase_count,
                    "total_reviews": p.stats.total_reviews
                }
            }
            for p in products
        ]

        next_cursor = str(products[-1].id) if has_more and products else None

        return {
            "products": product_list,
            "pagination": {
                "next_cursor": next_cursor,
                "has_more": has_more
            }
        }
    except Exception as e:
        raise Exception(f"Failed to list public products: {str(e)}")
```
</details>

#### Verification

```javascript
// Test the public listing with various filters:

// 1. All active products
db.products.find({ status: "active" }).count()

// 2. Category filter
db.products.find({ status: "active", category: "electronics" })

// 3. Price range
db.products.find({ status: "active", base_price_cents: { $gte: 1000, $lte: 5000 } })
```

---

## 6. VERIFICATION CHECKLIST

After implementing all methods, verify each one works:

| # | Method | Test |
|---|--------|------|
| 1 | `create_product` | Create a product with 2 variants, 1 stock location |
| 2 | `get_product` | Get it back with the correct supplier_id |
| 3 | `get_product` (wrong supplier) | Should return "Product not found" |
| 4 | `list_products` | List all supplier products, verify pagination works |
| 5 | `list_products` with status filter | Filter by `["draft"]` - should only show drafts |
| 6 | `update_product` | Change the name, verify it works |
| 7 | `update_product` (duplicate name) | Should fail with "already exists" |
| 8 | `publish_product` | Draft → Active (must have short_description) |
| 9 | `mark_out_of_stock` | Active → Out of Stock |
| 10 | `discontinue_product` | Active or OOS → Discontinued |
| 11 | `delete_product` | Any → Deleted |
| 12 | `delete_product` (already deleted) | Should succeed silently (idempotent) |
| 13 | `get_public_product` | Only returns active products |
| 14 | `list_public_products` | Test with category and price range ($gte/$lte) |

---

## 7. ADVANCED CHALLENGES

### Challenge 1: The Dict Field Query Puzzle

The Product model stores variants as a `Dict[str, ProductVariant]`.

**Experiment**: Run these in the MongoDB shell:
```javascript
// Can you query into dict values?
db.products.find({"variants.Red-Large.price_cents": {"$gte": 5000}})

// What about querying across ALL variants regardless of key?
db.products.find({"variants.$**.price_cents": {"$gte": 5000}})
```

**Question**: How would you find all products that have ANY variant priced over $50? With a List this would be easy. With a Dict, it requires either:
1. An aggregation pipeline with `$objectToArray`
2. Denormalized min/max price fields on the Product

Which approach would you choose and why?

### Challenge 2: Price Range vs Variant Prices

The current `list_public_products` filters on `base_price_cents`. But products have **variants with different prices**.

**Scenario**: A product has `base_price_cents: 5000` ($50) but a variant "Premium Gold" with `price_cents: 15000` ($150).

**Question**: If a user searches for products $100-$200, this product WON'T appear (base price is $50), even though a variant costs $150. How would you fix this?

**Think about**:
1. Adding `min_variant_price` and `max_variant_price` denormalized fields to the Product document
2. Updating these fields whenever variants are added/modified
3. Querying these denormalized fields instead of `base_price_cents`

---

## 8. WHAT'S NEXT

You've built the **product catalog** - the most structurally complex service so far.

**Concepts you mastered**:
- `Dict` (Map) field construction and querying
- `$gte` / `$lte` for numeric range queries
- `$in` for multi-value filtering
- `$ne` for exclusion queries
- Cross-collection validation (supplier lookup)
- `$addToSet` for idempotent array updates
- 5-state lifecycle machine with guarded transitions
- Complex embedded document construction (7 types)
- Denormalized data (supplier_info snapshot)
- Public vs. supplier-scoped query patterns

**TASK_05: Post Service** will introduce:
- Social content creation (text, image, video, link posts)
- Feed generation with cursor pagination
- Post engagement statistics
- Soft delete patterns
- Author denormalization (PostAuthor embedded type)
