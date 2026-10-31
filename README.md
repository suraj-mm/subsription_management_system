# 🚀 Brightloop Subscription Management System

> **Odoo Hackathon Kochi — 8-Hour Build Submission**  
> A unified, real-time, high-performance subscription and billing management platform built strictly adhering to ERP principles, robust relational integrity, and strict role-based access control.

---

## 🌟 Quick Start for Evaluators (Zero Setup)

The system is configured to run out-of-the-box with **zero required environment files**. All configuration values have safe local defaults, and the database automatically migrates and seeds the initial administrator account upon startup.

### 1. Prerequisites
- Python 3.10+ (Tested on Python 3.14)

### 2. Install Dependencies
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Run the Backend Server
```bash
uvicorn backend.app.main:app --reload --port 8000
```

### 4. Interactive API Documentation
- **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 🔑 Seeded Credentials for Testing

The application automatically seeds a default system administrator during startup:

| Role | Email | Password | Permissions |
|------|-------|----------|-------------|
| **Admin** | `admin@brightloop.com` | `Admin@12345` | Full system access, staff provisioning, system config |
| **Staff** | *(Create via `/admin/staff`)* | *(Configurable)* | Operational workflows, quotations, billing |
| **Customer** | *(Register via `/auth/signup`)*| *(Configurable)* | Customer portal, personal invoices & subscriptions |

---

## 🏛 Architecture & Enterprise Design Highlights

1. **Zero-Lock Concurrency & Foreign Keys:**
   - Powered by SQLite with `PRAGMA foreign_keys=ON` and `PRAGMA journal_mode=WAL` (Write-Ahead Logging).
   - High-throughput concurrency without database locks during high-traffic reads.
   - Switchable to **PostgreSQL** in production by altering a single `DATABASE_URL` environment variable.

2. **Accurate Financial Modeling:**
   - All monetary calculations (sales price, cost price, discounts, tax rates, invoice amounts) use SQLAlchemy `Numeric(12, 2)` mapped to Python `Decimal`. **Zero floating-point rounding errors.**

3. **Strict Double-Billing Prevention:**
   - Database-level unique constraint on `invoices`: `UniqueConstraint("subscription_id", "period_start")`. Prevents recurring billing overlap even under concurrent requests.

4. **Sub-2-Second Query Performance:**
   - Composite database indexes applied on critical paths:
     - `subscriptions(status, customer_id, next_invoice_date)`
     - `invoices(status, due_date, customer_id)`
     - `payments(invoice_id)`

5. **Direct Bcrypt & Stateless Fingerprinted Reset:**
   - Uses native `bcrypt` (no deprecated passlib dependency).
   - Password reset tokens use cryptographic password fingerprints (`fp = hashed_password[-10:]`). Tokens become instantly invalid once used without maintaining an extra database table.

---

## 📦 Database Schema (All 13 Tables)

1. `users`: Role-based identities (Admin, Staff, Customer), company & tax profile.
2. `products`: Services and goods with standard and cost pricing.
3. `product_variants`: Attributes (e.g., Brand=Odoo) with price delta modifiers (+₹560).
4. `plans`: Recurring periods (daily, weekly, monthly, yearly) and lifecycle flags.
5. `taxes`: Rate rules (e.g. 18% GST).
6. `discounts`: Fixed or percentage discounts with validity dates, minimum quantities, and usage limits.
7. `quotation_templates`: Reusable proposal blueprints.
8. `quotation_template_lines`: Template item line configurations.
9. `subscriptions`: Lifecycle status engine (Draft → Quotation → Confirmed → Active → Paused → Closed).
10. `subscription_lines`: Line items, quantity, unit price, tax, and total.
11. `invoices`: Recurring invoices with status machine (Draft, Confirmed, Paid, Cancelled).
12. `invoice_lines`: Line-by-line billing items.
13. `payments`: Payment records linked to invoices with payment methods (card, bank transfer, UPI).
