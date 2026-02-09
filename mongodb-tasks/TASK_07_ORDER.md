# TASK 07: Order Service - E-Commerce Transactions & Product Snapshots

## 1. MISSION BRIEFING

Orders are where the **entire platform converges**. Users browse products, discover what they want, and eventually place an order. An order captures a complete purchase - product snapshots frozen at purchase time, shipping details, per-item pricing, and status tracking.

This is the **most transactional service** you've built. The Order service introduces patterns from real e-commerce: product snapshot denormalization freezes product data at purchase time, cross-collection validation ensures data integrity, and order number generation provides human-readable identifiers.

### What You Will Build
The `OrderService` class - 4 methods covering order creation with cross-collection validation and product snapshot denormalization, order retrieval, skip/limit pagination with status filtering, and order cancellation with status guards.

### What You Will Learn

| MongoDB Concept | Where You'll Use It |
|----------------|-------------------|
| **Cross-collection validation chain** | User (exists + active) -> Products (exist + ACTIVE status) |
| **Product snapshot denormalization** | Freeze product data at purchase time in `ProductSnapshot` |
| **`find_one` by ID** | `Order.get(PydanticObjectId(order_id))` - simple order lookup |
| **Skip/limit pagination** | `.skip(skip).limit(min(limit, 100))` with sort |
| **`$in` status filter** | Filter orders by multiple comma-separated statuses |
| **Nested field queries** | `customer.user_id` for scoping orders to a user |
| **Order number generation** | Human-readable unique identifier: `ORD-YYYYMMDD-XXXX` |
| **Status guard on cancel** | Only PENDING or CONFIRMED orders can be cancelled |

### How This Differs From Previous Tasks

| Aspect | Post (05) | Order (07) |
|--------|-----------|------------|
| Embedded doc types | 4 | **4** (OrderCustomer, ProductSnapshot, OrderItem, ShippingAddress) |
| Collections touched | 2 (posts + users) | **3** (orders + users + products) |
| Pagination | Skip/limit | **Skip/limit** with status filter |
| Denormalized data | PostAuthor from User | **OrderCustomer** from User + **ProductSnapshot** from Product |
| Delete pattern | Soft delete (`deleted_at`) | **Status-based** (no `deleted_at` field) |
| Utility functions | `build_post_author()` | **3 functions**: `build_order_customer()`, `build_order_item()`, `generate_order_number()` |

---

## 2. BEFORE YOU START

### Prerequisites
- **TASK_01 (User) must be complete** - Orders require a customer (User)
- **TASK_04 (Product) must be complete** - Orders reference products with variant info
- Have at least one active user and one ACTIVE product

### Files You MUST Read Before Coding

| Order | File | Why |
|-------|------|-----|
| 1 | `shared/models/order.py` | 191 lines - 4 enums, 4 embedded types, 4 indexes |
| 2 | `apps/mongo_backend/schemas/order.py` | Request/response schemas - `CreateOrderRequest`, `CancelOrderRequest` |
| 3 | `apps/mongo_backend/routes/order.py` | 4 endpoints your service must support |
| 4 | `apps/mongo_backend/utils/order_utils.py` | Utility functions: `order_response()`, `get_order_or_404()`, `generate_order_number()`, `build_order_customer()`, `build_product_snapshot()`, `build_order_item()` |
| 5 | `shared/models/product.py` | Product model - you'll validate products and read variant data |
| 6 | `shared/models/user.py` | User model - utility builds `OrderCustomer` from User |

### The Data Flow

```
HTTP Request (X-User-ID header)
    |
    v
+-----------+   Extracts user_id from X-User-ID header
|  Route    |   Parses CreateOrderRequest / CancelOrderRequest body
|           |
|  Calls    |
|  your     |
|  service  |
    |
    v
+--------------------------------------------------------------+
|               OrderService (YOU WRITE THIS)                   |
|                                                               |
|  Uses UTILITY FUNCTIONS from utils/order_utils.py:            |
|    - build_order_customer(user_id)  -> OrderCustomer          |
|    - build_order_item(i, product, variant_name, qty)          |
|    - generate_order_number()  -> "ORD-YYYYMMDD-XXXX"          |
|                                                               |
|  Reads from THREE collections:                                |
|    1. Order      (main CRUD)                                  |
|    2. User       (via build_order_customer utility)            |
|    3. Product    (validation + snapshot in build_order_item)   |
|                                                               |
|  Returns Order documents                                      |
+--------------------------------------------------------------+
    |
    v
+-----------+   Route transforms Order -> JSON
|  Route    |   using order_response() from utils
+-----------+
```

### The 4 Enums

```python
OrderStatus:       pending | confirmed | processing | shipped | delivered | cancelled | refunded | failed
PaymentStatus:     pending | authorized | captured | failed | refunded | partially_refunded
FulfillmentStatus: pending | processing | shipped | delivered | cancelled | returned
PaymentMethod:     credit_card | debit_card | paypal | apple_pay | google_pay | bank_transfer | cash_on_delivery
```

> **Note**: `PaymentStatus`, `FulfillmentStatus`, and `PaymentMethod` enums are defined in the model. `FulfillmentStatus` is used per-item on `OrderItem` (defaults to PENDING). `PaymentStatus` and `PaymentMethod` are available for future payment integration but are not directly set in the current service.

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

### Index Analysis (4 indexes)

```python
indexes = [
    # 1. Unique order number
    [("order_number", 1)],

    # 2. Customer's orders (list_orders query)
    [("customer.user_id", 1), ("created_at", -1)],
    # -> Nested field query into denormalized customer!

    # 3. Status filtering
    [("status", 1), ("created_at", -1)],

    # 4. Date range queries
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
| **Order number index** | `order_number` has its own index for fast lookups |

### Understanding ProductSnapshot

The `ProductSnapshot` is the **most important pattern** in this task. When a user places an order, we "freeze" the product data:

```python
# Without snapshot: If product name changes, all old orders show the NEW name
# With snapshot: Each order preserves the product data as it was at purchase time
```

This is why `ProductSnapshot` copies `product_name`, `supplier_name`, `image_url`, etc. from the Product. Even if the product is later deleted or modified, the order retains the original data.

---

## 4. SERVICE CONTRACT

Your service file: `apps/mongo_backend/services/order.py`

### Class Setup

```python
from shared.models.order import Order, OrderStatus, ShippingAddress
from shared.models.product import Product, ProductStatus
from shared.models.user import User
from shared.errors import NotFoundError, ValidationError
from utils.datetime_utils import utc_now
from utils.order_utils import generate_order_number, build_order_customer, build_order_item
from kafka.producer import get_kafka_producer
from shared.kafka.topics import EventType
from utils.serialization import oid_to_str

class OrderService:
    def __init__(self):
        self._kafka = get_kafka_producer()
```

### Method Overview

| # | Method | MongoDB Concepts | Difficulty |
|---|--------|-----------------|-----------|
| 1 | `create_order(user_id, body)` | Cross-collection validation + insert | **Hard** |
| 2 | `get_order(order_id)` | Simple `Order.get()` by ID | Easy |
| 3 | `list_orders(user_id, skip, limit, status_filter)` | Skip/limit pagination + `$in` filter | Medium |
| 4 | `cancel_order(order_id, reason)` | Status guard + save | Medium |

### Utility Functions (in `utils/order_utils.py`)

These utility functions are **already provided** - you call them from your service:

| Function | What It Does |
|----------|-------------|
| `generate_order_number()` | Returns `"ORD-YYYYMMDD-XXXX"` using `secrets.token_hex(2)` |
| `build_order_customer(user_id)` | Fetches User, returns `OrderCustomer` snapshot. Raises `NotFoundError` if user not found or deleted |
| `build_product_snapshot(product, variant_name)` | Builds `ProductSnapshot` from Product + variant |
| `build_order_item(index, product, variant_name, quantity)` | Builds `OrderItem` with pricing: uses `variant.price_cents` if variant specified, else `product.base_price_cents` |
| `order_response(order)` | Converts Order to JSON dict with `id` field |
| `get_order_or_404(order_id)` | Fetches order or raises `NotFoundError` |

---

## 5. EXERCISES

---

### Exercise 5.1: Understanding the Utility Functions

**Concept**: Before writing the service, understand how the utility functions work.

Read `apps/mongo_backend/utils/order_utils.py` and answer these questions:

1. **`generate_order_number()`** - What format does it produce? How many unique values per day?
2. **`build_order_customer(user_id)`** - What fields does it copy from the User? What errors can it raise?
3. **`build_order_item(index, product, variant_name, quantity)`** - How does it determine the unit price? What does it use as the `item_id`?

<!-- TODO: Implement understanding of utility functions -->

---

### Exercise 5.2: Create Order - Cross-Collection Validation + Snapshot Build

**Concept**: Multi-collection reads (User + Product), product snapshot denormalization, complex document construction

#### The Method Signature

```python
async def create_order(self, user_id: str, body) -> Order:
    """Create a new order. `body` is a CreateOrderRequest."""
```

The `body` parameter is a `CreateOrderRequest` (from `schemas/order.py`) with these fields:
- `body.items` - `List[OrderItemRequest]`, each with `.product_id`, `.variant_name`, `.quantity`
- `body.shipping_address` - `ShippingAddressRequest` with `.recipient_name`, `.phone`, `.street_address_1`, etc.
- `body.payment_info` - `PaymentInfoRequest` (not used by the service currently)

#### Step-by-Step Algorithm

```
1. Build customer snapshot (cross-collection)
   +-- customer = await build_order_customer(user_id)
   +-- This utility fetches the User, checks deleted_at, builds OrderCustomer

2. Validate and build each order item:
   For each item_req in body.items:
   +-- Fetch product: await Product.get(PydanticObjectId(item_req.product_id))
   +-- Check product exists
   +-- Check product.status == ProductStatus.ACTIVE
   +-- Call build_order_item(i, product, item_req.variant_name, item_req.quantity)

3. Build ShippingAddress from body.shipping_address

4. Build the Order document:
   +-- order_number = generate_order_number()
   +-- customer = customer (from step 1)
   +-- items = items (from step 2)
   +-- shipping_address = shipping_address (from step 3)

5. await order.insert()

6. Emit Kafka event: EventType.ORDER_CREATED

7. Return order
```

#### Error Handling

| Condition | Error Type | Message |
|-----------|-----------|---------|
| Product fetch fails (invalid ID) | `NotFoundError` | `"Product not found: {product_id}"` |
| Product is None or status != ACTIVE | `ValidationError` | `"Product not available: {product_id}"` |
| User not found / deleted | Raised by `build_order_customer()` | `NotFoundError` / `ValidationError` |

#### Building OrderItems

```python
items = []
for i, item_req in enumerate(body.items):
    try:
        product = await Product.get(PydanticObjectId(item_req.product_id))
    except Exception:
        raise NotFoundError(f"Product not found: {item_req.product_id}")
    if not product or product.status != ProductStatus.ACTIVE:
        raise ValidationError(f"Product not available: {item_req.product_id}")

    items.append(build_order_item(i, product, item_req.variant_name, item_req.quantity))
```

> **Think about it**: Why do we validate `product.status != ProductStatus.ACTIVE` rather than just `not product`? Because a product might exist but be in DRAFT, DISCONTINUED, or DELETED status. Only ACTIVE products can be ordered.

#### Building ShippingAddress

```python
addr = body.shipping_address
shipping_address = ShippingAddress(
    recipient_name=addr.recipient_name,
    phone=addr.phone,
    street_address_1=addr.street_address_1,
    street_address_2=addr.street_address_2,
    city=addr.city,
    state=addr.state,
    zip_code=addr.zip_code,
    country=addr.country,
)
```

#### Kafka Event

```python
self._kafka.emit(
    event_type=EventType.ORDER_CREATED,
    entity_id=oid_to_str(order.id),
    data=order.model_dump(mode="json"),
)
```

> **Hint Level 1**: The service orchestrates utility functions. `build_order_customer()` handles user lookup and snapshot creation. `build_order_item()` handles pricing and snapshot building. You just need to validate products and wire everything together.

> **Hint Level 2**: Loop through `body.items` with `enumerate()`. For each item, fetch the product, validate it's ACTIVE, then call `build_order_item(i, product, item_req.variant_name, item_req.quantity)`.

<!-- TODO: Implement create_order -->

#### Verify

```bash
# First, get a valid user ID and an ACTIVE product ID from your database

# Create an order
curl -s -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -H "X-User-ID: <user_id>" \
  -d '{
    "items": [
      {
        "product_id": "<product_id>",
        "variant_name": "Default",
        "quantity": 2
      }
    ],
    "shipping_address": {
      "recipient_name": "John Doe",
      "phone": "+1234567890",
      "street_address_1": "123 Main St",
      "city": "New York",
      "state": "NY",
      "zip_code": "10001",
      "country": "US"
    },
    "payment_info": {
      "payment_method": "credit_card",
      "payment_provider": "stripe"
    }
  }' | python3 -m json.tool
```

**Expected**: Status 201, order with `status: "pending"`, `order_number` like `"ORD-XXXXXXXX-XXXX"`, items with `ProductSnapshot` data frozen from the product.

---

### Exercise 5.3: Get Order - Simple ID Lookup

**Concept**: Fetch a single document by `_id` using Beanie's `Order.get()`

#### The Method Signature

```python
async def get_order(self, order_id: str) -> Order:
```

#### Algorithm

```
1. Try to fetch: Order.get(PydanticObjectId(order_id))
2. Wrap in try/except for invalid ObjectId strings
3. If order is None, raise NotFoundError
4. Return the order
```

> **Note**: Unlike the old pattern, `get_order` does NOT take a `user_id` parameter. There is no ownership/anti-enumeration check. The route for listing orders uses `X-User-ID` to scope, but the individual get endpoint does not.

> **Hint Level 1**: This is the simplest method. It's nearly identical to `get_post()` and `get_product()` from previous tasks.

> **Hint Level 2**: Use `PydanticObjectId(order_id)` to convert the string, catch any exception, raise `NotFoundError("Order not found")`.

<!-- TODO: Implement get_order -->

#### Verify

```bash
# Use the order ID from Exercise 5.2
curl -s http://localhost:8000/orders/<order_id> | python3 -m json.tool
```

**Expected**: Full order with customer snapshot, items with product snapshots, shipping address.

---

### Exercise 5.4: List Orders - Skip/Limit Pagination with Status Filter

**Concept**: Nested field query on `customer.user_id`, `$in` operator for multi-status filter, skip/limit pagination

#### The Method Signature

```python
async def list_orders(
    self,
    user_id: str,
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None,
) -> list[Order]:
```

#### How It Works

The route extracts `user_id` from the `X-User-ID` header and passes `status` as a comma-separated string query parameter (e.g., `?status=pending,confirmed`).

#### The Query

```python
query = {"customer.user_id": PydanticObjectId(user_id)}
```

This queries inside the embedded `OrderCustomer` document. The index `[("customer.user_id", 1), ("created_at", -1)]` supports this query.

#### The `$in` Status Filter

The `status_filter` comes as a comma-separated string like `"pending,confirmed"`. Split it into a list:

```python
if status_filter:
    statuses = [s.strip() for s in status_filter.split(",")]
    query["status"] = {"$in": statuses}
```

This lets the client request only specific statuses:
- `?status=pending,confirmed` - show "active" orders
- `?status=delivered,cancelled` - show "completed" orders

> **Index used**: `[("status", 1), ("created_at", -1)]` supports status-filtered queries.

#### Pagination

```python
return (
    await Order.find(query)
    .sort("-created_at")
    .skip(skip)
    .limit(min(limit, 100))
    .to_list()
)
```

> **Hint Level 1**: Build a query dict starting with `customer.user_id`. Conditionally add `$in` for status filter. Sort by `-created_at`, apply skip/limit, return list.

> **Hint Level 2**: Remember to cap the limit with `min(limit, 100)` to prevent abuse. Use `PydanticObjectId(user_id)` for the nested field query.

<!-- TODO: Implement list_orders -->

#### Verify

```bash
# List all orders for a user
curl -s "http://localhost:8000/orders?skip=0&limit=10" \
  -H "X-User-ID: <user_id>" | python3 -m json.tool

# Filter by status
curl -s "http://localhost:8000/orders?status=pending" \
  -H "X-User-ID: <user_id>" | python3 -m json.tool

# Multiple statuses
curl -s "http://localhost:8000/orders?status=pending,confirmed" \
  -H "X-User-ID: <user_id>" | python3 -m json.tool
```

**Expected**: Array of orders sorted newest first, filtered by status if provided.

---

### Exercise 5.5: Cancel Order - Status Guard

**Concept**: Status validation before state transition, Kafka event emission

#### The Method Signature

```python
async def cancel_order(self, order_id: str, reason: str) -> Order:
```

> **Note the parameters**: Unlike previous tasks, cancel takes a `reason` string (from `CancelOrderRequest.reason`) rather than a `user_id`. The route extracts `X-User-ID` but only for auth - it passes `body.reason` to the service.

#### Algorithm

```
1. Get the order (reuse self.get_order(order_id))
2. Guard: order.status must be PENDING or CONFIRMED
3. Set order.status = OrderStatus.CANCELLED
4. Save
5. Emit Kafka event: EventType.ORDER_CANCELLED
6. Return order
```

#### The Status Guard

```python
if order.status not in (OrderStatus.PENDING, OrderStatus.CONFIRMED):
    raise ValidationError("Only pending or confirmed orders can be cancelled")
```

> **Why only PENDING and CONFIRMED?** Once an order moves to PROCESSING, SHIPPED, or DELIVERED, cancellation requires a different workflow (returns, refunds). The service enforces this business rule.

#### Kafka Event Data

The cancel event only sends minimal data:

```python
self._kafka.emit(
    event_type=EventType.ORDER_CANCELLED,
    entity_id=oid_to_str(order.id),
    data={"order_number": order.order_number},
)
```

> **Contrast with create**: `ORDER_CREATED` sends the full `order.model_dump(mode="json")`. `ORDER_CANCELLED` only sends `order_number`. The MySQL consumer only needs to update the status column.

> **Hint Level 1**: Fetch the order, check the status, update and save. Remember to emit the Kafka event.

> **Hint Level 2**: Use `ValidationError` (not `ValueError`) from `shared.errors`. The `reason` parameter is received but not stored on the Order model in the current implementation - it's available for logging/event data if needed.

<!-- TODO: Implement cancel_order -->

#### Verify

```bash
# Cancel a pending order
curl -s -X POST http://localhost:8000/orders/<order_id>/cancel \
  -H "Content-Type: application/json" \
  -H "X-User-ID: <user_id>" \
  -d '{"order_id": "<order_id>", "reason": "Changed my mind about this purchase"}' \
  | python3 -m json.tool
```

**Expected**: Order returned with `status: "cancelled"`.

```bash
# Try to cancel again (should fail)
curl -s -X POST http://localhost:8000/orders/<order_id>/cancel \
  -H "Content-Type: application/json" \
  -H "X-User-ID: <user_id>" \
  -d '{"order_id": "<order_id>", "reason": "Trying again"}' \
  | python3 -m json.tool
```

**Expected**: 422 error - "Only pending or confirmed orders can be cancelled".

---

## 6. VERIFICATION CHECKLIST

| # | Test | What to Verify |
|---|------|---------------|
| 1 | Create an order with valid user and ACTIVE product | Order created with status `pending`, `OrderCustomer` has user data, `ProductSnapshot` has product data |
| 2 | Create an order with invalid product ID | Returns `NotFoundError` |
| 3 | Create an order with DRAFT/DISCONTINUED product | Returns `ValidationError` - product not available |
| 4 | Create an order with deleted user | Returns `NotFoundError` from `build_order_customer` |
| 5 | Get order by ID | Returns full order with all embedded data |
| 6 | Get nonexistent order | Returns `NotFoundError` |
| 7 | List user orders | Newest first, skip/limit works |
| 8 | List user orders with status filter | Only matching statuses returned |
| 9 | List with skip | Second page returns different orders |
| 10 | Cancel a PENDING order | Status changes to `cancelled` |
| 11 | Cancel a CANCELLED order | Returns `ValidationError` |
| 12 | Cancel with reason | Service accepts reason parameter |
| 13 | Order number format | Matches `ORD-YYYYMMDD-XXXX` pattern |
| 14 | Product snapshot | Snapshot contains product_name, supplier_name, variant info frozen at order time |

---

## 7. ADVANCED CHALLENGES

### Challenge 1: Order Number Collision

The `generate_order_number()` function uses 4 hex chars = 65,536 combinations per day. What happens when two orders get the same number?

**Questions**:
1. What error does MongoDB throw when a duplicate is inserted against the `order_number` index?
2. Design a retry loop that catches `DuplicateKeyError` and regenerates the order number:
   ```python
   for attempt in range(3):
       try:
           order.order_number = generate_order_number()
           await order.insert()
           break
       except DuplicateKeyError:
           if attempt == 2:
               raise ValidationError("Failed to generate unique order number")
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

### Challenge 3: Add Ownership Check to get_order

The current `get_order` has no user_id check - any user can view any order by ID. How would you add ownership scoping?

**Design**:
```python
async def get_order(self, order_id: str, user_id: str = None) -> Order:
    order = ...  # fetch by ID
    if user_id:
        # Anti-enumeration: compound query
        order = await Order.find_one({
            "_id": PydanticObjectId(order_id),
            "customer.user_id": PydanticObjectId(user_id)
        })
    ...
```

**Questions**:
1. Why is a compound `find_one` better than fetch-then-check for anti-enumeration?
2. Which index supports this compound query?
3. What would the route change look like?

### Challenge 4: Full Status State Machine

The current service only implements `cancel_order`. Design additional status transition methods:

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

Implement a generic `update_order_status(order_id, new_status)` method that validates transitions against this map.

### Challenge 5: Per-Item Fulfillment Tracking

Each `OrderItem` has a `fulfillment_status` field. Design an `update_item_fulfillment` method that:
1. Finds an item by `item_id` within the order
2. Updates its `fulfillment_status`, `tracking_number`, `carrier`
3. Sets `shipped_at` / `delivered_at` timestamps
4. Auto-updates the order-level `status` when all items reach SHIPPED or DELIVERED

---

## 8. WHAT'S NEXT?

You've built the **e-commerce transaction engine** - the service that ties together users and products.

**Concepts you mastered**:
- Cross-collection validation chain (User -> Product)
- Product snapshot denormalization (freezing data at purchase time)
- Utility function pattern (delegating snapshot building to helper functions)
- Skip/limit pagination with `$in` status filter
- Nested field queries (`customer.user_id`)
- Status guard for order cancellation
- Order number generation pattern
- Kafka event emission with `EventType` enum

**Your next task**: `TASK_08_ANALYTICS.md` - Aggregation Pipeline Exercises. You'll move beyond `find()` queries and build MongoDB **aggregation pipelines** using `$group`, `$match`, `$project`, `$unwind`, `$lookup`, and `$facet` to generate platform analytics across all the data you've created.
