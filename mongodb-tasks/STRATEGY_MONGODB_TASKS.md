# MongoDB Advanced Learning - Task Strategy

## Philosophy & Core Idea

Students receive a **fully scaffolded Social Commerce Platform** with:
- **Models** (complete) - The data structures and indexes
- **Schemas** (complete) - The request/response contracts
- **Routes** (complete) - The HTTP endpoints that call services
- **Services** (EMPTY SHELLS) - **This is what students implement**

Each service file will be stripped down to **method signatures only** with docstrings explaining what the method should do. Students write every MongoDB query from scratch, guided by per-domain MD files.

> **The student never touches models, schemas, or routes. They ONLY write service-layer MongoDB queries.**

---

## How The MDs Work

### Each MD = One Domain (Model + Route pair)

```
mongodb-tasks/
├── STRATEGY_MONGODB_TASKS.md          ← This file (meta-strategy)
├── TASK_00_SETUP.md                   ← Environment setup + architecture primer
├── TASK_01_USER.md                    ← User CRUD service
├── TASK_02_SUPPLIER.md                ← Supplier CRUD service
├── TASK_04_PRODUCT.md                 ← Product catalog service
├── TASK_05_POST.md                    ← Social content service
├── TASK_07_ORDER.md                   ← Order processing service
├── TASK_08_ANALYTICS.md               ← Cross-domain aggregation pipelines
└── TASK_09_KAFKA.md                   ← Kafka producer/consumer (bonus)
```

### Strict Ordering - Each MD Unlocks The Next

```
TASK_01 (User)
   └─→ TASK_02 (Supplier)       ← Same patterns, harder model
         ├─→ TASK_04 (Product)   ← References Supplier
         └─→ TASK_05 (Post)      ← References User
               └─→ TASK_07 (Order) ← References User + Product
                     └─→ TASK_08 (Analytics) ← Aggregates everything
                           └─→ TASK_09 (Kafka) ← Event-driven consumers
```

Students MUST complete earlier tasks before later ones because:
- Later services CALL earlier services (e.g., Order calls Product to validate stock)
- MongoDB concepts build incrementally
- Test data from earlier tasks feeds into later ones

---

## MD Template (Every MD follows this structure)

```markdown
# TASK_XX: [Domain Name] Service Implementation

## 1. MISSION BRIEFING
- What this entity does in the business
- Why it matters to the platform
- What the student will learn (MongoDB concepts)

## 2. BEFORE YOU START
- Prerequisites (which previous tasks must be complete)
- Files to read before coding:
  - Model file (understand the data)
  - Schema file (understand inputs/outputs)
  - Route file (understand how your service gets called)

## 3. MODEL DEEP DIVE
- Annotated walkthrough of the model
- Field-by-field explanation of WHY each field exists
- Index analysis: what queries are optimized

## 4. THE SERVICE CONTRACT
- Every method signature with:
  - Input parameters (mapped to schema)
  - Expected return type
  - Business rules to enforce
  - Error conditions to handle

## 5. IMPLEMENTATION EXERCISES (ordered by difficulty)

### Exercise 5.1: [Name] - [MongoDB Concept]
**Concept:** What MongoDB operation this teaches
**Implement:** Which method(s) to write
**Requirements:**
  - Step-by-step business logic
  - Exact query patterns to use
  - Error handling expectations
**Hints:**
  - Beanie ODM syntax examples
  - Index usage reminders
**Verify:** curl command + expected response

### Exercise 5.2: [Name] - [MongoDB Concept]
...

## 6. VERIFICATION CHECKLIST
- [ ] All methods implemented
- [ ] All error cases handled
- [ ] Queries use appropriate indexes
- [ ] Soft delete pattern followed

## 7. ADVANCED CHALLENGES (optional)
- Performance optimization tasks
- Aggregation pipeline exercises
- Edge case handling
```

---

## MongoDB Concept Progression Map

Each task introduces NEW MongoDB concepts while reinforcing previous ones.

### TASK_01: User Service
**New Concepts:**
| Concept | Method | What They Learn |
|---------|--------|----------------|
| `find_one` with field match | `create_user()` | Check email uniqueness via nested field lookup |
| `insert` | `create_user()` | Document creation with Beanie |
| Nested field query | `get_user()` | Query by `_id` with `PydanticObjectId` |
| `$set` via `.save()` | `update_user()` | Partial update on nested profile fields |
| Soft delete pattern | `delete_user()` | Set `deleted_at` timestamp instead of hard delete |
| Find with filter + sort | `list_users()` | Filter `deleted_at == None`, sort, skip/limit |

**Reinforced:** None (this is the foundation)

---

### TASK_02: Supplier Service
**New Concepts:**
| Concept | Method | What They Learn |
|---------|--------|----------------|
| Deeply nested documents | `create_supplier()` | Build complex structures: `ContactInfo` → `CompanyInfo` → `CompanyAddress` → `BusinessInfo` → `BankingInfo` |
| Array field queries | `create_supplier()` | Query `additional_emails` array for uniqueness |
| Multi-level partial update | `update_supplier()` | Update fields across nested objects (`contact_info.primary_phone`, `company_info.legal_name`, etc.) |
| Hard delete | `delete_supplier()` | Permanent document removal (contrast with User soft delete) |

**Reinforced:** find_one, insert, save, nested fields, password hashing

---

### TASK_04: Product Service
**New Concepts:**
| Concept | Method | What They Learn |
|---------|--------|----------------|
| Dict/Map field queries | Variant operations | Query inside `variants` dict |
| Complex nested structures | `create_product()` | Variants + stock locations + topic descriptions |
| Multi-filter queries | `list_products()` | Combine status, category, supplier_id filters |
| Cross-collection validation | `create_product()` | Validate supplier exists before creating product |
| Status state transitions | lifecycle methods | DRAFT → ACTIVE → DISCONTINUED / OUT_OF_STOCK |
| Back-reference management | `create_product()` / `delete_product()` | Add/remove product_id from `supplier.product_ids` |

**Reinforced:** find_one, insert, save, skip/limit pagination

---

### TASK_05: Post Service
**New Concepts:**
| Concept | Method | What They Learn |
|---------|--------|----------------|
| Denormalized author snapshot | `create_post()` | Store `PostAuthor` from User data (display_name, avatar) |
| Multi-condition filter | `list_posts()` | Filter `deleted_at == None` AND `published_at != None`, optional `author_id` |
| Sort by published_at | `list_posts()` | Sort by `-published_at` for timeline ordering |
| Draft/publish lifecycle | `publish_post()` | Set `published_at` to transition from draft to live |
| Nested field queries | `list_posts()` | Query `author.user_id` when filtering by author |
| Media attachment handling | `create_post()` / `update_post()` | Build `MediaAttachment` and `LinkPreview` embedded docs |

**Reinforced:** Soft delete, partial update, denormalized data

---

### TASK_07: Order Service
**New Concepts:**
| Concept | Method | What They Learn |
|---------|--------|----------------|
| Product snapshot denormalization | `create_order()` | Freeze product data at purchase time via `ProductSnapshot` |
| Order number generation | `create_order()` | Human-readable unique IDs (e.g., `ORD-20250209-ABC1`) |
| Multi-collection validation | `create_order()` | Validate User exists + each Product is ACTIVE |
| Per-item order building | `create_order()` | Build `OrderItem` list with pricing and fulfillment status |
| Status guard on cancel | `cancel_order()` | Only allow cancel from PENDING/CONFIRMED |
| Compound query filters | `list_orders()` | Filter by `customer.user_id` + optional status + sort |

**Reinforced:** Everything from previous tasks

---

### TASK_08: Analytics & Aggregation Pipelines
**New Concepts:**
| Concept | Method | What They Learn |
|---------|--------|----------------|
| `$match` + `$group` | Revenue by supplier | Basic aggregation pipeline |
| `$unwind` | Top products by orders | Flatten arrays for grouping |
| `$lookup` | Order details with products | Left outer join across collections |
| `$facet` | Dashboard stats | Multiple aggregations in one query |
| `$bucket` | Price distribution | Range-based grouping |
| `$dateToString` | Daily revenue | Date-based aggregation |
| `$sortByCount` | Top categories | Frequency analysis |
| `$project` + `$addFields` | Computed fields | Transform output shapes |
| `$sum` as expression | Order totals | Sum array field values within a document |
| Pipeline optimization | All exercises | Filter early, project late |

**Reinforced:** Everything (this task is the capstone)

---

## Service Preparation Strategy

### What To Strip From Services Before Student Gets Them

For each service file, we create a **student version** that contains:

```python
class ProductService:
    """
    Service layer for product catalog management.
    Handles CRUD, lifecycle, and catalog queries.
    """

    def __init__(self):
        self._kafka = get_kafka_producer()

    # ──────────────────────────────────────────────
    # HELPER METHODS
    # ──────────────────────────────────────────────

    @staticmethod
    def _build_topic_descriptions(items: list) -> list[TopicDescription]:
        """
        Convert request topic description items to model objects.
        """
        # TODO: Implement this method
        pass

    # ──────────────────────────────────────────────
    # EXERCISE 5.1: CREATE PRODUCT
    # ──────────────────────────────────────────────

    async def create_product(
        self,
        supplier_id: str,
        body: CreateProductRequest,
    ) -> Product:
        """
        Create a new product for a supplier.

        Business Rules:
        1. Supplier must exist
        2. Build product with all embedded types
        3. Set initial status to DRAFT
        4. Add product_id to supplier.product_ids

        MongoDB Operations:
        - Find supplier by ID
        - Insert new product document
        - Update supplier.product_ids array
        - Emit PRODUCT_CREATED Kafka event

        Returns: The created Product document
        Errors: NotFoundError if supplier not found
        """
        # TODO: Implement this method
        pass
```

### What STAYS in the student version:
- Class definition with `__init__` (Kafka producer initialization)
- All method signatures with full type hints
- Comprehensive docstrings explaining:
  - Business rules
  - MongoDB operations needed
  - Error conditions (using `AppError` hierarchy)
  - Return types
- Import statements
- Helper method signatures (e.g., `_build_topic_descriptions`, `_build_stock_locations`)

### What gets REMOVED:
- All method bodies (replaced with `pass`)
- Implementation logic
- Query construction
- Error handling implementation

---

## How Students Use The MDs

### Workflow Per Task

```
1. READ the MD
   ├── Understand the domain
   ├── Read the model file (shared/models/X.py)
   ├── Read the schema file (schemas/X.py)
   └── Read the route file (routes/X.py)

2. IMPLEMENT exercises in order
   ├── Exercise 5.1 (easiest)
   ├── Exercise 5.2
   ├── ...
   └── Exercise 5.N (hardest)

3. VERIFY each exercise
   ├── Run the provided curl commands
   ├── Check responses match expected output
   └── Verify database state via MongoDB shell

4. COMPLETE the verification checklist

5. (Optional) ATTEMPT advanced challenges

6. MOVE to next task MD
```

### AI Assistant Integration

Each MD is designed so that an AI assistant can:
1. **Reference it** when helping the student
2. **Check student work** against the requirements
3. **Give hints** without giving away the answer (hint levels in each exercise)
4. **Validate** that the student used the correct MongoDB patterns
5. **Explain WHY** a pattern is used (each exercise links concept to real-world need)

The AI assistant should:
- Ask the student to read the model/schema/route FIRST before coding
- Guide through exercises IN ORDER (don't skip ahead)
- Encourage the student to try before revealing hints
- Verify each exercise works before moving to the next
- Point out when a query doesn't use indexes efficiently

---

## Difficulty Curve

```
Difficulty
    │
    │                                          ┌─ TASK_08 (Aggregation)
    │                                     ┌────┘
    │                                ┌────┘ TASK_07 (Orders/State Machines)
    │                           ┌────┘
    │                      ┌────┘ TASK_05 (Posts/Feeds)
    │                 ┌────┘
    │            ┌────┘ TASK_04 (Products/Variants)
    │       ┌────┘
    │  ┌────┘ TASK_02 (Supplier/Nested Docs)
    │──┘ TASK_01 (User/CRUD Basics)
    └─────────────────────────────────────────── Time
```

### Per-Task Breakdown (approximate exercises per MD):
| Task | Exercises | Est. Effort | Key Challenge |
|------|-----------|-------------|---------------|
| 01 - User | 6 | Low | First time writing Beanie queries |
| 02 - Supplier | 6 | Low-Med | Deeper nesting, stricter validation |
| 04 - Product | 8 | Medium | Variants, inventory, lifecycle |
| 05 - Post | 7 | Medium-High | Denormalized snapshots, draft/publish, media |
| 07 - Order | 7 | High | Multi-collection validation, snapshot denormalization |
| 08 - Analytics | 8 | Very High | Pure aggregation pipelines |

---

## Exercise Design Principles

### 1. Every Exercise Has ONE Primary MongoDB Concept
Don't mix concepts. If the exercise is about `$inc`, that's the focus.

### 2. Every Exercise Has Real Business Context
Not "insert a document" but "Create a user who wants to buy handmade jewelry and engage with social content."

### 3. Three Hint Levels Per Exercise
- **Hint 1:** Direction (e.g., "Use Beanie's find_one with a filter dict")
- **Hint 2:** Pattern (e.g., "The filter should match on nested field contact_info.primary_email")
- **Hint 3:** Near-solution (e.g., "await User.find_one({'contact_info.primary_email': email, 'deleted_at': None})")

### 4. Verification Is Concrete
Every exercise ends with a curl command and expected JSON response that proves it works.

### 5. Error Cases Are Explicit
Each exercise lists error scenarios the student must handle (not discover on their own).

---

## Testing & Seed Data Strategy

### TASK_00 (Setup MD) Includes:
1. Docker compose up (MongoDB + Kafka + MySQL + app + mysql-service)
2. Seed scripts available in `scripts/`:
   - `seed.py` - Creates sample users + 16 suppliers via REST API
   - `generate_posts.py` - Generates sample social posts
   - `generate_products.py` - Generates sample products with variants
3. MongoDB shell access instructions
4. How to check indexes: `db.collection.getIndexes()`
5. How to inspect documents: `db.collection.findOne()`

### Each subsequent task MD provides:
- Additional seed data specific to that domain
- curl commands using IDs from seed data + previous tasks

---

## File Delivery Plan

### Phase 1: Prepare Student Codebase
1. Create `student/` branch or directory
2. Strip all service implementations -> method stubs with docstrings
3. Keep models, schemas, routes, utils intact
4. Keep seed data scripts

### Phase 2: Create MDs (in order)
1. `TASK_00_SETUP.md` - Environment + architecture primer
2. `TASK_01_USER.md` - User CRUD service
3. `TASK_02_SUPPLIER.md` - Supplier CRUD service
4. `TASK_04_PRODUCT.md` - Product catalog service
5. `TASK_05_POST.md` - Social content service
6. `TASK_07_ORDER.md` - Order processing service
7. `TASK_08_ANALYTICS.md` - Aggregation pipeline exercises
8. `TASK_09_KAFKA.md` - Kafka consumer exercises (bonus)

### Phase 3: Create Solution Branch
- Full implementations as reference
- Students never see this unless instructor reveals it

---

## Success Criteria

A student who completes all tasks will be able to:

1. **Write efficient MongoDB queries** using Beanie ODM
2. **Design compound indexes** and understand query optimization
3. **Implement skip/limit and cursor-based pagination** for production-scale datasets
4. **Handle concurrent updates** with atomic operators (`$inc`, `$set`)
5. **Build status-based workflows** (state machines with transition validation)
6. **Implement product snapshot denormalization** for order integrity
7. **Write aggregation pipelines** for analytics and reporting
8. **Apply soft-delete patterns** consistently
9. **Build denormalized read models** for performance (author snapshots, product snapshots)
10. **Flatten nested documents** for event-driven consumers
