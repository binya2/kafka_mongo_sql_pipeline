# TASK 08: Analytics Service - Aggregation Pipelines (Capstone)

## 1. MISSION BRIEFING

You've spent previous tasks writing `find()`, `find_one()`, `insert()`, and `save()` queries. Now you enter a completely different world: **MongoDB Aggregation Pipelines**. Aggregation pipelines are multi-stage data processing workflows that transform, filter, group, join, and reshape documents - all executed server-side inside MongoDB. They're the equivalent of SQL's `GROUP BY`, `JOIN`, `HAVING`, window functions, and subqueries - but expressed as a pipeline of stages where each stage's output feeds into the next.

This is the **capstone task**. There are no routes or schemas to follow - you'll create a standalone `AnalyticsService` class from scratch and write 8 aggregation pipelines that answer real business questions by querying across ALL the data you've built in previous tasks.

### What You Will Build
A new `AnalyticsService` class with 8 methods, each implementing a different aggregation pipeline pattern. These methods generate platform analytics: revenue breakdowns, top-performing entities, time-series trends, distribution analyses, and a full admin dashboard.

### What You Will Learn

| Aggregation Stage | Exercise | What It Does |
|------------------|----------|--------------|
| **`$match`** | All exercises | Filter documents before processing (always first!) |
| **`$group`** | Ex 1, 2, 6 | Group documents and compute aggregates (`$sum`, `$avg`, `$max`, `$first`) |
| **`$unwind`** | Ex 2, 3 | Flatten arrays into individual documents |
| **`$lookup`** | Ex 3 | Left outer join across collections |
| **`$project` + `$addFields`** | Ex 4 | Reshape output, compute new fields |
| **`$bucket`** | Ex 5 | Range-based grouping (histograms) |
| **`$dateToString`** | Ex 6 | Date formatting for time-series grouping |
| **`$sortByCount`** | Ex 7 | Frequency analysis (shorthand for `$group` + `$sort`) |
| **`$facet`** | Ex 8 | Multiple independent pipelines in a single query |

### How This Differs From All Previous Tasks

| Aspect | Previous Tasks | Task 08 (Analytics) |
|--------|-------------|---------------------|
| Query type | `find()`, `find_one()` | **Aggregation pipelines** |
| Data flow | Filter -> Return | **Multi-stage: filter -> transform -> group -> reshape** |
| Joins | Manual cross-collection reads | **`$lookup` server-side joins** |
| Output shape | Full documents | **Custom computed results** |
| Service file | Implement existing stub | **Create from scratch** |
| Routes | Pre-built | **None - run from tests/shell** |
| Collections | 1-2 per method | **All 5 collections available** |

---

## 2. BEFORE YOU START

### Prerequisites
- **ALL previous tasks should be complete** with test data in the database
- The more data you have, the more interesting the analytics will be
- Recommended minimum: 3 users, 2 suppliers, 5 products, 10 posts, 5 orders

### The Collections You'll Query

| Collection | Key Fields for Analytics |
|-----------|------------------------|
| `users` | `created_at`, `profile.display_name`, `contact_info`, `deleted_at` |
| `suppliers` | `created_at`, `company_info.*`, `product_ids[]`, `contact_info` |
| `products` | `status`, `base_price_cents`, `category`, `supplier_id`, `stats.*`, `created_at` |
| `posts` | `post_type`, `author.user_id`, `author.author_type`, `stats.*`, `published_at`, `deleted_at` |
| `orders` | `status`, `items[]`, `customer.user_id`, `order_number`, `created_at` |

### Beanie Aggregation Syntax

In Beanie, you call `.aggregate()` on a Document class:

```python
# Basic aggregation
results = await Order.aggregate([
    {"$match": {"status": "confirmed"}},
    {"$unwind": "$items"},
    {"$group": {"_id": "$customer.user_id", "total": {"$sum": "$items.total_cents"}}}
]).to_list()

# With raw motor collection (for $lookup across collections)
collection = Order.get_motor_collection()
results = await collection.aggregate([
    {"$match": {...}},
    {"$lookup": {...}},
    ...
]).to_list(length=None)
```

> **Important**: `Model.aggregate()` returns Beanie cursor that needs `.to_list()`. Raw motor aggregation needs `.to_list(length=None)` where `length=None` means "get all results".

### Create Your Service File

Create a new file: `apps/mongo_backend/services/analytics.py`

```python
"""
Analytics Service - Aggregation pipeline exercises
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from beanie import PydanticObjectId

from shared.models.order import Order
from shared.models.product import Product
from shared.models.user import User
from shared.models.post import Post
from shared.models.supplier import Supplier
from utils.datetime_utils import utc_now


class AnalyticsService:
    """
    Analytics service using MongoDB aggregation pipelines.

    Each method implements a different aggregation pattern
    that answers a real business question.
    """

    # Exercise 1-8 methods go here
    pass
```

---

## 3. AGGREGATION PIPELINE PRIMER

Before diving into exercises, understand the pipeline concept:

```
Documents in collection
    |
    v
+----------------+
|  $match        |  Filter documents (like WHERE)
|  { status:     |  ALWAYS put this first for performance
|    "active"}   |
+-------+--------+
        |
        v
+----------------+
|  $unwind       |  Flatten array field into individual docs
|  "$items"      |  1 doc with 3 items -> 3 docs (one per item)
+-------+--------+
        |
        v
+----------------+
|  $group        |  Group by key, compute aggregates
|  { _id:        |  Like GROUP BY + SUM/AVG/COUNT
|    "$field"}   |
+-------+--------+
        |
        v
+----------------+
|  $sort         |  Sort the results
|  { total: -1}  |
+-------+--------+
        |
        v
+----------------+
|  $project      |  Reshape output (include/exclude/compute fields)
|  { name: 1,    |  Like SELECT in SQL
|    total: 1}   |
+-------+--------+
        |
        v
  Final Results
```

### The Golden Rule: `$match` First

```python
# GOOD: Filter 1M docs down to 1K, then group 1K
[
    {"$match": {"status": "confirmed"}},      # 1K docs pass through
    {"$group": {"_id": "$supplier_id", ...}}   # Group 1K docs
]

# BAD: Group 1M docs, then filter results
[
    {"$group": {"_id": "$supplier_id", ...}},  # Group ALL 1M docs
    {"$match": {"total": {"$gt": 1000}}}       # Filter results after
]
```

---

## 4. SERVICE CONTRACT

```python
class AnalyticsService:
    # Exercise 1: $match + $group
    async def revenue_by_supplier(self, start_date=None, end_date=None) -> List[Dict]

    # Exercise 2: $unwind + $group
    async def top_products_by_order_count(self, limit: int = 10) -> List[Dict]

    # Exercise 3: $lookup (cross-collection join)
    async def orders_with_product_details(self, supplier_id: str, limit: int = 20) -> List[Dict]

    # Exercise 4: $project + $addFields (computed fields)
    async def post_engagement_report(self) -> List[Dict]

    # Exercise 5: $bucket (distribution analysis)
    async def product_price_distribution(self) -> List[Dict]

    # Exercise 6: $dateToString (time-series)
    async def daily_revenue(self, days: int = 30) -> List[Dict]

    # Exercise 7: $sortByCount (frequency analysis)
    async def top_product_categories(self, limit: int = 10) -> List[Dict]

    # Exercise 8: $facet (admin dashboard)
    async def platform_dashboard(self) -> Dict[str, Any]
```

---

## 5. EXERCISES

---

### Exercise 1: Revenue by Supplier - `$match` + `$group`

**Aggregation Concepts**: `$match`, `$group`, `$sum`, `$avg`, `$first`, `$sort`, `$addFields` with `$sum` as expression

**Business Question**: "How much revenue has each supplier generated from confirmed orders?"

#### Method: `revenue_by_supplier`
```python
async def revenue_by_supplier(
    self,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[Dict]:
```

**The Pipeline:**

```python
# TODO: Implement your pipeline here
pass
```

**Breaking down the key stages:**

**`$unwind "$items"`**: An order with 3 items becomes 3 documents, each with one item. This is necessary because each item may have a different `supplier_id` in its `product_snapshot`. Without unwind, you can't group by supplier at the item level.

**`$group` accumulators:**
- `$sum: "$items.total_cents"` - Adds up all revenue per item
- `$sum: "$items.quantity"` - Counts total units sold
- `$sum: 1` - Counts the number of order-item pairs (like COUNT(*))
- `$avg: "$items.total_cents"` - Average item value
- `$first: "$items.product_snapshot.supplier_name"` - Takes the supplier name from the first matching doc (they're all the same for one supplier)

**`$project` with `$divide` and `$round`**: These are **aggregation expressions** that compute new fields. `$divide: ["$total_revenue_cents", 100]` converts cents to dollars. `$round: ["$avg_item_value_cents", 0]` rounds to integer.

<!-- TODO: Implement this -->

**Expected Output:**
```json
[
  {
    "supplier_id": "507f1f77bcf86cd799439011",
    "supplier_name": "Artisan Crafts Co",
    "total_revenue_cents": 245000,
    "total_revenue_dollars": 2450.00,
    "total_items_sold": 23,
    "order_count": 15,
    "avg_item_value_cents": 10652
  },
  ...
]
```

---

### Exercise 2: Top Products by Order Count - `$unwind` + `$group`

**Aggregation Concepts**: `$unwind`, `$group`, `$sort`, `$limit`, nested field accumulation

**Business Question**: "Which products are ordered most frequently?"

#### Method: `top_products_by_order_count`
```python
async def top_products_by_order_count(self, limit: int = 10) -> List[Dict]:
```

**The Pipeline:**

```python
# TODO: Implement your pipeline here
pass
```

**Key teaching point - `$unwind` before `$group`:**

```
Order 1: {items: [Widget(qty:2), Gadget(qty:1)]}
Order 2: {items: [Widget(qty:3)]}

After $unwind:
  {item: Widget, qty:2, order:1}
  {item: Gadget, qty:1, order:1}
  {item: Widget, qty:3, order:2}

After $group by product_id:
  Widget: {times_ordered: 2, total_quantity: 5}
  Gadget: {times_ordered: 1, total_quantity: 1}
```

Without `$unwind`, you couldn't count individual products across orders because each order contains an array of items.

<!-- TODO: Implement this -->

---

### Exercise 3: Orders with Product Details - `$lookup` (Cross-Collection Join)

**Aggregation Concepts**: `$lookup`, `$unwind` (for flattening join results), pipeline inside `$lookup`

**Business Question**: "For a given supplier, show their orders enriched with current product information."

#### Method: `orders_with_product_details`
```python
async def orders_with_product_details(
    self, supplier_id: str, limit: int = 20
) -> List[Dict]:
```

**The Pipeline (using raw motor for cross-collection `$lookup`):**

```python
# TODO: Implement your pipeline here
pass
```

**Understanding `$lookup`:**

```
$lookup is a LEFT OUTER JOIN:

orders collection          products collection
+--------------+           +---------------+
| order_item   |           | product       |
| product_id --+---JOIN--->| _id           |
|              |           | name          |
|              |           | price         |
+--------------+           +---------------+

Result: each order item gets a "current_product" array
        (empty if product was deleted)
```

**Key options:**
- `from`: The collection to join with (string name, not the model)
- `localField`: The field in the current document to match
- `foreignField`: The field in the `from` collection to match against
- `as`: The output array field name

**`preserveNullAndEmptyArrays: True`**: Without this, orders for deleted products would be dropped from the results. With it, `current_product` is `null` for deleted products - which is exactly what we want (we can show "Product no longer available").

<!-- TODO: Implement this -->

---

### Exercise 4: Post Engagement Report - `$project` + `$addFields`

**Aggregation Concepts**: `$addFields`, `$project`, `$cond`, `$divide`, `$multiply`, `$switch`, computed fields

**Business Question**: "Generate an engagement report for published posts with computed metrics like like-to-view ratio and engagement tiers."

#### Method: `post_engagement_report`
```python
async def post_engagement_report(self) -> List[Dict]:
```

**The Pipeline:**

```python
# TODO: Implement your pipeline here
pass
```

**Key aggregation expressions:**

**`$addFields`** vs **`$project`**: `$addFields` adds new fields while keeping ALL existing fields. `$project` explicitly includes/excludes fields. Use `$addFields` for intermediate computation, `$project` for final output shaping.

**`$switch`**: MongoDB's equivalent of SQL's `CASE WHEN`. Each `branch` has a `case` (condition) and `then` (value). The `default` handles unmatched cases.

**`$add`**: Adds multiple numeric values together. Used here to compute total interactions from separate stat counters.

**`$substr`**: Extracts a substring. `$substr: ["$text_content", 0, 80]` takes the first 80 characters as a preview.

<!-- TODO: Implement this -->

---

### Exercise 5: Product Price Distribution - `$bucket`

**Aggregation Concepts**: `$bucket`, `$push`, `$sum`, range-based grouping

**Business Question**: "How are our product prices distributed? How many products in each price range?"

#### Method: `product_price_distribution`
```python
async def product_price_distribution(self) -> List[Dict]:
```

**The Pipeline:**

```python
# TODO: Implement your pipeline here
pass
```

**Understanding `$bucket`:**

```
Products:  Widget($5), Gadget($15), Tool($80), Machine($200)

$bucket with boundaries [0, 1000, 5000, 10000, 25000]:

Bucket $0-$9.99:    [Widget($5)]           -> count: 1
Bucket $10-$49.99:  [Gadget($15)]          -> count: 1
Bucket $50-$99.99:  [Tool($80)]            -> count: 1
Bucket $100-$249.99:[Machine($200)]        -> count: 1
```

Each document falls into the bucket where `boundaries[i] <= value < boundaries[i+1]`.

**`$push` inside `$bucket`**: Collects matching documents into an array. We later use `$slice` to take only the first 3 as samples (avoid huge arrays).

**`$addToSet` inside `$bucket`**: Collects unique category values per bucket, so you can see what categories fall into each price range.

<!-- TODO: Implement this -->

---

### Exercise 6: Daily Revenue - `$dateToString` (Time-Series)

**Aggregation Concepts**: `$dateToString`, `$group` by formatted date, `$sort`, `$addFields` with `$sum` as expression, time-series analysis

**Business Question**: "What is our daily revenue trend over the last N days?"

#### Method: `daily_revenue`
```python
async def daily_revenue(self, days: int = 30) -> List[Dict]:
```

**The Pipeline:**

Since Order has no top-level totals field, we first compute each order's total from its items using `$addFields` with `$sum` as an **expression operator** (not as a `$group` accumulator). This is an important distinction:

```python
# TODO: Implement your pipeline here
pass
```

**Understanding `$sum` as expression vs accumulator:**

```python
# AS EXPRESSION (in $addFields/$project) - sums values within a single document
{"$addFields": {"order_total": {"$sum": "$items.total_cents"}}}
# "$items.total_cents" resolves to an ARRAY like [1000, 2000, 500]
# $sum adds them: 3500

# AS ACCUMULATOR (in $group) - sums values across multiple documents
{"$group": {"_id": "$date", "revenue": {"$sum": "$order_total"}}}
# Adds order_total from every document in the group
```

**Understanding `$dateToString`:**

```python
# Input document: {"created_at": ISODate("2025-06-15T14:32:10Z")}
{"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}
# Output: "2025-06-15"

# Used as $group _id, this groups all orders from the same day together
```

**Format tokens**: `%Y` = 4-digit year, `%m` = month, `%d` = day, `%H` = hour.
- Daily: `"%Y-%m-%d"` -> "2025-06-15"
- Monthly: `"%Y-%m"` -> "2025-06"
- Hourly: `"%Y-%m-%dT%H"` -> "2025-06-15T14"

**`$addToSet` for unique counts**: `$addToSet: "$customer.user_id"` collects unique customer IDs per day. Then `$size` counts them. This gives "unique customers per day" without needing `$distinct`.

<!-- TODO: Implement this -->

**Expected Output:**
```json
[
  {"date": "2025-06-01", "revenue_cents": 125000, "revenue_dollars": 1250.00, "order_count": 8, "items_sold": 15, "unique_customer_count": 6},
  {"date": "2025-06-02", "revenue_cents": 89000, "revenue_dollars": 890.00, "order_count": 5, "items_sold": 9, "unique_customer_count": 4},
  ...
]
```

---

### Exercise 7: Top Product Categories - `$sortByCount`

**Aggregation Concepts**: `$sortByCount` (shorthand), and the equivalent `$group` + `$sort` expansion

**Business Question**: "What are the most popular product categories on the platform?"

#### Method: `top_product_categories`
```python
async def top_product_categories(self, limit: int = 10) -> List[Dict]:
```

**The Simple Way - `$sortByCount`:**

```python
# TODO: Implement your pipeline here
pass
```

**`$sortByCount`** is a shorthand that expands to:
```python
# These two are equivalent:
{"$sortByCount": "$category"}

# Expands to:
{"$group": {"_id": "$category", "count": {"$sum": 1}}},
{"$sort": {"count": -1}}
```

**Now enhance it** - add richer metrics per category:

```python
# TODO: Implement your enhanced pipeline here
pass
```

**Accessing embedded stats**: `$stats.view_count` reaches into the embedded `ProductStats` document. MongoDB lets you dot-navigate into any nested field in aggregation expressions, just like in queries.

<!-- TODO: Implement this -->

---

### Exercise 8: Platform Dashboard - `$facet` (The Grand Finale)

**Aggregation Concepts**: `$facet`, multiple parallel pipelines, `$count`, combining results from different collections

**Business Question**: "Generate a complete platform dashboard with stats from every collection in a single operation."

#### Method: `platform_dashboard`
```python
async def platform_dashboard(self) -> Dict[str, Any]:
```

**`$facet` runs multiple pipelines in parallel on the same input:**

```
Input Documents
    |
    +---> Pipeline A (total count)        -> result_a
    +---> Pipeline B (status breakdown)   -> result_b
    +---> Pipeline C (recent activity)    -> result_c
    |
    v
{ result_a: [...], result_b: [...], result_c: [...] }
```

**Step 1: Order Dashboard Facet**

```python
# TODO: Implement your pipeline here
pass
```

**Step 2: Gather stats from other collections**

Since `$facet` runs within ONE collection, you need separate aggregations for other collections:

```python
# TODO: Implement your pipeline here
pass
```

**Step 3: Combine into dashboard**

```python
# TODO: Implement your pipeline here
pass
```

**Why `$facet` is powerful**: Without `$facet`, the order dashboard would require 4 separate database round-trips. With `$facet`, it's 1 round-trip that runs 4 sub-pipelines in parallel on the server.

**Why multiple `$facet` calls**: `$facet` operates within a single collection. To get stats from orders, users, products, posts, and suppliers, you need one `$facet` per collection (5 total round-trips instead of ~15).

<!-- TODO: Implement this -->

---

## 6. VERIFICATION CHECKLIST

Since there are no routes for analytics, verify by calling methods directly or via the MongoDB shell.

### Option A: Python Test Script

Create `test_analytics.py`:

```python
import asyncio
from services.analytics import AnalyticsService

async def main():
    # Initialize Beanie (copy from your app startup)
    analytics = AnalyticsService()

    # Exercise 1
    revenue = await analytics.revenue_by_supplier()
    print("Revenue by supplier:", revenue)

    # Exercise 2
    top_products = await analytics.top_products_by_order_count(limit=5)
    print("Top products:", top_products)

    # ... etc for each exercise

    # Exercise 8
    dashboard = await analytics.platform_dashboard()
    print("Dashboard:", json.dumps(dashboard, indent=2, default=str))

asyncio.run(main())
```

### Option B: MongoDB Shell (mongosh)

You can run any pipeline directly in the shell:

```javascript
// Exercise 1: Revenue by supplier
db.orders.aggregate([
  {$match: {status: {$in: ["confirmed", "processing", "shipped", "delivered"]}}},
  {$unwind: "$items"},
  {$group: {
    _id: "$items.product_snapshot.supplier_id",
    total: {$sum: "$items.total_cents"},
    count: {$sum: 1}
  }},
  {$sort: {total: -1}}
])

// Exercise 5: Price distribution
db.products.aggregate([
  {$match: {status: "active"}},
  {$bucket: {
    groupBy: "$base_price_cents",
    boundaries: [0, 1000, 2500, 5000, 10000, 25000, 50000, 100000],
    default: "expensive",
    output: {count: {$sum: 1}, avg: {$avg: "$base_price_cents"}}
  }}
])
```

### Checklist

- [ ] Exercise 1: Revenue by supplier returns sorted list with dollars/cents
- [ ] Exercise 2: Top products shows order frequency and quantity
- [ ] Exercise 3: `$lookup` enriches orders with current product data
- [ ] Exercise 4: Post engagement report has computed rates and engagement tiers
- [ ] Exercise 5: Price buckets have counts and sample products
- [ ] Exercise 6: Daily revenue shows time series for last N days
- [ ] Exercise 7: Product category frequency sorted by count with price stats
- [ ] Exercise 8: Dashboard combines stats from all 5 collections

---

## 7. ADVANCED CHALLENGES

### Challenge 1: Pipeline Performance Analysis

Run `explain` on your pipelines to see execution stats:

```javascript
db.orders.explain("executionStats").aggregate([
  {$match: {status: {$in: ["confirmed", "processing", "shipped", "delivered"]}}},
  {$unwind: "$items"},
  {$group: {_id: "$items.product_snapshot.supplier_id", total: {$sum: "$items.total_cents"}}}
])
```

**Questions**:
1. Which stages use indexes? Which ones scan in memory?
2. Move the `$match` after `$unwind` and compare the `executionStats`. What changes?
3. Can `$group` ever use an index? Under what conditions?
4. For Exercise 6 (daily revenue), the `[("status", 1), ("created_at", -1)]` index supports the `$match` stage. Re-run explain to confirm.

### Challenge 2: Customer Cohort Analysis

Design a pipeline that groups users by their signup month and tracks their order activity over time:

```
Cohort "2025-01" (users who signed up in January 2025):
  Month 1: 5 orders, $500 revenue
  Month 2: 3 orders, $320 revenue
  Month 3: 2 orders, $210 revenue

Cohort "2025-02" (users who signed up in February 2025):
  Month 1: 8 orders, $750 revenue
  ...
```

**Approach:**
1. Start from the `users` collection
2. `$lookup` to the `orders` collection (join by `customer.user_id`)
3. `$unwind` the joined orders
4. Compute each order's total from items using `$sum`
5. `$group` by signup month + order month
6. Compute cohort metrics

**Questions:**
1. This pipeline joins users -> orders. How would you reverse it (start from orders, lookup users)?
2. What happens to users with zero orders? How does `preserveNullAndEmptyArrays` help?
3. At what data volume does this become impractical? How would you pre-compute cohort data?

### Challenge 3: Window Functions with $setWindowFields

MongoDB 5.0+ supports window functions. Design a pipeline that computes:
- Running total of revenue per day
- 7-day moving average of order count
- Rank of each day's revenue within the month

```javascript
{$setWindowFields: {
  sortBy: {date: 1},
  output: {
    running_total: {
      $sum: "$revenue_cents",
      window: {documents: ["unbounded", "current"]}
    },
    moving_avg_7d: {
      $avg: "$order_count",
      window: {documents: [-6, "current"]}
    },
    revenue_rank: {
      $rank: {},
      window: {partitionBy: {$substr: ["$date", 0, 7]}}
    }
  }
}}
```

---

## 8. COURSE COMPLETION

Congratulations! You've completed all tasks of the MongoDB Advanced Learning course.

### What You've Built

| Task | Domain | Key Skill |
|------|--------|-----------|
| 01 | User | CRUD basics, `find_one`, nested fields, soft delete |
| 02 | Supplier | Complex nested docs, array queries, hard delete |
| 04 | Product | Cross-collection validation, status lifecycle state machine, back-references |
| 05 | Post | Denormalized author snapshots, draft/publish lifecycle, skip/limit pagination |
| 07 | Order | Cross-collection validation chain, product snapshot denormalization, status guards |
| 08 | Analytics | **Aggregation pipelines**: `$group`, `$unwind`, `$lookup`, `$facet`, `$bucket` |

### MongoDB Mastery Checklist

After completing this course, you should be confident with:

- [ ] **Query operators**: `$in`, `$ne`, `$gte`, `$lte`, `$or`, `$and`, `$lt`, `$gt`
- [ ] **Update patterns**: Partial update via `.save()`, status transitions
- [ ] **Aggregation stages**: `$match`, `$group`, `$unwind`, `$lookup`, `$project`, `$addFields`, `$bucket`, `$facet`, `$sortByCount`, `$dateToString`
- [ ] **Aggregation expressions**: `$sum`, `$avg`, `$min`, `$max`, `$first`, `$push`, `$addToSet`, `$size`, `$cond`, `$switch`, `$divide`, `$round`, `$toString`
- [ ] **`$sum` dual usage**: As accumulator in `$group` (sum across docs) vs as expression in `$addFields` (sum within array)
- [ ] **Pagination**: Skip/limit with sort and optional filters
- [ ] **Data patterns**: Denormalization (author/customer/product snapshots), soft delete, status-based lifecycle
- [ ] **Indexing**: Understanding compound indexes and how `$match` uses them
- [ ] **Design patterns**: Cross-collection validation, status guards, utility function delegation
