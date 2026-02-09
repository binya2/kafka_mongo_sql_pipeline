# TASK 04: Product Catalog Service

## 1. MISSION BRIEFING

Products are the **commerce core** of the platform. While Users socialize, Products are what actually get bought and sold. Every product is owned by a Supplier and goes through a lifecycle from draft to active to eventually discontinued or deleted.

This is the **most structurally complex entity** you've built so far. The Product model has 7 different embedded document types, a `Dict[str, ProductVariant]` map field (not just a list!), multi-location inventory tracking, and a 5-state lifecycle machine.

### What You Will Build
The `ProductService` class in `apps/mongo_backend/services/product.py` - methods covering CRUD, a 5-state lifecycle machine, cross-collection supplier validation, and product discovery with advanced filtering.

### What You Will Learn

| MongoDB Concept | Where You'll Use It |
|----------------|-------------------|
| **Complex document construction** | Building 7+ embedded sub-documents from typed request objects |
| **Cross-collection validation** | Supplier must exist before creating products |
| **`Dict` (Map) field handling** | Variants stored as `Dict[str, ProductVariant]` |
| **`$ne` exclusion filter** | Excluding DELETED products from listings |
| **`$in` operator** | Multi-status filtering (e.g., `status in ["active", "draft"]`) |
| **Skip/limit pagination** | Paginated product listing with `.skip()` and `.limit()` |
| **State machine transitions** | 5-status lifecycle with guarded transitions |
| **Back-reference management** | Adding/removing product ID from supplier's `product_ids` array |
| **Denormalized snapshot** | Caching `supplier_info` dict on product document |
| **Partial update pattern** | Updating only provided fields from `UpdateProductRequest` |

### How This Differs From Previous Tasks

| Aspect | User (01) / Supplier (02) | Product (04) |
|--------|--------------------------|-------------|
| Embedded docs | 2-5 types | **7 types** |
| Data structure | Flat fields + nested objects | **Dict/Map** (variants) + Lists |
| Query operators | Basic `find_one` | **`$ne`, `$in`** for filtered listing |
| Enums | None | **3 enums** (ProductStatus, ProductCategory, UnitType) |
| Collections touched | 1 | **2** (products + suppliers for validation & back-reference) |
| Write pattern | Insert + partial update | **Insert + partial update + lifecycle transitions** |
| Delete pattern | Soft delete (User) / Hard delete (Supplier) | **Status-based delete** (set `status=DELETED`) |

---

## 2. BEFORE YOU START

### Prerequisites
- **TASK_01 (User) must be complete** - You need users in the database
- **TASK_02 (Supplier) must be complete** - Products require a supplier
- Have at least one registered supplier from TASK_02

### Files You MUST Read Before Coding

| Order | File | Why |
|-------|------|-----|
| 1 | `shared/models/product.py` | The data model - 3 enums, 7 embedded types, 3 indexes, Dict-based variants |
| 2 | `apps/mongo_backend/schemas/product.py` | Request/response schemas including nested variant/location request types |
| 3 | `apps/mongo_backend/routes/product.py` | Endpoints: CRUD + lifecycle, `X-Supplier-ID` header extraction |
| 4 | `shared/models/supplier.py` | Cross-collection reference - you'll validate supplier + update `product_ids` |
| 5 | `shared/kafka/topics.py` | `EventType.PRODUCT_CREATED`, `PRODUCT_UPDATED`, etc. |

### The Data Flow

```
HTTP Request
    │
    ▼
┌─────────┐   Extracts X-Supplier-ID header
│  Route   │   (required for write operations)
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
│  └── suppliers (validation: does supplier exist?)      │
│                                                        │
│  Writes to TWO collections:                            │
│  ├── products (insert, update, status changes)         │
│  └── suppliers (append/remove product_id)              │
│                                                        │
│  Also emits Kafka events:                              │
│  └── EventType.PRODUCT_CREATED, PRODUCT_UPDATED,       │
│       PRODUCT_PUBLISHED, PRODUCT_DELETED, etc.         │
└──────────────────────────────────────────────────────┘
    │
    ▼
┌─────────┐
│  Route   │   Wraps returned Product in product_response()
│          │   → JSON-safe dict via model_dump(mode="json")
└─────────┘
```

> **Key pattern**: The route layer calls `product_response(product)` to convert the returned `Product` document into a JSON dict. Your service returns `Product` documents, not dicts.

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
          mark_out_ │         │ discontinue_product()
          of_stock() │         │
                    ▼         ▼
              ┌──────────┐ ┌──────────────┐
              │OUT_OF_   │ │DISCONTINUED  │
              │STOCK     │ │              │
              └──┬───────┘ └──────────────┘
                 │
                 │ discontinue_product() (also valid)
                 ▼
              ┌──────────────┐
              │DISCONTINUED  │
              └──────────────┘

  Any non-DELETED status ──restore_product()──► DRAFT

  Any non-DELETED status ──delete_product()──► DELETED (terminal)
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
    SPORTS_OUTDOORS = "sports_outdoors"
    FOOD_BEVERAGE = "food_beverage"
    HEALTH_WELLNESS = "health_wellness"
    TOYS_GAMES = "toys_games"
    BOOKS_MEDIA = "books_media"
    AUTOMOTIVE = "automotive"
    OTHER = "other"

class UnitType(str, Enum):
    PIECE = "piece"
    PAIR = "pair"
    SET = "set"
    BOX = "box"
    PACK = "pack"
    BUNDLE = "bundle"
    KG = "kg"
    GRAM = "gram"
    LITER = "liter"
    ML = "ml"
    METER = "meter"
    OTHER = "other"
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
    # → Used by: list_products(supplier_id=...)

    # Index 2: Status-based filtering
    [("status", 1)],
    # → Used by: list_products(status_filter=...), lifecycle queries

    # Index 3: Recent products
    [("created_at", -1)],
    # → Used by: sorting in list queries
]
```

### Model Methods

```python
await product.save()  # Automatically sets updated_at to utc_now() before saving
```

There are no other helper methods - your service layer will implement all business logic directly.

---

## 4. THE SERVICE CONTRACT

Your service file: `apps/mongo_backend/services/product.py`

### Method Overview

| # | Method | MongoDB Concepts | Difficulty |
|---|--------|-----------------|-----------|
| 1 | `_build_topic_descriptions(items)` | Static helper - convert request objects to model objects | Easy |
| 2 | `_build_stock_locations(items)` | Static helper - convert request objects to model objects | Easy |
| 3 | `_build_variants(variants_dict)` | Static helper - build `Dict[str, ProductVariant]` from request data | Medium |
| 4 | `create_product(supplier_id, body)` | Cross-collection get + complex insert + back-reference update | Hard |
| 5 | `get_product(product_id)` | `Product.get()` + status gate (exclude DELETED) | Easy |
| 6 | `list_products(skip, limit, ...)` | `find` with `$ne`, `$in`, skip/limit | Medium |
| 7 | `update_product(product_id, body)` | Get + partial update via field checks + `.save()` | Medium |
| 8 | `delete_product(product_id)` | Set status DELETED + remove from supplier's `product_ids` | Medium |
| 9 | `publish_product(product_id)` | Status gate (DRAFT only) + transition to ACTIVE | Easy |
| 10 | `discontinue_product(product_id)` | Status gate (ACTIVE/OUT_OF_STOCK) + transition | Easy |
| 11 | `mark_out_of_stock(product_id)` | Status gate (ACTIVE only) + transition | Easy |
| 12 | `restore_product(product_id)` | Fetch + transition any status to DRAFT | Easy |

### Error Types

The service uses errors from `shared.errors`:
- **`NotFoundError`** - when supplier or product is not found
- **`ValidationError`** - when a lifecycle transition is invalid (e.g., publishing a non-draft product)

### Return Type Convention

Every method returns a `Product` document (or `None` for delete). The route layer handles formatting via `product_response(product)`.

---

## 5. EXERCISES

---

### Exercise 5.1: Helper Methods - Building Embedded Documents

**Concept**: Converting typed request objects (from Pydantic schemas) into model embedded documents

The service has three `@staticmethod` helper methods that convert request schema objects into model objects. These are called by `create_product` and `update_product`.

#### 5.1a: `_build_topic_descriptions(items)`

**What it does**: Converts a list of `TopicDescriptionRequest` objects into `TopicDescription` model objects.

**Input**: `items` is a `list` of request objects with `.topic`, `.description`, `.display_order` attributes.
**Output**: `list[TopicDescription]`

```python
# Each item in the list has attributes you can access with dot notation:
# item.topic, item.description, item.display_order
```

<details>
<summary>Hint Level 1 - Direction</summary>

Use a list comprehension to map each request item to a `TopicDescription` model object.
</details>

<details>
<summary>Hint Level 2 - Pattern</summary>

```python
return [
    TopicDescription(topic=td.topic, description=td.description, display_order=td.display_order)
    for td in items
]
```
</details>

---

#### 5.1b: `_build_stock_locations(items)`

**What it does**: Converts a list of `StockLocationRequest` objects into `StockLocation` model objects.

**Input**: `items` is a `list` of request objects with `.location_name`, `.street_address`, `.city`, `.state`, `.zip_code`, `.country`, `.quantity` attributes.
**Output**: `list[StockLocation]`

<details>
<summary>Hint Level 1 - Direction</summary>

Same pattern as topic descriptions - a list comprehension mapping each field.
</details>

<details>
<summary>Hint Level 2 - Pattern</summary>

```python
return [
    StockLocation(
        location_name=sl.location_name,
        street_address=sl.street_address,
        city=sl.city,
        state=sl.state,
        zip_code=sl.zip_code,
        country=sl.country,
        quantity=sl.quantity,
    )
    for sl in items
]
```
</details>

---

#### 5.1c: `_build_variants(variants_dict)` - The Tricky One

**What it does**: Converts a `Dict[str, ProductVariantRequest]` into `Dict[str, ProductVariant]` model objects. This involves building nested `VariantAttribute` and `PackageDimensions` objects for each variant.

**Input**: `variants_dict` is a `dict` where keys are variant names (strings) and values are `ProductVariantRequest` objects.
**Output**: `dict[str, ProductVariant]`

```python
# variants_dict arrives as:
# {
#   "Red-Large": ProductVariantRequest(variant_id="v1", variant_name="Red-Large", attributes=[...], ...),
#   "Blue-Small": ProductVariantRequest(variant_id="v2", variant_name="Blue-Small", attributes=[...], ...)
# }
```

> **Why is this trickier?** You need to iterate dict items AND build nested objects inside each variant (attributes list + package dimensions).

<details>
<summary>Hint Level 1 - Direction</summary>

Iterate `variants_dict.items()` and for each `(key, vr)` pair, build a `ProductVariant`. Inside, map `vr.attributes` to `VariantAttribute` objects and `vr.package_dimensions` to a `PackageDimensions` object.
</details>

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
@staticmethod
def _build_variants(variants_dict: dict) -> dict[str, ProductVariant]:
    variants = {}
    for key, vr in variants_dict.items():
        variants[key] = ProductVariant(
            variant_id=vr.variant_id,
            variant_name=vr.variant_name,
            attributes=[
                VariantAttribute(attribute_name=a.attribute_name, attribute_value=a.attribute_value)
                for a in vr.attributes
            ],
            price_cents=vr.price_cents,
            cost_cents=vr.cost_cents,
            quantity=vr.quantity,
            package_dimensions=PackageDimensions(
                width_cm=vr.package_dimensions.width_cm,
                height_cm=vr.package_dimensions.height_cm,
                depth_cm=vr.package_dimensions.depth_cm,
            ),
            image_url=vr.image_url,
        )
    return variants
```
</details>

---

### Exercise 5.2: Create Product - The Construction Challenge

**Concept**: Cross-collection validation, complex document construction from typed request body, back-reference management, Kafka event emission

#### The Method Signature

```python
async def create_product(self, supplier_id: str, body) -> Product:
    """Create a product in draft status. `body` is a CreateProductRequest."""
```

> **Important**: `body` is a `CreateProductRequest` Pydantic object - you access fields with dot notation (`body.name`, `body.category`), NOT dict syntax (`body["name"]`).

#### Step-by-Step Algorithm

```
1. Validate supplier exists (cross-collection)
   └── Supplier.get(PydanticObjectId(supplier_id))
   └── Raise NotFoundError("Supplier not found") if None

2. Build Product document using helper methods + body fields:
   ├── supplier_id = PydanticObjectId(supplier_id)
   ├── supplier_info = {"name": supplier.company_info.legal_name}
   ├── name = body.name
   ├── short_description = body.short_description
   ├── topic_descriptions = self._build_topic_descriptions(body.topic_descriptions)
   ├── category = ProductCategory(body.category)
   ├── unit_type = UnitType(body.unit_type)
   ├── metadata = ProductMetadata(base_sku=body.base_sku, brand=body.brand)
   ├── stock_locations = self._build_stock_locations(body.stock_locations)
   ├── variants = self._build_variants(body.variants)
   └── base_price_cents = body.base_price_cents
   (status defaults to DRAFT via model default)

3. await product.insert()

4. Update supplier's product_ids back-reference
   └── supplier.product_ids.append(product.id)
   └── await supplier.save()

5. Emit Kafka event
   └── EventType.PRODUCT_CREATED

6. Return the Product document
```

#### The Denormalized `supplier_info` Pattern

```python
# Why store supplier data ON the product?
# Because when displaying a product, you don't want to JOIN to the suppliers collection.
# MongoDB doesn't have JOINs - instead, you embed frequently-read data.

supplier_info = {"name": supplier.company_info.legal_name}
```

> **Trade-off**: If the supplier changes their name, the product still shows the old name. This is acceptable because business names rarely change, and a background job can refresh denormalized data.

#### The Kafka Event Pattern

```python
self._kafka.emit(
    event_type=EventType.PRODUCT_CREATED,
    entity_id=oid_to_str(product.id),
    data=product.model_dump(mode="json"),
)
```

> **Note the difference from old tasks**: We use `EventType.PRODUCT_CREATED` (an enum value), not `Topic.PRODUCT` + `action="created"`. The event type encodes both the topic and the action.

<details>
<summary>Hint Level 1 - Direction</summary>

Start by fetching the supplier with `Supplier.get()`. Wrap in try/except because invalid ObjectIds will throw. Then build the Product using body fields and your helper methods. Insert, update supplier, emit Kafka, return.
</details>

<details>
<summary>Hint Level 2 - Key Details</summary>

```python
# Fetching supplier safely:
try:
    supplier = await Supplier.get(PydanticObjectId(supplier_id))
except Exception:
    raise NotFoundError("Supplier not found")
if not supplier:
    raise NotFoundError("Supplier not found")

# Building the product:
product = Product(
    supplier_id=PydanticObjectId(supplier_id),
    supplier_info={"name": supplier.company_info.legal_name},
    # ... all other fields from body using helper methods
)
```
</details>

<details>
<summary>Hint Level 3 - Full Implementation</summary>

```python
async def create_product(self, supplier_id: str, body) -> Product:
    try:
        supplier = await Supplier.get(PydanticObjectId(supplier_id))
    except Exception:
        raise NotFoundError("Supplier not found")
    if not supplier:
        raise NotFoundError("Supplier not found")

    product = Product(
        supplier_id=PydanticObjectId(supplier_id),
        supplier_info={"name": supplier.company_info.legal_name},
        name=body.name,
        short_description=body.short_description,
        topic_descriptions=self._build_topic_descriptions(body.topic_descriptions),
        category=ProductCategory(body.category),
        unit_type=UnitType(body.unit_type),
        metadata=ProductMetadata(base_sku=body.base_sku, brand=body.brand),
        stock_locations=self._build_stock_locations(body.stock_locations),
        variants=self._build_variants(body.variants),
        base_price_cents=body.base_price_cents,
    )
    await product.insert()

    supplier.product_ids.append(product.id)
    await supplier.save()

    self._kafka.emit(
        event_type=EventType.PRODUCT_CREATED,
        entity_id=oid_to_str(product.id),
        data=product.model_dump(mode="json"),
    )
    return product
```
</details>

#### Verification

```bash
# Create a product (replace SUPPLIER_ID with an actual supplier ID):
curl -s -X POST http://localhost:8000/products \
  -H "Content-Type: application/json" \
  -H "X-Supplier-ID: SUPPLIER_ID" \
  -d '{
    "name": "Wireless Headphones",
    "short_description": "Premium noise-cancelling headphones",
    "topic_descriptions": [
      {"topic": "Features", "description": "Active noise cancellation with 30hr battery", "display_order": 1}
    ],
    "category": "electronics",
    "unit_type": "piece",
    "base_sku": "HDPH-001",
    "brand": "AudioTech",
    "base_price_cents": 9999,
    "images": [{"url": "https://example.com/img.jpg", "alt_text": "Headphones", "order": 0, "is_primary": true}],
    "shipping": {"free_shipping": true, "ships_from_country": "US"},
    "variants": {
      "Black": {
        "variant_id": "v1",
        "variant_name": "Black",
        "attributes": [{"attribute_name": "Color", "attribute_value": "Black"}],
        "sku": "HDPH-001-BLK",
        "price_cents": 9999,
        "quantity": 50,
        "package_dimensions": {"width_cm": 20, "height_cm": 15, "depth_cm": 10, "weight_grams": 350}
      }
    },
    "stock_locations": [
      {"location_id": "wh-1", "location_name": "Main Warehouse", "city": "Austin", "zip_code": "73301", "country": "US", "quantity": 100}
    ]
  }' | python3 -m json.tool

# Expected: Product document with status "draft", supplier_info.name filled in
```

```javascript
// In MongoDB shell - verify the product was created:
db.products.findOne({ name: "Wireless Headphones" })

// Verify supplier's product_ids was updated:
db.suppliers.findOne(
  { _id: ObjectId("your_supplier_id") },
  { product_ids: 1 }
)
```

---

### Exercise 5.3: Get Product

**Concept**: `Document.get()` with `PydanticObjectId`, status-based exclusion

#### The Method Signature

```python
async def get_product(self, product_id: str) -> Product:
```

#### Algorithm

```
1. Fetch product by ID using Product.get(PydanticObjectId(product_id))
   └── Wrap in try/except for invalid ObjectIds
2. If product is None OR product.status is DELETED → raise NotFoundError
3. Return the product
```

> **Note**: Unlike the old pattern, there is NO supplier_id ownership check in `get_product`. The route is a public GET endpoint - anyone can view a product by ID. The `X-Supplier-ID` header is only required for write operations.

<details>
<summary>Hint Level 1 - Direction</summary>

Use `Product.get()` (Beanie's built-in fetch by `_id`) wrapped in try/except. Check for None and DELETED status.
</details>

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def get_product(self, product_id: str) -> Product:
    try:
        product = await Product.get(PydanticObjectId(product_id))
    except Exception:
        raise NotFoundError("Product not found")
    if not product or product.status == ProductStatus.DELETED:
        raise NotFoundError("Product not found")
    return product
```
</details>

#### Verification

```bash
# Get the product you just created (replace PRODUCT_ID):
curl -s http://localhost:8000/products/PRODUCT_ID | python3 -m json.tool

# Expected: Full product document as JSON

# Try a non-existent ID:
curl -s http://localhost:8000/products/000000000000000000000000

# Expected: 404 error with "Product not found"
```

---

### Exercise 5.4: List Products (Filtered + Paginated)

**Concept**: Dynamic query building with `$ne`, `$in`, skip/limit pagination, `.sort().skip().limit().to_list()`

#### The Method Signature

```python
async def list_products(
    self,
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None,
    category: Optional[str] = None,
    supplier_id: Optional[str] = None,
) -> list[Product]:
```

> **Note the parameters**: `skip`/`limit` pagination (not cursor-based), optional filters passed as query parameters from the route.

#### Query Building (Dynamic Filters)

```python
# Start with base query: exclude DELETED products
query = {"status": {"$ne": ProductStatus.DELETED}}

# Add optional filters:
if status_filter:
    # status_filter is a comma-separated string like "active,draft"
    statuses = [s.strip() for s in status_filter.split(",")]
    query["status"] = {"$in": statuses}  # This REPLACES the $ne filter
if category:
    query["category"] = category
if supplier_id:
    query["supplier_id"] = PydanticObjectId(supplier_id)
```

> **Important**: When `status_filter` is provided, it replaces the `$ne: DELETED` filter with an `$in` filter. This means if someone explicitly requests `status=deleted`, they would get deleted products. The route layer controls what filters are available.

#### Key Operators

```python
# $ne: Not Equal - exclude a specific value
{"status": {"$ne": "deleted"}}
# Matches all products where status is NOT "deleted"

# $in: Match ANY value in the provided array
{"status": {"$in": ["active", "draft"]}}
# Matches products where status is "active" OR "draft"
```

#### The Fetch Pattern

```python
return (
    await Product.find(query)
    .sort("-created_at")          # Most recent first
    .skip(skip)                   # Skip N documents
    .limit(min(limit, 100))       # Cap at 100 max
    .to_list()                    # Execute and return list
)
```

<details>
<summary>Hint Level 1 - Direction</summary>

Build a query dict starting with `{"status": {"$ne": ProductStatus.DELETED}}`. Add optional filters conditionally. Then use Beanie's `find().sort().skip().limit().to_list()` chain.
</details>

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def list_products(
    self,
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None,
    category: Optional[str] = None,
    supplier_id: Optional[str] = None,
) -> list[Product]:
    query: dict = {"status": {"$ne": ProductStatus.DELETED}}

    if status_filter:
        statuses = [s.strip() for s in status_filter.split(",")]
        query["status"] = {"$in": statuses}
    if category:
        query["category"] = category
    if supplier_id:
        query["supplier_id"] = PydanticObjectId(supplier_id)

    return (
        await Product.find(query)
        .sort("-created_at")
        .skip(skip)
        .limit(min(limit, 100))
        .to_list()
    )
```
</details>

#### Verification

```bash
# List all non-deleted products:
curl -s "http://localhost:8000/products" | python3 -m json.tool

# List only draft products:
curl -s "http://localhost:8000/products?status=draft" | python3 -m json.tool

# List by category:
curl -s "http://localhost:8000/products?category=electronics" | python3 -m json.tool

# List by supplier:
curl -s "http://localhost:8000/products?supplier_id=SUPPLIER_ID" | python3 -m json.tool

# Pagination:
curl -s "http://localhost:8000/products?skip=0&limit=5" | python3 -m json.tool
```

---

### Exercise 5.5: Update Product (Partial Update)

**Concept**: Get-then-modify with field-by-field conditional update, calling helper methods for nested objects

#### The Method Signature

```python
async def update_product(self, product_id: str, body) -> Product:
    """Partial update. `body` is an UpdateProductRequest."""
```

#### Algorithm

```
1. Get product (reuse self.get_product - checks existence + not DELETED)
2. For each field in UpdateProductRequest, if the value is not None, update the product:
   ├── body.name → product.name
   ├── body.short_description → product.short_description
   ├── body.category → product.category (wrap in ProductCategory())
   ├── body.base_price_cents → product.base_price_cents
   ├── body.base_sku → product.metadata.base_sku
   ├── body.brand → product.metadata.brand
   ├── body.topic_descriptions → self._build_topic_descriptions(...)
   ├── body.stock_locations → self._build_stock_locations(...)
   └── body.variants → self._build_variants(...)
3. await product.save()
4. Emit EventType.PRODUCT_UPDATED Kafka event
5. Return updated product
```

#### The `is not None` Pattern

```python
# Only update fields that were actually provided in the request:
if body.name is not None:
    product.name = body.name
if body.short_description is not None:
    product.short_description = body.short_description
# ... etc.

# WHY not None? Because UpdateProductRequest has all Optional fields.
# A missing field = None = "don't change this"
# A provided field = new value = "update this"
```

#### Nested Field Updates

```python
# For metadata fields, update the nested object's attributes:
if body.base_sku is not None:
    product.metadata.base_sku = body.base_sku
if body.brand is not None:
    product.metadata.brand = body.brand

# For lists/dicts, rebuild using helper methods:
if body.topic_descriptions is not None:
    product.topic_descriptions = self._build_topic_descriptions(body.topic_descriptions)
if body.stock_locations is not None:
    product.stock_locations = self._build_stock_locations(body.stock_locations)
if body.variants is not None:
    product.variants = self._build_variants(body.variants)
```

<details>
<summary>Hint Level 1 - Direction</summary>

Fetch with `self.get_product()`, then check each body field for `is not None` and apply. Remember to use helper methods for nested objects. Save and emit Kafka event.
</details>

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def update_product(self, product_id: str, body) -> Product:
    product = await self.get_product(product_id)

    if body.name is not None:
        product.name = body.name
    if body.short_description is not None:
        product.short_description = body.short_description
    if body.category is not None:
        product.category = ProductCategory(body.category)
    if body.base_price_cents is not None:
        product.base_price_cents = body.base_price_cents
    if body.base_sku is not None:
        product.metadata.base_sku = body.base_sku
    if body.brand is not None:
        product.metadata.brand = body.brand
    if body.topic_descriptions is not None:
        product.topic_descriptions = self._build_topic_descriptions(body.topic_descriptions)
    if body.stock_locations is not None:
        product.stock_locations = self._build_stock_locations(body.stock_locations)
    if body.variants is not None:
        product.variants = self._build_variants(body.variants)

    await product.save()

    self._kafka.emit(
        event_type=EventType.PRODUCT_UPDATED,
        entity_id=oid_to_str(product.id),
        data=product.model_dump(mode="json"),
    )
    return product
```
</details>

#### Verification

```bash
# Update the product name:
curl -s -X PATCH http://localhost:8000/products/PRODUCT_ID \
  -H "Content-Type: application/json" \
  -H "X-Supplier-ID: SUPPLIER_ID" \
  -d '{"name": "Premium Wireless Headphones"}' | python3 -m json.tool

# Expected: Product with updated name, updated_at changed

# Update category:
curl -s -X PATCH http://localhost:8000/products/PRODUCT_ID \
  -H "Content-Type: application/json" \
  -H "X-Supplier-ID: SUPPLIER_ID" \
  -d '{"category": "fashion"}' | python3 -m json.tool
```

---

### Exercise 5.6: Delete Product

**Concept**: Status-based soft delete + back-reference cleanup

#### The Method Signature

```python
async def delete_product(self, product_id: str) -> None:
```

#### Algorithm

```
1. Get product (self.get_product - checks existence + not already DELETED)
2. Set product.status = ProductStatus.DELETED
3. await product.save()
4. Remove product from supplier's product_ids array:
   ├── Fetch supplier by product.supplier_id
   ├── If supplier exists and product.id is in supplier.product_ids:
   │   ├── supplier.product_ids.remove(product.id)
   │   └── await supplier.save()
   └── Wrap in try/except (don't fail if supplier cleanup fails)
5. Emit EventType.PRODUCT_DELETED Kafka event
```

> **Back-reference cleanup**: When deleting, you remove the product ID from the supplier's `product_ids` array. This is the reverse of what `create_product` does. Wrap it in try/except so a failed cleanup doesn't prevent the delete.

<details>
<summary>Hint Level 1 - Direction</summary>

Set status to DELETED, save, then try to clean up the supplier's `product_ids` list. Use `.remove()` on the Python list. Emit Kafka event with just the product ID in data.
</details>

<details>
<summary>Hint Level 2 - Full Implementation</summary>

```python
async def delete_product(self, product_id: str) -> None:
    product = await self.get_product(product_id)
    product.status = ProductStatus.DELETED
    await product.save()

    try:
        supplier = await Supplier.get(product.supplier_id)
        if supplier and product.id in supplier.product_ids:
            supplier.product_ids.remove(product.id)
            await supplier.save()
    except Exception:
        pass

    self._kafka.emit(
        event_type=EventType.PRODUCT_DELETED,
        entity_id=oid_to_str(product.id),
        data={"product_id": oid_to_str(product.id)},
    )
```
</details>

#### Verification

```bash
# Delete a product:
curl -s -X DELETE http://localhost:8000/products/PRODUCT_ID \
  -H "X-Supplier-ID: SUPPLIER_ID" -w "\nHTTP Status: %{http_code}\n"

# Expected: HTTP 204 No Content

# Verify it's gone from GET:
curl -s http://localhost:8000/products/PRODUCT_ID

# Expected: 404 "Product not found"
```

```javascript
// In MongoDB shell - the document still exists but has status "deleted":
db.products.findOne({ _id: ObjectId("PRODUCT_ID") }, { status: 1 })
// → { status: "deleted" }

// Verify supplier's product_ids no longer contains this product:
db.suppliers.findOne({ _id: ObjectId("SUPPLIER_ID") }, { product_ids: 1 })
```

---

### Exercise 5.7: Product Lifecycle - State Machine Transitions

**Concept**: Status gates with guarded transitions, `ValidationError` for invalid transitions

Each lifecycle method follows the same pattern:
1. Get the product
2. Check current status is allowed for this transition
3. Update status (and possibly `published_at`)
4. Save
5. Emit Kafka event
6. Return updated product

#### 5.7a: `publish_product(product_id)` - DRAFT to ACTIVE

**Status gate**: Only DRAFT products can be published.

```python
if product.status != ProductStatus.DRAFT:
    raise ValidationError("Only draft products can be published")
```

**Update**: Set status to ACTIVE and `published_at` to current time.

<details>
<summary>Full Implementation</summary>

```python
async def publish_product(self, product_id: str) -> Product:
    product = await self.get_product(product_id)
    if product.status != ProductStatus.DRAFT:
        raise ValidationError("Only draft products can be published")

    product.status = ProductStatus.ACTIVE
    product.published_at = utc_now()
    await product.save()

    self._kafka.emit(
        event_type=EventType.PRODUCT_PUBLISHED,
        entity_id=oid_to_str(product.id),
        data=product.model_dump(mode="json"),
    )
    return product
```
</details>

---

#### 5.7b: `discontinue_product(product_id)` - ACTIVE or OUT_OF_STOCK to DISCONTINUED

**Status gate**: Only ACTIVE or OUT_OF_STOCK can be discontinued.

```python
if product.status not in (ProductStatus.ACTIVE, ProductStatus.OUT_OF_STOCK):
    raise ValidationError("Only active or out-of-stock products can be discontinued")
```

<details>
<summary>Full Implementation</summary>

```python
async def discontinue_product(self, product_id: str) -> Product:
    product = await self.get_product(product_id)
    if product.status not in (ProductStatus.ACTIVE, ProductStatus.OUT_OF_STOCK):
        raise ValidationError("Only active or out-of-stock products can be discontinued")

    product.status = ProductStatus.DISCONTINUED
    await product.save()

    self._kafka.emit(
        event_type=EventType.PRODUCT_DISCONTINUED,
        entity_id=oid_to_str(product.id),
        data=product.model_dump(mode="json"),
    )
    return product
```
</details>

---

#### 5.7c: `mark_out_of_stock(product_id)` - ACTIVE to OUT_OF_STOCK

**Status gate**: Only ACTIVE can be marked out of stock.

```python
if product.status != ProductStatus.ACTIVE:
    raise ValidationError("Only active products can be marked out of stock")
```

<details>
<summary>Full Implementation</summary>

```python
async def mark_out_of_stock(self, product_id: str) -> Product:
    product = await self.get_product(product_id)
    if product.status != ProductStatus.ACTIVE:
        raise ValidationError("Only active products can be marked out of stock")

    product.status = ProductStatus.OUT_OF_STOCK
    await product.save()

    self._kafka.emit(
        event_type=EventType.PRODUCT_OUT_OF_STOCK,
        entity_id=oid_to_str(product.id),
        data=product.model_dump(mode="json"),
    )
    return product
```
</details>

---

#### 5.7d: `restore_product(product_id)` - Any Status to DRAFT

**What it does**: Restores any product (including deleted ones) back to DRAFT status. Unlike other lifecycle methods, this fetches the product directly (not via `self.get_product()`) so it can find DELETED products too.

> **Note**: This is the only lifecycle method that can "undo" a delete, since `get_product()` excludes DELETED products.

<details>
<summary>Full Implementation</summary>

```python
async def restore_product(self, product_id: str) -> Product:
    try:
        product = await Product.get(PydanticObjectId(product_id))
    except Exception:
        raise NotFoundError("Product not found")
    if not product:
        raise NotFoundError("Product not found")

    product.status = ProductStatus.DRAFT
    await product.save()

    self._kafka.emit(
        event_type=EventType.PRODUCT_RESTORED,
        entity_id=oid_to_str(product.id),
        data=product.model_dump(mode="json"),
    )
    return product
```
</details>

#### Lifecycle Verification

```bash
# First, create a fresh product for testing lifecycle:
# (use the create curl from Exercise 5.2)

# 1. Publish (DRAFT → ACTIVE):
curl -s -X POST http://localhost:8000/products/PRODUCT_ID/publish \
  -H "X-Supplier-ID: SUPPLIER_ID" | python3 -m json.tool
# Expected: status "active", published_at set

# 2. Mark out of stock (ACTIVE → OUT_OF_STOCK):
curl -s -X POST http://localhost:8000/products/PRODUCT_ID/mark-out-of-stock \
  -H "X-Supplier-ID: SUPPLIER_ID" | python3 -m json.tool
# Expected: status "out_of_stock"

# 3. Discontinue (OUT_OF_STOCK → DISCONTINUED):
curl -s -X POST http://localhost:8000/products/PRODUCT_ID/discontinue \
  -H "X-Supplier-ID: SUPPLIER_ID" | python3 -m json.tool
# Expected: status "discontinued"

# 4. Restore (DISCONTINUED → DRAFT):
curl -s -X POST http://localhost:8000/products/PRODUCT_ID/restore \
  -H "X-Supplier-ID: SUPPLIER_ID" | python3 -m json.tool
# Expected: status "draft"

# 5. Try invalid transition (DRAFT → DISCONTINUE should fail):
curl -s -X POST http://localhost:8000/products/PRODUCT_ID/discontinue \
  -H "X-Supplier-ID: SUPPLIER_ID" | python3 -m json.tool
# Expected: 422 error "Only active or out-of-stock products can be discontinued"
```

---

## 6. VERIFICATION CHECKLIST

After implementing all methods, verify each one works:

| # | Method | Test |
|---|--------|------|
| 1 | `_build_topic_descriptions` | Used by create_product - verify topic_descriptions in response |
| 2 | `_build_stock_locations` | Used by create_product - verify stock_locations in response |
| 3 | `_build_variants` | Used by create_product - verify variants dict in response |
| 4 | `create_product` | Create a product with variants, stock locations, topic descriptions |
| 5 | `create_product` (bad supplier) | Should fail with NotFoundError |
| 6 | `get_product` | Get by ID - returns full product |
| 7 | `get_product` (non-existent) | Should fail with NotFoundError |
| 8 | `list_products` | List all non-deleted products |
| 9 | `list_products` with status filter | Filter by `?status=draft` |
| 10 | `list_products` with category | Filter by `?category=electronics` |
| 11 | `list_products` with supplier | Filter by `?supplier_id=...` |
| 12 | `update_product` | Change name, verify updated_at changes |
| 13 | `update_product` (nested) | Update variants, verify old variants replaced |
| 14 | `delete_product` | Any → DELETED, supplier product_ids cleaned up |
| 15 | `publish_product` | DRAFT → ACTIVE, published_at set |
| 16 | `publish_product` (wrong status) | Non-DRAFT → ValidationError |
| 17 | `discontinue_product` | ACTIVE/OUT_OF_STOCK → DISCONTINUED |
| 18 | `mark_out_of_stock` | ACTIVE → OUT_OF_STOCK |
| 19 | `restore_product` | Any → DRAFT (even DELETED) |

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

**Question**: How would you find all products that have ANY variant priced over $50? With a List this would be easy (`$elemMatch`). With a Dict, it requires either:
1. An aggregation pipeline with `$objectToArray`
2. Denormalized min/max price fields on the Product

Which approach would you choose and why?

### Challenge 2: Compound Index Optimization

The current indexes are all single-field. Consider this common query pattern:

```python
{"status": {"$ne": "deleted"}, "supplier_id": ObjectId("...")}
```

**Question**: Would a compound index `[("supplier_id", 1), ("status", 1)]` be more efficient than two separate indexes? Why?

**Experiment**:
```javascript
// Check which index is used:
db.products.find({
    status: { $ne: "deleted" },
    supplier_id: ObjectId("...")
}).explain("executionStats")
```

### Challenge 3: Atomic Back-Reference Update

The current implementation uses `supplier.product_ids.append()` + `supplier.save()`. This is a read-modify-write cycle that's NOT atomic.

**Question**: What happens if two products are created simultaneously for the same supplier? Could the second `save()` overwrite the first?

**Better approach**: Use MongoDB's `$addToSet` operator for atomic array update:
```python
await Supplier.find_one({"_id": supplier.id}).update(
    {"$addToSet": {"product_ids": product.id}}
)
```

When would you prefer `$addToSet` over the read-modify-write pattern?

---

## 8. WHAT'S NEXT

You've built the **product catalog** - the most structurally complex service so far.

**Concepts you mastered**:
- Complex embedded document construction (7 types) from typed request objects
- `Dict` (Map) field construction (variants)
- Cross-collection validation (supplier lookup before product creation)
- Back-reference management (`supplier.product_ids` append/remove)
- `$ne` for exclusion filtering (hide DELETED products)
- `$in` for multi-value status filtering
- Skip/limit pagination
- 5-state lifecycle machine with guarded transitions (`ValidationError`)
- Denormalized data (supplier_info snapshot)
- Partial update pattern with `is not None` checks

**TASK_05: Post Service** will introduce:
- Denormalized author snapshot (`PostAuthor` embedded from User data)
- Draft/publish lifecycle with `published_at` gating
- Media attachment handling (`MediaAttachment`, `LinkPreview` embedded docs)
- Soft delete pattern (using `deleted_at` timestamp, different from product's status-based delete)
- Feed listing filtered by `published_at != None` and `deleted_at == None`
