# TASK 09: Kafka Producer & Consumer - Event-Driven Architecture (Bonus)

## 1. MISSION BRIEFING

Every mutation in the Social Commerce Platform emits a **domain event** through Kafka. When a user registers, an order completes, or a product is published - the backend service **produces** an event, and downstream consumers **react** to it. This is the backbone of the platform's event-driven architecture: the backend writes to MongoDB and emits events, while a separate consumer service subscribes to topics and builds **read-optimized projections** in MySQL for analytics.

Your job is to **implement the core Kafka infrastructure** - the Docker configuration, shared config/topics, the producer, and the consumer. Then study how the domain consumers and DAL layer use these building blocks to process events end-to-end.

### What You Will Implement

- **Docker Compose**: Configure Kafka in KRaft mode (no Zookeeper) and wire environment variables
- **KafkaConfig**: Read environment variables and produce config dicts for producer/consumer
- **Topics & EventTypes**: Define the 5 topics and 18 event type constants
- **KafkaProducer**: Send messages, build event envelopes, singleton pattern
- **KafkaConsumer**: Poll loop, handler registration, signal handling for graceful shutdown

### What You Will Study (Already Implemented)

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
- **Docker installed** - You'll configure the Kafka service
- **TASK_01 (User) should be complete** - So events are actually being produced
- Familiarity with the MongoDB service layer from previous tasks

### Files You Will Implement

| Order | File | What to Implement |
|-------|------|-------------------|
| 1 | `docker-compose.yml` | Kafka service environment + app/mysql-service env vars |
| 2 | `shared/kafka/config.py` | `from_env()`, `to_producer_config()`, `to_consumer_config()` |
| 3 | `shared/kafka/topics.py` | Topic constants, `all()` method, EventType constants |
| 4 | `apps/mongo_backend/kafka/producer.py` | `__init__`, `send()`, `emit()`, `flush()`, singleton |
| 5 | `apps/mysql_server/src/kafka/consumer.py` | `__init__`, `register_handler()`, `subscribe()`, `start()`, `stop()`, signals |

### Files You Should Study (Already Implemented)

| File | Why |
|------|-----|
| `apps/mysql_server/src/consumers/user_consumer.py` | Reference consumer pattern |
| `apps/mysql_server/src/dal/user_dal.py` | UserDAL with SQL upsert operations |
| `apps/mysql_server/src/db/tables.py` | All 7 MySQL table definitions |
| `apps/mysql_server/src/db/connection.py` | Database with connection pool |
| `apps/mysql_server/main.py` | Entry point: init DB, register all handlers, subscribe, start |

---

## 3. THE EVENT ENVELOPE

Every event produced by `KafkaProducer.emit()` has this structure:

```python
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

| Pattern | When Used | Payload Size | Example |
|---------|-----------|-------------|---------|
| **Full model dump** | `*.created`, `*.updated`, lifecycle events | Large - entire document | `product.model_dump(mode="json")` |
| **Minimal fields** | `*.deleted`, `*.cancelled` | Small - just IDs | `{"order_number": ..., "product_id": ...}` |

---

## 4. EXERCISES

### Exercise 1: Configure Kafka in Docker Compose

**File:** `docker-compose.yml`

The `kafka` service is already defined with image, container_name, ports, volumes, and networks. You need to fill in the `environment` block to configure KRaft mode (Kafka without Zookeeper).

#### Expected Configuration

The kafka service environment should contain:

| Environment Variable | Value |
|---------------------|-------|
| `KAFKA_NODE_ID` | `1` |
| `KAFKA_PROCESS_ROLES` | `broker,controller` |
| `KAFKA_CONTROLLER_QUORUM_VOTERS` | `1@kafka:29093` |
| `KAFKA_CONTROLLER_LISTENER_NAMES` | `CONTROLLER` |
| `KAFKA_LISTENERS` | `PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:29093` |
| `KAFKA_ADVERTISED_LISTENERS` | `PLAINTEXT://kafka:9092` |
| `KAFKA_LISTENER_SECURITY_PROTOCOL_MAP` | `CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT` |
| `KAFKA_INTER_BROKER_LISTENER_NAME` | `PLAINTEXT` |
| `CLUSTER_ID` | `MkU3OEVBNTcwNTJENDM2Qk` |
| `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR` | `1` |
| `KAFKA_AUTO_CREATE_TOPICS_ENABLE` | `"true"` |

Also wire these environment variables into the **`app`** and **`mysql-service`** services:

| Service | Variable | Value |
|---------|----------|-------|
| `app` | `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` |
| `app` | `KAFKA_CLIENT_ID` | `backend-service` |
| `mysql-service` | `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` |
| `mysql-service` | `KAFKA_CLIENT_ID` | `mysql-service` |
| `mysql-service` | `KAFKA_GROUP_ID` | `mysql-analytics-service` |

---

### Exercise 2: Implement KafkaConfig

**File:** `shared/kafka/config.py`

The `KafkaConfig` class has two fields already declared: `bootstrap_servers` and `client_id`. Implement the three methods:

#### `from_env(cls, client_id="service")` -> `KafkaConfig`

Read from environment variables:
- `KAFKA_BOOTSTRAP_SERVERS` (default: `"localhost:9092"`)
- `KAFKA_CLIENT_ID` (default: the `client_id` parameter)

#### `to_producer_config(self)` -> `dict`

Return:
```python
{
    "bootstrap.servers": self.bootstrap_servers,
    "client.id": self.client_id,
}
```

#### `to_consumer_config(self, group_id)` -> `dict`

Return:
```python
{
    "bootstrap.servers": self.bootstrap_servers,
    "group.id": group_id,
    "client.id": self.client_id,
    "auto.offset.reset": "earliest",
    "enable.auto.commit": True,
    "auto.commit.interval.ms": 5000,
}
```

> **Note:** The `auto.offset.reset` value can optionally be read from an environment variable `KAFKA_AUTO_OFFSET_RESET` with default `"earliest"`.

---

### Exercise 3: Define Topics & Event Types

**File:** `shared/kafka/topics.py`

#### `Topic` class

Define 5 topic constants and an `all()` class method:

| Constant | Value |
|----------|-------|
| `USER` | `"user"` |
| `ORDER` | `"order"` |
| `POST` | `"post"` |
| `PRODUCT` | `"product"` |
| `SUPPLIER` | `"supplier"` |

`all()` returns a list of all 5 topic strings.

#### `EventType` class

Define 19 event type constants in `"topic.action"` format:

| Constant | Value | Topic |
|----------|-------|-------|
| `USER_CREATED` | `"user.created"` | user |
| `USER_UPDATED` | `"user.updated"` | user |
| `USER_DELETED` | `"user.deleted"` | user |
| `SUPPLIER_CREATED` | `"supplier.created"` | supplier |
| `SUPPLIER_UPDATED` | `"supplier.updated"` | supplier |
| `SUPPLIER_DELETED` | `"supplier.deleted"` | supplier |
| `PRODUCT_CREATED` | `"product.created"` | product |
| `PRODUCT_UPDATED` | `"product.updated"` | product |
| `PRODUCT_PUBLISHED` | `"product.published"` | product |
| `PRODUCT_DISCONTINUED` | `"product.discontinued"` | product |
| `PRODUCT_OUT_OF_STOCK` | `"product.out_of_stock"` | product |
| `PRODUCT_RESTORED` | `"product.restored"` | product |
| `PRODUCT_DELETED` | `"product.deleted"` | product |
| `ORDER_CREATED` | `"order.created"` | order |
| `ORDER_CANCELLED` | `"order.cancelled"` | order |
| `POST_CREATED` | `"post.created"` | post |
| `POST_UPDATED` | `"post.updated"` | post |
| `POST_PUBLISHED` | `"post.published"` | post |
| `POST_DELETED` | `"post.deleted"` | post |

---

### Exercise 4: Implement KafkaProducer

**File:** `apps/mongo_backend/kafka/producer.py`

All imports are already provided. Implement the method bodies:

#### `__init__(self, config=None)`

- Use provided config or create one with `KafkaConfig.from_env()`
- Create a `confluent_kafka.Producer` from `config.to_producer_config()`
- Log initialization

#### `_delivery_callback(self, err, msg)`

- If `err`: log error with the error message
- Else: log debug with topic and partition info (`msg.topic()`, `msg.partition()`)

#### `send(self, topic, value, key=None)`

- Serialize `value` to JSON bytes: `json.dumps(value).encode("utf-8")`
- Encode `key` to UTF-8 bytes if provided, otherwise `None`
- Call `self._producer.produce(topic=..., key=..., value=..., callback=self._delivery_callback)`
- Call `self._producer.poll(0)` to trigger delivery callbacks

#### `flush(self, timeout=10.0)` -> `int`

- Return `self._producer.flush(timeout)`

#### `emit(self, event_type, entity_id, data)`

- Extract topic from event_type: `event_type.split(".")[0]`
- Build the event envelope:
  ```python
  {
      "event_type": event_type,
      "event_id": str(uuid.uuid4()),
      "timestamp": utc_now().isoformat(),
      "entity_id": entity_id,
      "data": data,
  }
  ```
- Call `self.send(topic=topic, key=entity_id, value=event)`

#### `get_kafka_producer()` -> `KafkaProducer` (module-level function)

- Singleton pattern using the module-level `kafka_producer` variable
- Create a new `KafkaProducer()` if `kafka_producer is None`
- Return the instance

---

### Exercise 5: Implement KafkaConsumer

**File:** `apps/mysql_server/src/kafka/consumer.py`

All imports are already provided. Implement the method bodies:

#### `__init__(self, group_id="mysql-analytics-service")`

- Create config with `KafkaConfig.from_env(client_id="mysql-service")`
- Create a `confluent_kafka.Consumer` from `config.to_consumer_config(group_id)`
- Initialize `self._handlers: dict[str, Callable] = {}`
- Initialize `self._running = False`
- Log initialization

#### `register_handler(self, event_type, handler)`

- Store handler in `self._handlers` dict keyed by event_type
- Log registration

#### `subscribe(self, topics=None)`

- Default to `Topic.all()` if topics is None
- Call `self._consumer.subscribe(topics)`
- Log subscription

#### `_process_message(self, msg)`

- JSON decode: `json.loads(msg.value().decode("utf-8"))`
- Extract `event_type` from the decoded value
- If no event_type, log warning and return
- Look up handler in `self._handlers`
- If handler found, call `handler(value)` and log success
- If no handler, log debug
- Handle `json.JSONDecodeError` and general exceptions with error logging

#### `start(self)`

- Set `self._running = True`
- Call `self._setup_signal_handlers()`
- Log start message
- Enter poll loop: `while self._running`
  - `msg = self._consumer.poll(timeout=1.0)`
  - If `msg is None`: continue
  - If `msg.error()`:
    - `KafkaError._PARTITION_EOF`: continue
    - `KafkaError.UNKNOWN_TOPIC_OR_PART`: log warning, continue
    - Other errors: log error, continue
  - Else: call `self._process_message(msg)`
- Wrap in try/except for `KeyboardInterrupt`
- In finally block: call `self.stop()`

#### `stop(self)`

- Set `self._running = False`
- Call `self._consumer.close()`
- Log stop message

#### `_setup_signal_handlers(self)`

- Define a handler function that sets `self._running = False`
- Register it for both `signal.SIGINT` and `signal.SIGTERM`

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

19 event types across 5 topics:

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
| `EventType` | `shared/kafka/topics.py` | 19 event type constants |
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

Before completing this task, verify:

### Implementation
- [ ] **Exercise 1**: Kafka service environment configured in `docker-compose.yml` (KRaft mode)
- [ ] **Exercise 1**: `KAFKA_BOOTSTRAP_SERVERS` and `KAFKA_CLIENT_ID` wired to `app` service
- [ ] **Exercise 1**: `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_CLIENT_ID`, and `KAFKA_GROUP_ID` wired to `mysql-service`
- [ ] **Exercise 2**: `KafkaConfig.from_env()` reads environment variables correctly
- [ ] **Exercise 2**: `to_producer_config()` returns correct dict
- [ ] **Exercise 2**: `to_consumer_config()` returns correct dict with all 6 keys
- [ ] **Exercise 3**: All 5 topic constants defined in `Topic` class
- [ ] **Exercise 3**: `Topic.all()` returns list of all 5 topics
- [ ] **Exercise 3**: All 19 event type constants defined in `EventType` class
- [ ] **Exercise 4**: `KafkaProducer.__init__` creates config and Producer instance
- [ ] **Exercise 4**: `send()` serializes JSON, encodes key, calls produce()
- [ ] **Exercise 4**: `emit()` builds event envelope and extracts topic from event_type
- [ ] **Exercise 4**: `get_kafka_producer()` implements singleton pattern
- [ ] **Exercise 5**: `KafkaConsumer.__init__` creates config, Consumer, handlers dict
- [ ] **Exercise 5**: `register_handler()` stores handlers by event_type
- [ ] **Exercise 5**: `subscribe()` defaults to `Topic.all()`
- [ ] **Exercise 5**: `_process_message()` decodes JSON, routes to handler
- [ ] **Exercise 5**: `start()` implements poll loop with error handling
- [ ] **Exercise 5**: `stop()` and `_setup_signal_handlers()` enable graceful shutdown

### Understanding
- [ ] You understand the event envelope: `{event_type, event_id, timestamp, entity_id, data}`
- [ ] You can explain how `emit()` extracts the topic from event_type (`"order.created"` -> `"order"`)
- [ ] You traced the full lifecycle: API -> Service -> Producer -> Kafka -> Consumer -> DAL -> MySQL
- [ ] You understand `auto.commit.interval.ms = 5000` and its implications for at-least-once delivery
- [ ] You can explain why `entity_id` is used as the partition key (ordering guarantee per entity)
- [ ] You understand the upsert pattern (`ON DUPLICATE KEY UPDATE`) for idempotent processing
