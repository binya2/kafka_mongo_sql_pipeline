# TASK 00: MySQL Analytics Service - Environment Setup & Architecture Primer

## 1. WELCOME

You are building the **MySQL Analytics Service** - a Kafka consumer that subscribes to domain events, flattens nested MongoDB documents into relational rows, and persists them to MySQL for analytics queries.

This track can be completed **independently of (or in parallel with) the MongoDB tasks**. The MongoDB backend, Kafka broker, and all shared models are already in place. As events flow through Kafka - whether from seed scripts, the REST API, or completed MongoDB services - your MySQL consumer will catch them and store the data.

The codebase is **already scaffolded** for you:
- **Connection pool** (EMPTY SHELL) - `src/db/connection.py` has class structure only
- **Kafka consumer framework** (complete) - `src/kafka/consumer.py` handles message polling and routing
- **Bootstrap** (complete) - `main.py` wires everything together
- **Tables** (EMPTY) - `src/db/tables.py` has an empty `TABLE_DEFINITIONS` list
- **DALs** (EMPTY SHELLS) - `src/dal/*_dal.py` files have class definitions only
- **Consumers** (EMPTY SHELLS) - `src/consumers/*_consumer.py` files have class definitions only

Your **first task** is to implement the connection pool in `connection.py`. Then you implement **three layers per domain**: DDL (CREATE TABLE), DAL (raw SQL), and Consumer (event handlers).

```
Kafka Event (JSON)
    |
    v
+-------------------+     +------------------+     +------------------+
|    Consumer       |---->|    DAL            |---->|    MySQL         |
| (flatten event)   |     | (raw SQL)        |     | (analytics DB)  |
| src/consumers/    |     | src/dal/          |     | src/db/tables.py |
+-------------------+     +------------------+     +------------------+
   YOU WRITE THIS            YOU WRITE THIS           YOU WRITE THIS
```

> **Rule:** You never touch `consumer.py` or `main.py`. You implement `connection.py` once (TASK_00), then write CREATE TABLE statements, DAL methods, and consumer event handlers.

---

## 2. PREREQUISITES

### Required: All 5 Docker Containers Running

| Container | Image | Port | Purpose |
|-----------|-------|------|---------|
| `social_commerce_mongodb` | `mongo:latest` | **27017** | MongoDB (primary data store) |
| `social_commerce_kafka` | `confluentinc/cp-kafka:7.6.0` | **9092** | Kafka broker (event bus) |
| `social_commerce_app` | Python 3.11 + FastAPI | **8000** | MongoDB backend (emits events) |
| `social_commerce_mysql` | `mysql:8.0` | **3306** | MySQL (analytics database) |
| `social_commerce_mysql_service` | Python 3.11 | - | MySQL consumer (your code runs here) |

```bash
# Verify all containers are running
docker compose ps

# All 5 should show "running" or "Up"
```

### Parallel With MongoDB Tasks

These MySQL tasks do **not** require the MongoDB tasks to be completed first. The two tracks are independent:

- **MongoDB tasks** teach you to write Beanie ODM queries in the service layer
- **MySQL tasks** teach you to write DDL, raw SQL, and Kafka consumers

Events can be generated via seed scripts (`scripts/seed.py`, `scripts/generate_products.py`, `scripts/generate_posts.py`) or through the REST API. As long as the containers are running, events flow through Kafka regardless of which track you're working on.

---

## 3. THE BIG PICTURE: EVENT-DRIVEN ARCHITECTURE

### Why Two Databases?

MongoDB stores the **operational data** - the live, nested, denormalized documents that power the REST API. But when the data team wants to answer questions like:

- "How many users signed up last week?"
- "What's the average order value by shipping country?"
- "Which suppliers have the most products?"

They need **relational data** - flat rows with typed columns, joinable tables, and SQL aggregation. That's what you're building.

### The Event Flow

```
                     MongoDB Backend (port 8000)
                     ===========================
   HTTP Request ---> Route ---> Service ---> MongoDB
                                   |
                                   | emit Kafka event
                                   v
                            +-------------+
                            |   Kafka     |
                            |   Broker    |
                            | (port 9092) |
                            +-------------+
                                   |
                          consume events
                                   |
                                   v
                     MySQL Analytics Service
                     =======================
   Kafka Message ---> Consumer ---> DAL ---> MySQL
                     (flatten)    (SQL)    (analytics DB)
```

### What Happens When You Create a User

1. You send `POST /users` to the MongoDB backend
2. The UserService creates the MongoDB document
3. The UserService calls `self._kafka.emit(EventType.USER_CREATED, ...)`
4. A JSON message appears on the `user` Kafka topic
5. The MySQL consumer polls the topic, sees the message
6. The UserConsumer's `handle_user_created()` fires
7. It flattens the nested document (contact_info, profile) into flat parameters
8. It calls `UserDAL.insert_user(...)` with the flat values
9. The DAL executes `INSERT INTO users ... ON DUPLICATE KEY UPDATE ...`
10. The row appears in the MySQL `users` table

### The Kafka Event Envelope

Every Kafka message has the same structure:

```json
{
  "event_type": "user.created",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "entity_id": "507f1f77bcf86cd799439011",
  "timestamp": "2025-01-15T10:30:00Z",
  "data": {
    // The full MongoDB document (nested)
  }
}
```

| Field | Type | Purpose |
|-------|------|---------|
| `event_type` | `str` | Routes to the correct handler (e.g., `"user.created"`) |
| `event_id` | `str` (UUID) | Unique event ID for deduplication |
| `entity_id` | `str` (ObjectId) | The MongoDB document's `_id` |
| `timestamp` | `str` (ISO 8601) | When the event was emitted |
| `data` | `dict` | The full document payload (nested MongoDB structure) |

---

## 4. THE THREE LAYERS YOU IMPLEMENT

For each domain (User, Supplier, Product, Post, Order), you implement three files:

### Layer 1: DDL - CREATE TABLE (`src/db/tables.py`)

You write SQL `CREATE TABLE IF NOT EXISTS` statements. These define the schema for the flattened analytics tables.

```python
# src/db/tables.py
TABLE_DEFINITIONS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id         VARCHAR(24) PRIMARY KEY,
        email           VARCHAR(255) NOT NULL,
        -- ... more columns
    )
    """,
    # ... more tables
]
```

**Key decision:** How to flatten nested MongoDB documents into flat columns. For example:
- `user.contact_info.primary_email` becomes column `email`
- `user.profile.display_name` becomes column `display_name`
- `user.profile.avatar` becomes column `avatar`

### Layer 2: DAL - Data Access Layer (`src/dal/*_dal.py`)

You write raw SQL methods that insert, update, and delete rows. Each method:
1. Gets a connection from the pool: `conn = get_database().get_connection()`
2. Creates a cursor: `cursor = conn.cursor()`
3. Executes parameterized SQL: `cursor.execute("INSERT ...", (param1, param2, ...))`
4. Closes cursor and connection in a `try/finally` block

```python
# Pattern for every DAL method:
def some_method(self, param1, param2, ...):
    conn = get_database().get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SQL HERE", (param1, param2, ...))
        cursor.close()
    finally:
        conn.close()
```

**Key pattern:** `INSERT ... ON DUPLICATE KEY UPDATE` for idempotent upserts. If the same event is processed twice (Kafka at-least-once delivery), the row gets updated instead of causing a duplicate key error.

### Layer 3: Consumer - Event Handlers (`src/consumers/*_consumer.py`)

You write handler methods that:
1. Receive a Kafka event dict
2. Extract nested fields from `event["data"]`
3. Parse timestamps
4. Call the appropriate DAL method with flat parameters

```python
# Pattern for every consumer handler:
def handle_entity_created(self, event: dict):
    data = event.get("data", {})
    nested_obj = data.get("nested_field", {})

    self._dal.insert_entity(
        entity_id=event.get("entity_id"),
        flat_field=nested_obj.get("deep_field"),
        created_at=self._parse_ts(data.get("created_at")),
        event_id=event.get("event_id"),
        event_timestamp=self._parse_ts(event.get("timestamp")),
    )
```

---

## 5. FILES YOU MUST READ BEFORE CODING

### Infrastructure Files (read once, reference as needed)

| File | Lines | What It Does |
|------|-------|-------------|
| `apps/mysql_server/main.py` | 52 | Bootstrap: connects DB, creates consumer, registers handlers, starts polling |
| `apps/mysql_server/src/db/connection.py` | 38 | Connection pool (stubbed): you implement `connect()`, `init_tables()`, `get_connection()` |
| `apps/mysql_server/src/kafka/consumer.py` | 104 | Kafka framework: poll loop, JSON parsing, handler dispatch, signal handling |
| `shared/kafka/topics.py` | 55 | Event catalog: 5 Topics + 19 EventTypes |

### Read `main.py` First

```
apps/mysql_server/main.py
```

This is 52 lines. Read every line. It shows you:
- How the database pool is initialized
- How `init_tables()` is called (executes your DDL from `TABLE_DEFINITIONS`)
- How domain consumers are instantiated and registered
- How the Kafka consumer subscribes and starts

### Read `connection.py` Second

```
apps/mysql_server/src/db/connection.py
```

This file is **stubbed out** - you will implement it. It has:
- The `Database` class with `self._pool = None`
- Three empty methods: `connect()`, `init_tables()`, `get_connection()`
- `get_database()` singleton accessor (already complete)

### Read `consumer.py` Third

```
apps/mysql_server/src/kafka/consumer.py
```

This shows you:
- How `register_handler(event_type, handler)` maps event strings to your methods
- How `_process_message()` extracts `event_type` from JSON and dispatches
- The poll loop that continuously reads from Kafka

### Read `topics.py` Fourth

```
shared/kafka/topics.py
```

This is the complete event catalog:

| Topic | Event Types |
|-------|------------|
| `user` | `user.created`, `user.updated`, `user.deleted` |
| `supplier` | `supplier.created`, `supplier.updated`, `supplier.deleted` |
| `product` | `product.created`, `product.updated`, `product.published`, `product.discontinued`, `product.out_of_stock`, `product.restored`, `product.deleted` |
| `order` | `order.created`, `order.cancelled` |
| `post` | `post.created`, `post.updated`, `post.published`, `post.deleted` |

---

## 6. THE FLATTENING CONCEPT

The central challenge of every MySQL task is **flattening** - transforming nested MongoDB documents into flat relational rows.

### Example: User Document -> User Row

**MongoDB document (nested):**
```json
{
  "_id": "507f1f77bcf86cd799439011",
  "contact_info": {
    "primary_email": "jane@example.com",
    "phone": "+1234567890"
  },
  "profile": {
    "display_name": "Jane Smith",
    "avatar": "https://cdn.example.com/default.jpg",
    "bio": "Hello world"
  },
  "version": 1,
  "deleted_at": null,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

**MySQL row (flat):**

| Column | Value | Source Path |
|--------|-------|-------------|
| `user_id` | `507f1f77bcf86cd799439011` | `_id` (via `entity_id`) |
| `email` | `jane@example.com` | `contact_info.primary_email` |
| `phone` | `+1234567890` | `contact_info.phone` |
| `display_name` | `Jane Smith` | `profile.display_name` |
| `avatar` | `https://cdn.example.com/default.jpg` | `profile.avatar` |
| `bio` | `Hello world` | `profile.bio` |
| `version` | `1` | `version` |
| `deleted_at` | `NULL` | `deleted_at` |
| `created_at` | `2025-01-15 10:30:00` | `created_at` |
| `updated_at` | `2025-01-15 10:30:00` | `updated_at` |

The consumer does this flattening: it extracts `data["contact_info"]["primary_email"]` and passes it as the `email` parameter to the DAL method, which writes it to the `email` column.

### Type Conversions

| MongoDB Type | MySQL Type | Notes |
|-------------|-----------|-------|
| `ObjectId` | `VARCHAR(24)` | 24-char hex string |
| `str` | `VARCHAR(n)` or `TEXT` | Choose length based on content |
| `int` | `INT` | Direct mapping |
| `float` | `DOUBLE` | For engagement rates, dimensions |
| `datetime` (ISO string) | `DATETIME(6)` | Microsecond precision, parse with `fromisoformat()` |
| `list` / `dict` | `JSON` | Serialize with `json.dumps()` when schema is variable |
| `bool` | Not used | Status strings used instead |
| `None` | `NULL` | Direct mapping |

---

## 7. VERIFICATION WORKFLOW

Unlike MongoDB tasks where you verify via HTTP response, MySQL tasks use a **three-step verification pattern**:

### Step 1: Trigger an Event

Use curl or Swagger to hit the MongoDB backend. This creates a document and emits a Kafka event.

```bash
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "Pass123!", "display_name": "Test User"}'
```

### Step 2: Check Consumer Logs

See if the MySQL analytics service received and processed the event.

```bash
docker compose logs mysql-service | grep USER_CREATED
# Expected: [USER_CREATED] 507f1f77bcf86cd799439011
```

### Step 3: Query MySQL

Connect to MySQL and verify the data landed correctly.

```bash
# Connect to MySQL
docker compose exec mysql mysql -u analytics -panalytics123 analytics

# Query the table
SELECT * FROM users WHERE email = 'test@example.com'\G
```

> The `\G` suffix formats output vertically (one field per line), which is much easier to read for wide tables.

### MySQL Shell Quick Reference

```bash
# Connect
docker compose exec mysql mysql -u analytics -panalytics123 analytics

# Useful commands inside the MySQL shell:
SHOW TABLES;                          -- List all tables
DESCRIBE users;                       -- Show table structure
SHOW CREATE TABLE users\G             -- Show full DDL
SELECT COUNT(*) FROM users;           -- Count rows
SELECT * FROM users LIMIT 5\G         -- Sample data
```

---

## 8. COMMON PATTERNS YOU'LL USE

### Pattern 1: INSERT ... ON DUPLICATE KEY UPDATE (Idempotent Upsert)

```sql
INSERT INTO users (user_id, email, display_name, created_at, updated_at)
VALUES (%s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    email=VALUES(email),
    display_name=VALUES(display_name),
    updated_at=VALUES(updated_at)
```

**Why:** Kafka guarantees at-least-once delivery. The same event may arrive twice. `ON DUPLICATE KEY UPDATE` makes this safe - if the `user_id` already exists, it updates instead of failing.

**Note:** `created_at` is intentionally excluded from the UPDATE clause - it should only be set on the first insert.

### Pattern 2: Hard DELETE

```sql
DELETE FROM suppliers WHERE supplier_id = %s
```

**When:** For entities that are permanently removed (Supplier, Product).

### Pattern 3: Soft Delete via UPDATE

```sql
UPDATE users SET deleted_at = NOW(6), event_id = %s WHERE user_id = %s
```

**When:** For entities that are logically deleted but preserved (User, Post).

### Pattern 4: Replace Pattern (DELETE + INSERT)

```sql
DELETE FROM product_variants WHERE product_id = %s;

INSERT INTO product_variants (product_id, variant_key, ...) VALUES (%s, %s, ...);
INSERT INTO product_variants (product_id, variant_key, ...) VALUES (%s, %s, ...);
-- one INSERT per variant
```

**When:** For child tables where the full set is replaced on every update (variants).

### Pattern 5: Timestamp Parsing

```python
def _parse_ts(self, ts):
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))
```

Every consumer needs this helper to convert ISO 8601 strings (from Kafka events) to Python `datetime` objects (for MySQL `DATETIME(6)` columns).

---

## 9. TASK PROGRESSION

### The Learning Path

```
TASK_01: User (Easy)
    |     DDL: 12 columns, 2 indexes
    |     DAL: INSERT ON DUPLICATE KEY UPDATE + soft delete UPDATE
    |     Consumer: 3 handlers, 2-source flattening (contact_info + profile)
    |
    v
TASK_02: Supplier (Medium)
    |     DDL: 26 columns, 3 indexes (including composite)
    |     DAL: 26-param INSERT + hard DELETE
    |     Consumer: 3 handlers, 4-source flattening
    |
    +---------------------------+
    v                           v
TASK_04: Product (Hard)     TASK_05: Post (Medium-High)
    |   DDL: 2 tables!          |   DDL: JSON columns, DOUBLE type
    |   (parent + child FK)     |   DAL: 26-param upsert + soft delete
    |   DAL: upsert + replace   |   Consumer: json.dumps for media
    |   + delete                |
    |                           |
    +-------------+-------------+
                  v
TASK_07: Order (Very High)
          DDL: 2 tables (orders + order_items)
          DAL: Selective upsert + batch inserts + cancel by business key
          Consumer: Multi-table writes, product_snapshot flattening
```

### SQL Concepts Per Task

| Task | New SQL Concepts |
|------|-----------------|
| **01 User** | CREATE TABLE, VARCHAR/INT/DATETIME, PRIMARY KEY, INDEX, INSERT ON DUPLICATE KEY UPDATE, UPDATE SET WHERE |
| **02 Supplier** | Wide tables (25+ cols), composite INDEX, hard DELETE, 26-param queries |
| **04 Product** | FOREIGN KEY ON DELETE CASCADE, AUTO_INCREMENT, UNIQUE KEY, JSON column, DELETE+INSERT replace pattern |
| **05 Post** | JSON column for arrays, DOUBLE, compound indexes, `json.dumps()` serialization |
| **07 Order** | UNIQUE KEY on business field, selective ON DUPLICATE KEY UPDATE, batch INSERT loop, composite UNIQUE, cancel by non-PK field |

---

## 10. DEVELOPMENT TIPS

### Hot Reload for MySQL Service

Like the MongoDB backend, the MySQL service mounts your code:

```yaml
# From docker-compose.yml:
volumes:
  - ./apps/mysql_server:/app
  - ./shared:/app/shared
```

However, the MySQL service does **not** auto-reload on file changes. After editing MySQL service files:

```bash
# Restart the MySQL consumer service
docker compose restart mysql-service
```

### Checking If Tables Exist

After adding DDL to `tables.py` and restarting:

```bash
docker compose exec mysql mysql -u analytics -panalytics123 analytics -e "SHOW TABLES;"
```

### Resetting MySQL Data

```bash
# Drop all tables and restart (re-runs init_tables)
docker compose exec mysql mysql -u analytics -panalytics123 analytics -e "
  SET FOREIGN_KEY_CHECKS = 0;
  DROP TABLE IF EXISTS order_items, product_variants, orders, products, posts, suppliers, users;
  SET FOREIGN_KEY_CHECKS = 1;
"
docker compose restart mysql-service
```

### Replaying Events

If you want to re-process all events (e.g., after fixing a bug):

```bash
# Reset the consumer group offset to the beginning
docker compose exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group mysql-analytics-service \
  --reset-offsets --to-earliest \
  --all-topics --execute

# Restart the consumer
docker compose restart mysql-service
```

---

## 11. EXERCISE: IMPLEMENT THE CONNECTION POOL

**File:** `apps/mysql_server/src/db/connection.py`

Open the file. You'll see three stubbed methods. Implement them:

### 11.1 `connect(self)`

Create a MySQL connection pool using `mysql.connector.pooling.MySQLConnectionPool`.

- Read connection parameters from environment variables (`MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`) with sensible defaults
- Set `pool_size=5` and `autocommit=True`
- Store the pool in `self._pool`
- Log that the pool was created

### 11.2 `init_tables(self)`

Execute all DDL statements from `TABLE_DEFINITIONS` to create the analytics tables.

- Import `TABLE_DEFINITIONS` from `src.db.tables` (local import to avoid circular imports)
- Get a connection from the pool
- Iterate all DDL statements and execute each one
- Always close the connection in a `finally` block (returns it to the pool)

### 11.3 `get_connection(self)`

Return a connection from the pool.

### Verification

After implementing, restart the mysql-service:

```bash
docker compose restart mysql-service
docker compose logs mysql-service | grep "connection pool created"
# Expected: MySQL connection pool created
```

---

## 12. CHECKLIST

Before starting TASK_01_MYSQL_USER, verify:

- [ ] All 5 Docker containers running (`docker compose ps`)
- [ ] Can connect to MySQL: `docker compose exec mysql mysql -u analytics -panalytics123 analytics -e "SELECT 1;"`
- [ ] Read `apps/mysql_server/main.py` (52 lines - understand the bootstrap)
- [ ] Read `apps/mysql_server/src/db/connection.py` (54 lines - understand the pool)
- [ ] Read `apps/mysql_server/src/kafka/consumer.py` (104 lines - understand message dispatch)
- [ ] Read `shared/kafka/topics.py` (55 lines - understand the event catalog)
- [ ] You understand the three-layer pattern: DDL -> DAL -> Consumer
- [ ] You understand the three-step verification: Trigger -> Check Logs -> Query MySQL
- [ ] You read this entire document

**Ready? Open `mysql-tasks/TASK_01_MYSQL_USER.md` and start building.**
