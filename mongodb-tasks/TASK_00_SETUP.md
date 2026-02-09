# TASK 00: Environment Setup & Architecture Primer

## 1. WELCOME

You are about to build the **service layer** of a Social Commerce Platform - a system where users discover products, engage with social content, and make purchases without ever leaving the ecosystem. Think Instagram + Shopify as a single unified experience.

The entire codebase is **already scaffolded** for you:
- **Models** (complete) - MongoDB document schemas with indexes and validators
- **Schemas** (complete) - Pydantic request/response contracts for every endpoint
- **Routes** (complete) - HTTP endpoints that call your service methods
- **Services** (EMPTY) - **This is what you implement**

You will write every MongoDB query from scratch. The route layer calls your methods, you talk to MongoDB through [Beanie ODM](https://beanie-odm.dev/), and you return data that the route layer formats into HTTP responses.

```
HTTP Request
    │
    ▼
┌─────────┐     ┌─────────────┐     ┌──────────┐
│  Route  │────►│  Service    │────►│ MongoDB  │
│ (done)  │     │  (YOU WRITE)│     │ (Beanie) │
└─────────┘     └─────────────┘     └──────────┘
    │                                     │
    ▼                                     │
HTTP Response ◄───────────────────────────┘
```

> **Rule:** You never touch models, schemas, or routes. You ONLY write service-layer MongoDB queries.

---

## 2. PREREQUISITES

Before starting, make sure you have:

| Requirement | Version | Check Command |
|------------|---------|---------------|
| **Docker Desktop** | 4.x+ | `docker --version` |
| **Docker Compose** | v2+ (bundled with Docker Desktop) | `docker compose version` |
| **Git** | Any | `git --version` |
| **Python** | 3.11+ (for local development/debugging) | `python3 --version` |
| **Postman** (optional) | Latest | For API testing outside Swagger |

---

## 3. PROJECT SETUP

### 3a. Clone the Repository

```bash
git clone <repository-url>
cd mongo_advanced_leaerning
```

### 3b. Start All Services

One command brings up the entire infrastructure:

```bash
docker compose up -d
```

This starts **5 containers**:

| Container | Image | Port | Purpose |
|-----------|-------|------|---------|
| `social_commerce_mongodb` | `mongo:latest` | **27017** | MongoDB database (your primary data store) |
| `social_commerce_kafka` | `confluentinc/cp-kafka:7.6.0` | **9092** | Kafka broker (event streaming) |
| `social_commerce_app` | Python 3.11 + FastAPI | **8000** | Backend API (your service runs here) |
| `social_commerce_mysql` | `mysql:8.0` | **3306** | MySQL analytics database |
| `social_commerce_mysql_service` | Python 3.11 | - | Kafka consumer (writes to MySQL) |

### 3c. Verify Everything Is Running

```bash
# Check all containers are up
docker compose ps

# Expected output (all should show "running" or "Up"):
# social_commerce_mongodb         ... running
# social_commerce_kafka           ... running
# social_commerce_app             ... running
# social_commerce_mysql           ... running
# social_commerce_mysql_service   ... running
```

### 3d. Verify the API

Open your browser and navigate to:

```
http://localhost:8000/docs
```

This is the **Swagger UI** - FastAPI's built-in interactive API documentation. You should see the full list of endpoints grouped by tag (Authentication, Products, Orders, etc.). If this page loads, your backend is running correctly.

You can also check the health endpoint directly in Swagger:
1. Find the **GET /** endpoint
2. Click "Try it out" → "Execute"
3. You should see: `{"status": "ok", "message": "Social Commerce Platform API", "version": "1.0.0"}`

### 3e. View Application Logs

```bash
# See the FastAPI app startup logs
docker compose logs app

# Expected to see:
# ✓ Connected to MongoDB: social_commerce
# ✓ Initialized Beanie ODM with all models
# ✓ Application started successfully

# Follow logs in real-time (useful during development):
docker compose logs -f app
```

---

## 4. API TESTING: SWAGGER UI & POSTMAN

You will test every endpoint you build using **Swagger UI** (built into FastAPI) or **Postman**.

### Swagger UI (Recommended for Quick Testing)

```
http://localhost:8000/docs      ← Interactive Swagger UI
http://localhost:8000/redoc     ← Read-only ReDoc (better for reading)
```

Swagger UI lets you:
- See every endpoint with its request/response schemas
- Click **"Try it out"** on any endpoint
- Fill in the request body/parameters
- Click **"Execute"** to send the request
- See the response, status code, and headers

```
┌──────────────────────────────────────────────────────────────┐
│  Swagger UI Workflow                                          │
│                                                               │
│  1. Find the endpoint (e.g., POST /register)                 │
│  2. Click "Try it out"                                        │
│  3. Edit the request body JSON                                │
│  4. Click "Execute"                                           │
│  5. Read the response below                                   │
│     ├── 201 = Success (check the response body)              │
│     ├── 400 = Your service raised ValueError                 │
│     ├── 404 = Not found                                       │
│     └── 500 = Unhandled exception (check docker logs)        │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

> **Tip:** When an endpoint requires headers (like `X-User-ID` or `X-Supplier-ID`), Swagger shows input fields for them at the top of the endpoint form.

### Postman (For Complex Flows)

For multi-step flows (register → login → use token → create order), Postman is more convenient because:
- You can save requests in collections
- You can store variables (user IDs, tokens) and reuse them
- You can chain requests together

Import the base URL as a Postman variable: `{{base_url}} = http://localhost:8000`

---

## 5. PROJECT STRUCTURE

### Directory Layout

```
mongo_advanced_leaerning/
│
├── docker-compose.yml              ← Orchestrates all 5 services
│
├── apps/
│   ├── backend-service/            ← FastAPI backend (where you work)
│   │   ├── Dockerfile
│   │   ├── main.py                 ← Entry point (uvicorn server)
│   │   ├── server.py               ← FastAPI app setup + route registration
│   │   ├── requirements.txt        ← Python dependencies
│   │   └── src/
│   │       ├── db/
│   │       │   └── mongo_db.py     ← MongoDB connection + Beanie initialization
│   │       ├── kafka/
│   │       │   └── producer.py     ← Kafka event producer (already works)
│   │       ├── routes/             ← HTTP endpoints (COMPLETE - don't modify)
│   │       │   ├── auth.py         ← /register, /login, /verify-email, ...
│   │       │   ├── supplier_auth.py ← /supplier/register, /supplier/login, ...
│   │       │   ├── product.py      ← /products/...
│   │       │   ├── post.py         ← /posts/...
│   │       │   ├── order.py        ← /orders/...
│   │       │   └── admin.py        ← /admin/...
│   │       ├── schemas/            ← Request/response models (COMPLETE - don't modify)
│   │       │   ├── auth.py
│   │       │   ├── supplier_auth.py
│   │       │   ├── product.py
│   │       │   ├── post.py
│   │       │   └── order.py
│   │       ├── services/           ← Business logic (YOU IMPLEMENT THESE)
│   │       │   ├── auth.py         ← TASK_01
│   │       │   ├── supplier_auth.py ← TASK_02
│   │       │   ├── product.py      ← TASK_04
│   │       │   ├── post.py         ← TASK_05
│   │       │   └── order.py        ← TASK_07
│   │       └── utils/              ← Helper functions (COMPLETE - use freely)
│   │           ├── datetime_utils.py ← utc_now() helper
│   │           ├── serialization.py  ← oid_to_str() for Kafka
│   │           ├── order_utils.py
│   │           └── post_utils.py
│   │
│   └── mysql-service/              ← Kafka consumer → MySQL (TASK_09)
│       ├── Dockerfile
│       ├── main.py                 ← Consumer entry point
│       └── src/
│           ├── db/
│           │   └── connection.py   ← MySQL connection pool
│           ├── kafka/
│           │   └── consumer.py     ← Kafka consumer with handler routing
│           ├── consumers/
│           │   └── auth_consumer.py ← Reference consumer (User events → MySQL)
│           └── dal/
│               └── user_dal.py     ← Data access layer for MySQL
│
├── shared/                         ← Shared across all services
│   ├── kafka/
│   │   ├── config.py              ← Kafka connection settings
│   │   └── topics.py             ← 7 topics + 28 event types
│   └── models/                    ← MongoDB document models (COMPLETE - don't modify)
│       ├── user.py                ← User entity (Consumer/Leader)
│       ├── auth.py                ← Email verification + password reset tokens
│       ├── supplier.py            ← Supplier/vendor entity
│       ├── product.py             ← Product catalog
│       ├── post.py                ← Social content
│       └── order.py               ← Purchase orders
│
└── docs/
    ├── ARCHITECTURE.md            ← Full system architecture
    ├── TASK_1_ARCHITECTURE.md     ← Kafka architecture design
    ├── TASK_2_TOPIC_CATALOG.md    ← Event catalog & topic definitions
    └── mongodb-tasks/             ← YOUR LEARNING TRACK
        ├── STRATEGY_MONGODB_TASKS.md ← Course philosophy (read this!)
        ├── TASK_00_SETUP.md       ← This file
        ├── TASK_01_USER.md        ← Start here
        ├── TASK_02_SUPPLIER.md
        ├── TASK_04_PRODUCT.md
        ├── TASK_05_POST.md
        ├── TASK_07_ORDER.md
        ├── TASK_08_ANALYTICS.md
        └── TASK_09_KAFKA.md
```

### The Three Layers You Need to Understand

For every domain (User, Supplier, Product, Post, Order), there are three files you must read before writing code:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│  LAYER 1: MODEL (shared/models/X.py)                         READ FIRST │
│  ─────────────────────────────────────                                   │
│  What gets stored in MongoDB.                                            │
│  • Document classes (extend beanie.Document)                             │
│  • Embedded document types (Pydantic BaseModel)                          │
│  • Enums for status fields                                               │
│  • Indexes (in class Settings)                                           │
│                                                                          │
│  LAYER 2: SCHEMA (src/schemas/X.py)                         READ SECOND │
│  ─────────────────────────────────────                                   │
│  What the API sends and receives.                                        │
│  • Request schemas (what the route gives you)                            │
│  • Response schemas (what you must return)                               │
│  • Validation rules (min/max lengths, enums)                             │
│                                                                          │
│  LAYER 3: ROUTE (src/routes/X.py)                            READ THIRD │
│  ─────────────────────────────────────                                   │
│  How your service gets called.                                           │
│  • HTTP method + path                                                    │
│  • What parameters the route extracts (headers, path, body)              │
│  • How it calls YOUR service method                                      │
│  • How it handles errors (ValueError → 400, etc.)                        │
│                                                                          │
│  YOUR JOB: SERVICE (src/services/X.py)                       YOU WRITE   │
│  ─────────────────────────────────────                                   │
│  The business logic + MongoDB queries.                                   │
│  • Method signatures are given (with docstrings)                         │
│  • Bodies are empty (pass or TODO)                                       │
│  • You implement every method                                            │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 6. THE BUSINESS DOMAIN

### What Is This Platform?

A Social Commerce Platform where four user types interact:

```
┌───────────────────────────────────────────────────────────────────────┐
│                     STAKEHOLDER ECOSYSTEM                             │
│                                                                       │
│                           ┌─────────┐                                 │
│                           │  ADMIN  │                                 │
│                           │         │                                 │
│                           │Moderates│                                 │
│                           │Approves │                                 │
│                           └────┬────┘                                 │
│                                │                                      │
│         ┌──────────────────────┼──────────────────────┐               │
│         │                      │                      │               │
│         ▼                      ▼                      ▼               │
│  ┌────────────┐        ┌────────────┐         ┌────────────┐         │
│  │   LEADER   │        │  CONSUMER  │         │  SUPPLIER  │         │
│  │            │        │            │         │            │         │
│  │ Creates    │◄──────►│ Browses    │◄───────►│ Lists      │         │
│  │ posts      │ engage │ posts      │ purchase│ products   │         │
│  │            │        │            │         │            │         │
│  │ Curates    │        │ Discovers  │         │ Manages    │         │
│  │ content    │        │ products   │         │ inventory  │         │
│  └────────────┘        └────────────┘         └────────────┘         │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

### The Five Domains

| # | Domain | Collection | What It Does |
|---|--------|------------|-------------|
| 1 | **User/Auth** | `users` | Consumer + Leader registration, login, email verification, password reset |
| 2 | **Supplier** | `suppliers` | Vendor registration, login, profile management |
| 3 | **Product** | `products` | Catalog items owned by Suppliers. Variants, inventory, pricing, lifecycle |
| 4 | **Post** | `posts` | Social content created by users. Media, engagement tracking |
| 5 | **Order** | `orders` | Purchase transactions. Status lifecycle, per-item fulfillment tracking |

### Supporting Collections

| Collection | Purpose |
|-----------|---------|
| `email_verification_tokens` | Token storage for email verification flow |
| `password_reset_tokens` | Token storage for password reset flow |

---

## 7. API ENDPOINTS OVERVIEW

The FastAPI backend exposes these route groups. Each group corresponds to a service you'll implement. You can explore all of them interactively at `http://localhost:8000/docs`.

### Authentication (`/register`, `/login`, ...)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/register` | Register consumer user |
| POST | `/register/leader` | Register leader user |
| POST | `/login` | Login (email + password) |
| POST | `/verify-email` | Verify email with token |
| POST | `/request-password-reset` | Request password reset |
| POST | `/reset-password` | Reset password with token |

### Supplier Auth (`/supplier/...`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/supplier/register` | Register supplier |
| POST | `/supplier/login` | Supplier login |
| POST | `/supplier/submit-documents` | Submit verification documents |
| GET | `/supplier/me` | Get own profile |
| PUT | `/supplier/me` | Update own profile |

### Products (`/products/...`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/products/` | Create product |
| GET | `/products/supplier` | List supplier's products |
| GET | `/products/public` | Public catalog with filters |
| GET | `/products/{id}` | Get product |
| GET | `/products/public/{id}` | Get public product |
| PUT | `/products/{id}` | Update product |
| DELETE | `/products/{id}` | Soft delete |
| POST | `/products/{id}/publish` | Publish (draft → active) |
| POST | `/products/{id}/discontinue` | Discontinue product |

### Posts (`/posts/...`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/posts/` | Create post |
| GET | `/posts/` | List posts |
| GET | `/posts/user/{id}` | List user's posts |
| GET | `/posts/{id}` | Get post |
| PUT | `/posts/{id}` | Update post |
| DELETE | `/posts/{id}` | Soft delete |

### Orders (`/orders/...`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/orders/` | Create order |
| GET | `/orders/` | List user's orders |
| GET | `/orders/{id}` | Get order by ID |
| GET | `/orders/number/{num}` | Get by order number |
| POST | `/orders/{id}/complete` | Complete order (payment) |
| PUT | `/orders/{id}` | Modify pending order |
| POST | `/orders/{id}/cancel` | Cancel order |

---

## 8. KEY TECHNOLOGIES

### Beanie ODM (Your Primary Tool)

[Beanie](https://beanie-odm.dev/) is an async MongoDB ODM built on top of [Motor](https://motor.readthedocs.io/) and [Pydantic](https://docs.pydantic.dev/). Every MongoDB operation you write uses Beanie.

**Core operations you'll use throughout all tasks:**

```python
from shared.models.user import User

# ── FIND ONE ──
user = await User.find_one({"contact_info.primary_email": email})
user = await User.find_one(User.deleted_at == None)
user = await User.get(object_id)           # Find by _id (PydanticObjectId)

# ── FIND MANY ──
users = await User.find(
    User.deleted_at == None,
).sort(-User.created_at).limit(10).to_list()

# ── COUNT ──
count = await User.find(User.deleted_at == None).count()

# ── INSERT ──
user = User(
    contact_info=ContactInfo(primary_email="test@example.com"),
    profile=UserProfile(display_name="Test User"),
    # ... more fields
)
await user.insert()  # Saves to MongoDB, user.id now populated

# ── UPDATE (via save) ──
user.profile.display_name = "New Name"
user.updated_at = utc_now()
await user.save()    # Saves all changes to MongoDB

# ── AGGREGATION ──
pipeline = [
    {"$match": {"deleted_at": None}},
    {"$group": {"_id": "$profile.display_name", "count": {"$sum": 1}}}
]
results = await User.aggregate(pipeline).to_list()
```

### Key Beanie Patterns

| Pattern | Beanie Syntax |
|---------|--------------|
| Find by field | `await User.find_one({"email": x})` |
| Find by ID | `await User.get(oid)` |
| Nested field | `await User.find_one({"contact_info.primary_email": x})` |
| Sort + limit | `await User.find(...).sort(-User.created_at).limit(10).to_list()` |
| Skip pagination | `await User.find(...).skip(20).limit(10).to_list()` |
| Cursor pagination | `await User.find({"_id": {"$gt": cursor}}).limit(10).to_list()` |
| Insert | `await doc.insert()` |
| Update | `await doc.save()` |
| Count | `await User.find(filter).count()` |
| Aggregate | `await User.aggregate(pipeline).to_list()` |

### PydanticObjectId

MongoDB uses `ObjectId` for document IDs. In Beanie, these are `PydanticObjectId`:

```python
from beanie import PydanticObjectId

# Convert string to ObjectId
oid = PydanticObjectId(user_id_string)

# Use in queries
user = await User.get(PydanticObjectId(user_id))

# Convert back to string
user_id_str = str(user.id)
```

### Other Technologies in the Stack

| Technology | Where Used | Purpose |
|-----------|-----------|---------|
| **FastAPI** | Backend routes | Async web framework |
| **Pydantic** | Schemas + models | Data validation |
| **Motor** | Under Beanie | Async MongoDB driver |
| **confluent-kafka** | Producer + Consumer | Kafka client library |
| **bcrypt** | Auth service | Password hashing |
| **PyJWT** | Auth service | JWT token generation |
| **MySQL Connector** | MySQL service | MySQL driver for analytics |

---

## 9. DEVELOPMENT WORKFLOW

### Your Day-to-Day Process

```
1. READ the task MD
   │
   ├── Read the model file (understand what gets stored)
   ├── Read the schema file (understand what you receive/return)
   └── Read the route file (understand how you're called)
   │
2. IMPLEMENT one exercise at a time
   │
   ├── Edit: apps/backend-service/src/services/<domain>.py
   ├── The container auto-reloads when you save (volume mount + --reload)
   └── No need to restart Docker
   │
3. VERIFY via Swagger UI or Postman
   │
   ├── Open http://localhost:8000/docs
   ├── Find the endpoint for your exercise
   ├── Click "Try it out" → fill in request → "Execute"
   └── Check the response matches what the task MD expects
   │
4. MOVE to next exercise (in order - don't skip!)
```

### Hot Reload

The Docker setup mounts your local code into the container:

```yaml
# From docker-compose.yml:
volumes:
  - ./apps/backend-service:/app    # Your code is live-mounted
  - ./shared:/app/shared           # Shared models too
```

This means:
- Edit `apps/backend-service/src/services/auth.py` locally
- Save the file
- The FastAPI server **auto-restarts** inside the container
- Your changes are immediately live at `http://localhost:8000`

**No need to rebuild or restart containers for code changes.**

### When You DO Need to Restart

```bash
# If you change requirements.txt (new dependency):
docker compose build app
docker compose up -d app

# If containers crash or get into bad state:
docker compose down
docker compose up -d

# Nuclear reset (removes all data volumes):
docker compose down -v    # WARNING: Deletes all MongoDB, MySQL, Kafka data
docker compose up -d
```

### Viewing Logs

```bash
# See app logs (your print statements and errors appear here)
docker compose logs -f app

# See all service logs
docker compose logs -f

# See only errors
docker compose logs app 2>&1 | grep -i error
```

---

## 10. TASK PROGRESSION

### The Learning Path

Tasks MUST be completed in order. Each task builds on concepts and data from previous tasks.

```
TASK_01: User Authentication
    │     ├── find_one, insert, save, nested fields
    │     └── Foundation for everything else
    │
    ▼
TASK_02: Supplier Authentication
    │     ├── Deeper nesting, array field queries
    │     └── Builds on: User patterns (same auth, harder model)
    │
    ├─────────────────────────────────┐
    ▼                                 ▼
TASK_04: Product Catalog          TASK_05: Social Posts
    │   ├── Dict fields, cross-       │   ├── Cursor pagination
    │   │   collection validation     │   │   $inc atomic counters
    │   └── Builds on: Supplier       │   └── Builds on: User
    │                                 │
    └─────────────┬───────────────────┘
                  ▼
TASK_07: Order Processing
    │     ├── State machine, per-item fulfillment, snapshots
    │     └── Builds on: User + Product
    │
    ▼
TASK_08: Analytics (Capstone)
    │     ├── Aggregation pipelines across all collections
    │     └── Builds on: Everything
    │
    ▼
TASK_09: Kafka Consumers (Bonus)
          ├── Event-driven architecture, document flattening
          └── Builds on: Understanding all domain events
```

### What You Learn Per Task

| Task | New MongoDB Concepts | Methods | Difficulty |
|------|---------------------|---------|-----------|
| **01 - User** | `find_one`, `insert`, `save`, nested field queries, index awareness | ~8 | Low |
| **02 - Supplier** | Array field queries, deeply nested documents, dual token strategy | ~8 | Low-Medium |
| **04 - Product** | Dict/Map fields, `$gte/$lte` ranges, cross-collection validation, status lifecycle | ~10 | Medium |
| **05 - Post** | Cursor pagination with `$or` tiebreaker, `$inc` atomic counters, base64 cursors | ~10 | Medium-High |
| **07 - Order** | State machine, per-item fulfillment tracking, product snapshot denormalization | ~10 | High |
| **08 - Analytics** | `$match`, `$group`, `$unwind`, `$lookup`, `$facet`, `$bucket`, `$dateToString` | ~8 | Very High |
| **09 - Kafka** | Producer/consumer pattern, event envelope, document-to-relational flattening | ~15 handlers | Bonus |

---

## 11. COMMON ISSUES & TROUBLESHOOTING

### Container Won't Start

```bash
# Check what's wrong
docker compose logs app

# Common: Port already in use
# Fix: Stop whatever is using port 8000/27017/9092/3306
lsof -i :8000    # Find what's using the port
kill -9 <PID>    # Kill it

# Common: Old containers lingering
docker compose down
docker compose up -d
```

### MongoDB Connection Refused

```bash
# Check if MongoDB is running
docker compose ps mongodb

# Check MongoDB logs
docker compose logs mongodb

# Try restarting just MongoDB
docker compose restart mongodb
```

### Service Returns 500 Error

```bash
# Check the app logs for the full traceback
docker compose logs -f app

# Common causes:
# 1. Your service method raises an unhandled exception
# 2. You returned the wrong type (route expects dict, you returned Document)
# 3. Import error in your service file
```

### Changes Not Appearing

```bash
# Check if auto-reload picked up your changes
docker compose logs app | tail -20
# Look for: "Detected changes in '...', reloading"

# If not reloading, check the volume mount
docker compose exec app ls -la /app/src/services/
# Your local changes should appear here

# Force restart
docker compose restart app
```

### Fresh Start (Reset Everything)

```bash
# Remove containers + volumes (deletes all data)
docker compose down -v

# Rebuild images (if Dockerfile changed)
docker compose build

# Start fresh
docker compose up -d
```

---

## 12. CHECKLIST

Before starting TASK_01, verify:

- [ ] `docker compose up -d` - All 5 containers running
- [ ] `http://localhost:8000/docs` - Swagger UI loads with all endpoint groups
- [ ] Health endpoint in Swagger returns a success response
- [ ] `docker compose logs app` shows "Connected to MongoDB" and "Application started successfully"
- [ ] You understand the 3-layer architecture (Model → Schema → Route → **Service**)
- [ ] You know where your service files are: `apps/backend-service/src/services/`
- [ ] You know how to view logs: `docker compose logs -f app`
- [ ] You read this entire document

**Ready? Open `docs/mongodb-tasks/TASK_01_USER.md` and start building.**
