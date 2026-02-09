# TASK 09: Kafka Producer & Consumer - Event-Driven Architecture (Bonus)

## 1. MISSION BRIEFING

Every mutation in the Social Commerce Platform emits a **domain event** through Kafka. When a user registers, an order completes, or a product is published - the backend service **produces** an event, and downstream consumers **react** to it. This is the backbone of the platform's event-driven architecture: the backend writes to MongoDB and emits events, while a separate consumer service subscribes to topics and builds **read-optimized projections** in MySQL for analytics.

The entire pipeline is **already built**. Your job is to study how each piece works, trace events from end to end, and understand the architectural patterns. This task is a study exercise, not a build exercise.

### What You Will Study

- **Producer side**: How `KafkaProducer.emit()` wraps data in an event envelope and sends it to Kafka
- **Consumer side**: How `KafkaConsumer` routes messages to domain-specific handlers
- **5 domain consumers**: `UserConsumer`, `SupplierConsumer`, `ProductConsumer`, `OrderConsumer`, `PostConsumer`
- **5 DAL classes**: How nested MongoDB documents are flattened into relational MySQL tables
- **7 MySQL tables**: The analytics read model that mirrors MongoDB data

### What You Will Learn

| Kafka/Architecture Concept | Where You'll See It |
|---------------------------|-------------------|
| **Event envelope pattern** | Every event has `event_type`, `event_id`, `timestamp`, `entity_id`, `data` |
| **Producer `emit()` method** | `emit(event_type=EventType.X, entity_id=..., data=...)` |
| **Consumer handler registration** | `register_handler(event_type, handler)` routes events to the right function |
| **Consumer group + partition key** | `entity_id` as partition key guarantees ordering per entity |
| **Document-to-relational flattening** | Nested MongoDB documents -> flat MySQL columns |
| **Full model dump vs selective payload** | `created` events send full `model_dump()`, lifecycle events send minimal data |
| **Idempotent upserts** | `INSERT ... ON DUPLICATE KEY UPDATE` for replay safety |
| **Topic extraction from event type** | `"order.created"` -> topic `"order"` (first part before `.`) |

### Architecture Overview

```
+---------------------------------------------------------------+
|                     MONGO BACKEND (Producer)                    |
|                                                                |
|  UserService ----+                                             |
|  OrderService ---+                                             |
|  PostService ----+---> KafkaProducer.emit() ---> Kafka Broker  |
|  ProductService--+         |                       |           |
|  SupplierService-+    event envelope:         5 topics:        |
|                      {event_type,            user, order,      |
|                       event_id,              post, product,    |
|                       timestamp,             supplier          |
|                       entity_id,                               |
|                       data: {...}}                              |
+---------------------------------------------------------------+
                              |
                              v
+---------------------------------------------------------------+
|                     MYSQL SERVER (Consumer)                     |
|                                                                |
|  KafkaConsumer                                                 |
|    +-- register_handler(event_type, handler)                   |
|    +-- subscribe(Topic.all())                                  |
|    +-- start() --> poll loop --> _process_message()             |
|                                       |                        |
|                          +------------+------------+           |
|                          |  Route by event_type    |           |
|                          +------------+------------+           |
|                                       |                        |
|    +-----------+-----------+----------+----------+             |
|    v           v           v          v          v             |
|  UserConsumer  OrderConsumer  PostConsumer  ProductConsumer     |
|                                            SupplierConsumer    |
|                                                                |
|  Each consumer:                                                |
|    1. Extracts data from event envelope                        |
|    2. Flattens nested MongoDB docs to flat columns             |
|    3. Calls DAL methods to INSERT/UPDATE MySQL                 |
+---------------------------------------------------------------+
```

---

## 2. BEFORE YOU START

### Prerequisites
- **Docker with Kafka running** - The platform uses KRaft mode Kafka (no Zookeeper)
- **MySQL running** - The analytics database where consumers write
- **TASK_01 (User) should be complete** - So events are actually being produced
- Familiarity with the MongoDB service layer from previous tasks

### Files You MUST Read (In This Order)

| Order | File | Why |
|-------|------|-----|
| 1 | `shared/kafka/config.py` | KafkaConfig with `to_producer_config()` and `to_consumer_config()` |
| 2 | `shared/kafka/topics.py` | `Topic` enum (5 topics) + `EventType` enum (18 event types) |
| 3 | `apps/mongo_backend/kafka/producer.py` | KafkaProducer with `send()` and `emit()` |
| 4 | `apps/mysql_server/src/kafka/consumer.py` | KafkaConsumer with handler registration and poll loop |
| 5 | `apps/mysql_server/src/consumers/user_consumer.py` | UserConsumer - study this as the reference pattern |
| 6 | `apps/mysql_server/src/dal/user_dal.py` | UserDAL with SQL upsert operations |
| 7 | `apps/mysql_server/src/db/tables.py` | All 7 MySQL table definitions |
| 8 | `apps/mysql_server/src/db/connection.py` | Database with connection pool |
| 9 | `apps/mysql_server/main.py` | Entry point: init DB, register all handlers, subscribe, start |

### How This Differs From Previous Tasks

| Aspect | MongoDB Tasks (01-08) | Kafka Task (09) |
|--------|----------------------|-----------------|
| Data flow | Request -> Service -> MongoDB | Kafka -> Consumer -> MySQL |
| Programming model | Async (Beanie ODM) | Synchronous (confluent_kafka) |
| Data shape | Nested documents | Flat relational rows |
| Trigger | HTTP request | Event message on topic |
| Error handling | Raise AppError | Log + continue (don't block queue) |
| Service location | `apps/mongo_backend/` | `apps/mysql_server/` |
| Your role | Implement service methods | **Study existing implementation** |

---

## 3. THE EVENT ENVELOPE

Every event produced by `KafkaProducer.emit()` has this structure:

```python
# From apps/mongo_backend/kafka/producer.py
event = {
    "event_type": event_type,              # e.g., EventType.ORDER_CREATED -> "order.created"
    "event_id": str(uuid.uuid4()),         # unique ID for idempotency
    "timestamp": utc_now().isoformat(),    # ISO format timestamp
    "entity_id": entity_id,               # e.g., user_id, order_id (also partition key)
    "data": data,                          # the actual payload (varies per event)
}
```

The topic is **extracted from the event_type** string - `"order.created"` goes to the `"order"` topic.

### Two Types of Event Payloads

Understanding this distinction is critical:

| Pattern | When Used | Payload Size | Example |
|---------|-----------|-------------|---------|
| **Full model dump** | `*.created`, `*.updated`, lifecycle events | Large - entire document | `product.model_dump(mode="json")` |
| **Minimal fields** | `*.deleted`, `*.cancelled` | Small - just IDs | `{"order_number": ..., "product_id": ...}` |

```python
# PATTERN 1: Full dump on creation/update (large payload)
self._kafka.emit(
    event_type=EventType.ORDER_CREATED,
    entity_id=oid_to_str(order.id),
    data=order.model_dump(mode="json"),        # <-- entire order document
)

# PATTERN 2: Minimal fields on cancel/delete (small payload)
self._kafka.emit(
    event_type=EventType.ORDER_CANCELLED,
    entity_id=oid_to_str(order.id),
    data={"order_number": order.order_number},  # <-- just what's needed
)
```

---

## 4. EXERCISES

### Exercise 1: Understand the Producer Side

**Goal:** Trace exactly what happens when a backend service emits an event.

**What to study:** `apps/mongo_backend/kafka/producer.py`

#### 1a. Trace `emit()` vs `send()`

Read the `KafkaProducer` class and answer these questions:

```python
# Q1: What does emit() add that send() doesn't?
# (Hint: Look at the event envelope built in emit() - event_id, timestamp, etc.)

# Q2: How does emit() determine which Kafka topic to send to?
# (Hint: Look at how it extracts the topic from event_type)

# Q3: What is the partition key for events? Why does this matter for ordering?
# (Hint: Look at the key= parameter - entity_id ensures all events for the same entity are ordered)

# Q4: Why is there a singleton pattern (get_kafka_producer)?
# (Hint: Think about connection pooling and config consistency)
```

<!-- TODO: Answer these questions by studying the code -->

#### 1b. Map All Emit Calls

Find all the `emit()` calls across the backend services and identify the event types and payload patterns:

| Service File | EventType | Payload |
|-------------|-----------|---------|
| `services/user.py` | `USER_CREATED` | Full `user.model_dump(mode="json")` |
| `services/user.py` | `USER_UPDATED` | Full `user.model_dump(mode="json")` |
| `services/user.py` | `USER_DELETED` | `{"user_id": ...}` |
| `services/user.py` | `SUPPLIER_CREATED` | Full `supplier.model_dump(mode="json")` |
| `services/user.py` | `SUPPLIER_UPDATED` | Full `supplier.model_dump(mode="json")` |
| `services/user.py` | `SUPPLIER_DELETED` | `{"supplier_id": ...}` |
| `services/product.py` | `PRODUCT_CREATED` | Full `product.model_dump(mode="json")` |
| `services/product.py` | `PRODUCT_UPDATED` | Full `product.model_dump(mode="json")` |
| `services/product.py` | `PRODUCT_PUBLISHED` | Full `product.model_dump(mode="json")` |
| `services/product.py` | `PRODUCT_DISCONTINUED` | Full `product.model_dump(mode="json")` |
| `services/product.py` | `PRODUCT_OUT_OF_STOCK` | Full `product.model_dump(mode="json")` |
| `services/product.py` | `PRODUCT_RESTORED` | Full `product.model_dump(mode="json")` |
| `services/product.py` | `PRODUCT_DELETED` | `{"product_id": ...}` |
| `services/order.py` | `ORDER_CREATED` | Full `order.model_dump(mode="json")` |
| `services/order.py` | `ORDER_CANCELLED` | `{"order_number": ...}` |
| `services/post.py` | `POST_CREATED` | Full `post.model_dump(mode="json")` |
| `services/post.py` | `POST_UPDATED` | Full `post.model_dump(mode="json")` |
| `services/post.py` | `POST_PUBLISHED` | Full `post.model_dump(mode="json")` |
| `services/post.py` | `POST_DELETED` | `{"post_id": ...}` |

> **Verify yourself:** Search for `self._kafka.emit(` across all service files and confirm this table.

---

### Exercise 2: Understand the Consumer Side

**Goal:** Trace the full consumer lifecycle from startup to message processing.

**What to study:** `apps/mysql_server/main.py` + `apps/mysql_server/src/kafka/consumer.py`

#### 2a. Trace the Startup Sequence

Read `main.py` and trace the initialization:

```python
# Step 1: Database initialization
db = get_database()
db.connect()         # Creates MySQL connection pool (5 connections)
db.init_tables()     # Creates all 7 MySQL tables

# Step 2: Consumer creation
consumer = KafkaConsumer(group_id="mysql-analytics-service")
# Q: What config does this create? (Look at KafkaConfig.to_consumer_config)
# Q: What does auto.offset.reset = "earliest" mean for a new consumer group?

# Step 3: Handler registration (ALL 5 domain consumers)
domain_consumers = [
    UserConsumer(),
    SupplierConsumer(),
    ProductConsumer(),
    OrderConsumer(),
    PostConsumer(),
]
for dc in domain_consumers:
    for event_type, handler in dc.get_handlers().items():
        consumer.register_handler(event_type, handler)
# Q: How many handlers are registered total? (Count across all consumers)

# Step 4: Topic subscription
consumer.subscribe(Topic.all())
# Q: Topic.all() returns all 5 topics. Why subscribe to all?

# Step 5: Start consuming
consumer.start()
# Q: What happens in the poll loop when a message has no registered handler?
```

<!-- TODO: Answer these questions by studying the code -->

#### 2b. Trace Message Processing

Follow a single event through the consumer:

```
Kafka message arrives (JSON bytes)
    |
    v
consumer.poll(timeout=1.0)              # Blocks up to 1 second
    |
    v
msg.error() check                       # Handle partition EOF, unknown topic
    |
    v
_process_message(msg)
    |
    +-- json.loads(msg.value().decode())  # Deserialize JSON
    |
    +-- value.get("event_type")           # Extract event_type from envelope
    |
    +-- self._handlers.get(event_type)    # Lookup registered handler
    |
    +-- handler(value)                    # Call handler with full event dict
```

> **Key insight:** The consumer doesn't know about MongoDB models. It receives a plain dict and extracts what it needs. The "flattening" happens in the handler, not the consumer infrastructure.

---

### Exercise 3: Study the UserConsumer (Reference Pattern)

**Goal:** Understand the consumer pattern that all domain consumers follow.

**What to study:** `apps/mysql_server/src/consumers/user_consumer.py`

#### The Pattern

Every consumer follows this structure:

```python
class UserConsumer:
    def __init__(self):
        self._dal = UserDAL()                    # 1. DAL handles all SQL

    def _parse_ts(self, ts: str):                # 2. Shared timestamp parser
        ...

    def handle_user_created(self, event):        # 3. One handler per event type
        data = event.get("data", {})             #    Extract data from envelope
        contact = data.get("contact_info", {})   #    Navigate nested MongoDB doc
        profile = data.get("profile", {})        #    Flatten to individual fields
        self._dal.insert_user(                   #    Call DAL to write to MySQL
            user_id=event.get("entity_id"),
            email=contact.get("primary_email"),
            display_name=profile.get("display_name"),
            ...
        )

    def get_handlers(self) -> dict:              # 4. Map event types to handlers
        return {
            EventType.USER_CREATED: self.handle_user_created,
            EventType.USER_UPDATED: self.handle_user_updated,
            EventType.USER_DELETED: self.handle_user_deleted,
        }
```

#### Key Patterns to Note:

1. **One DAL per consumer** - Consumer owns a DAL instance for its domain
2. **`_parse_ts()` helper** - Parses ISO timestamps for MySQL storage
3. **`event.get("data", {})` first** - Always extract the data payload from the envelope
4. **Navigate with `.get()` chains** - Never assume fields exist (MongoDB docs can vary)
5. **`get_handlers()` dict** - Returns `{EventType.X: self.handle_x}` mapping for registration
6. **Handlers are synchronous** - The consumer poll loop is blocking, handlers run inline
7. **Upsert pattern** - Created and updated events often use the same `_handle_*_upsert()` method

---

### Exercise 4: Study the Flattening Pattern Across All Consumers

**Goal:** Understand how each consumer transforms nested MongoDB documents into flat MySQL rows.

#### 4a. User Flattening (`user_consumer.py`)

```
MongoDB User Document           MySQL users table
{                                +-------------------+
  "contact_info": {              | user_id           | <- event["entity_id"]
    "primary_email": "...",      | email             | <- data["contact_info"]["primary_email"]
    "phone": "..."               | phone             | <- data["contact_info"]["phone"]
  },                             | display_name      | <- data["profile"]["display_name"]
  "profile": {                   | avatar            | <- data["profile"]["avatar"]
    "display_name": "...",       | bio               | <- data["profile"]["bio"]
    "avatar": "...",             | deleted_at        | <- data["deleted_at"]
    "bio": "..."                 +-------------------+
  }
}
```

#### 4b. Order Flattening (`order_consumer.py`)

The most complex flattening - one event inserts into TWO tables:

```
MongoDB Order Document           MySQL orders table
{                                +-------------------+
  "order_number": "...",         | order_id          | <- event["entity_id"]
  "customer": {                  | order_number      | <- data["order_number"]
    "user_id": "...",            | customer_user_id  | <- data["customer"]["user_id"]
    "display_name": "...",       | customer_name     | <- data["customer"]["display_name"]
    "email": "..."               | customer_email    | <- data["customer"]["email"]
  },                             | shipping_*        | <- data["shipping_address"]["*"]
  "shipping_address": {...},     | status            | <- data["status"]
  "items": [...]                 +-------------------+
}
                                 MySQL order_items table
  items[0]:                      +-------------------+
  {                              | order_id          | <- event["entity_id"]
    "item_id": "...",            | item_id           | <- item["item_id"]
    "product_snapshot": {        | product_id        | <- item["product_snapshot"]["product_id"]
      "product_id": "...",       | product_name      | <- item["product_snapshot"]["product_name"]
      "product_name": "...",     | supplier_id       | <- item["product_snapshot"]["supplier_id"]
      "supplier_id": "..."       | variant_name      | <- item["product_snapshot"]["variant_name"]
    },                           | quantity          | <- item["quantity"]
    "quantity": 2,               | unit_price_cents  | <- item["unit_price_cents"]
    "unit_price_cents": 1500,    | total_cents       | <- item["total_cents"]
    "total_cents": 3000          +-------------------+
  }
```

#### 4c. Product Flattening (`product_consumer.py`)

Also inserts into TWO tables - products AND product_variants:

```
MongoDB Product Document         MySQL products table
{                                +-------------------+
  "name": "...",                 | product_id        | <- event["entity_id"]
  "category": "...",             | supplier_id       | <- data["supplier_id"]
  "base_price_cents": 1500,      | name              | <- data["name"]
  "supplier_id": "...",          | category          | <- data["category"]
  "status": "active",           | base_price_cents  | <- data["base_price_cents"]
  "metadata": {"base_sku":..},   | status            | <- data["status"]
  "stats": {...},                | stats fields      | <- data["stats"]["*"]
  "variants": {                  +-------------------+
    "Default": {
      "price_cents": 1500,       MySQL product_variants table
      "quantity": 10,            +-------------------+
      "attributes": [...]        | product_id        |
    }                            | variant_key       | <- dict key ("Default")
  }                              | price_cents       | <- variant["price_cents"]
}                                | quantity          | <- variant["quantity"]
                                 +-------------------+
```

> **Note**: Product lifecycle events (`PUBLISHED`, `DISCONTINUED`, `OUT_OF_STOCK`, `RESTORED`) all send the **full model dump** and reuse the same `_handle_product_upsert()` method. This means every lifecycle change fully refreshes the MySQL row.

#### 4d. Post Flattening (`post_consumer.py`)

```
MongoDB Post Document            MySQL posts table
{                                +-------------------+
  "post_type": "text",           | post_id           | <- event["entity_id"]
  "author": {                    | author_user_id    | <- data["author"]["user_id"]
    "user_id": "...",            | author_name       | <- data["author"]["display_name"]
    "display_name": "...",       | post_type         | <- data["post_type"]
    "avatar": "...",             | text_content      | <- data["text_content"]
    "author_type": "user"        | media_json        | <- json.dumps(data["media"])
  },                             | link_url          | <- data["link_preview"]["url"]
  "text_content": "...",         | link_title        | <- data["link_preview"]["title"]
  "media": [...],                | stats fields      | <- data["stats"]["*"]
  "link_preview": {...},         | published_at      | <- data["published_at"]
  "stats": {...}                 | deleted_at        | <- data["deleted_at"]
}                                +-------------------+
```

#### 4e. Supplier Flattening (`supplier_consumer.py`)

```
MongoDB Supplier Document        MySQL suppliers table
{                                +-------------------+
  "contact_info": {              | supplier_id       | <- event["entity_id"]
    "primary_email": "...",      | email             | <- data["contact_info"]["primary_email"]
    "primary_phone": "...",      | primary_phone     | <- data["contact_info"]["primary_phone"]
    "contact_person_*": "..."    | contact_person_*  | <- data["contact_info"]["*"]
  },                             | legal_name        | <- data["company_info"]["legal_name"]
  "company_info": {              | dba_name          | <- data["company_info"]["dba_name"]
    "legal_name": "...",         | address fields    | <- data["company_info"]["business_address"]["*"]
    "business_address": {        | support_*         | <- data["business_info"]["*"]
      "street": "...",           | social_urls       | <- data["business_info"]["social_urls"]
      "city": "...",             +-------------------+
      ...
    }
  },
  "business_info": {...}
}
```

---

### Exercise 5: Study the DAL Layer

**Goal:** Understand the SQL patterns used for idempotent event processing.

**What to study:** All files in `apps/mysql_server/src/dal/`

#### The Upsert Pattern

Every DAL uses `INSERT ... ON DUPLICATE KEY UPDATE` for idempotency:

```sql
INSERT INTO users (user_id, email, display_name, ..., event_id, event_timestamp)
VALUES (%s, %s, %s, ..., %s, %s)
ON DUPLICATE KEY UPDATE
  email = VALUES(email),
  display_name = VALUES(display_name),
  ...,
  event_id = VALUES(event_id),
  event_timestamp = VALUES(event_timestamp)
```

> **Why upsert?** If a Kafka message is delivered twice (at-least-once delivery), the second insert becomes an update instead of failing. The `event_id` and `event_timestamp` columns provide an audit trail of the last processed event.

#### Delete Patterns

| Domain | Delete Type | SQL |
|--------|-----------|-----|
| User | Soft delete | `UPDATE users SET deleted_at = NOW(6) WHERE user_id = %s` |
| Post | Soft delete | `UPDATE posts SET deleted_at = NOW(6) WHERE post_id = %s` |
| Supplier | Hard delete | `DELETE FROM suppliers WHERE supplier_id = %s` |
| Product | Hard delete | `DELETE FROM products WHERE product_id = %s` (CASCADE to variants) |
| Order | Status update | `UPDATE orders SET status = 'cancelled' WHERE order_number = %s` |

#### The Replace Pattern (Product Variants)

Product variants use a transactional DELETE + INSERT:

```python
def replace_variants(self, product_id, variants):
    conn = self._db.get_connection()
    cursor = conn.cursor()
    # Step 1: Delete ALL existing variants for this product
    cursor.execute("DELETE FROM product_variants WHERE product_id = %s", (product_id,))
    # Step 2: Insert all current variants
    for v in variants:
        cursor.execute("INSERT INTO product_variants (...) VALUES (%s, ...)", ...)
    conn.commit()
```

> **Why replace instead of upsert?** Variants can be added or removed. An upsert wouldn't delete variants that no longer exist. The replace pattern guarantees MySQL always matches the current state.

---

### Exercise 6: Study the MySQL Schema

**Goal:** Understand the analytics read model.

**What to study:** `apps/mysql_server/src/db/tables.py`

#### The 7 Tables

| Table | Primary Key | Notable Columns | Indexes |
|-------|------------|----------------|---------|
| `users` | `user_id` (VARCHAR 24) | email, display_name, deleted_at, event_id | email, created_at |
| `suppliers` | `supplier_id` (VARCHAR 24) | email, legal_name, address fields, social_urls | email, legal_name, country/state/city |
| `products` | `product_id` (VARCHAR 24) | supplier_id, name, category, status, stats | supplier_id, category, status, created_at |
| `product_variants` | `id` (auto-increment) | product_id (FK CASCADE), variant_key, price, quantity | UNIQUE(product_id, variant_key) |
| `orders` | `order_id` (VARCHAR 24) | order_number (UNIQUE), customer_*, shipping_*, status | customer_user_id, status, created_at |
| `order_items` | `id` (auto-increment) | order_id (FK CASCADE), item_id, product snapshot fields | UNIQUE(order_id, item_id) |
| `posts` | `post_id` (VARCHAR 24) | author_*, post_type, media_json, link_*, stats, deleted_at | author_user_id, post_type, published_at |

#### Common Columns Across All Tables

Every table includes:
- `event_id` (VARCHAR 36) - UUID of the triggering Kafka event
- `event_timestamp` (DATETIME 6) - When the event was produced
- `created_at`, `updated_at` (DATETIME 6) - Record timestamps

> **Questions to answer:**
> 1. Why is `order_number` UNIQUE in the orders table?
> 2. Why do `product_variants` and `order_items` use CASCADE DELETE on their foreign keys?
> 3. Why are `user_id` columns VARCHAR(24) instead of auto-increment integers?

---

## 5. HOW THE PIECES FIT: COMPLETE EVENT LIFECYCLE

Trace one complete event from API call to MySQL row:

```
1. USER CALLS API
   POST /orders  (with X-User-ID header)

2. ROUTE LAYER
   routes/order.py -> calls OrderService.create_order()

3. SERVICE LAYER (apps/mongo_backend/services/order.py)
   +-- Validates user (build_order_customer)
   +-- Validates products (ACTIVE status)
   +-- Builds Order document (embedded types)
   +-- order.insert()  ->  MongoDB
   +-- self._kafka.emit(                          <- PRODUCES EVENT
           event_type=EventType.ORDER_CREATED,
           entity_id=oid_to_str(order.id),
           data=order.model_dump(mode="json"),
       )

4. KAFKA PRODUCER (apps/mongo_backend/kafka/producer.py)
   emit() builds envelope:
   {
       "event_type": "order.created",
       "event_id": "uuid-...",
       "timestamp": "2025-...",
       "entity_id": "order-id-...",
       "data": { ...full order document... }
   }
   -> extracts topic "order" from event_type
   -> producer.send(topic="order", key="order-id-...", value=envelope)
   -> confluent_kafka.Producer.produce() -> Kafka broker

5. KAFKA BROKER
   Message stored in "order" topic, partition determined by hash(key)

6. KAFKA CONSUMER (apps/mysql_server/src/kafka/consumer.py)
   consumer.poll(timeout=1.0) -> receives message
   -> _process_message(msg)
   -> json.loads(msg.value())
   -> handlers["order.created"](event)

7. ORDER CONSUMER (apps/mysql_server/src/consumers/order_consumer.py)
   handle_order_created(event):
   +-- data = event["data"]
   +-- customer = data["customer"]
   +-- shipping = data["shipping_address"]
   +-- dal.insert_order(order_id, order_number, customer fields, shipping fields, ...)
   +-- items = [flatten each item with product_snapshot data]
   +-- dal.insert_order_items(order_id, items)

8. ORDER DAL -> MySQL
   INSERT INTO orders (...) VALUES (...) ON DUPLICATE KEY UPDATE ...
   INSERT INTO order_items (...) VALUES (...) ON DUPLICATE KEY UPDATE ...
```

---

## 6. COMPLETE EVENT REFERENCE

### EventType Enum (`shared/kafka/topics.py`)

18 event types across 5 topics:

#### User Topic (`Topic.USER`)
| EventType | Consumer Handler | DAL Method | MySQL Action |
|-----------|-----------------|-----------|-------------|
| `USER_CREATED` | `handle_user_created` | `insert_user` (upsert) | INSERT/UPDATE `users` |
| `USER_UPDATED` | `handle_user_updated` | `insert_user` (upsert) | INSERT/UPDATE `users` |
| `USER_DELETED` | `handle_user_deleted` | `soft_delete_user` | UPDATE `users` SET `deleted_at` |

#### Supplier Topic (`Topic.SUPPLIER`)
| EventType | Consumer Handler | DAL Method | MySQL Action |
|-----------|-----------------|-----------|-------------|
| `SUPPLIER_CREATED` | `handle_supplier_created` | `insert_supplier` (upsert) | INSERT/UPDATE `suppliers` |
| `SUPPLIER_UPDATED` | `handle_supplier_updated` | `insert_supplier` (upsert) | INSERT/UPDATE `suppliers` |
| `SUPPLIER_DELETED` | `handle_supplier_deleted` | `delete_supplier` | DELETE FROM `suppliers` |

#### Product Topic (`Topic.PRODUCT`)
| EventType | Consumer Handler | DAL Method | MySQL Action |
|-----------|-----------------|-----------|-------------|
| `PRODUCT_CREATED` | `handle_product_created` | `upsert_product` + `replace_variants` | INSERT/UPDATE `products` + replace `product_variants` |
| `PRODUCT_UPDATED` | `handle_product_updated` | `upsert_product` + `replace_variants` | INSERT/UPDATE `products` + replace `product_variants` |
| `PRODUCT_PUBLISHED` | `handle_product_published` | `upsert_product` + `replace_variants` | INSERT/UPDATE `products` + replace `product_variants` |
| `PRODUCT_DISCONTINUED` | `handle_product_discontinued` | `upsert_product` + `replace_variants` | INSERT/UPDATE `products` + replace `product_variants` |
| `PRODUCT_OUT_OF_STOCK` | `handle_product_out_of_stock` | `upsert_product` + `replace_variants` | INSERT/UPDATE `products` + replace `product_variants` |
| `PRODUCT_RESTORED` | `handle_product_restored` | `upsert_product` + `replace_variants` | INSERT/UPDATE `products` + replace `product_variants` |
| `PRODUCT_DELETED` | `handle_product_deleted` | `delete_product` | DELETE FROM `products` (CASCADE to variants) |

#### Order Topic (`Topic.ORDER`)
| EventType | Consumer Handler | DAL Method | MySQL Action |
|-----------|-----------------|-----------|-------------|
| `ORDER_CREATED` | `handle_order_created` | `insert_order` + `insert_order_items` | INSERT/UPDATE `orders` + INSERT/UPDATE `order_items` |
| `ORDER_CANCELLED` | `handle_order_cancelled` | `cancel_order` | UPDATE `orders` SET status='cancelled' |

#### Post Topic (`Topic.POST`)
| EventType | Consumer Handler | DAL Method | MySQL Action |
|-----------|-----------------|-----------|-------------|
| `POST_CREATED` | `handle_post_created` | `upsert_post` | INSERT/UPDATE `posts` |
| `POST_UPDATED` | `handle_post_updated` | `upsert_post` | INSERT/UPDATE `posts` |
| `POST_PUBLISHED` | `handle_post_published` | `upsert_post` | INSERT/UPDATE `posts` |
| `POST_DELETED` | `handle_post_deleted` | `soft_delete_post` | UPDATE `posts` SET `deleted_at` |

---

## 7. ADVANCED CHALLENGES

### Challenge 1: Idempotent Event Processing

**Problem:** If the consumer crashes after processing but before committing the Kafka offset, the event will be redelivered. The current implementation handles this via upserts (`ON DUPLICATE KEY UPDATE`).

**Study:**
1. Find the `auto.commit.interval.ms` setting in `KafkaConfig.to_consumer_config()`. What's the window where duplicate processing could occur?
2. The `event_id` column stores the UUID of the last processed event. How could you use this to detect duplicate processing?
3. Design a more robust approach using a `processed_events` table:
   ```sql
   CREATE TABLE processed_events (
       event_id VARCHAR(36) PRIMARY KEY,
       event_type VARCHAR(100),
       processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   ```

### Challenge 2: Dead Letter Queue (DLQ)

**Problem:** What happens when a handler throws an exception? Currently, the consumer logs the error and continues - the event is lost (auto-commit advances the offset).

**Design** a DLQ pattern:

```python
# In _process_message(), instead of just logging:
except Exception as e:
    logger.error(f"Error processing message: {e}")
    # Send to a DLQ topic for later retry/investigation
    dlq_producer.send(
        topic=f"dlq.{msg.topic()}",
        value={
            "original_event": value,
            "error": str(e),
            "failed_at": utc_now().isoformat(),
            "retry_count": 0,
        }
    )
```

**Questions:**
1. The DLQ requires a KafkaProducer inside the consumer service. How would you initialize it?
2. Should failed events be retried automatically? What are the risks?
3. What monitoring would you add to detect DLQ accumulation?

### Challenge 3: Consumer Lag Monitoring

**Problem:** How do you know if your consumer is falling behind?

```bash
# Using kafka-consumer-groups CLI tool:
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
    --group mysql-analytics-service \
    --describe

# Shows: TOPIC, PARTITION, CURRENT-OFFSET, LOG-END-OFFSET, LAG
```

**Questions:**
1. What lag is acceptable for an analytics replica? (Hint: minutes of delay is usually fine)
2. What should happen when lag exceeds a threshold?
3. How would you expose lag as a health check endpoint?

### Challenge 4: Add a New Event Type

Design what it would take to add a new event type (e.g., `ORDER_SHIPPED`):

1. **Producer side**: Add `ORDER_SHIPPED` to the `EventType` enum, add `emit()` call in the service
2. **Consumer side**: Add handler in `OrderConsumer`, update DAL with a new method
3. **Schema side**: Does the `orders` table need changes? (Hint: probably just a status update)

Trace through all the files that would need to change.

---

## 8. KEY CONCEPTS SUMMARY

### Producer Side

| Component | File | Purpose |
|-----------|------|---------|
| `KafkaConfig` | `shared/kafka/config.py` | Connection settings from env vars |
| `Topic` | `shared/kafka/topics.py` | 5 topic constants: USER, ORDER, POST, PRODUCT, SUPPLIER |
| `EventType` | `shared/kafka/topics.py` | 18 event type constants |
| `KafkaProducer` | `apps/mongo_backend/kafka/producer.py` | `send()` for raw, `emit()` for enveloped |
| `get_kafka_producer()` | Same file | Singleton access pattern |

### Consumer Side

| Component | File | Purpose |
|-----------|------|---------|
| `KafkaConsumer` | `apps/mysql_server/src/kafka/consumer.py` | Poll loop + handler routing |
| `UserConsumer` | `apps/mysql_server/src/consumers/user_consumer.py` | Handles USER_CREATED/UPDATED/DELETED |
| `SupplierConsumer` | `apps/mysql_server/src/consumers/supplier_consumer.py` | Handles SUPPLIER_CREATED/UPDATED/DELETED |
| `ProductConsumer` | `apps/mysql_server/src/consumers/product_consumer.py` | Handles 7 product lifecycle events |
| `OrderConsumer` | `apps/mysql_server/src/consumers/order_consumer.py` | Handles ORDER_CREATED/CANCELLED |
| `PostConsumer` | `apps/mysql_server/src/consumers/post_consumer.py` | Handles POST_CREATED/UPDATED/PUBLISHED/DELETED |
| `main.py` | `apps/mysql_server/main.py` | Wires all consumers + subscribes to all topics |

### Data Access Layer

| Component | File | Purpose |
|-----------|------|---------|
| `UserDAL` | `apps/mysql_server/src/dal/user_dal.py` | `insert_user` (upsert), `soft_delete_user` |
| `SupplierDAL` | `apps/mysql_server/src/dal/supplier_dal.py` | `insert_supplier` (upsert), `delete_supplier` |
| `ProductDAL` | `apps/mysql_server/src/dal/product_dal.py` | `upsert_product`, `replace_variants`, `delete_product` |
| `OrderDAL` | `apps/mysql_server/src/dal/order_dal.py` | `insert_order`, `insert_order_items`, `cancel_order` |
| `PostDAL` | `apps/mysql_server/src/dal/post_dal.py` | `upsert_post`, `soft_delete_post` |

---

## 9. CHECKLIST

Before completing this task, verify you can answer:

- [ ] You understand the event envelope: `{event_type, event_id, timestamp, entity_id, data}`
- [ ] You can explain how `emit()` extracts the topic from event_type (`"order.created"` -> `"order"`)
- [ ] You traced the full lifecycle: API -> Service -> Producer -> Kafka -> Consumer -> DAL -> MySQL
- [ ] You understand `auto.commit.interval.ms = 5000` and its implications for at-least-once delivery
- [ ] You can explain why `entity_id` is used as the partition key (ordering guarantee per entity)
- [ ] You understand the upsert pattern (`ON DUPLICATE KEY UPDATE`) for idempotent processing
- [ ] You can identify which events send full model dumps vs minimal payloads
- [ ] You understand the variant replace pattern (DELETE + INSERT) vs standard upsert
- [ ] You know the difference between soft delete (users, posts) and hard delete (suppliers, products)
- [ ] You can trace how a nested MongoDB document maps to flat MySQL columns for each domain
