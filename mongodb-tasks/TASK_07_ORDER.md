# TASK 07: Order Service - E-Commerce Transactions & Fulfillment

## 1. MISSION BRIEFING

Orders are where the **entire platform converges**. Users browse products, discover what they want, and eventually place an order. An order captures a complete purchase - product snapshots frozen at purchase time, shipping details, per-item fulfillment tracking, and status transitions through the order lifecycle.

This is the **most transactional service** you've built. The Order service introduces patterns from real e-commerce: product snapshot denormalization freezes product data at purchase time, per-item fulfillment tracking allows partial shipments, and the 8-status state machine governs the entire order lifecycle.

### What You Will Build
The `OrderService` class - ~10 methods covering order creation with product snapshot denormalization, status management, per-item fulfillment tracking, cursor-based listing, and two different lookup strategies (by ID and by order number).

### What You Will Learn

| MongoDB Concept | Where You'll Use It |
|----------------|-------------------|
| **Cross-collection validation chain** | User (exists + active) -> Products (exist + active) |
| **Product snapshot denormalization** | Freeze product data at purchase time in `ProductSnapshot` |
| **Compound `find_one` (anti-enumeration)** | `{_id, customer.user_id}` - orders scoped to owner |
| **`find_one` on unique field** | `{order_number, customer.user_id}` - lookup by human-readable ID |
| **Cursor-based pagination with `$lt`** | Descending order list with reverse cursor direction |
| **`$in` status filter** | Filter orders by multiple statuses |
| **Nested field queries** | `customer.user_id`, `items.product_snapshot.supplier_id` |
| **Per-item embedded updates** | Updating `fulfillment_status`, `tracking_number` on individual OrderItems |
| **Order number generation** | Human-readable unique identifier pattern |

### How This Differs From Previous Tasks

| Aspect | Post (05) | Order (07) |
|--------|-----------|------------|
| Embedded doc types | 4 | **4** (OrderCustomer, ProductSnapshot, OrderItem, ShippingAddress) |
| Collections touched | 2 (posts + users) | **3** (orders + users + products) |
| Cursor pagination | `published_at` + `_id` tiebreaker | **`_id` only** with descending `$lt` |
| Denormalized data | PostAuthor from User | **OrderCustomer** from User + **ProductSnapshot** from Product |
| State machine | None (soft delete only) | **8 statuses** (pending -> confirmed -> shipped -> delivered) |
| Lookup methods | By ID only | **By ID AND by order number** |
| Per-item tracking | N/A | **FulfillmentStatus** per OrderItem |

---

## 2. BEFORE YOU START

### Prerequisites
- **TASK_01 (User) must be complete** - Orders require a customer (User)
- **TASK_04 (Product) must be complete** - Orders reference products with variant info
- Have at least one active user and one active product

### Files You MUST Read Before Coding

| Order | File | Why |
|-------|------|-----|
| 1 | `shared/models/order.py` | 190 lines - 4 enums, 4 embedded types, 3 indexes |
| 2 | `apps/backend-service/src/schemas/order.py` | Request/response schemas |
| 3 | `apps/backend-service/src/routes/order.py` | Endpoints your service must support |
| 4 | `apps/backend-service/src/utils/order_utils.py` | Response builders, header extraction |
| 5 | `shared/models/product.py` | Product model - you'll read variant data for snapshots |
| 6 | `shared/models/user.py` | User model - you'll build `OrderCustomer` from User |

### The Data Flow

```
HTTP Request (User JWT)
    |
    v
+-----------+   Extracts user_id from X-User-ID header
|  Route    |
|           |
|  Calls    |
|  your     |
|  service  |
    |
    v
+--------------------------------------------------------------+
|               OrderService (YOU WRITE THIS)                   |
|                                                               |
|  Reads from THREE collections:                                |
|    1. Order      (main CRUD + lifecycle)                      |
|    2. User       (customer info for denormalization)           |
|    3. Product    (validation, pricing, snapshots)              |
|                                                               |
|  Writes to ONE collection:                                    |
|    1. Order      (insert, status updates, fulfillment)        |
|                                                               |
|  Returns Order documents                                      |
+--------------------------------------------------------------+
    |
    v
+-----------+   Route transforms Order -> response schemas
|  Route    |   using utils/order_utils.py
+-----------+
```

### The 8-Status Order Lifecycle

```
                    confirm_order()
    PENDING --------------------------> CONFIRMED
       |                                    |
       |  cancel_order()                    |  start_processing()
       |                                    v
       +-----------> CANCELLED          PROCESSING
                       ^                    |
                       |                    |  mark_shipped()
                       |                    v
                       +------------     SHIPPED
                       |                    |
                       |                    |  mark_delivered()
                       |                    v
                       |               DELIVERED
                       |
                       +-- cancel_order() (if not shipped)

    Payment fails:
    PENDING -----------------------------> FAILED

    After delivery (or anytime after payment):
    ANY paid -----------------------------> REFUNDED
```

### The 4 Enums

```python
OrderStatus:       pending | confirmed | processing | shipped | delivered | cancelled | refunded | failed
PaymentStatus:     pending | authorized | captured | failed | refunded | partially_refunded
FulfillmentStatus: pending | processing | shipped | delivered | cancelled | returned
PaymentMethod:     credit_card | debit_card | paypal | apple_pay | google_pay | bank_transfer | cash_on_delivery
```

> **Note**: `PaymentStatus`, `FulfillmentStatus`, and `PaymentMethod` enums are defined in the model. `FulfillmentStatus` is used per-item on `OrderItem`. `PaymentStatus` and `PaymentMethod` are available for future payment integration but are not used in any document field currently.

---

## 3. MODEL DEEP DIVE

### Embedded Document Hierarchy (4 types)

```
Order (Document)
|
+-- customer: OrderCustomer                      <- Denormalized from User
|   +-- user_id, display_name, email, phone
|
+-- items: List[OrderItem]                       <- Products purchased
|   +-- item_id, product_snapshot, quantity,
|       unit_price_cents, final_price_cents,
|       fulfillment_status, shipped_quantity,
|       tracking_number, carrier, shipped_at,
|       delivered_at, total_cents
|   |
|   +-- product_snapshot: ProductSnapshot        <- Frozen product at purchase time
|       +-- product_id, supplier_id, product_name,
|           variant_name, variant_attributes,
|           image_url, supplier_name
|
+-- shipping_address: ShippingAddress            <- Delivery address
|   +-- recipient_name, phone, street_address_1/2,
|       city, state, zip_code, country
|
+-- order_number: str                            <- Human-readable ID (e.g., "ORD-20250203-A1B2")
+-- status: OrderStatus                          <- 8 possible values (default: PENDING)
+-- created_at: datetime                         <- Auto-set on creation
+-- updated_at: datetime                         <- Auto-set on save
```

### Key Embedded Types

```python
# Frozen product at purchase time
class ProductSnapshot(BaseModel):
    product_id: PydanticObjectId
    supplier_id: PydanticObjectId
    product_name: str
    variant_name: Optional[str]           # If a variant was selected
    variant_attributes: Dict[str, str]    # {"Color": "Red", "Size": "L"}
    image_url: str
    supplier_name: str                    # Denormalized supplier name

# Each item with pricing + fulfillment tracking
class OrderItem(BaseModel):
    item_id: str                          # "item_1", "item_2"
    product_snapshot: ProductSnapshot
    quantity: int                         # >= 1
    unit_price_cents: int                 # Price per unit
    final_price_cents: int                # Final price after any discount
    fulfillment_status: FulfillmentStatus # Per-item tracking (default: PENDING)
    shipped_quantity: int                 # How many shipped (default: 0)
    tracking_number: Optional[str]        # Shipping tracking
    carrier: Optional[str]               # Shipping carrier
    shipped_at: Optional[datetime]        # When shipped
    delivered_at: Optional[datetime]      # When delivered
    total_cents: int                      # Grand total for this item
```

### Index Analysis (3 indexes)

```python
indexes = [
    # 1. Customer's orders (list_user_orders query)
    [("customer.user_id", 1), ("created_at", -1)],
    # -> Nested field query into denormalized customer!

    # 2. Status filtering
    [("status", 1), ("created_at", -1)],

    # 3. Date range queries
    [("created_at", -1)],
]
```

### Key Model Observations

| Feature | Detail |
|---------|--------|
| **Collection name** | `orders` (set in `Settings.name`) |
| **Timestamps** | `save()` override auto-updates `updated_at` |
| **No soft delete** | No `deleted_at` field - orders use status-based lifecycle |
| **Per-item fulfillment** | Each `OrderItem` has its own `fulfillment_status` |
| **Product snapshot** | Product data is frozen at purchase time - price changes don't affect existing orders |
| **Denormalized customer** | `OrderCustomer` captures user data at order time |

### Understanding ProductSnapshot

The `ProductSnapshot` is the **most important pattern** in this task. When a user places an order, we "freeze" the product data:

```python
# Without snapshot: If product name changes, all old orders show the NEW name
# With snapshot: Each order preserves the product data as it was at purchase time
```

This is why `ProductSnapshot` copies `product_name`, `supplier_name`, `image_url`, etc. from the Product. Even if the product is later deleted or modified, the order retains the original data.

---

## 4. SERVICE CONTRACT

Your service file: `apps/backend-service/src/services/order.py`

### Class Setup

```python
from shared.models.order import (
    Order, OrderStatus, FulfillmentStatus,
    OrderCustomer, ProductSnapshot, OrderItem, ShippingAddress
)
from shared.models.product import Product, ProductStatus
from shared.models.user import User

class OrderService:
    def __init__(self, kafka_service=None):
        self._kafka = kafka_service
        self.default_page_size = 20
        self.max_page_size = 100
```

### Method Overview

| # | Method | MongoDB Concepts | Difficulty |
|---|--------|-----------------|-----------|
| 1 | `_generate_order_number()` | Pure Python | Easy |
| 2 | `_get_user_order(order_id, user_id)` | Compound `find_one` (anti-enumeration) | Medium |
| 3 | `_build_customer(user)` | Denormalized snapshot from User | Easy |
| 4 | `_build_product_snapshot(product, variant_name)` | Denormalized snapshot from Product | Easy |
| 5 | `create_order(...)` | Cross-collection validation + insert | **Hard** |
| 6 | `get_order(order_id, user_id)` | Delegates to `_get_user_order` | Easy |
| 7 | `get_order_by_number(order_number, user_id)` | `find_one` on unique field + ownership | Medium |
| 8 | `list_user_orders(...)` | Cursor pagination with `$lt` + `$in` filter | **Hard** |
| 9 | `update_order_status(order_id, new_status)` | Status transition validation | Medium |
| 10 | `cancel_order(order_id, user_id)` | Status guard + item fulfillment update | Medium |

---

## 5. EXERCISES

---

### Exercise 5.1: Helper Methods - Order Foundations

**Concept**: Order number generation, compound `find_one` (anti-enumeration), denormalized snapshots

#### 5.1a: `_generate_order_number`

```python
def _generate_order_number(self) -> str:
```
**What it does**: Generate a human-readable order number like `ORD-20250203-A1B2`.

```python
import secrets

date_part = utc_now().strftime("%Y%m%d")
random_part = secrets.token_hex(2).upper()  # 4 hex chars
return f"ORD-{date_part}-{random_part}"
```

> **Note**: This is NOT guaranteed unique (4 hex chars = 65,536 combinations per day). In production, you'd catch duplicate key errors and retry with a new random part.

---

#### 5.1b: `_get_user_order` (Anti-Enumeration)

```python
async def _get_user_order(self, order_id: str, user_id: str) -> Order:
```
**What it does**: Fetch an order scoped to the requesting user. Same anti-enumeration pattern from previous tasks.

**The compound query:**
```python
order = await Order.find_one({
    "_id": PydanticObjectId(order_id),
    "customer.user_id": PydanticObjectId(user_id)
})
```

Both conditions must match. If the order exists but belongs to a different user, the result is `None` - indistinguishable from "doesn't exist". This prevents attackers from discovering which order IDs exist.

**Steps**:
1. Wrap the `find_one` in try/except for invalid ObjectIds
2. If `order` is None, raise `ValueError("Order not found")`
3. Return the order

> **Index used**: `[("customer.user_id", 1), ("created_at", -1)]` - partially covers this query.

<details>
<summary>Full Implementation</summary>

```python
async def _get_user_order(self, order_id: str, user_id: str) -> Order:
    try:
        order = await Order.find_one({
            "_id": PydanticObjectId(order_id),
            "customer.user_id": PydanticObjectId(user_id)
        })
    except Exception:
        raise ValueError("Invalid order or user ID")

    if not order:
        raise ValueError("Order not found")

    return order
```
</details>

---

#### 5.1c: `_build_customer` (Denormalized Customer Snapshot)

```python
def _build_customer(self, user: User) -> OrderCustomer:
```

Build an `OrderCustomer` from a User document. This captures the user's information at order time.

```python
def _build_customer(self, user: User) -> OrderCustomer:
    return OrderCustomer(
        user_id=user.id,
        display_name=user.profile.display_name,
        email=user.contact_info.primary_email,
        phone=user.contact_info.phone
    )
```

---

#### 5.1d: `_build_product_snapshot` (Frozen Product Data)

```python
def _build_product_snapshot(
    self, product: Product, variant_name: Optional[str] = None
) -> ProductSnapshot:
```

Build a `ProductSnapshot` from a Product document and optional variant name.

**Steps**:
1. Start with base product data: `product.name`, `product.supplier_id`, image from first variant or default
2. If `variant_name` specified: Look up the variant in `product.variants` (it's a `Dict[str, ProductVariant]`)
3. Copy `variant_name`, `variant_attributes` (list of VariantAttribute -> dict), and variant's `image_url`
4. Include `supplier_name` from `product.supplier_info.get("name", "Unknown Supplier")`
5. Return `ProductSnapshot`

<details>
<summary>Full Implementation</summary>

```python
def _build_product_snapshot(
    self, product: Product, variant_name: Optional[str] = None
) -> ProductSnapshot:
    image_url = "https://example.com/default-product.jpg"
    variant_attrs = {}
    v_name = variant_name

    if variant_name and variant_name in product.variants:
        variant = product.variants[variant_name]
        if variant.image_url:
            image_url = variant.image_url
        variant_attrs = {
            attr.attribute_name: attr.attribute_value
            for attr in variant.attributes
        }
    elif product.variants:
        # Use first variant's image as default
        first_variant = next(iter(product.variants.values()))
        if first_variant.image_url:
            image_url = first_variant.image_url

    return ProductSnapshot(
        product_id=product.id,
        supplier_id=product.supplier_id,
        product_name=product.name,
        variant_name=v_name,
        variant_attributes=variant_attrs,
        image_url=image_url,
        supplier_name=product.supplier_info.get("name", "Unknown Supplier")
    )
```
</details>

---

### Exercise 5.2: Create Order - Cross-Collection Validation + Snapshot Build

**Concept**: Multi-collection reads (User + Product), product snapshot denormalization, complex document construction

#### The Method Signature

```python
async def create_order(
    self,
    user_id: str,
    items_data: List[Dict],
    shipping_address_data: Dict
) -> Order:
```

#### Step-by-Step Algorithm

```
1. Validate user exists (cross-collection)
   +-- user = await User.get(PydanticObjectId(user_id))
   +-- Check user exists and user.deleted_at is None

2. Validate and build each order item:
   For each item in items_data:
   +-- Fetch product: await Product.get(product_id)
   +-- Check product exists and status is ACTIVE
   +-- If variant_name provided, verify variant exists in product.variants
   +-- Determine unit_price: variant.price_cents or product.base_price_cents
   +-- Build ProductSnapshot
   +-- Build OrderItem with pricing

3. Build shipping address from request data

4. Build the Order document:
   +-- order_number = self._generate_order_number()
   +-- customer = self._build_customer(user)
   +-- status = OrderStatus.PENDING

5. await order.insert()

6. Emit Kafka event (order.created)

7. Return order
```

#### Building OrderItems

```python
order_items = []
for i, item_data in enumerate(items_data):
    product_id = item_data["product_id"]
    variant_name = item_data.get("variant_name")
    quantity = item_data.get("quantity", 1)

    # Validate product
    try:
        product = await Product.get(PydanticObjectId(product_id))
    except Exception:
        raise ValueError(f"Invalid product ID: {product_id}")

    if not product or product.status != ProductStatus.ACTIVE:
        raise ValueError(f"Product not available: {product_id}")

    # Determine price
    unit_price = product.base_price_cents
    if variant_name:
        if variant_name not in product.variants:
            raise ValueError(f"Variant '{variant_name}' not found for product '{product.name}'")
        variant = product.variants[variant_name]
        unit_price = variant.price_cents

    # Build snapshot and item
    snapshot = self._build_product_snapshot(product, variant_name)
    total = unit_price * quantity

    order_items.append(OrderItem(
        item_id=f"item_{i + 1}",
        product_snapshot=snapshot,
        quantity=quantity,
        unit_price_cents=unit_price,
        final_price_cents=unit_price,  # No discount logic for now
        total_cents=total,
    ))
```

> **Think about it**: Why do we use `product.base_price_cents` as the default and only override with `variant.price_cents` when a variant is selected? Because some products have no variants - they just have a base price. The variant price takes precedence when specified.

> **Hint Level 1**: Follow the algorithm. The key insight is building the `ProductSnapshot` from the Product document before inserting. The snapshot freezes the product data so price changes don't affect existing orders.

<details>
<summary>Full Implementation</summary>

```python
async def create_order(
    self, user_id: str, items_data: List[Dict], shipping_address_data: Dict
) -> Order:
    # 1. Validate user
    try:
        user = await User.get(PydanticObjectId(user_id))
    except Exception:
        raise ValueError("Invalid user ID")
    if not user or user.deleted_at:
        raise ValueError("User not found")

    # 2. Validate and build items
    if not items_data:
        raise ValueError("Order must have at least one item")

    order_items = []
    for i, item_data in enumerate(items_data):
        product_id = item_data.get("product_id")
        variant_name = item_data.get("variant_name")
        quantity = item_data.get("quantity", 1)

        if quantity < 1:
            raise ValueError("Quantity must be at least 1")

        try:
            product = await Product.get(PydanticObjectId(product_id))
        except Exception:
            raise ValueError(f"Invalid product ID: {product_id}")

        if not product or product.status != ProductStatus.ACTIVE:
            raise ValueError(f"Product not available: {product_id}")

        unit_price = product.base_price_cents
        if variant_name:
            if variant_name not in product.variants:
                raise ValueError(
                    f"Variant '{variant_name}' not found for product '{product.name}'"
                )
            unit_price = product.variants[variant_name].price_cents

        snapshot = self._build_product_snapshot(product, variant_name)
        total = unit_price * quantity

        order_items.append(OrderItem(
            item_id=f"item_{i + 1}",
            product_snapshot=snapshot,
            quantity=quantity,
            unit_price_cents=unit_price,
            final_price_cents=unit_price,
            total_cents=total,
        ))

    # 3. Build shipping address
    shipping_address = ShippingAddress(
        recipient_name=shipping_address_data["recipient_name"],
        phone=shipping_address_data.get("phone"),
        street_address_1=shipping_address_data["street_address_1"],
        street_address_2=shipping_address_data.get("street_address_2"),
        city=shipping_address_data["city"],
        state=shipping_address_data["state"],
        zip_code=shipping_address_data["zip_code"],
        country=shipping_address_data["country"],
    )

    # 4. Build and insert order
    order = Order(
        order_number=self._generate_order_number(),
        customer=self._build_customer(user),
        items=order_items,
        shipping_address=shipping_address,
        status=OrderStatus.PENDING,
    )

    await order.insert()

    # 5. Emit Kafka event
    if self._kafka:
        self._kafka.emit(
            topic=Topic.ORDER,
            action="created",
            entity_id=oid_to_str(order.id),
            data=order.model_dump(mode="json"),
        )

    return order
```
</details>

---

### Exercise 5.3: List User Orders (Descending Cursor Pagination)

**Concept**: Cursor pagination with `$lt` (descending direction), `$in` status filter, nested field query

#### The Method Signature

```python
async def list_user_orders(
    self,
    user_id: str,
    cursor: Optional[str] = None,
    limit: int = 20,
    status_filter: Optional[List[str]] = None
) -> Tuple[List[Order], bool]:
```

#### Descending Cursor Direction

**This cursor goes BACKWARDS (newest first):**

```python
query = {"customer.user_id": PydanticObjectId(user_id)}

if cursor:
    query["_id"] = {"$lt": PydanticObjectId(cursor)}  # $lt, not $gt!

orders = await Order.find(query).sort(
    [("created_at", -1)]
).limit(limit + 1).to_list()
```

**Why `$lt` instead of `$gt`?** The sort is `-created_at` (descending - newest first). ObjectIds are monotonically increasing, so the "next page" has SMALLER (older) IDs. The cursor points to the last item on the current page, and we want items with IDs LESS THAN that.

| Sort Direction | Cursor Operator | Meaning |
|----------------|-----------------|---------|
| Ascending | `$gt` | "Give me items AFTER this cursor" |
| **Descending** | **`$lt`** | **"Give me items BEFORE this cursor"** |

> **Contrast with TASK_05**: Post feeds used a `published_at` + `_id` tiebreaker with base64 cursors. Order lists use simple `_id` cursors with `$lt` because we sort by `created_at` descending, and ObjectIds are inherently time-ordered.

#### The `$in` Status Filter

```python
if status_filter:
    query["status"] = {"$in": status_filter}
```

This lets the client request only specific statuses, e.g., `["pending", "confirmed"]` to show "active" orders, or `["delivered", "cancelled"]` to show "completed" orders.

> **Index used**: `[("status", 1), ("created_at", -1)]` - index #2 supports status-filtered queries.

> **Hint Level 1**: Build base query with `customer.user_id`. Add `$in` for status filter if provided. Add `$lt` for cursor if provided. Sort descending. Use the fetch+has-more pattern.

<details>
<summary>Full Implementation</summary>

```python
async def list_user_orders(
    self, user_id: str, cursor=None, limit=20, status_filter=None
) -> Tuple[List[Order], bool]:
    try:
        uid = PydanticObjectId(user_id)
    except Exception:
        raise ValueError("Invalid user ID")

    query = {"customer.user_id": uid}

    if status_filter:
        query["status"] = {"$in": status_filter}

    if cursor:
        try:
            query["_id"] = {"$lt": PydanticObjectId(cursor)}
        except Exception:
            pass  # Invalid cursor, ignore

    limit = min(limit, self.max_page_size)
    orders = await Order.find(query).sort(
        [("created_at", -1)]
    ).limit(limit + 1).to_list()

    has_more = len(orders) > limit
    if has_more:
        orders = orders[:limit]

    return orders, has_more
```
</details>

---

### Exercise 5.4: Get Order - Two Lookup Strategies

**Concept**: Lookup by internal `_id` vs. human-readable `order_number`, both with ownership scoping

#### 5.4a: `get_order` (By ID)

```python
async def get_order(self, order_id: str, user_id: str) -> Order:
    return await self._get_user_order(order_id, user_id)
```

That's it! Delegates to the helper. The route uses this method name for API clarity.

---

#### 5.4b: `get_order_by_number` (By Human-Readable Number)

```python
async def get_order_by_number(self, order_number: str, user_id: str) -> Order:
```

**The query:**
```python
order = await Order.find_one({
    "order_number": order_number.strip().upper(),
    "customer.user_id": PydanticObjectId(user_id)
})
```

**Why `.upper()`?** Order numbers are stored as uppercase (e.g., `"ORD-20250203-A1B2"`). If the user types `"ord-20250203-a1b2"`, we need to normalize to match.

> **Two lookup strategies**: `get_order` uses the internal `_id` (machine-friendly, in URLs). `get_order_by_number` uses the human-readable `order_number` (shown on receipts, in customer emails). Both include `customer.user_id` for anti-enumeration.

<details>
<summary>Full Implementation</summary>

```python
async def get_order_by_number(self, order_number: str, user_id: str) -> Order:
    try:
        uid = PydanticObjectId(user_id)
    except Exception:
        raise ValueError("Invalid user ID")

    order = await Order.find_one({
        "order_number": order_number.strip().upper(),
        "customer.user_id": uid
    })

    if not order:
        raise ValueError("Order not found")

    return order
```
</details>

---

### Exercise 5.5: Update Order Status

**Concept**: Status transition validation, state machine enforcement

#### The Method Signature

```python
async def update_order_status(
    self,
    order_id: str,
    user_id: str,
    new_status: str
) -> Order:
```

#### Valid Status Transitions

Not every status change is allowed. Define the valid transitions:

```python
VALID_TRANSITIONS = {
    OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED, OrderStatus.FAILED},
    OrderStatus.CONFIRMED: {OrderStatus.PROCESSING, OrderStatus.CANCELLED},
    OrderStatus.PROCESSING: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: {OrderStatus.REFUNDED},
    OrderStatus.CANCELLED: set(),      # Terminal state
    OrderStatus.REFUNDED: set(),       # Terminal state
    OrderStatus.FAILED: set(),         # Terminal state
}
```

> **Why enforce transitions?** Without validation, a bug could move an order from DELIVERED back to PENDING. The transition map ensures the state machine is always followed.

**Algorithm**:
1. Get order with ownership check
2. Validate `new_status` is a valid `OrderStatus` enum value
3. Check the transition is allowed: `new_status in VALID_TRANSITIONS[order.status]`
4. Update `order.status = new_status`
5. Save

<details>
<summary>Full Implementation</summary>

```python
VALID_TRANSITIONS = {
    OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED, OrderStatus.FAILED},
    OrderStatus.CONFIRMED: {OrderStatus.PROCESSING, OrderStatus.CANCELLED},
    OrderStatus.PROCESSING: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: {OrderStatus.REFUNDED},
    OrderStatus.CANCELLED: set(),
    OrderStatus.REFUNDED: set(),
    OrderStatus.FAILED: set(),
}

async def update_order_status(
    self, order_id: str, user_id: str, new_status: str
) -> Order:
    order = await self._get_user_order(order_id, user_id)

    try:
        status_enum = OrderStatus(new_status)
    except ValueError:
        raise ValueError(f"Invalid order status: {new_status}")

    allowed = self.VALID_TRANSITIONS.get(order.status, set())
    if status_enum not in allowed:
        raise ValueError(
            f"Cannot transition from '{order.status.value}' to '{new_status}'"
        )

    order.status = status_enum
    await order.save()

    if self._kafka:
        self._kafka.emit(
            topic=Topic.ORDER,
            action="status_updated",
            entity_id=oid_to_str(order.id),
            data={
                "order_number": order.order_number,
                "old_status": order.status.value,
                "new_status": new_status,
                "customer_id": oid_to_str(order.customer.user_id),
            },
        )

    return order
```
</details>

---

### Exercise 5.6: Cancel Order

**Concept**: Status guard, per-item fulfillment status update

#### The Method Signature

```python
async def cancel_order(self, order_id: str, user_id: str) -> Order:
```

#### Algorithm

```
1. Get order with ownership check
2. Guard: only PENDING, CONFIRMED, or PROCESSING can be cancelled
3. Update order status to CANCELLED
4. Update each item's fulfillment_status to CANCELLED
5. Save
6. Emit Kafka event
```

**Cancelling per-item fulfillment:**
```python
for item in order.items:
    if item.fulfillment_status not in (
        FulfillmentStatus.SHIPPED, FulfillmentStatus.DELIVERED
    ):
        item.fulfillment_status = FulfillmentStatus.CANCELLED
```

> **Why check each item's fulfillment status?** In a partially-shipped order, some items may already be SHIPPED or DELIVERED. Those items can't be cancelled - only the unshipped ones change to CANCELLED.

<details>
<summary>Full Implementation</summary>

```python
async def cancel_order(self, order_id: str, user_id: str) -> Order:
    order = await self._get_user_order(order_id, user_id)

    cancellable = {OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PROCESSING}
    if order.status not in cancellable:
        raise ValueError(
            f"Cannot cancel order in '{order.status.value}' status"
        )

    order.status = OrderStatus.CANCELLED

    for item in order.items:
        if item.fulfillment_status not in (
            FulfillmentStatus.SHIPPED, FulfillmentStatus.DELIVERED
        ):
            item.fulfillment_status = FulfillmentStatus.CANCELLED

    await order.save()

    if self._kafka:
        self._kafka.emit(
            topic=Topic.ORDER,
            action="cancelled",
            entity_id=oid_to_str(order.id),
            data={
                "order_number": order.order_number,
                "customer_id": oid_to_str(order.customer.user_id),
            },
        )

    return order
```
</details>

---

### Exercise 5.7: Update Item Fulfillment (Per-Item Tracking)

**Concept**: Updating specific items within an embedded array, per-item state transitions

#### The Method Signature

```python
async def update_item_fulfillment(
    self,
    order_id: str,
    item_id: str,
    fulfillment_status: str,
    tracking_number: Optional[str] = None,
    carrier: Optional[str] = None
) -> Order:
```

#### Algorithm

```
1. Get order by ID
2. Find the item by item_id within order.items
3. Validate the fulfillment status transition
4. Update the item's fulfillment fields
5. If all items shipped -> update order status to SHIPPED
6. If all items delivered -> update order status to DELIVERED
7. Save
```

**Finding an item in the embedded array:**
```python
target_item = None
for item in order.items:
    if item.item_id == item_id:
        target_item = item
        break
if not target_item:
    raise ValueError(f"Item '{item_id}' not found in order")
```

**Setting fulfillment fields:**
```python
target_item.fulfillment_status = FulfillmentStatus(fulfillment_status)
if tracking_number:
    target_item.tracking_number = tracking_number
if carrier:
    target_item.carrier = carrier
if fulfillment_status == FulfillmentStatus.SHIPPED.value:
    target_item.shipped_at = utc_now()
    target_item.shipped_quantity = target_item.quantity
elif fulfillment_status == FulfillmentStatus.DELIVERED.value:
    target_item.delivered_at = utc_now()
```

**Auto-updating order status based on items:**
```python
# Check if all items have the same fulfillment status
all_shipped = all(
    item.fulfillment_status in (FulfillmentStatus.SHIPPED, FulfillmentStatus.DELIVERED)
    for item in order.items
)
all_delivered = all(
    item.fulfillment_status == FulfillmentStatus.DELIVERED
    for item in order.items
)

if all_delivered:
    order.status = OrderStatus.DELIVERED
elif all_shipped:
    order.status = OrderStatus.SHIPPED
```

<details>
<summary>Full Implementation</summary>

```python
async def update_item_fulfillment(
    self, order_id: str, item_id: str, fulfillment_status: str,
    tracking_number=None, carrier=None
) -> Order:
    # Note: no user_id check - this is typically called by supplier/admin
    try:
        order = await Order.get(PydanticObjectId(order_id))
    except Exception:
        raise ValueError("Invalid order ID")
    if not order:
        raise ValueError("Order not found")

    # Find the item
    target_item = None
    for item in order.items:
        if item.item_id == item_id:
            target_item = item
            break
    if not target_item:
        raise ValueError(f"Item '{item_id}' not found in order")

    # Validate fulfillment status
    try:
        new_status = FulfillmentStatus(fulfillment_status)
    except ValueError:
        raise ValueError(f"Invalid fulfillment status: {fulfillment_status}")

    # Update item
    target_item.fulfillment_status = new_status
    if tracking_number:
        target_item.tracking_number = tracking_number
    if carrier:
        target_item.carrier = carrier
    if new_status == FulfillmentStatus.SHIPPED:
        target_item.shipped_at = utc_now()
        target_item.shipped_quantity = target_item.quantity
    elif new_status == FulfillmentStatus.DELIVERED:
        target_item.delivered_at = utc_now()

    # Auto-update order status
    all_delivered = all(
        item.fulfillment_status == FulfillmentStatus.DELIVERED
        for item in order.items
    )
    all_shipped = all(
        item.fulfillment_status in (FulfillmentStatus.SHIPPED, FulfillmentStatus.DELIVERED)
        for item in order.items
    )

    if all_delivered:
        order.status = OrderStatus.DELIVERED
    elif all_shipped:
        order.status = OrderStatus.SHIPPED

    await order.save()
    return order
```
</details>

---

## 6. VERIFICATION CHECKLIST

| # | Test | What to Verify |
|---|------|---------------|
| 1 | Create an order with valid user and product | Order created with status PENDING, `OrderCustomer` has user data, `ProductSnapshot` has product data |
| 2 | Create an order with invalid product | Returns error |
| 3 | Create an order with nonexistent variant | Returns error |
| 4 | Get order by ID | Returns full order with all embedded data |
| 5 | Get order by order number | Same order returned, case-insensitive |
| 6 | Get another user's order | Returns "Order not found" (anti-enumeration) |
| 7 | List user orders | Newest first, cursor pagination works |
| 8 | List user orders with status filter | Only matching statuses returned |
| 9 | List with cursor | Second page returns different orders |
| 10 | Update order status (PENDING -> CONFIRMED) | Status changes |
| 11 | Update order status (DELIVERED -> PENDING) | Returns error (invalid transition) |
| 12 | Cancel a PENDING order | Status CANCELLED, items CANCELLED |
| 13 | Cancel a SHIPPED order | Returns error |
| 14 | Update item fulfillment to SHIPPED | Item has tracking_number, shipped_at set |
| 15 | Ship all items | Order status auto-updates to SHIPPED |
| 16 | Deliver all items | Order status auto-updates to DELIVERED |

---

## 7. ADVANCED CHALLENGES

### Challenge 1: Order Number Collision

The `_generate_order_number` method uses 4 hex chars = 65,536 combinations per day. What happens when two orders get the same number?

**Questions**:
1. What error does MongoDB throw when a duplicate is inserted against a unique index?
2. Design a retry loop that catches `DuplicateKeyError` and regenerates the order number:
   ```python
   for attempt in range(3):
       try:
           order.order_number = self._generate_order_number()
           await order.insert()
           break
       except DuplicateKeyError:
           if attempt == 2:
               raise ValueError("Failed to generate unique order number")
   ```
3. What alternative strategies exist? (UUID, database sequences, snowflake IDs)

### Challenge 2: Product Snapshot Staleness

The `ProductSnapshot` freezes product data at order time. But what if:
- The product image URL becomes a broken link?
- The supplier changes their name?
- The product is recalled?

**Questions**:
1. Should snapshots ever be updated after order creation? What are the tradeoffs?
2. How would you implement a "refresh snapshot" admin action using `updateMany`?
   ```javascript
   db.orders.updateMany(
     { "items.product_snapshot.product_id": ObjectId("...") },
     { $set: { "items.$[elem].product_snapshot.image_url": "new-url.jpg" } },
     { arrayFilters: [{ "elem.product_snapshot.product_id": ObjectId("...") }] }
   )
   ```
3. What MongoDB feature does `arrayFilters` use? (Filtered positional operator)

### Challenge 3: Partial Shipment Edge Cases

Consider an order with 3 items where item 1 is SHIPPED, item 2 is DELIVERED, and item 3 is PENDING.

**Questions**:
1. What should `order.status` be? (PROCESSING? SHIPPED? Something else?)
2. Our current logic checks `all_shipped` and `all_delivered`. What about mixed states?
3. Design a more nuanced status calculation:
   ```python
   if all_delivered:
       return OrderStatus.DELIVERED
   elif all_shipped_or_delivered:
       return OrderStatus.SHIPPED
   elif any_shipped_or_delivered:
       return OrderStatus.PROCESSING
   else:
       return order.status  # No change
   ```

---

## 8. WHAT'S NEXT?

You've built the **e-commerce transaction engine** - the service that ties together users and products.

**Concepts you mastered**:
- Cross-collection validation chain (User -> Product)
- Product snapshot denormalization (freezing data at purchase time)
- Compound `find_one` for anti-enumeration
- Dual lookup strategies (by `_id` and by `order_number`)
- Cursor pagination with descending `$lt` direction
- `$in` status filter for multiple statuses
- 8-status order lifecycle state machine
- Per-item fulfillment tracking within embedded arrays
- Order number generation pattern

**Your next task**: `TASK_08_ANALYTICS.md` - Aggregation Pipeline Exercises. You'll move beyond `find()` queries and build MongoDB **aggregation pipelines** using `$group`, `$match`, `$project`, `$unwind`, `$lookup`, and `$facet` to generate platform analytics across all the data you've created.
