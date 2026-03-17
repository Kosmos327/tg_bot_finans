# CODEBASE AUDIT

---

## 1. Project structure

```
tg_bot_finans/
├── .env.example                         # Template for required environment variables
├── .dockerignore
├── Dockerfile                           # Container build for the backend service
├── README.md
├── DEPLOYMENT_AUDIT.md                  # Existing deployment notes
├── requirements.txt                     # Python dependencies
├── app.py                               # Legacy stub (unused by current app)
├── config.py                            # Legacy stub (unused by current app)
│
├── app/                                 # SQLAlchemy ORM layer (shared with backend)
│   ├── __init__.py
│   ├── main.py                          # Legacy ASGI entry point (NOT the active server)
│   ├── core/
│   │   └── config.py                    # Settings loaded from env via pydantic-settings
│   ├── database/
│   │   ├── database.py                  # Async SQLAlchemy engine + get_db() dependency
│   │   ├── models.py                    # ORM models: all tables (roles, managers, deals, …)
│   │   └── schemas.py                   # Legacy ORM schemas (unused by SQL-function routers)
│   ├── crud/                            # Legacy ORM CRUD helpers (unused by active routers)
│   │   ├── billing.py
│   │   ├── clients.py
│   │   ├── deals.py
│   │   ├── expenses.py
│   │   └── managers.py
│   ├── routers/                         # Legacy app/ routers (NOT mounted by active server)
│   │   ├── billing.py
│   │   ├── clients.py
│   │   ├── deals.py
│   │   ├── expenses.py
│   │   ├── managers.py
│   │   └── reports.py
│   └── services/                        # Legacy service layer for app/ routers
│       ├── billing_service.py
│       ├── deal_service.py
│       ├── expense_service.py
│       └── journal_service.py
│
├── backend/                             # ACTIVE backend (FastAPI server)
│   ├── __init__.py
│   ├── main.py                          # ACTIVE entry point: uvicorn backend.main:app
│   ├── config.py                        # Re-exports config/config.py settings (thin shim)
│   ├── dependencies.py                  # Shared FastAPI dependencies
│   ├── models/                          # Pydantic request/response models
│   │   ├── common.py
│   │   ├── deal.py                      # DealUpdate model for PATCH /deals/update/{id}
│   │   ├── schemas.py
│   │   └── settings.py                  # UserAccessResponse, ClientCreate, ManagerCreate, …
│   ├── routers/                         # FastAPI route handlers
│   │   ├── auth.py                      # /auth/* — Mini App login + role-login
│   │   ├── billing.py                   # /billing/* — LEGACY (Sheets-based, kept for compat)
│   │   ├── billing_sql.py               # /billing/v2/* — ACTIVE (PostgreSQL SQL functions)
│   │   ├── dashboard.py                 # /dashboard — analytics dashboard
│   │   ├── deals.py                     # /deal/* — LEGACY ORM-based deals router
│   │   ├── deals_sql.py                 # /deals/* — ACTIVE (PostgreSQL SQL functions/views)
│   │   ├── expenses.py                  # /expenses/* — LEGACY Sheets-based
│   │   ├── expenses_sql.py              # /expenses/v2/* — ACTIVE (PostgreSQL SQL functions)
│   │   ├── journal.py                   # /journal — audit journal
│   │   ├── month_close.py               # /month/* — month archiving/closing
│   │   ├── receivables.py               # /receivables — receivables report
│   │   ├── reports.py                   # /reports — report download (LEGACY)
│   │   └── settings.py                  # /settings/* — reference data CRUD
│   ├── schemas/                         # Pydantic request body schemas
│   │   ├── billing.py                   # BillingUpsertRequest, BillingPayRequest, BillingPaymentMarkRequest
│   │   ├── deals.py                     # DealCreateRequest, DealPayRequest
│   │   ├── expenses.py                  # ExpenseCreateRequest
│   │   └── month_close.py               # ArchiveMonthRequest, CleanupMonthRequest, CloseMonthRequest
│   ├── services/                        # Business logic and integrations
│   │   ├── auth.py                      # Thin wrapper (legacy)
│   │   ├── auth_service.py              # Role-password validation helpers (Sheets-era)
│   │   ├── billing_service.py
│   │   ├── clients_service.py           # get_clients() helper
│   │   ├── db_exec.py                   # call_sql_function / read_sql_view (ACTIVE)
│   │   ├── deal_service.py              # Legacy deal service
│   │   ├── deals.py                     # Legacy deals helpers
│   │   ├── deals_service.py             # Async PG deal CRUD including update_deal_pg()
│   │   ├── expenses_service.py
│   │   ├── journal_service.py           # Audit journal write helpers
│   │   ├── managers_service.py
│   │   ├── miniapp_auth_service.py      # ACTIVE auth: upsert app_users, resolve caller
│   │   ├── permissions.py               # Role constants, editable-field maps
│   │   ├── reports_service.py
│   │   ├── settings_service.py          # Reference data loaders (pg + enriched)
│   │   ├── sheets.py                    # Google Sheets client (legacy)
│   │   ├── sheets_service.py            # Legacy Sheets CRUD
│   │   └── telegram_auth.py             # validate_telegram_init_data / extract_user_from_init_data
│   ├── data/store.js                    # Node.js in-memory store (legacy JS backend, unused)
│   ├── middleware/auth.js               # Node.js auth middleware (legacy, unused)
│   ├── package.json / package-lock.json # Node.js manifest (legacy JS backend)
│   ├── permissions/index.js             # Node.js permission helpers (legacy, unused)
│   ├── routes/                          # Node.js route handlers (legacy, unused)
│   │   ├── analytics.js
│   │   ├── deals.js
│   │   └── journal.js
│   ├── server.js                        # Node.js Express server (legacy, unused)
│   └── tests/                           # Node.js Jest tests (legacy)
│       ├── deals.test.js
│       └── permissions.test.js
│
├── config/
│   └── config.py                        # Settings class (pydantic-settings, reads env vars)
│
├── miniapp/                             # Telegram Mini App static frontend (ACTIVE)
│   ├── app.js                           # Main JS entry point for the Mini App
│   ├── index.html                       # Single-page HTML shell
│   └── styles.css                       # CSS styles
│
├── frontend/                            # Web browser frontend (separate from Mini App)
│   ├── index.html
│   ├── css/styles.css
│   └── js/
│       ├── api.js                       # ApiClient class — calls legacy Node.js /api/* routes
│       ├── app.js                       # Browser-mode app entry point
│       └── permissions.js               # Role-based UI helpers
│
├── bot/                                 # Telegram bot (polling / webhooks)
│   ├── __init__.py
│   ├── bot.py
│   ├── handlers.py                      # aiogram router with bot command handlers
│   ├── keyboards.py
│   └── main.py                          # Standalone bot entry point
│
├── routers/                             # Root-level legacy routers (unused by active server)
│   └── deal_router.py
│
├── services/                            # Root-level legacy services (Sheets-era)
│   ├── deal_service.py
│   ├── journal_service.py
│   └── sheets_service.py
│
├── src/
│   └── settings_parser.py               # Utility to parse settings from config files
│
├── static/
│   └── index.html                       # Placeholder static file
│
└── tests/                               # Python test suite (pytest)
    ├── test_bot_keyboard.py
    ├── test_deal_service.py
    ├── test_health_endpoints.py
    ├── test_init_data_fallback.py
    ├── test_integration_happy_path.py
    ├── test_journal_service.py
    ├── test_miniapp_auth.py
    ├── test_new_features.py
    ├── test_scenario_verification.py
    ├── test_settings_parser.py
    ├── test_sheets_service.py
    ├── test_sheets_utils.py
    ├── test_smoke.py
    └── test_sql_layer.py
```

**Active entry point (backend):** `backend/main.py` — run with:
```
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

**Active frontend entry point:** `miniapp/app.js` loaded by `miniapp/index.html`, served by FastAPI at `/miniapp/*`.

`app/main.py` is a legacy entry point from a previous architecture iteration when the `app/` package was the top-level ASGI application. It was superseded by `backend/main.py` when the project adopted the `backend/` layout and SQL-function-based routers. It is **not** registered in any Dockerfile `CMD` or process manager config found in the repository, and is **not** imported by `backend/main.py`.

---

## 2. Backend (FastAPI)

### How the app starts (`backend/main.py`)

1. Module imports: all routers are imported at the top of `backend/main.py`.
2. A `lifespan()` async context manager is attached to the `FastAPI` application.
3. Inside `lifespan()`, `validate_settings()` (from `config/config.py`) is called first. It raises `RuntimeError` if `DATABASE_URL` is absent, or if `RUN_BOT=true` and `TELEGRAM_BOT_TOKEN` is absent.
4. If the environment variable `RUN_BOT=true`, an aiogram `Dispatcher` is created and bot polling is started as a background `asyncio.Task`.
5. CORS middleware is added with `allow_origins=["*"]`.
6. Routers are registered in this order (order matters — SQL-function routers must precede legacy ones):
   - `deals`, `settings`, `auth`, `dashboard`, `journal`
   - **`deals_sql`**, **`expenses_sql`**, **`billing_sql`**, **`month_close`** (SQL-function routers — registered first)
   - `billing`, `expenses`, `reports`, `receivables` (legacy — registered after)
7. If a `miniapp/` directory exists on disk, its contents are served as static files at `/miniapp`.
8. `GET /health`, `HEAD /health`, `GET /`, `HEAD /` health-check endpoints are added.

---

### Router: `deals_sql.py` (prefix `/deals`)

All endpoints share the same auth fallback chain via `_resolve_user()`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/deals` | List deals from `public.v_api_deals`. Managers see only their own (filtered by `manager_telegram_id`). Other roles can filter by `manager_id`, `client_id`, `status_id`, `business_direction_id`. |
| POST | `/deals/create` | Create a deal via `public.api_create_deal(...)`. Roles: `manager`, `operations_director`, `admin`. |
| POST | `/deals/pay` | Record a payment via `public.api_pay_deal(deal_id, payment_amount, payment_date)`. Roles: `accounting`, `operations_director`, `admin`. |
| GET | `/deals/{deal_id}` | Fetch a single deal from `public.v_api_deals` by integer `id` (or falls back to `deal_id` text column). Managers can only fetch their own deals. |
| PATCH | `/deals/update/{deal_id}` | Update deal fields via `deals_service.update_deal_pg()`. Role-based field filtering applied server-side. Managers can only update their own deals. |

**`GET /deals` — DB operation:**
`SELECT * FROM public.v_api_deals [WHERE ...] ORDER BY created_at DESC`

**`POST /deals/create` — input schema (`DealCreateRequest`):**
```
status_id: int (required)
business_direction_id: int (required)
client_id: int (required)
manager_id: int (required)
charged_with_vat: Decimal (required)
charged_without_vat: Decimal | None
vat_type_id: int | None
vat_rate: Decimal | None
paid: Decimal = 0
project_start_date: date | None
project_end_date: date | None
act_date: date | None
variable_expense_1_without_vat: Decimal | None
variable_expense_2_without_vat: Decimal | None
production_expense_without_vat: Decimal | None
manager_bonus_percent: Decimal | None
source_id: int | None
document_link: str | None
comment: str | None
```

**`POST /deals/create` — DB operation:**
```sql
SELECT * FROM public.api_create_deal(
  :status_id, :business_direction_id, :client_id, :manager_id,
  :charged_with_vat, :charged_without_vat, :vat_type_id, :vat_rate,
  :paid, :project_start_date, :project_end_date, :act_date,
  :variable_expense_1_without_vat, :variable_expense_2_without_vat,
  :production_expense_without_vat, :manager_bonus_percent,
  :source_id, :document_link, :comment
)
```

**`POST /deals/create` — output:** Single dict returned by the SQL function (confirmed deal row).

**`POST /deals/pay` — input schema (`DealPayRequest`):**
```
deal_id: int (required)
payment_amount: Decimal (required)
payment_date: date | None
```

**`POST /deals/pay` — DB operation:**
```sql
SELECT * FROM public.api_pay_deal(:deal_id, :payment_amount, :payment_date)
```

---

### Router: `billing_sql.py` (prefix `/billing/v2`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/billing/v2` | List billing entries from `public.v_api_billing`. Filters: `client_id`, `warehouse_id`, `month` (YYYY-MM). |
| POST | `/billing/v2/upsert` | Create or update a billing entry via `public.api_upsert_billing_entry(...)`. Roles: `manager`, `accounting`, `operations_director`, `admin`. |
| POST | `/billing/v2/pay` | Record a billing payment via `public.api_pay_billing_entry(billing_entry_id, payment_amount, payment_date)`. Roles: `accounting`, `operations_director`, `admin`. |
| GET | `/billing/v2/search` | Search billing entry by `client_id`, `warehouse_id`, `month`, `period`. Returns `{"found": true/false, …entry}`. |
| POST | `/billing/v2/payment/mark` | Mark a deal payment via `public.api_pay_deal(deal_id, payment_amount, payment_date)`. Accepts `deal_id` as numeric string; resolves to integer PK. Roles: `accounting`, `operations_director`, `admin`. |

**`POST /billing/v2/upsert` — input schema (`BillingUpsertRequest`):**
```
client_id: int (required)
warehouse_id: int (required)
month: str YYYY-MM (required)
period: str | None  (p1 / p2)
shipments_with_vat: Decimal | None
shipments_without_vat: Decimal | None
units_count: int | None
storage_with_vat: Decimal | None
storage_without_vat: Decimal | None
pallets_count: int | None
returns_pickup_with_vat: Decimal | None
returns_pickup_without_vat: Decimal | None
returns_trips_count: int | None
additional_services_with_vat: Decimal | None
additional_services_without_vat: Decimal | None
penalties: Decimal | None
vat_type_id: int | None
comment: str | None
```

**`POST /billing/v2/payment/mark` — input schema (`BillingPaymentMarkRequest`):**
```
deal_id: str (required — numeric string)
payment_amount: Decimal (required)
payment_date: date | None
```

---

### Router: `expenses_sql.py` (prefix `/expenses/v2`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/expenses/v2` | List expenses from `public.v_api_expenses`. Optional filter: `deal_id`. |
| POST | `/expenses/v2/create` | Create expense via `public.api_create_expense(...)`. Roles: `manager`, `accounting`, `operations_director`, `admin`. `created_by` is set server-side from the resolved `user_id`. |

**`POST /expenses/v2/create` — input schema (`ExpenseCreateRequest`):**
```
deal_id: int | None
category_level_1_id: int | None
category_level_2_id: int | None
amount_without_vat: Decimal (required)
vat_type_id: int | None
vat_rate: Decimal | None
comment: str | None
expense_type: str | None  (legacy, not sent to SQL function)
category_level_1: str | None  (legacy, not sent to SQL function)
category_level_2: str | None  (legacy, not sent to SQL function)
```

**`POST /expenses/v2/create` — DB operation:**
```sql
SELECT * FROM public.api_create_expense(
  :deal_id, :category_level_1_id, :category_level_2_id,
  :amount_without_vat, :vat_type_id, :vat_rate, :comment, :created_by
)
```

---

### Router: `month_close.py` (prefix `/month`)

All month-close write operations require role `operations_director` or `admin`.

| Method | Path | DB operation |
|--------|------|--------------|
| POST | `/month/archive` | `SELECT * FROM public.archive_month(:year, :month, :dry_run)` |
| POST | `/month/cleanup` | `SELECT * FROM public.cleanup_month(:year, :month)` |
| POST | `/month/close` | `SELECT * FROM public.close_month(:year, :month, :comment)` |
| GET | `/month/archive-batches` | `SELECT * FROM public.archive_batches [WHERE …] ORDER BY created_at DESC` |
| GET | `/month/archived-deals` | `SELECT * FROM public.v_archived_deals [WHERE …] ORDER BY archived_at DESC` |

Read endpoints (`archive-batches`, `archived-deals`) allow `operations_director`, `accounting`, `admin`.

---

### Router: `auth.py` (prefix `/auth`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/miniapp-login` | Two-path login: auto-login via `init_data` (HMAC-validated Telegram initData), or manual login via `telegram_id + full_name + selected_role + password`. Returns `MiniAppLoginResponse`. |
| POST | `/auth/role-login` | Browser/web-mode login: validates `role + password` against env vars. For `manager` role requires `selected_manager` (`"ekaterina"` or `"yulia"`). Returns `RoleLoginResponse` with `manager_id`. |
| POST | `/auth/validate` | Validates `X-Telegram-Init-Data` HMAC and returns user info + role from settings. |
| GET | `/auth/role` | Returns role and editable fields for the authenticated user from `X-Telegram-Init-Data`. |

---

## 3. Database (PostgreSQL)

All tables are defined in `app/database/models.py`.

### Table: `roles`
| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer | PRIMARY KEY |
| code | String(50) | UNIQUE, NOT NULL |
| name | String(100) | NOT NULL |

### Table: `warehouses`
| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer | PRIMARY KEY |
| code | String(20) | UNIQUE, NOT NULL |
| name | String(100) | NOT NULL |

### Table: `business_directions`
| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer | PRIMARY KEY |
| name | String(100) | UNIQUE, NOT NULL |

### Table: `deal_statuses`
| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer | PRIMARY KEY |
| name | String(50) | UNIQUE, NOT NULL |

### Table: `vat_types`
| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer | PRIMARY KEY |
| name | String(50) | UNIQUE, NOT NULL |
| rate | Numeric(5,2) | nullable |

### Table: `sources`
| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer | PRIMARY KEY |
| name | String(100) | UNIQUE, NOT NULL |

### Table: `expense_categories_level_1`
| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer | PRIMARY KEY |
| name | String(100) | UNIQUE, NOT NULL |

### Table: `expense_categories_level_2`
| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer | PRIMARY KEY |
| parent_id | Integer | FK → `expense_categories_level_1.id`, NOT NULL |
| name | String(100) | NOT NULL |

### Table: `app_users`
| Column | Type | Constraints |
|--------|------|-------------|
| id | BigInteger | PRIMARY KEY |
| telegram_id | BigInteger | UNIQUE, NOT NULL |
| full_name | String(200) | NOT NULL |
| username | String(200) | nullable |
| role_id | Integer | FK → `roles.id`, NOT NULL |
| is_active | Boolean | DEFAULT true |
| created_at | DateTime(tz) | server_default=now() |
| updated_at | DateTime(tz) | server_default=now(), onupdate=now() |

### Table: `managers`
| Column | Type | Constraints |
|--------|------|-------------|
| id | BigInteger | PRIMARY KEY, autoincrement |
| manager_name | String(200) | NOT NULL |
| role_id | Integer | FK → `roles.id`, nullable |
| telegram_user_id | BigInteger | UNIQUE, nullable |
| created_at | DateTime(tz) | server_default=now() |
| updated_at | DateTime(tz) | server_default=now(), onupdate=now() |

### Table: `clients`
| Column | Type | Constraints |
|--------|------|-------------|
| id | BigInteger | PRIMARY KEY, autoincrement |
| client_name | String(300) | NOT NULL |
| created_at | DateTime(tz) | server_default=now() |
| updated_at | DateTime(tz) | server_default=now(), onupdate=now() |

### Table: `deals`
| Column | Type | Constraints |
|--------|------|-------------|
| id | BigInteger | PRIMARY KEY, autoincrement |
| manager_id | BigInteger | FK → `managers.id`, nullable |
| client_id | BigInteger | FK → `clients.id`, nullable |
| status | String(50) | nullable |
| business_direction | String(100) | nullable |
| deal_name | String(300) | nullable |
| description | Text | nullable |
| amount_with_vat | Numeric(15,2) | nullable |
| vat_rate | Numeric(5,2) | nullable |
| vat_amount | Numeric(15,2) | nullable |
| amount_without_vat | Numeric(15,2) | nullable |
| paid_amount | Numeric(15,2) | DEFAULT 0 |
| remaining_amount | Numeric(15,2) | nullable |
| variable_expense_1 | Numeric(15,2) | nullable |
| variable_expense_2 | Numeric(15,2) | nullable |
| production_expense | Numeric(15,2) | nullable |
| manager_bonus_pct | Numeric(5,2) | nullable |
| manager_bonus_amount | Numeric(15,2) | nullable |
| marginal_income | Numeric(15,2) | nullable |
| gross_profit | Numeric(15,2) | nullable |
| source | String(100) | nullable |
| document_url | Text | nullable |
| comment | Text | nullable |
| act_date | DateTime(tz) | nullable |
| date_start | DateTime(tz) | nullable |
| date_end | DateTime(tz) | nullable |
| created_at | DateTime(tz) | server_default=now() |
| updated_at | DateTime(tz) | server_default=now(), onupdate=now() |

### Table: `billing_entries`
| Column | Type | Constraints |
|--------|------|-------------|
| id | BigInteger | PRIMARY KEY, autoincrement |
| client_id | BigInteger | FK → `clients.id`, nullable |
| warehouse_id | Integer | FK → `warehouses.id`, nullable |
| month | String(7) | nullable (YYYY-MM) |
| period | String(10) | nullable (p1/p2) |
| shipments_with_vat | Numeric(15,2) | nullable |
| shipments_vat | Numeric(15,2) | nullable |
| shipments_without_vat | Numeric(15,2) | nullable |
| units_count | Integer | nullable |
| storage_with_vat | Numeric(15,2) | nullable |
| storage_vat | Numeric(15,2) | nullable |
| storage_without_vat | Numeric(15,2) | nullable |
| pallets_count | Integer | nullable |
| returns_pickup_with_vat | Numeric(15,2) | nullable |
| returns_pickup_vat | Numeric(15,2) | nullable |
| returns_pickup_without_vat | Numeric(15,2) | nullable |
| returns_trips_count | Integer | nullable |
| additional_services_with_vat | Numeric(15,2) | nullable |
| additional_services_vat | Numeric(15,2) | nullable |
| additional_services_without_vat | Numeric(15,2) | nullable |
| penalties | Numeric(15,2) | nullable |
| total_without_vat | Numeric(15,2) | nullable |
| total_vat | Numeric(15,2) | nullable |
| total_with_vat | Numeric(15,2) | nullable |
| payment_status | String(50) | nullable |
| payment_amount | Numeric(15,2) | nullable |
| payment_date | DateTime(tz) | nullable |
| created_at | DateTime(tz) | server_default=now() |
| updated_at | DateTime(tz) | server_default=now(), onupdate=now() |

### Table: `expenses`
| Column | Type | Constraints |
|--------|------|-------------|
| id | BigInteger | PRIMARY KEY, autoincrement |
| deal_id | BigInteger | FK → `deals.id`, nullable |
| category_level_1 | String(100) | nullable |
| category_level_2 | String(100) | nullable |
| expense_type | String(50) | nullable |
| amount_with_vat | Numeric(15,2) | nullable |
| vat_rate | Numeric(5,2) | nullable |
| vat_amount | Numeric(15,2) | nullable |
| amount_without_vat | Numeric(15,2) | nullable |
| comment | Text | nullable |
| created_by | String(200) | nullable |
| created_at | DateTime(tz) | server_default=now() |

### Table: `journal_entries`
| Column | Type | Constraints |
|--------|------|-------------|
| id | BigInteger | PRIMARY KEY, autoincrement |
| user_id | String(100) | nullable |
| role_name | String(50) | nullable |
| action | String(100) | NOT NULL |
| entity | String(100) | nullable |
| entity_id | String(100) | nullable |
| details | Text | nullable |
| created_at | DateTime(tz) | server_default=now() |

### How deals are stored

Deals are written via the PostgreSQL SQL function `public.api_create_deal(...)`. The ORM `Deal` model in `app/database/models.py` mirrors the `deals` table but is used only for read operations and updates (`update_deal_pg`). All FK columns (`manager_id`, `client_id`) are nullable at the ORM level, but the SQL function `public.api_create_deal` is called with non-null values from the validated request.

### How `manager_id` is used

`deals.manager_id` is a `BigInteger` FK pointing to `managers.id`. In the Mini App, the frontend resolves the integer `manager_id` from the enriched settings (`/settings/enriched`). For users with `role=manager`, the `manager_id` is stored in `localStorage` after web login (returned by `/auth/role-login` from `ID_MANAGER_*` env vars). For other roles, the dropdown value from the form is used.

### Constraints confirmed from ORM models

- `app_users.telegram_id` — UNIQUE
- `managers.telegram_user_id` — UNIQUE, nullable
- `roles.code` — UNIQUE
- `warehouses.code` — UNIQUE
- `business_directions.name` — UNIQUE
- `deal_statuses.name` — UNIQUE
- `vat_types.name` — UNIQUE
- `sources.name` — UNIQUE
- `expense_categories_level_1.name` — UNIQUE
- `deals.manager_id` FK → `managers.id` (nullable — no NOT NULL enforced at ORM level)
- `deals.client_id` FK → `clients.id` (nullable)
- `billing_entries.client_id` FK → `clients.id` (nullable)
- `billing_entries.warehouse_id` FK → `warehouses.id` (nullable)
- `expenses.deal_id` FK → `deals.id` (nullable)
- `app_users.role_id` FK → `roles.id` (NOT NULL)

---

## 4. Deal creation flow (CRITICAL)

### Step-by-step trace

**1. Frontend (`miniapp/app.js`) — form collection**

`handleFormSubmit()` is called on deal form `submit` event.
It calls `collectFormDataSql()` which builds the payload:

```javascript
// manager_id resolution:
if (currentRole === 'manager') {
  // Uses manager_id stored in localStorage during /auth/role-login
  managerId = parseInt(localStorage.getItem('manager_id'), 10);
} else {
  // Reads the integer ID from the manager <select> dropdown
  managerId = parseInt(document.getElementById('manager').value, 10);
}

return {
  status_id:                       parseInt(document.getElementById('status').value, 10),
  business_direction_id:           parseInt(document.getElementById('business_direction').value, 10),
  client_id:                       parseInt(document.getElementById('client').value, 10),
  manager_id:                       managerId,
  charged_with_vat:                parseFloat(document.getElementById('charged_with_vat').value),
  vat_type_id:                     parseInt(document.getElementById('vat_type').value, 10),
  vat_rate:                        parseFloat(document.getElementById('vat_rate').value),
  paid:                            parseFloat(document.getElementById('paid').value) || 0,
  project_start_date:              document.getElementById('project_start_date').value || null,
  project_end_date:                document.getElementById('project_end_date').value || null,
  act_date:                        document.getElementById('act_date').value || null,
  variable_expense_1_without_vat:  parseFloat(document.getElementById('variable_expense_1').value),
  variable_expense_2_without_vat:  parseFloat(document.getElementById('variable_expense_2').value),
  production_expense_without_vat:  parseFloat(document.getElementById('general_production_expense').value)
                                   || parseFloat(document.getElementById('production_expense_with_vat').value),
  manager_bonus_percent:           parseFloat(document.getElementById('manager_bonus_percent').value),
  source_id:                       parseInt(document.getElementById('source').value, 10),
  document_link:                   document.getElementById('document_link').value || null,
  comment:                         document.getElementById('comment').value || null,
};
```

**2. Frontend — HTTP request**

```javascript
apiFetch('/deals/create', {
  method: 'POST',
  body: JSON.stringify(dealData),
});
```

Auth headers attached automatically by `getAuthHeaders()`:
- `X-Telegram-Init-Data`: raw Telegram `initData` string (if inside Telegram)
- `X-Telegram-Id`: Telegram user ID (from `telegramUser.id` or `localStorage.get('telegram_id')`)
- `X-User-Role`: role string from `localStorage.get('user_role')`

**3. Backend (`deals_sql.py`) — endpoint receives request**

`POST /deals/create` handler:
1. Calls `_resolve_user(db, x_telegram_id, x_telegram_init_data, x_user_role)`.
2. Returns 403 if role is `no_access`.
3. Returns 403 if role not in `("manager", "operations_director", "admin")`.
4. Calls `body.model_dump()` to convert the Pydantic `DealCreateRequest` to a `params` dict.

**4. Backend — SQL call**

```python
sql = (
  "SELECT * FROM public.api_create_deal("
  ":status_id, :business_direction_id, :client_id, :manager_id, "
  ":charged_with_vat, :charged_without_vat, :vat_type_id, :vat_rate, "
  ":paid, :project_start_date, :project_end_date, :act_date, "
  ":variable_expense_1_without_vat, :variable_expense_2_without_vat, "
  ":production_expense_without_vat, :manager_bonus_percent, "
  ":source_id, :document_link, :comment"
  ")"
)
result = await call_sql_function_one(db, sql, params)
```

`call_sql_function_one` calls `call_sql_function` which does:
```python
await db.execute(text(sql), params)
```

SQLAlchemy's `text()` with asyncpg translates each named `:name` placeholder into a positional `$N` in the order they first appear in the SQL string. **The positional order sent to PostgreSQL is:**

| Position | Parameter name | Source in request |
|----------|---------------|-------------------|
| $1 | status_id | `DealCreateRequest.status_id` |
| $2 | business_direction_id | `DealCreateRequest.business_direction_id` |
| $3 | client_id | `DealCreateRequest.client_id` |
| $4 | manager_id | `DealCreateRequest.manager_id` |
| $5 | charged_with_vat | `DealCreateRequest.charged_with_vat` |
| $6 | charged_without_vat | `DealCreateRequest.charged_without_vat` |
| $7 | vat_type_id | `DealCreateRequest.vat_type_id` |
| $8 | vat_rate | `DealCreateRequest.vat_rate` |
| $9 | paid | `DealCreateRequest.paid` |
| $10 | project_start_date | `DealCreateRequest.project_start_date` |
| $11 | project_end_date | `DealCreateRequest.project_end_date` |
| $12 | act_date | `DealCreateRequest.act_date` |
| $13 | variable_expense_1_without_vat | `DealCreateRequest.variable_expense_1_without_vat` |
| $14 | variable_expense_2_without_vat | `DealCreateRequest.variable_expense_2_without_vat` |
| $15 | production_expense_without_vat | `DealCreateRequest.production_expense_without_vat` |
| $16 | manager_bonus_percent | `DealCreateRequest.manager_bonus_percent` |
| $17 | source_id | `DealCreateRequest.source_id` |
| $18 | document_link | `DealCreateRequest.document_link` |
| $19 | comment | `DealCreateRequest.comment` |

This order **must match** the PostgreSQL function signature of `public.api_create_deal`.

**5. `manager_id` — where it comes from**

- **Telegram Mini App (manager role):** Stored in `localStorage` as `manager_id` during `/auth/role-login`. The `/auth/role-login` endpoint reads it from the `ID_MANAGER_EKATERINA` or `ID_MANAGER_YULIA` environment variable and returns it in `RoleLoginResponse.manager_id`. The Mini App stores it client-side.
- **Telegram Mini App (other roles):** Selected from the manager `<select>` dropdown, populated from `/settings/enriched` which returns `{id, name}` objects from the `managers` DB table.

**Validation of `manager_id`:**
- The Pydantic schema `DealCreateRequest` validates that `manager_id` is an `int` (not null). No FK existence check is performed in the Python layer. FK enforcement is done by PostgreSQL inside `public.api_create_deal`. A missing `manager_id` in the `managers` table causes `asyncpg` to raise a `DBAPIError` which is caught and re-raised as `HTTPException(422)`.

---

## 5. Auth system

### Login paths

**Path A — Telegram Mini App auto-login**

1. On `DOMContentLoaded`, `loginWithTelegram()` is called if `hasTelegramAuthContext()` is true.
2. It calls `POST /auth/miniapp-login` with `{ init_data: tg.initData }`.
3. Backend validates the HMAC signature using `validate_telegram_init_data(init_data, bot_token)`:
   - Computes `secret_key = HMAC-SHA256(key="WebAppData", msg=bot_token)`.
   - Computes `computed_hash = HMAC-SHA256(key=secret_key, msg=data_check_string)`.
   - Compares with the `hash=` field from the initData string using `hmac.compare_digest`.
4. If valid, backend extracts `telegram_id` from the `user` field in initData.
5. Looks up `app_users` by `telegram_id`. Returns 403 if not found.
6. Returns `MiniAppLoginResponse(user_id, telegram_id, full_name, username, role)`.
7. Frontend stores `telegram_id` and `user_role` in `localStorage`.

**Path B — Telegram Mini App manual first-time registration**

1. User opens auth screen, selects a role, enters password.
2. Frontend calls `POST /auth/miniapp-login` with `{ telegram_id, full_name, selected_role, password }`.
3. Backend (in `miniapp_auth_service.miniapp_login()`):
   a. Queries `roles` table by `code = selected_role` — raises `ValueError` if not found.
   b. Validates password via `_verify_role_password(selected_role, password)` against `app/core/config.py` settings attributes (`role_password_manager`, `role_password_operations_director`, `role_password_accounting`, `role_password_admin`).
   c. Calls `_upsert_app_user_sql()` which calls `public.upsert_app_user(telegram_id, full_name, username, role_code)` SQL function. Falls back to ORM `_upsert_app_user()` in non-production environments if the SQL function is unavailable.
   d. If role is `manager`, calls `_ensure_manager_record()` which creates or updates the `managers` table entry for this `telegram_user_id`.
4. Returns `MiniAppLoginResponse`.

**Path C — Browser (web) role-login**

1. User opens `/miniapp/index.html` in a browser (no Telegram).
2. User selects role, enters password. For `manager` role, also selects `"ekaterina"` or `"yulia"`.
3. Frontend calls `POST /auth/role-login` with `{ role, password, selected_manager? }`.
4. Backend validates password:
   - For `manager`: compares against `settings.password_manager_ekaterina` or `settings.password_manager_yulia` (from `PASSWORD_MANAGER_EKATERINA`/`PASSWORD_MANAGER_YULIA` env vars).
   - For other roles: calls `verify_role_password(role, password)` which reads `ROLE_PASSWORD_{ROLE}` env vars.
5. Returns `RoleLoginResponse(success, role, role_label, user_id, full_name, manager_id)`.
6. Frontend stores `user_role`, `manager_id` in `localStorage`.

### Passwords storage

All passwords are in environment variables. No passwords are stored in the database.

| Environment variable | Role |
|---------------------|------|
| `ROLE_PASSWORD_MANAGER` | manager (Telegram path) |
| `ROLE_PASSWORD_OPERATIONS_DIRECTOR` | operations_director |
| `ROLE_PASSWORD_ACCOUNTING` | accounting |
| `ROLE_PASSWORD_ADMIN` | admin |
| `PASSWORD_MANAGER_EKATERINA` | manager "Екатерина" (web path) |
| `PASSWORD_MANAGER_YULIA` | manager "Юлия" (web path) |
| `ID_MANAGER_EKATERINA` | manager_id for "Екатерина" (integer string) |
| `ID_MANAGER_YULIA` | manager_id for "Юлия" (integer string) |

### Session storage

Auth data is stored in `localStorage`:
- `user_role` — role string (e.g. `"manager"`)
- `telegram_id` — Telegram user ID (string)
- `manager_id` — manager's integer PK (manager role only)
- `user_id` — app_users PK (set on manual registration)
- `user_name` — full name (set on manual registration)
- `user_role_label` — Russian label for display

### Telegram auth in code

Telegram auth **does** exist in code:
- `backend/services/telegram_auth.py`: `validate_telegram_init_data()` and `extract_user_from_init_data()`.
- Used in `/auth/miniapp-login` (auto-login path) and `resolve_user_from_init_data()` in `miniapp_auth_service.py`.
- Used in `/auth/validate` and `/auth/role` endpoints.
- The HMAC algorithm strictly follows the [official Telegram documentation](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app).

---

## 6. Frontend (Mini App / Web)

### Entry point

`miniapp/app.js` is loaded by `miniapp/index.html`. The script is self-contained (no bundler). It runs `init()` on `DOMContentLoaded`.

### How API calls are made

All API calls go through the `apiFetch(path, options)` helper function:

```javascript
async function apiFetch(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...getAuthHeaders(),  // X-Telegram-Init-Data, X-Telegram-Id, X-User-Role
    ...options.headers,
  };
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) { throw new Error(detail); }
  return response.json();
}
```

`API_BASE` is resolved at startup in this order:
1. `<meta name="api-base">` tag content in `index.html`.
2. `window.APP_CONFIG.apiBase`.
3. `window.location.origin` (same-origin fallback).

### Where auth data is stored

In `localStorage`:
- `user_role` — role string
- `telegram_id` — Telegram user ID as string
- `manager_id` — integer manager PK (manager role only)

### How deal creation UI works

1. `loadSettings()` is called on app init. It fetches `/settings/enriched` and populates all `<select>` dropdowns with `{id, name}` objects (integer IDs as `<option value>`).
2. For `manager` role: the `manager` dropdown is auto-selected from `localStorage.manager_id`.
3. User fills in the form. Required fields: `status`, `business_direction`, `client`, `manager`, `charged_with_vat`, `vat_type`, `project_start_date`, `project_end_date`.
4. On submit, `validateForm()` checks required fields are non-empty.
5. `collectFormDataSql()` builds the payload (integer IDs from dropdowns, floats from numeric inputs).
6. `apiFetch('/deals/create', { method: 'POST', body: JSON.stringify(dealData) })` is called.
7. On success: `showSuccessScreen(dealId)` renders a confirmation.
8. `state.enrichedSettings` must be non-null when submitting, otherwise an error is thrown before the API call.

### How manager is selected

- **Manager role (web login):** `manager_id` is returned from `/auth/role-login` and stored in `localStorage`. On `populateSelects()`, the `manager` dropdown is auto-set to `localStorage.manager_id`.
- **Other roles:** Manager is selected from a dropdown populated from `/settings/enriched` → `managers` array (each item `{id, name}`).

---

## 7. Data flow (end-to-end)

### User creates a deal

1. **Browser loads Mini App** (`GET /miniapp/`).
2. **Telegram SDK init**: `tg = window.Telegram.WebApp`, `tg.ready()`, `telegramUser = tg.initDataUnsafe.user`.
3. **Auto-login attempt**: if `hasTelegramAuthContext()`, calls `POST /auth/miniapp-login` with `{init_data}`. Backend validates HMAC → looks up `app_users` → returns role. Stored to `localStorage`.
4. **Settings load**: `GET /settings/enriched` → returns `{statuses, clients, managers, business_directions, warehouses, vat_types, sources, expense_categories}` with integer IDs. All dropdowns are populated.
5. **User fills deal form**: selects status, direction, client, manager (or auto-selected), enters `charged_with_vat`, optional dates/expenses.
6. **Form submit** → `collectFormDataSql()` builds payload with integer IDs.
7. **`POST /deals/create`** with JSON body + auth headers (`X-Telegram-Id`, `X-User-Role`).
8. **Backend** `deals_sql.py`:
   a. Resolves user from `X-Telegram-Id` → queries `app_users` → gets `role_id` → queries `roles` → confirms role.
   b. Validates role is in `("manager", "operations_director", "admin")`.
   c. Calls `call_sql_function_one(db, sql, params)` → `db.execute(text(sql), params)`.
9. **PostgreSQL** executes `public.api_create_deal($1…$19)`. Performs FK checks (`manager_id` → `managers.id`, `client_id` → `clients.id`). Inserts row into `deals`. Returns the created row.
10. **Backend** returns the result dict as JSON.
11. **Frontend** shows `showSuccessScreen(deal_id)` and a success toast.
12. `state.deals = []` invalidates the local deals cache so the next load fetches fresh data.

### Where the flow may break

- **Step 3**: If `TELEGRAM_BOT_TOKEN` is not set, HMAC validation always fails. Auto-login returns 403, user is redirected to manual auth screen.
- **Step 4**: If `DATABASE_URL` is invalid or DB is unreachable, all endpoints fail with `500`. No graceful degradation except a fallback UI with static dropdown lists (the form loads but deal creation will fail).
- **Step 6**: If `state.enrichedSettings` is `null` (settings fetch failed), `handleFormSubmit` throws before making the API call: `"Справочники не загружены. Перезагрузите страницу и попробуйте снова."`.
- **Step 8a**: If `telegram_id` is not in `app_users` (new user who skipped manual registration), returns 403.
- **Step 9**: If `manager_id` is not a valid FK into `managers.id` (e.g. `ID_MANAGER_EKATERINA` env var contains an ID not present in the DB), PostgreSQL raises a FK constraint violation, caught as `HTTPException(422)`.

---

## 8. Potential problem areas

### 1. Positional parameter order in `public.api_create_deal`

The SQL string in `deals_sql.py` uses named parameters (`:name`) which asyncpg translates to positional `$N` in the order they appear in the string. **If the PostgreSQL function signature does not exactly match this order**, parameters will be silently misassigned (e.g. `manager_id` value sent to wrong column). There is no Python-level validation that the function signature matches the call site. A historical note in the code states this previously caused a FK violation when `:manager_id` and `:charged_with_vat` were swapped.

**Recommendation:** Add an integration test that calls `public.api_create_deal` with known, unique-per-position integer values and asserts the resulting DB row maps each value to the correct column, verifying the call-site order matches the function signature.

### 2. `manager_id` from env var not validated against DB

`ID_MANAGER_EKATERINA` and `ID_MANAGER_YULIA` are read as string env vars and parsed to integers in `/auth/role-login`. If the integer does not correspond to a row in the `managers` table, every deal created by that manager will fail with a FK violation at the PostgreSQL level (not caught until `POST /deals/create` is called).

**Recommendation:** Extend `validate_settings()` (called in `lifespan()`) to query the `managers` table and confirm that the configured `ID_MANAGER_*` values exist as primary keys, failing fast at startup if they do not.

### 3. Dual settings read path (`app/core/config.py` vs `config/config.py`)

`miniapp_auth_service.py` imports from `app.core.config.settings`. The `backend/routers/auth.py` imports from `config.config.settings`. Both define the same env vars but as separate `pydantic-settings` `Settings` instances. If only one is populated (e.g. via `.env` vs environment injection), the other may return empty strings, causing silent auth failures.

### 4. `ROLE_PASSWORD_MANAGER` — two config locations

The password for `manager` role in the **Telegram Mini App path** is read from `app.core.config.settings.role_password_manager` (env var `ROLE_PASSWORD_MANAGER`) inside `miniapp_auth_service._verify_role_password()`. The **web path** (`/auth/role-login`) uses `settings.password_manager_ekaterina` / `settings.password_manager_yulia` (different env vars). If `ROLE_PASSWORD_MANAGER` is not set but the Telegram Mini App manager tries to register, login will silently fail with "No password configured".

### 5. ORM `Deal` model has `status`/`business_direction` as plain strings

The `Deal` ORM model stores `status` as `String(50)` and `business_direction` as `String(100)`, not FK references. The SQL function endpoints (`/deals/create`) pass integer IDs (`status_id`, `business_direction_id`) to `public.api_create_deal`, so FK enforcement exists there. But the `PATCH /deals/update/{deal_id}` endpoint calls `deals_service.update_deal_pg()` which may accept and write free-form string values directly via ORM, bypassing FK validation.

### 6. No input validation on `manager_id` when role is `manager` (web mode)

In `collectFormDataSql()`, if `localStorage.getItem('manager_id')` is missing or non-numeric, `managerId` becomes `NaN`. The Pydantic schema (`DealCreateRequest`) declares `manager_id: int`, so FastAPI will return a 422 validation error. However, the frontend does not check for `NaN` before submitting, resulting in a confusing validation error rather than a pre-submit warning.

### 7. `state.enrichedSettings` null check after settings fallback

If `/settings/enriched` fails, `state.enrichedSettings` is set to `null` and a fallback settings object (with plain-string lists, no IDs) is used. The form remains usable, but deal creation is blocked at `handleFormSubmit()` with `"Справочники не загружены"` error. This is a correct guard but the UI does not clearly communicate to the user that settings failed and deal creation is blocked.

### 8. `get_db()` commits unconditionally on success

`app/database/database.py`'s `get_db()` always calls `await session.commit()` after the endpoint handler returns without exception. This means any unintentional partial write within a request will be committed. There is no explicit transaction boundary per SQL function call inside the routers; all writes within a single request share one session and one final commit.

### 9. ⚠️ SECURITY: CORS policy is `allow_origins=["*"]`

`backend/main.py` sets `CORSMiddleware(allow_origins=["*"])`. Any web page on any origin can make cross-origin requests to the API. Because auth is carried in custom request headers (`X-Telegram-Init-Data`, `X-Telegram-Id`, `X-User-Role`) rather than cookies, this does not expose existing sessions to CSRF, but it does allow any third-party site that obtains valid auth headers to issue authenticated API requests. **This should be restricted to the known frontend origin(s) in production.**

### 10. Legacy routers still registered

`billing.py`, `expenses.py`, `reports.py` are still registered in `backend/main.py` for backward compatibility. They contain Sheets-based logic. If the Google Sheets integration is no longer configured, requests to these legacy endpoints will fail with unhandled exceptions from the Sheets client rather than informative HTTP errors.

### 11. ⚠️ BUG: `production_expense_without_vat` field name mismatch (form vs schema)

In `collectFormDataSql()`, the field is read from either `general_production_expense` or `production_expense_with_vat` HTML element IDs. The schema field name is `production_expense_without_vat`. The frontend reads from `general_production_expense` (preferred) or `production_expense_with_vat` (fallback). The fallback element name (`production_expense_with_vat`) suggests a VAT-inclusive value, but the schema and SQL function expect a VAT-exclusive (`without_vat`) value. If only the `production_expense_with_vat` element exists in the HTML and the user enters a VAT-inclusive amount, the SQL function will receive a systematically over-stated production expense, silently corrupting the profitability calculation.

**Fix:** Either remove the `production_expense_with_vat` fallback and require `general_production_expense` to be present in all HTML templates, or — if both fields may coexist — apply the VAT deduction to `production_expense_with_vat` before passing it to the schema: `production_expense_without_vat = value / (1 + vat_rate)`.
