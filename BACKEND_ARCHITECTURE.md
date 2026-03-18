# Backend Architecture Map

> **Scope:** Backend/API/database side of the project and every file directly used by it.
> **Methodology:** Confirmed from code only. No guesses. Where something cannot be proven from code, it is explicitly stated.

---

## 1. BACKEND FILE TREE

### Entry Point

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI application factory; CORS middleware; router registration; optional Telegram bot polling |

### Routers

| File | Purpose |
|------|---------|
| `backend/routers/auth.py` | Login endpoints: `/auth/miniapp-login`, `/auth/role-login`, `/auth/validate`, `/auth/role` |
| `backend/routers/deals_sql.py` | **ACTIVE** – Deal CRUD via SQL functions/views (`/deals`) |
| `backend/routers/billing_sql.py` | **ACTIVE** – Billing CRUD via SQL functions/views (`/billing/v2`) |
| `backend/routers/expenses_sql.py` | **ACTIVE** – Expense CRUD via SQL functions/views (`/expenses/v2`) |
| `backend/routers/month_close.py` | **ACTIVE** – Month archive/cleanup/close via SQL functions (`/month`) |
| `backend/routers/settings.py` | Reference data CRUD (`/settings`, `/settings/enriched`, clients, managers, directions, statuses) |
| `backend/routers/dashboard.py` | Role-aware dashboard summaries (`/dashboard`, `/dashboard/owner`, `/dashboard/summary`) |
| `backend/routers/journal.py` | Audit log read/write (`/journal`, `/journal/recent`) – reads from Google Sheets |
| `backend/routers/deals.py` | **LEGACY/DEPRECATED** – ORM-based deal CRUD (`/deal`) |
| `backend/routers/billing.py` | **LEGACY/DEPRECATED** – Sheets-based billing CRUD (`/billing`) |
| `backend/routers/expenses.py` | **LEGACY/DEPRECATED** – Sheets-based expense CRUD (`/expenses`) |
| `backend/routers/reports.py` | Reports download (file too large to read fully; prefix `/reports`) |
| `backend/routers/receivables.py` | Accounts receivable aggregation (`/receivables`) – reads from Google Sheets |

### Services

> **Note on "cannot confirm" entries:** Several service files exist in the repository but were not read during this audit (either because no router imports them, or they are candidates for unused/deprecated code). These are listed with an explicit "I cannot confirm" notice and should be investigated before being modified or deleted.

| File | Purpose |
|------|---------|
| `backend/services/miniapp_auth_service.py` | Mini App auth: login, user upsert, user resolution by telegram_id |
| `backend/services/db_exec.py` | Thin SQL execution layer: `call_sql_function`, `call_sql_function_one`, `read_sql_view` |
| `backend/services/permissions.py` | Role constants (`ALLOWED_ROLES`, `NO_ACCESS_ROLE`), field-level access rules, `verify_role_password` |
| `backend/services/settings_service.py` | Loads reference data from both Google Sheets (legacy) and PostgreSQL ORM (active) |
| `backend/services/deals_service.py` | Google Sheets–based deal CRUD + async PostgreSQL ORM CRUD (`*_pg` functions) |
| `backend/services/billing_service.py` | Google Sheets–based billing CRUD (legacy) |
| `backend/services/expenses_service.py` | Google Sheets–based expense CRUD (legacy) |
| `backend/services/clients_service.py` | PostgreSQL ORM CRUD for `clients` table |
| `backend/services/managers_service.py` | PostgreSQL ORM CRUD for `managers` table |
| `backend/services/telegram_auth.py` | HMAC validation of Telegram initData; user dict extraction |
| `backend/services/sheets_service.py` | Google Sheets connection helpers; sheet name constants |
| `backend/services/sheets.py` | I cannot confirm this from the code — file exists; separate from `sheets_service.py`; no confirmed router imports it |
| `backend/services/auth_service.py` | I cannot confirm this from the code — file exists; no confirmed router imports it |
| `backend/services/auth.py` | I cannot confirm this from the code — file exists; no confirmed router imports it |
| `backend/services/deal_service.py` | I cannot confirm this from the code — file exists; distinct from `deals_service.py`; no confirmed router imports it |
| `backend/services/deals.py` | I cannot confirm this from the code — file exists; distinct from `deals_service.py`; no confirmed router imports it |
| `backend/services/journal_service.py` | Journal append helpers (`append_journal_entry`, `append_new_journal_entry`) |
| `backend/services/reports_service.py` | I cannot confirm this from the code — file exists; likely used by `reports.py` router (not fully read) |

### Schemas

| File | Purpose |
|------|---------|
| `backend/schemas/deals.py` | `DealCreateRequest`, `DealPayRequest` – used by `deals_sql.py` |
| `backend/schemas/billing.py` | `BillingUpsertRequest`, `BillingPayRequest`, `BillingPaymentMarkRequest` – used by `billing_sql.py` |
| `backend/schemas/expenses.py` | `ExpenseCreateRequest` – used by `expenses_sql.py` |
| `backend/schemas/month_close.py` | `ArchiveMonthRequest`, `CleanupMonthRequest`, `CloseMonthRequest` – used by `month_close.py` |
| `backend/models/deal.py` | `DealCreate` (Sheets legacy), `DealUpdate`, `DealResponse` – used by `deals.py` (legacy) and `deals_sql.py` (DealUpdate for PATCH) |
| `backend/models/settings.py` | `SettingsResponse`, `UserAccessResponse`, `ClientCreate/Update`, `ManagerCreate/Update`, `DirectionItem`, `StatusItem` |
| `backend/models/schemas.py` | Legacy bulk schemas: `BillingEntryCreate`, `BillingEntryCreateV2`, `ExpenseCreate`, `ExpenseBulkCreate`, `PaymentMarkRequest`, `JournalEntryNewCreate` |
| `backend/models/common.py` | `SuccessResponse`, `ErrorResponse` |
| `app/database/schemas.py` | I cannot confirm this from the code (file exists but not read in this audit) |

### Database Layer

| File | Purpose |
|------|---------|
| `app/database/database.py` | Async SQLAlchemy engine + session factory; `get_db` dependency |
| `app/database/models.py` | All ORM models: `Role`, `Warehouse`, `BusinessDirection`, `DealStatus`, `VatType`, `Source`, `ExpenseCategoryLevel1/2`, `AppUser`, `Manager`, `Client`, `Deal`, `BillingEntry`, `Expense`, `JournalEntry` |

### Config

| File | Purpose |
|------|---------|
| `config/config.py` | Primary settings class for `backend/`; reads env vars for DB, Telegram, role passwords, manager IDs/passwords |
| `app/core/config.py` | Settings class for `app/` (used by `database.py` and `miniapp_auth_service.py`); includes `app_env` flag |
| `.env.example` | Template for required environment variables |

### SQL/Migrations

No `.sql` dump or migration files were found in the repository. I cannot confirm what SQL functions/views exist beyond what is called from Python code.

---

## 2. ENTRY POINTS

**Main backend entry point:** `backend/main.py`

**How FastAPI app is created:**
```python
app = FastAPI(title="Финансовая система API", version="2.0.0", lifespan=lifespan)
```
The `lifespan` context manager calls `validate_settings()` (checks `DATABASE_URL` is set) and optionally starts Telegram bot polling if `RUN_BOT=true`.

**Router registration order (exact as in `backend/main.py`):**
```
1.  backend.routers.deals          → prefix /deal        (LEGACY)
2.  backend.routers.settings       → no prefix           (ACTIVE)
3.  backend.routers.auth           → prefix /auth        (ACTIVE)
4.  backend.routers.dashboard      → prefix /dashboard   (ACTIVE, mixed Sheets/SQL)
5.  backend.routers.journal        → prefix /journal     (ACTIVE, Sheets)
6.  backend.routers.deals_sql      → prefix /deals       (ACTIVE, SQL)
7.  backend.routers.expenses_sql   → prefix /expenses/v2 (ACTIVE, SQL)
8.  backend.routers.billing_sql    → prefix /billing/v2  (ACTIVE, SQL)
9.  backend.routers.month_close    → prefix /month       (ACTIVE, SQL)
10. backend.routers.billing        → prefix /billing     (LEGACY)
11. backend.routers.expenses       → prefix /expenses    (LEGACY)
12. backend.routers.reports        → prefix unknown       (LEGACY/ACTIVE unclear)
13. backend.routers.receivables    → prefix /receivables  (LEGACY, Sheets)
```

**Route order conflicts:**
- `billing_sql` (prefix `/billing/v2`) is registered at position 8 and `billing` (prefix `/billing`) at position 10. Since `/billing/v2/*` paths are more specific and registered first, they match before `/billing/{warehouse}`. This is the correct and intentional order — the comment in `main.py` explicitly documents that SQL routers must be registered before legacy routers.
- `deals_sql` (prefix `/deals`) at position 6 and `deals` (prefix `/deal`) at position 1 are distinct prefixes, so no conflict.

---

## 3. ROUTER MAP

### `backend/routers/auth.py` — Active

**Prefix:** `/auth`

| Method | Path | Purpose | Service Called | DB Access |
|--------|------|---------|---------------|-----------|
| POST | `/auth/miniapp-login` | Dual-mode login: auto-login via `init_data` HMAC or manual login via telegram_id+password | `miniapp_auth_service.miniapp_login`, `miniapp_auth_service.get_user_by_telegram_id`, `miniapp_auth_service.get_role_code` | `app_users`, `roles`, `managers` tables via ORM; `public.upsert_app_user()` SQL function |
| POST | `/auth/role-login` | Browser/web mode: validate role+password, return role and optional manager_id | `permissions.verify_role_password` | No DB access; ENV vars only |
| POST | `/auth/validate` | Validate Telegram initData; return user info with role | `telegram_auth.validate_telegram_init_data`, `settings_service.get_user_role` | Google Sheets roles mapping (via `settings_service`) |
| GET | `/auth/role` | Return role and editable fields for caller | `telegram_auth.extract_user_from_init_data`, `settings_service.get_user_role` | Google Sheets roles mapping |

**Frontend screens likely using this router:** Login page (all modes), session initialization.

---

### `backend/routers/deals_sql.py` — Active

**Prefix:** `/deals`

| Method | Path | Purpose | Auth Headers | Role Check | DB Path |
|--------|------|---------|-------------|-----------|---------|
| GET | `/deals` | List deals from view; managers see only own | X-Telegram-Id, X-Telegram-Init-Data, X-User-Role | Any authenticated role | `public.v_api_deals` |
| GET | `/deals/{deal_id}` | Single deal from view; managers see only own | X-Telegram-Id, X-Telegram-Init-Data, X-User-Role | Any authenticated role | `public.v_api_deals` |
| POST | `/deals/create` | Create deal via SQL function | X-Telegram-Id, X-Telegram-Init-Data, X-User-Role | manager, operations_director, admin | `public.api_create_deal(...)` |
| POST | `/deals/pay` | Record deal payment via SQL function | X-Telegram-Id, X-Telegram-Init-Data, X-User-Role | accounting, operations_director, admin | `public.api_pay_deal(...)` |
| PATCH | `/deals/update/{deal_id}` | Update deal fields via ORM (no SQL function yet) | X-Telegram-Id, X-Telegram-Init-Data, X-User-Role | Any authenticated role; managers restricted to own deals | `deals_service.update_deal_pg(db, ...)` → `deals` table ORM |

**Service functions called:** `miniapp_auth_service.get_user_by_telegram_id`, `miniapp_auth_service.get_role_code`, `miniapp_auth_service.resolve_user_from_init_data`, `db_exec.call_sql_function_one`, `db_exec.read_sql_view`, `deals_service.update_deal_pg`

---

### `backend/routers/billing_sql.py` — Active

**Prefix:** `/billing/v2`

| Method | Path | Purpose | Auth Headers | Role Check | DB Path |
|--------|------|---------|-------------|-----------|---------|
| GET | `/billing/v2` | List billing entries; optional client_id, warehouse_id, month filters | X-Telegram-Id, X-Telegram-Init-Data, X-User-Role | Any authenticated role | `public.v_api_billing` |
| GET | `/billing/v2/search` | Find one billing entry by client_id, warehouse_id, month, period | X-Telegram-Id, X-Telegram-Init-Data, X-User-Role | Any authenticated role | `public.v_api_billing` |
| POST | `/billing/v2/upsert` | Create or update billing entry | X-Telegram-Id, X-Telegram-Init-Data, X-User-Role | manager, accounting, operations_director, admin | `public.api_upsert_billing_entry(...)` |
| POST | `/billing/v2/pay` | Record payment on a billing entry | X-Telegram-Id, X-Telegram-Init-Data, X-User-Role | accounting, operations_director, admin | `public.api_pay_billing_entry(...)` |
| POST | `/billing/v2/payment/mark` | Mark a deal payment (deal-level payment from billing screen) | X-Telegram-Id, X-Telegram-Init-Data, X-User-Role | accounting, operations_director, admin | `public.api_pay_deal(...)` |

**Service functions called:** `miniapp_auth_service.get_user_by_telegram_id`, `miniapp_auth_service.get_role_code`, `miniapp_auth_service.resolve_user_from_init_data`, `db_exec.call_sql_function_one`, `db_exec.read_sql_view`

---

### `backend/routers/expenses_sql.py` — Active

**Prefix:** `/expenses/v2`

| Method | Path | Purpose | Auth Headers | Role Check | DB Path |
|--------|------|---------|-------------|-----------|---------|
| GET | `/expenses/v2` | List expenses; optional deal_id filter | X-Telegram-Id, X-Telegram-Init-Data, X-User-Role | Any authenticated role | `public.v_api_expenses` |
| POST | `/expenses/v2/create` | Create expense via SQL function | X-Telegram-Id, X-Telegram-Init-Data, X-User-Role | manager, accounting, operations_director, admin | `public.api_create_expense(...)` |

**Service functions called:** `miniapp_auth_service.get_user_by_telegram_id`, `miniapp_auth_service.get_role_code`, `miniapp_auth_service.resolve_user_from_init_data`, `db_exec.call_sql_function_one`, `db_exec.read_sql_view`

---

### `backend/routers/month_close.py` — Active

**Prefix:** `/month`

| Method | Path | Purpose | Auth Headers | Role Check | DB Path |
|--------|------|---------|-------------|-----------|---------|
| POST | `/month/archive` | Archive a month (with optional dry_run) | X-Telegram-Id, X-Telegram-Init-Data, X-User-Role | operations_director, admin | `public.archive_month(year, month, dry_run)` |
| POST | `/month/cleanup` | Clean up staging data for a month | X-Telegram-Id, X-Telegram-Init-Data, X-User-Role | operations_director, admin | `public.cleanup_month(year, month)` |
| POST | `/month/close` | Close a month with comment | X-Telegram-Id, X-Telegram-Init-Data, X-User-Role | operations_director, admin | `public.close_month(year, month, comment)` |
| GET | `/month/archive-batches` | List archive batch records | X-Telegram-Id, X-Telegram-Init-Data, X-User-Role | operations_director, accounting, admin | `public.archive_batches` (table/view) |
| GET | `/month/archived-deals` | List archived deals | X-Telegram-Id, X-Telegram-Init-Data, X-User-Role | operations_director, accounting, admin | `public.v_archived_deals` |

---

### `backend/routers/settings.py` — Active

**Prefix:** none (routes are `/settings`, `/settings/enriched`, etc.)

| Method | Path | Purpose | DB Path |
|--------|------|---------|---------|
| GET | `/settings` | Return reference data (list-of-strings format) | PG ORM: `deal_statuses`, `business_directions`, `vat_types`, `sources`, `clients`, `managers` |
| GET | `/settings/enriched` | Return `{id, name}` enriched data + warehouses + expense categories | PG ORM: same tables + `warehouses`, `expense_categories_level_1/2` |
| GET | `/settings/clients` | List all clients | `clients_service.get_clients(db)` → `clients` table |
| POST | `/settings/clients` | Create client | `clients_service.add_client(db, name)` → `clients` table |
| PUT | `/settings/clients/{client_id}` | Update client name | `clients_service.update_client(db, ...)` → `clients` table |
| DELETE | `/settings/clients/{client_id}` | Delete client | `clients_service.delete_client(db, ...)` → `clients` table |
| GET | `/settings/managers` | List all managers | `managers_service.get_managers(db)` → `managers` table |
| POST | `/settings/managers` | Create manager | `managers_service.add_manager(db, ...)` → `managers` table |
| PUT | `/settings/managers/{manager_id}` | Update manager | `managers_service.update_manager(db, ...)` → `managers` table |
| DELETE | `/settings/managers/{manager_id}` | Delete manager | `managers_service.delete_manager(db, ...)` → `managers` table |
| GET | `/settings/directions` | List business directions | `settings_service.load_business_directions_pg(db)` → `business_directions` table |
| POST | `/settings/directions` | Add direction | `settings_service.add_direction_pg(db, ...)` |
| DELETE | `/settings/directions/{direction}` | Remove direction | `settings_service.delete_direction_pg(db, ...)` |
| GET | `/settings/statuses` | List deal statuses | `settings_service.load_statuses_pg(db)` → `deal_statuses` table |
| POST | `/settings/statuses` | Add status | `settings_service.add_status_pg(db, ...)` |
| DELETE | `/settings/statuses/{status}` | Remove status | `settings_service.delete_status_pg(db, ...)` |

Auth: Settings mutation endpoints accept optional `X-Telegram-Init-Data` and `X-User-Role` headers, resolved by the local `_actor()` helper. Read endpoints require no auth.

---

### `backend/routers/deals.py` — Legacy/Deprecated

**Prefix:** `/deal`

| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| POST | `/deal/create` | Create deal via PG ORM (`deals_service.create_deal_pg`) | Deprecated; superseded by `POST /deals/create` |
| GET | `/deal/all` | Return all deals via PG ORM | Deprecated; superseded by `GET /deals` |
| GET | `/deal/user` | Return deals for current user via PG ORM | Deprecated |
| GET | `/deal/filter` | Filter deals via PG ORM | Deprecated; superseded by `GET /deals` with query params |
| GET | `/deal/{deal_id}` | Get single deal via PG ORM | Deprecated; superseded by `GET /deals/{deal_id}` |
| PUT | `/deal/{deal_id}` | Update deal via PG ORM | Deprecated |
| PATCH | `/deal/update/{deal_id}` | Partially update deal via PG ORM | Deprecated; superseded by `PATCH /deals/update/{deal_id}` |

---

### `backend/routers/billing.py` — Legacy/Deprecated

**Prefix:** `/billing`

| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| GET | `/billing/search` | Text-name-based billing search (warehouse+client string params) | Deprecated; superseded by `GET /billing/v2/search` |
| GET | `/billing/{warehouse}` | List billing entries by warehouse code string | Deprecated; superseded by `GET /billing/v2` |
| GET | `/billing/{warehouse}/{client_name}` | Get single billing entry | Deprecated |
| POST | `/billing/{warehouse}` | Create/update billing entry (Sheets) | Deprecated; superseded by `POST /billing/v2/upsert` |
| POST | `/billing/payment/mark` | Mark deal payment (Sheets) | Deprecated; superseded by `POST /billing/v2/payment/mark` |

**Warning:** `GET /billing/{warehouse}` with `warehouse` = `v2` would be intercepted by the legacy route if `billing_sql` were registered after `billing`. Registration order in `main.py` prevents this: `billing_sql` is registered at position 8, `billing` at position 10.

---

### `backend/routers/expenses.py` — Legacy/Deprecated

**Prefix:** `/expenses`

| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| POST | `/expenses` | Create expense (Sheets) | Deprecated; superseded by `POST /expenses/v2/create` |
| POST | `/expenses/bulk` | Bulk create expenses (Sheets) | Deprecated |
| GET | `/expenses` | List expenses (Sheets) | Deprecated; superseded by `GET /expenses/v2` |

---

### `backend/routers/dashboard.py` — Mixed (Sheets + SQL)

**Prefix:** `/dashboard`

| Method | Path | Purpose | DB Path |
|--------|------|---------|---------|
| GET | `/dashboard` | Role-aware summary (uses Sheets `deals_service.get_all_deals`) | Google Sheets |
| GET | `/dashboard/owner` | Aggregated financial KPIs (Sheets billing + deals) | Google Sheets |
| GET | `/dashboard/summary` | SQL-view-based summary | `public.v_dashboard_summary` |

Auth resolution in `/dashboard` and `/dashboard/owner`: uses legacy Sheets-based `settings_service.get_user_role()` with X-Telegram-Init-Data, with X-User-Role fallback.
Auth resolution in `/dashboard/summary`: uses `_resolve_user_db()` with full X-Telegram-Id → app_users chain.

---

### `backend/routers/journal.py` — Active (Google Sheets only)

**Prefix:** `/journal`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/journal/recent` | Read legacy journal sheet ("Журнал действий") |
| GET | `/journal` | Read new journal sheet ("journal") |
| POST | `/journal` | Append entry to new journal sheet |

Auth: resolved via Sheets-based `settings_service.get_user_role()` from X-Telegram-Init-Data, with X-User-Role fallback.

---

### `backend/routers/receivables.py` — Active (Google Sheets only)

**Prefix:** `/receivables`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/receivables` | Aggregated debt report from billing Sheets |

Auth: Sheets-based resolution; requires `FINANCE_VIEW_ROLES` (operations_director, accounting, admin).

---

## 4. SERVICE MAP

### `backend/services/miniapp_auth_service.py` — Active

**Responsibility:** Full Mini App auth flow: role+password validation, app_users upsert (via SQL function with ORM fallback), manager auto-binding, user resolution for protected endpoints.

**Callers:** `auth.py`, `deals_sql.py`, `billing_sql.py`, `expenses_sql.py`, `month_close.py`, `dashboard.py`

**DB layer:** Async SQLAlchemy ORM (`AppUser`, `Manager`, `Role` models) + `public.upsert_app_user()` SQL function (primary write path)

**Key functions:**
- `miniapp_login(db, telegram_id, full_name, username, selected_role, password, selected_manager)` — full login
- `get_user_by_telegram_id(db, telegram_id)` — read-only user lookup; returns `AppUser` or `None`
- `get_role_code(db, role_id)` — read role code string
- `resolve_user_from_init_data(db, init_data)` — HMAC-validate initData, extract telegram_id, look up app_users; returns `(user_id, role_code, full_name)` or `(None, NO_ACCESS_ROLE, "")`
- `_upsert_app_user_sql(...)` — calls `public.upsert_app_user()`, falls back to ORM in non-production
- `_ensure_manager_record(...)` — create/update `managers` row for manager-role login

---

### `backend/services/db_exec.py` — Active

**Responsibility:** Thin, reusable SQL execution layer for calling PostgreSQL functions and reading views.

**Callers:** `deals_sql.py`, `billing_sql.py`, `expenses_sql.py`, `month_close.py`, `dashboard.py`

**Key functions:**
- `call_sql_function(db, func_call, params)` → `list[dict]`
- `call_sql_function_one(db, func_call, params)` → `dict | None`
- `read_sql_view(db, view_name, where_clause, params, order_by, limit)` → `list[dict]`

Uses `sqlalchemy.text()` with named bind parameters. Converts `DBAPIError` to `ValueError` and `SQLAlchemyError` to `RuntimeError`.

---

### `backend/services/permissions.py` — Active

**Responsibility:** Role constants, editable-field maps, role visibility, `verify_role_password`.

**Callers:** All routers.

**Constants confirmed from code:**
- `ALLOWED_ROLES` = `{"manager", "accountant", "accounting", "operations_director", "head_of_sales", "admin"}`
- `NO_ACCESS_ROLE` = `"no_access"`
- `BILLING_EDIT_ROLES` = `{"manager", "admin"}`
- `EXPENSE_ADD_ROLES` = `{"manager", "accounting", "operations_director", "admin"}`
- `FINANCE_VIEW_ROLES` = `{"operations_director", "accounting", "admin"}`
- `REPORT_DOWNLOAD_ROLES` = `{"operations_director", "accounting", "admin"}`
- `JOURNAL_VIEW_ROLES` = `{"operations_director", "accounting", "admin"}`
- `ADMIN_ROLES` = `{"admin"}`

`verify_role_password(role, password)` reads from env vars at call time via `_load_role_passwords()`.

---

### `backend/services/settings_service.py` — Active (dual: Sheets + PG)

**Responsibility:** Load reference data. Contains both Google Sheets–based functions (legacy) and async PostgreSQL ORM functions (active).

**Active PG functions:**
- `load_all_settings_pg(db)` → dict of string lists (used by `GET /settings`)
- `load_enriched_settings_pg(db)` → dict of `{id, name}` lists + warehouses + expense categories (used by `GET /settings/enriched`)
- `load_statuses_pg(db)`, `load_business_directions_pg(db)` → string lists
- `add_direction_pg`, `delete_direction_pg`, `add_status_pg`, `delete_status_pg` — PG ORM mutations

**Legacy Sheets functions (still present, called by `/auth/validate`, `/auth/role`, `/dashboard`, `/journal`, `/receivables`):**
- `get_user_role(telegram_user_id)` → role string from Sheets roles mapping
- `is_user_active(telegram_user_id)` → bool
- `get_user_full_name(telegram_user_id)` → str
- `load_all_settings()` → dict (Sheets path)

---

### `backend/services/deals_service.py` — Active (PG ORM) + Legacy (Sheets)

**Active PG ORM functions (called by `deals_sql.py` and `deals.py`):**
- `create_deal_pg(db, deal_data, telegram_user_id, user_role, full_name)`
- `get_deal_by_id_pg(db, deal_id)`
- `get_all_deals_pg(db)`
- `get_deals_by_user_pg(db, manager_name)`
- `get_deals_filtered_pg(db, filters)`
- `update_deal_pg(db, deal_id, update_data, telegram_user_id, user_role, full_name)`

**Legacy Sheets functions (called by `dashboard.py`, `billing.py`):**
- `get_all_deals()` — reads from Google Sheets
- `get_deals_by_user(manager_name)` — reads from Google Sheets
- `update_deal(deal_id, update_data, ...)` — writes to Google Sheets
- `get_deal_by_id(deal_id)` — reads from Google Sheets

---

### `backend/services/billing_service.py` — Legacy (Sheets only)

**Responsibility:** CRUD for billing Google Sheets (`billing_msk`, `billing_nsk`, `billing_ekb`).

**Callers:** `billing.py` (legacy router), `dashboard.py`, `receivables.py`

**Key functions:** `get_billing_entries(warehouse)`, `get_billing_entry(warehouse, client_name)`, `upsert_billing_entry(warehouse, entry_data, user, role)`, `search_billing_entry(...)`

---

### `backend/services/expenses_service.py` — Legacy (Sheets only)

**Responsibility:** CRUD for expenses Google Sheet.

**Callers:** `expenses.py` (legacy router)

**Key functions:** `add_expense(data, user, role)`, `add_expenses_bulk(rows, user, role)`, `get_expenses(deal_id, expense_type)`

---

### `backend/services/clients_service.py` — Active (PG ORM)

**Responsibility:** CRUD for `clients` PostgreSQL table.

**Callers:** `settings.py`

---

### `backend/services/managers_service.py` — Active (PG ORM)

**Responsibility:** CRUD for `managers` PostgreSQL table.

**Callers:** `settings.py`

---

### `backend/services/telegram_auth.py` — Active

**Responsibility:** Stateless HMAC validation of Telegram WebApp initData; user dict extraction.

**Key functions:**
- `validate_telegram_init_data(init_data, bot_token)` → `bool`
- `extract_user_from_init_data(init_data)` → `dict | None`

Used by `auth.py`, `deals.py`, `billing.py`, `expenses.py`, `dashboard.py`, `journal.py`, `receivables.py`, `miniapp_auth_service.py`

---

### `backend/services/journal_service.py` — Active (Google Sheets)

**Responsibility:** Append entries to journal Google Sheets.

**Key functions:** `append_journal_entry(...)`, `append_new_journal_entry(...)`

---

## 5. SCHEMA MAP

### `backend/schemas/deals.py`

| Schema | Used By | Required Fields | Key IDs |
|--------|---------|----------------|---------|
| `DealCreateRequest` | `POST /deals/create` | `status_id`, `business_direction_id`, `client_id`, `manager_id`, `charged_with_vat` | `status_id`, `business_direction_id`, `client_id`, `manager_id`, `vat_type_id`, `source_id` — all integers |
| `DealPayRequest` | `POST /deals/pay` | `deal_id`, `payment_amount` | `deal_id` — integer PK of `deals` table |

Note: `DealCreateRequest` contains `charged_without_vat` as an optional field but this field does **not** appear in the `api_create_deal()` SQL function signature and is intentionally excluded from the SQL call. The inline comment in `deals_sql.py` explains the reason: the original code included a spurious `:charged_without_vat` at positional slot 6, which shifted all subsequent arguments and caused FK violations on every deal creation. The fix removed this parameter from the SQL call while keeping the field in the schema for backward compatibility with existing frontend payloads.

---

### `backend/schemas/billing.py`

| Schema | Used By | Required Fields | Key IDs |
|--------|---------|----------------|---------|
| `BillingUpsertRequest` | `POST /billing/v2/upsert` | `client_id`, `warehouse_id`, `month` | `client_id`, `warehouse_id` — integers; `vat_type_id` — integer |
| `BillingPayRequest` | `POST /billing/v2/pay` | `billing_entry_id`, `payment_amount` | `billing_entry_id` — integer PK of `billing_entries` |
| `BillingPaymentMarkRequest` | `POST /billing/v2/payment/mark` | `deal_id` (string), `payment_amount` | `deal_id` — numeric string; converted to int inside handler |

---

### `backend/schemas/expenses.py`

| Schema | Used By | Required Fields | Key IDs |
|--------|---------|----------------|---------|
| `ExpenseCreateRequest` | `POST /expenses/v2/create` | `amount_without_vat` | `deal_id`, `category_level_1_id`, `category_level_2_id`, `vat_type_id` — all optional integers |

---

### `backend/schemas/month_close.py`

| Schema | Used By | Required Fields |
|--------|---------|----------------|
| `ArchiveMonthRequest` | `POST /month/archive` | `year`, `month`, `dry_run` (default False) |
| `CleanupMonthRequest` | `POST /month/cleanup` | `year`, `month` |
| `CloseMonthRequest` | `POST /month/close` | `year`, `month`, `comment` (optional) |

---

### `backend/models/deal.py`

| Schema | Used By | Notes |
|--------|---------|-------|
| `DealCreate` | `POST /deal/create` (legacy) | String-based fields (client/manager by name, not ID) |
| `DealUpdate` | `PATCH /deals/update/{deal_id}` (SQL router) and `PUT/PATCH /deal/{deal_id}` (legacy) | All fields optional; used for both Sheets and PG ORM updates |

---

### `backend/models/settings.py`

| Schema | Used By |
|--------|---------|
| `SettingsResponse` | `GET /settings` response |
| `UserAccessResponse` | `GET /auth/role` response |
| `ClientCreate`, `ClientUpdate` | `POST/PUT /settings/clients` |
| `ManagerCreate`, `ManagerUpdate` | `POST/PUT /settings/managers` |
| `DirectionItem`, `StatusItem` | `POST /settings/directions`, `POST /settings/statuses` |

---

## 6. AUTH FLOW

### Login Endpoints

**`POST /auth/miniapp-login`** (two modes):

1. **Auto-login** (`init_data` field provided):
   - Validates HMAC of Telegram WebApp initData using `settings.telegram_bot_token`
   - Extracts `telegram_id` from user JSON in initData
   - Looks up `app_users` by `telegram_id` via ORM (must already exist from prior manual login)
   - Returns 403 if initData invalid or user not yet registered
   - Returns `{user_id, telegram_id, full_name, username, role}` on success

2. **Manual login** (`telegram_id` + `full_name` + `selected_role` + `password` provided):
   - Validates `selected_role` exists in `roles` table
   - For `manager` role: requires `selected_manager` ("ekaterina" or "yulia"), validates against `settings.password_manager_ekaterina` / `settings.password_manager_yulia` (from env `PASSWORD_MANAGER_EKATERINA` / `PASSWORD_MANAGER_YULIA`)
   - For other roles: validates against `settings.role_password_*` (from env `ROLE_PASSWORD_MANAGER` / `ROLE_PASSWORD_OPERATIONS_DIRECTOR` / `ROLE_PASSWORD_ACCOUNTING` / `ROLE_PASSWORD_ADMIN`)
   - Calls `_upsert_app_user_sql()`: calls `public.upsert_app_user(p_telegram_id, p_full_name, p_username, p_role_code)`, falls back to ORM in non-production
   - For manager role: calls `_ensure_manager_record()` to create/update `managers` row
   - Returns `{user_id, telegram_id, full_name, username, role, manager_id?}`

**`POST /auth/role-login`** (browser/web mode):
- No DB access
- For `manager`: validates against `settings.password_manager_ekaterina` or `settings.password_manager_yulia`; returns `manager_id` from `settings.id_manager_ekaterina` / `settings.id_manager_yulia`
- For other roles: validates via `permissions.verify_role_password()` reading `ROLE_PASSWORD_*` env vars
- Returns `{success, role, role_label, user_id?, full_name?, manager_id?, telegram_id?}`
- Note: `telegram_id` is NOT returned (no Telegram session in browser mode)

**`POST /auth/validate`** (legacy initData validation):
- HMAC-validates X-Telegram-Init-Data header
- Role lookup via `settings_service.get_user_role()` — reads from Google Sheets roles table
- Returns `{valid, user, role, full_name, editable_fields}`

**`GET /auth/role`**:
- Uses X-Telegram-Init-Data header (no HMAC validation against DB; only parses user dict)
- Role resolved via Google Sheets `settings_service.get_user_role()`

### How passwords are checked

- `ROLE_PASSWORD_MANAGER`, `ROLE_PASSWORD_OPERATIONS_DIRECTOR`, `ROLE_PASSWORD_ACCOUNTING`, `ROLE_PASSWORD_ADMIN` — checked in `permissions.verify_role_password()` and `miniapp_auth_service._verify_role_password()`
- `PASSWORD_MANAGER_EKATERINA`, `PASSWORD_MANAGER_YULIA` — checked directly against `settings.password_manager_*` in both `auth.py::role_login` and `miniapp_auth_service.miniapp_login`
- All comparisons use direct string equality (`password == expected`)

### Current user identity on protected endpoints

**Telegram mode (Mini App):**
1. After `/auth/miniapp-login`, frontend stores `telegram_id`
2. On subsequent requests, frontend sends `X-Telegram-Id: {telegram_id}` header
3. Router calls `_resolve_user()` → `get_user_by_telegram_id(db, telegram_id)` → `app_users` lookup → returns `(app_user.id, role_code, app_user.full_name)`
4. `app_user.id` is the integer PK of `app_users` table — used as `created_by_user_id` / `updated_by_user_id` in SQL functions

**Fallback (initData header):**
- If `X-Telegram-Id` absent but `X-Telegram-Init-Data` present: `resolve_user_from_init_data()` HMAC-validates, extracts telegram_id, looks up app_users

**Web/browser mode:**
- Frontend sends `X-User-Role: {role}` header (role set after successful `/auth/role-login`)
- `_resolve_user()` accepts role as-is if it is in `ALLOWED_ROLES`
- `user_id` is set to `""` (empty string) — no DB lookup, no telegram_id
- `created_by_user_id` / `updated_by_user_id` passed to SQL functions is `None` in browser mode

---

## 7. ROLE / ACCESS CONTROL MAP

### ALLOWED_ROLES (defined in `backend/services/permissions.py`)

```
manager, accountant, accounting, operations_director, head_of_sales, admin
```

Note: `accountant` and `head_of_sales` are in `ALLOWED_ROLES` but have NO configured password env vars and no active router role checks. They exist for legacy compatibility. `ROLE_PASSWORD_MANAGER` env var is defined but there is no `_load_role_passwords()["accountant"]` mapping. I cannot confirm `accountant` or `head_of_sales` can actually log in.

### `verify_role_password` (in `permissions.py`)

Loads passwords at call time from OS env vars:
- `ROLE_PASSWORD_MANAGER` → `"manager"`
- `ROLE_PASSWORD_OPERATIONS_DIRECTOR` → `"operations_director"`
- `ROLE_PASSWORD_ACCOUNTING` → `"accounting"`
- `ROLE_PASSWORD_ADMIN` → `"admin"`

`accountant` and `head_of_sales` have no entry in this map → always return `False`.

### Role check locations

| Location | Method | Roles allowed |
|----------|--------|--------------|
| `POST /deals/create` | explicit list | manager, operations_director, admin |
| `POST /deals/pay` | explicit list | accounting, operations_director, admin |
| `PATCH /deals/update/{deal_id}` | any authenticated | all |
| `GET /deals` and `GET /deals/{deal_id}` | any authenticated | all (managers filtered to own) |
| `POST /billing/v2/upsert` | explicit list | manager, accounting, operations_director, admin |
| `POST /billing/v2/pay` | explicit list | accounting, operations_director, admin |
| `POST /billing/v2/payment/mark` | explicit list | accounting, operations_director, admin |
| `GET /billing/v2`, `GET /billing/v2/search` | any authenticated | all |
| `POST /expenses/v2/create` | explicit list | manager, accounting, operations_director, admin |
| `GET /expenses/v2` | any authenticated | all |
| `POST /month/archive`, `POST /month/cleanup`, `POST /month/close` | `_require_month_close_role` | operations_director, admin |
| `GET /month/archive-batches`, `GET /month/archived-deals` | explicit list | operations_director, accounting, admin |
| `GET /dashboard/summary` | explicit list | operations_director, accounting, admin |
| `GET /dashboard/owner` | `_OWNER_ACCESS_ROLES` | operations_director, accounting, admin |
| `GET /journal`, `GET /journal/recent` | `JOURNAL_VIEW_ROLES` | operations_director, accounting, admin |
| `GET /receivables` | `FINANCE_VIEW_ROLES` | operations_director, accounting, admin |

### Manager-only restrictions

- `GET /deals`: managers see only rows where `manager_telegram_id = X-Telegram-Id` (filtered via view column)
- `GET /deals/{deal_id}`: managers denied if `deal.manager_telegram_id != caller_tid`
- `PATCH /deals/update/{deal_id}`: managers denied if deal's `manager_telegram_id != caller_tid`
- `POST /deals/create`: for manager role, `manager_id` in params is overridden with the authenticated manager's DB record ID

### `NO_ACCESS_ROLE` usage

- Returned by `_resolve_user()` when no valid auth header found or user not in `app_users`
- All SQL-function routers return HTTP 403 when `role == NO_ACCESS_ROLE`

---

## 8. DEALS FLOW (BACKEND)

### `GET /deals`

- **Request schema:** Query params: `manager_id?`, `client_id?`, `status_id?`, `business_direction_id?`
- **Headers:** X-Telegram-Id, X-Telegram-Init-Data, X-User-Role
- **Auth resolution:** `_resolve_user()` in `deals_sql.py`
- **Role check:** any authenticated role
- **DB path:** `read_sql_view(db, "public.v_api_deals", where_clause, params, order_by="created_at DESC")`
- **Manager filtering:** WHERE `manager_telegram_id = :tid` (uses caller's telegram_id, NOT manager_id param)
- **Higher role filtering:** WHERE clauses on `manager_id`, `client_id`, `status_id`, `business_direction_id` as integers

---

### `POST /deals/create`

- **Request schema:** `DealCreateRequest` in `backend/schemas/deals.py`
- **Auth resolution:** `_resolve_user(db, x_telegram_id, x_telegram_init_data, x_user_role)` → `(user_id_int, role_code, full_name)`
- **Role check:** must be in `("manager", "operations_director", "admin")`
- **SQL function called:**
  ```sql
  SELECT * FROM public.api_create_deal(
    :created_by_user_id,        -- 1: app_users.id (int) or NULL for browser mode
    :status_id,                 -- 2
    :business_direction_id,     -- 3
    :client_id,                 -- 4
    :manager_id,                -- 5 (overridden for manager role)
    :charged_with_vat,          -- 6
    :vat_type_id,               -- 7
    :vat_rate,                  -- 8
    :paid,                      -- 9
    :project_start_date,        -- 10
    :project_end_date,          -- 11
    :act_date,                  -- 12
    :variable_expense_1_without_vat, -- 13
    :variable_expense_2_without_vat, -- 14
    :production_expense_without_vat, -- 15
    :manager_bonus_percent,     -- 16
    :source_id,                 -- 17
    :document_link,             -- 18
    :comment                    -- 19
  )
  ```
- **`manager_id` handling:** For manager role, the authenticated manager's DB record ID is looked up from `managers` by `telegram_user_id` and overwrites the submitted value
- **`client_id` handling:** Integer from `DealCreateRequest`; must match `clients.id`
- **`created_by_user_id`:** Set to `user_id` if integer (Telegram auth); `None` for browser mode

---

### `POST /deals/pay`

- **Request schema:** `DealPayRequest` — `deal_id: int`, `payment_amount: Decimal`, `payment_date: date?`
- **Auth resolution:** `_resolve_user()` → `(user_id_int, role_code, full_name)`
- **Role check:** must be in `("accounting", "operations_director", "admin")`
- **SQL function called:**
  ```sql
  SELECT * FROM public.api_pay_deal(
    :updated_by_user_id,   -- 1: app_users.id (int) or NULL
    :deal_id,              -- 2: deals.id integer PK
    :payment_amount,       -- 3
    :payment_date          -- 4
  )
  ```

---

### `PATCH /deals/update/{deal_id}`

- **Request schema:** `DealUpdate` (all fields optional) from `backend/models/deal.py`
- **Auth resolution:** `_resolve_user(db, x_telegram_id, x_telegram_init_data, x_user_role)`
- **Role check:** any authenticated role; managers checked against deal ownership via `v_api_deals.manager_telegram_id`
- **DB path:** `deals_service.update_deal_pg(db, deal_id, update_data, telegram_user_id, user_role, full_name)` — uses PG ORM, not a dedicated SQL function

---

## 9. BILLING FLOW (BACKEND)

### `GET /billing/v2`

- **Request schema:** Query params: `client_id?`, `warehouse_id?`, `month?` (YYYY-MM)
- **Auth resolution:** `_resolve_user()` in `billing_sql.py`
- **Role check:** any authenticated role
- **DB path:** `read_sql_view(db, "public.v_api_billing", where_clause, params, order_by="month DESC")`

---

### `GET /billing/v2/search`

- **Request schema:** Query params: `client_id?`, `warehouse_id?`, `month?`, `period?`
- **Constraint:** at least one filter required; returns HTTP 422 otherwise
- **Auth resolution:** `_resolve_user()`
- **Role check:** any authenticated role
- **DB path:** `read_sql_view(db, "public.v_api_billing", ..., limit=1)` → `{"found": True/False, ...entry}`

---

### `POST /billing/v2/upsert`

- **Request schema:** `BillingUpsertRequest`
- **Auth resolution:** `_resolve_user()`
- **Role check:** manager, accounting, operations_director, admin
- **SQL function called:**
  ```sql
  SELECT * FROM public.api_upsert_billing_entry(
    :updated_by_user_id,              -- 1: app_users.id or NULL
    :client_id,                       -- 2: clients.id integer
    :warehouse_id,                    -- 3: warehouses.id integer
    :month,                           -- 4: YYYY-MM string
    :period,                          -- 5: p1/p2 or NULL
    :shipments_with_vat,              -- 6
    :shipments_without_vat,           -- 7
    :units_count,                     -- 8
    :storage_with_vat,                -- 9
    :storage_without_vat,             -- 10
    :pallets_count,                   -- 11
    :returns_pickup_with_vat,         -- 12
    :returns_pickup_without_vat,      -- 13
    :returns_trips_count,             -- 14
    :additional_services_with_vat,    -- 15
    :additional_services_without_vat, -- 16
    :penalties,                       -- 17
    :vat_type_id,                     -- 18
    :comment                          -- 19
  )
  ```
- **`warehouse_id` handling:** Integer from `BillingUpsertRequest`; must match `warehouses.id`
- **`client_id` handling:** Integer from `BillingUpsertRequest`; must match `clients.id`
- **`billing_entry_id` handling:** Not in this request; upsert is keyed by `(client_id, warehouse_id, month, period)` inside the SQL function

---

### `POST /billing/v2/pay`

- **Request schema:** `BillingPayRequest` — `billing_entry_id: int`, `payment_amount: Decimal`, `payment_date: date?`
- **Auth resolution:** `_resolve_user()`
- **Role check:** accounting, operations_director, admin
- **SQL function called:**
  ```sql
  SELECT * FROM public.api_pay_billing_entry(
    :updated_by_user_id,   -- 1: app_users.id or NULL
    :billing_entry_id,     -- 2: billing_entries.id integer PK
    :payment_amount,       -- 3
    :payment_date          -- 4
  )
  ```

---

### `POST /billing/v2/payment/mark`

- **Request schema:** `BillingPaymentMarkRequest` — `deal_id: str`, `payment_amount: Decimal`, `payment_date: date?`
- **Auth resolution:** `_resolve_user()`
- **Role check:** accounting, operations_director, admin
- **`deal_id` resolution:** `int(body.deal_id)` attempted; if non-numeric, searches `v_api_deals` by `deal_id` text column to find integer `id`
- **SQL function called:**
  ```sql
  SELECT * FROM public.api_pay_deal(
    :updated_by_user_id,   -- 1: app_users.id or NULL
    :deal_id,              -- 2: deals.id integer PK
    :payment_amount,       -- 3
    :payment_date          -- 4
  )
  ```

---

### Legacy `/billing` Routes (still present)

| Route | DB Path | Auth |
|-------|---------|------|
| `GET /billing/search` | Google Sheets (`search_billing_entry`) | X-Telegram-Init-Data or X-User-Role |
| `GET /billing/{warehouse}` | Google Sheets (`get_billing_entries`) | X-Telegram-Init-Data or X-User-Role |
| `GET /billing/{warehouse}/{client_name}` | Google Sheets (`get_billing_entry`) | X-Telegram-Init-Data or X-User-Role |
| `POST /billing/{warehouse}` | Google Sheets (`upsert_billing_entry`) | X-Telegram-Init-Data or X-User-Role |
| `POST /billing/payment/mark` | Google Sheets (`update_deal`) | X-Telegram-Init-Data or X-User-Role |

---

## 10. EXPENSES FLOW (BACKEND)

### `GET /expenses/v2`

- **Request schema:** Query param: `deal_id?` (integer)
- **Auth resolution:** `_resolve_user()` in `expenses_sql.py`
- **Role check:** any authenticated role
- **SQL path:** `read_sql_view(db, "public.v_api_expenses", where_clause, params, order_by="created_at DESC")`

---

### `POST /expenses/v2/create`

- **Request schema:** `ExpenseCreateRequest` — required: `amount_without_vat`; optional: `deal_id`, `category_level_1_id`, `category_level_2_id`, `vat_type_id`, `vat_rate`, `comment`
- **Auth resolution:** `_resolve_user()`
- **Role check:** manager, accounting, operations_director, admin
- **`created_by` field:** set to `str(user_id)` if available, else `full_name`
- **SQL function called:**
  ```sql
  SELECT * FROM public.api_create_expense(
    :deal_id,                   -- 1
    :category_level_1_id,       -- 2
    :category_level_2_id,       -- 3
    :amount_without_vat,        -- 4
    :vat_type_id,               -- 5
    :vat_rate,                  -- 6
    :comment,                   -- 7
    :created_by                 -- 8: string (user_id or full_name)
  )
  ```

Note: `created_by_user_id` is NOT passed as a separate integer to `api_create_expense` — only the string `created_by` is used.

---

### Legacy `/expenses` Routes (still present)

| Route | DB Path |
|-------|---------|
| `POST /expenses` | Google Sheets (`add_expense`) |
| `POST /expenses/bulk` | Google Sheets (`add_expenses_bulk`) |
| `GET /expenses` | Google Sheets (`get_expenses`) |

---

## 11. SETTINGS / REFERENCE DATA FLOW

### `GET /settings`

- **Returns:** `{"statuses": [...], "business_directions": [...], "vat_types": [...], "sources": [...], "clients": [...], "managers": [...]}` — all values are plain strings
- **Source tables:** `deal_statuses.name`, `business_directions.name`, `vat_types.name`, `sources.name`, `clients.client_name`, `managers.manager_name`
- **Returns IDs:** No — returns names only
- **Frontend dependency:** Used by legacy deal-create flows that pass string values

---

### `GET /settings/enriched`

- **Returns:** `{"statuses": [{id, name}], "business_directions": [{id, name}], "vat_types": [{id, name}], "sources": [{id, name}], "clients": [{id, name}], "managers": [{id, name}], "warehouses": [{id, name, code}], "expense_categories": [{id, name, sub_categories: [{id, name}]}]}`
- **Source tables:** same as above + `warehouses`, `expense_categories_level_1`, `expense_categories_level_2`
- **Returns IDs:** Yes — all items include `id` field
- **Frontend dependency:** Required for SQL-function-based endpoints that need integer IDs (deals/billing/expenses create)

---

### `GET /settings/clients`

- **Returns:** `[{client_id, client_name, created_at}]`
- **Source:** `clients_service.get_clients(db)` → `clients` table
- **Returns IDs:** Yes (`client_id`)

---

### `GET /settings/managers`

- **Returns:** `[{manager_id, manager_name, role, created_at}]`
- **Source:** `managers_service.get_managers(db)` → `managers` table
- **Returns IDs:** Yes (`manager_id`)

---

### `GET /settings/directions`

- **Returns:** `[str]` — list of direction name strings
- **Source:** `settings_service.load_business_directions_pg(db)` → `business_directions` table

---

### `GET /settings/statuses`

- **Returns:** `[str]` — list of status name strings
- **Source:** `settings_service.load_statuses_pg(db)` → `deal_statuses` table

---

### Warehouse-related settings

- Warehouses are returned as part of `GET /settings/enriched` with `{id, name, code}` objects
- There is no standalone `/settings/warehouses` endpoint
- `warehouse_id` for billing must be obtained from `GET /settings/enriched` → `warehouses` list

---

## 12. DATABASE MAP

### Main Tables (confirmed from `app/database/models.py`)

| Table | ORM Model | Used By |
|-------|----------|---------|
| `roles` | `Role` | `miniapp_auth_service.py` — lookup by code, by id |
| `app_users` | `AppUser` | `miniapp_auth_service.py` — user resolution on every protected endpoint |
| `managers` | `Manager` | `miniapp_auth_service.py` — manager auto-binding; `deals_sql.py` — manager_id resolution |
| `clients` | `Client` | `clients_service.py`, `settings_service.py` |
| `deals` | `Deal` | `deals_service.py` ORM CRUD; also written by `api_create_deal`, `api_pay_deal` SQL functions |
| `billing_entries` | `BillingEntry` | `settings_service.py` (via ORM); written by `api_upsert_billing_entry`, `api_pay_billing_entry` SQL functions |
| `expenses` | `Expense` | Written by `api_create_expense` SQL function |
| `journal_entries` | `JournalEntry` | ORM model defined; I cannot confirm this table is written to from confirmed code paths |
| `warehouses` | `Warehouse` | `settings_service.load_enriched_settings_pg` |
| `business_directions` | `BusinessDirection` | `settings_service.py` |
| `deal_statuses` | `DealStatus` | `settings_service.py` |
| `vat_types` | `VatType` | `settings_service.py` |
| `sources` | `Source` | `settings_service.py` |
| `expense_categories_level_1` | `ExpenseCategoryLevel1` | `settings_service.py` enriched |
| `expense_categories_level_2` | `ExpenseCategoryLevel2` | `settings_service.py` enriched |

### Main Views (confirmed from SQL calls in routers)

| View | Used By |
|------|---------|
| `public.v_api_deals` | `deals_sql.py` — list, get single, update (ownership check) |
| `public.v_api_billing` | `billing_sql.py` — list, search |
| `public.v_api_expenses` | `expenses_sql.py` — list |
| `public.v_archived_deals` | `month_close.py` |
| `public.v_dashboard_summary` | `dashboard.py` |
| `public.archive_batches` | `month_close.py` — treated as a table/view |

### Main SQL Functions (confirmed from SQL call strings in routers)

| Function | Used By | Purpose |
|----------|---------|---------|
| `public.upsert_app_user(p_telegram_id, p_full_name, p_username, p_role_code)` | `miniapp_auth_service.py` | Create/update app_users row |
| `public.api_create_deal(19 params)` | `deals_sql.py` | Create deal record |
| `public.api_pay_deal(p_updated_by_user_id, p_deal_id, p_payment_amount, p_payment_date)` | `deals_sql.py`, `billing_sql.py` | Record deal payment |
| `public.api_upsert_billing_entry(19 params)` | `billing_sql.py` | Create/update billing entry |
| `public.api_pay_billing_entry(p_updated_by_user_id, p_billing_entry_id, p_payment_amount, p_payment_date)` | `billing_sql.py` | Record billing entry payment |
| `public.api_create_expense(8 params)` | `expenses_sql.py` | Create expense record |
| `public.archive_month(year, month, dry_run)` | `month_close.py` | Archive monthly data |
| `public.cleanup_month(year, month)` | `month_close.py` | Clean staging data |
| `public.close_month(year, month, comment)` | `month_close.py` | Close a month |

---

## 13. SQL SIGNATURE MAP

### `public.upsert_app_user`

```
Parameters (positional order as called):
  1. p_telegram_id  BigInt
  2. p_full_name    Text
  3. p_username     Text (nullable)
  4. p_role_code    Text

Called from: miniapp_auth_service._upsert_app_user_sql()
Risk if wrong order: user would be registered with wrong role, or role lookup fails
```

---

### `public.api_create_deal`

```
Parameters (positional order as called in deals_sql.py):
  1.  p_created_by_user_id            Integer (app_users.id) — NULL in browser mode
  2.  p_status_id                     Integer
  3.  p_business_direction_id         Integer
  4.  p_client_id                     Integer
  5.  p_manager_id                    Integer
  6.  p_charged_with_vat              Numeric
  7.  p_vat_type_id                   Integer (nullable)
  8.  p_vat_rate                      Numeric (nullable)
  9.  p_paid                          Numeric (nullable, default 0)
  10. p_project_start_date            Date (nullable)
  11. p_project_end_date              Date (nullable)
  12. p_act_date                      Date (nullable)
  13. p_variable_expense_1_without_vat Numeric (nullable)
  14. p_variable_expense_2_without_vat Numeric (nullable)
  15. p_production_expense_without_vat Numeric (nullable)
  16. p_manager_bonus_percent          Numeric (nullable)
  17. p_source_id                     Integer (nullable)
  18. p_document_link                 Text (nullable)
  19. p_comment                       Text (nullable)

Called from: deals_sql.py::create_deal()
Risk if wrong order: FK violations (wrong client/manager), incorrect financial amounts, deal attributed to wrong user
IMPORTANT: p_charged_without_vat does NOT exist in this signature. DealCreateRequest has
  a `charged_without_vat` field, but it is deliberately excluded from the SQL call.
```

---

### `public.api_pay_deal`

```
Parameters (positional order as called):
  1. p_updated_by_user_id   Integer (app_users.id) — NULL in browser mode
  2. p_deal_id              Integer (deals.id PK)
  3. p_payment_amount       Numeric
  4. p_payment_date         Date (nullable)

Called from: deals_sql.py::pay_deal(), billing_sql.py::mark_deal_payment()
Risk if wrong order: payment recorded on wrong deal, or amount misapplied
```

---

### `public.api_upsert_billing_entry`

```
Parameters (positional order as called):
  1.  p_updated_by_user_id              Integer (app_users.id) — NULL in browser mode
  2.  p_client_id                       Integer
  3.  p_warehouse_id                    Integer
  4.  p_month                           Text (YYYY-MM)
  5.  p_period                          Text (p1/p2) or NULL
  6.  p_shipments_with_vat              Numeric (nullable)
  7.  p_shipments_without_vat           Numeric (nullable)
  8.  p_units_count                     Integer (nullable)
  9.  p_storage_with_vat                Numeric (nullable)
  10. p_storage_without_vat             Numeric (nullable)
  11. p_pallets_count                   Integer (nullable)
  12. p_returns_pickup_with_vat         Numeric (nullable)
  13. p_returns_pickup_without_vat      Numeric (nullable)
  14. p_returns_trips_count             Integer (nullable)
  15. p_additional_services_with_vat    Numeric (nullable)
  16. p_additional_services_without_vat Numeric (nullable)
  17. p_penalties                       Numeric (nullable)
  18. p_vat_type_id                     Integer (nullable)
  19. p_comment                         Text (nullable)

Called from: billing_sql.py::upsert_billing_entry()
Risk if wrong order: billing attributed to wrong client/warehouse, financial amounts in wrong columns
```

---

### `public.api_pay_billing_entry`

```
Parameters (positional order as called):
  1. p_updated_by_user_id   Integer (app_users.id) — NULL in browser mode
  2. p_billing_entry_id     Integer (billing_entries.id PK)
  3. p_payment_amount       Numeric
  4. p_payment_date         Date (nullable)

Called from: billing_sql.py::pay_billing_entry()
Risk if wrong order: payment on wrong entry, amount misapplied
```

---

### `public.api_create_expense`

```
Parameters (positional order as called):
  1. p_deal_id              Integer (nullable)
  2. p_category_level_1_id  Integer (nullable)
  3. p_category_level_2_id  Integer (nullable)
  4. p_amount_without_vat   Numeric
  5. p_vat_type_id          Integer (nullable)
  6. p_vat_rate             Numeric (nullable)
  7. p_comment              Text (nullable)
  8. p_created_by           Text (string, not integer user_id)

Called from: expenses_sql.py::create_expense()
Risk if wrong order: expense attributed to wrong deal, wrong amount
```

---

### `public.archive_month` / `public.cleanup_month` / `public.close_month`

```
archive_month(year INT, month INT, dry_run BOOL)
cleanup_month(year INT, month INT)
close_month(year INT, month INT, comment TEXT)

Called from: month_close.py
Risk if wrong order: wrong month archived/closed, or dry_run ignored
```

---

## 14. LEGACY VS ACTIVE BACKEND LOGIC

### Active SQL-function-based paths

| Area | Router | SQL Function / View |
|------|--------|-------------------|
| Deals list/get | `deals_sql.py` | `public.v_api_deals` |
| Deal create | `deals_sql.py` | `public.api_create_deal` |
| Deal pay | `deals_sql.py` | `public.api_pay_deal` |
| Deal update | `deals_sql.py` | ORM `update_deal_pg` (no dedicated SQL function) |
| Billing list/search | `billing_sql.py` | `public.v_api_billing` |
| Billing upsert | `billing_sql.py` | `public.api_upsert_billing_entry` |
| Billing pay | `billing_sql.py` | `public.api_pay_billing_entry` |
| Deal payment mark | `billing_sql.py` | `public.api_pay_deal` |
| Expenses list | `expenses_sql.py` | `public.v_api_expenses` |
| Expense create | `expenses_sql.py` | `public.api_create_expense` |
| Month close | `month_close.py` | `public.archive_month`, `cleanup_month`, `close_month` |
| User login | `auth.py` + `miniapp_auth_service.py` | `public.upsert_app_user` |
| Dashboard summary | `dashboard.py` `/summary` | `public.v_dashboard_summary` |
| Settings CRUD | `settings.py` | PG ORM (deal_statuses, business_directions, clients, managers, warehouses) |

### Legacy Google Sheets paths (still registered, still receiving requests)

| Area | Router | Sheets Source |
|------|--------|--------------|
| Deal CRUD (name-based) | `deals.py` (`/deal`) | `deals_service.get_all_deals()`, `create_deal()` |
| Billing CRUD (warehouse string) | `billing.py` (`/billing`) | `billing_service.get_billing_entries()` |
| Expenses CRUD | `expenses.py` (`/expenses`) | `expenses_service.add_expense()` |
| Dashboard (role-based) | `dashboard.py` (`/dashboard`, `/dashboard/owner`) | `deals_service.get_all_deals()`, `billing_service.get_billing_entries()` |
| Journal read/write | `journal.py` (`/journal`) | Google Sheets SHEET_JOURNAL / SHEET_JOURNAL_NEW |
| Receivables | `receivables.py` (`/receivables`) | `billing_service.get_billing_entries()` |
| Auth validate/role | `auth.py` (`/auth/validate`, `/auth/role`) | `settings_service.get_user_role()` (Sheets) |

### Dangerous overlap areas

1. **`/billing` vs `/billing/v2`:** Registration order in `main.py` is critical. If `billing_sql` were registered after `billing`, `GET /billing/v2` would be caught by `GET /billing/{warehouse}` with `warehouse="v2"`. Confirmed correct ordering is in place.

2. **`deals_service.update_deal_pg`** is called by both `deals.py` (legacy, `/deal/update/{id}`) and `deals_sql.py` (active, `/deals/update/{id}`). Both share the same underlying ORM function. Changes to `update_deal_pg` affect both routers.

3. **Sheets-based `get_user_role()`** is still called by `auth.py` `/auth/validate` and `/auth/role`, by `dashboard.py` (non-summary endpoints), and by `journal.py`. These endpoints give access based on the Google Sheets roles table, not the `app_users` PostgreSQL table. A user can be active in one system and not the other.

4. **`api_pay_deal` is called from two routers:** `POST /deals/pay` and `POST /billing/v2/payment/mark`. Both routes call the same SQL function with the same parameter order.

### Routes that must not be touched during frontend-only fixes

- `backend/services/db_exec.py`
- `backend/services/miniapp_auth_service.py`
- `backend/services/permissions.py`
- `config/config.py`, `app/core/config.py`
- `app/database/models.py`
- `app/database/database.py`

### Routes that must not be touched during auth-only fixes

- `backend/routers/deals_sql.py` — deal business logic
- `backend/routers/billing_sql.py` — billing business logic
- `backend/routers/expenses_sql.py` — expense business logic
- `backend/schemas/deals.py`, `backend/schemas/billing.py`, `backend/schemas/expenses.py`

---

## 15. FILE RESPONSIBILITY MATRIX

```
FILE: backend/main.py
RESPONSIBILITY: FastAPI app creation, CORS, router registration order, bot polling toggle
SAFE TO MODIFY FOR: adding new routers, changing CORS settings, adjusting startup validation
DO NOT TOUCH WHEN FIXING: auth bugs, deal/billing/expense business logic
DEPENDS ON: all routers, config/config.py

FILE: backend/routers/auth.py
RESPONSIBILITY: Login endpoints (miniapp-login auto/manual, role-login, validate, role)
SAFE TO MODIFY FOR: auth flow changes, login response format
DO NOT TOUCH WHEN FIXING: deal/billing/expense data bugs, settings rendering
DEPENDS ON: backend.services.miniapp_auth_service, backend.services.permissions, backend.services.telegram_auth, backend.services.settings_service, config.config.settings

FILE: backend/routers/deals_sql.py
RESPONSIBILITY: Active SQL-function-based deal endpoints (list, get, create, pay, update)
SAFE TO MODIFY FOR: deal creation/pay parameter order, manager_id enforcement, deal list filtering, role checks
DO NOT TOUCH WHEN FIXING: billing bugs, expense bugs, auth login flow, settings rendering
DEPENDS ON: backend.schemas.deals, backend.models.deal (DealUpdate), backend.services.db_exec, backend.services.miniapp_auth_service, backend.services.permissions, backend.services.deals_service (update_deal_pg only), public.api_create_deal, public.api_pay_deal, public.v_api_deals

FILE: backend/routers/billing_sql.py
RESPONSIBILITY: Active SQL-function-based billing endpoints (list, search, upsert, pay, payment/mark)
SAFE TO MODIFY FOR: billing upsert params, billing payment, deal payment from billing screen, warehouse_id/client_id handling
DO NOT TOUCH WHEN FIXING: deal create/pay bugs, expense bugs, auth login bugs
DEPENDS ON: backend.schemas.billing, backend.services.db_exec, backend.services.miniapp_auth_service, backend.services.permissions, public.api_upsert_billing_entry, public.api_pay_billing_entry, public.api_pay_deal, public.v_api_billing, public.v_api_deals

FILE: backend/routers/expenses_sql.py
RESPONSIBILITY: Active SQL-function-based expense endpoints (list, create)
SAFE TO MODIFY FOR: expense create params, deal_id filter, role checks
DO NOT TOUCH WHEN FIXING: deal bugs, billing bugs, auth bugs
DEPENDS ON: backend.schemas.expenses, backend.services.db_exec, backend.services.miniapp_auth_service, backend.services.permissions, public.api_create_expense, public.v_api_expenses

FILE: backend/routers/month_close.py
RESPONSIBILITY: Month archive/cleanup/close SQL operations
SAFE TO MODIFY FOR: month-close role restrictions, param order for archive/cleanup/close
DO NOT TOUCH WHEN FIXING: deal/billing/expense data bugs, auth bugs, settings bugs
DEPENDS ON: backend.schemas.month_close, backend.services.db_exec, backend.services.miniapp_auth_service, backend.services.permissions, public.archive_month, public.cleanup_month, public.close_month

FILE: backend/routers/settings.py
RESPONSIBILITY: Reference data CRUD (clients, managers, directions, statuses, enriched settings)
SAFE TO MODIFY FOR: adding new reference data endpoints, enriched settings format changes
DO NOT TOUCH WHEN FIXING: deal/billing/expense data bugs, auth flow bugs
DEPENDS ON: backend.models.settings, backend.services.settings_service, backend.services.clients_service, backend.services.managers_service, backend.services.journal_service, app.database.models

FILE: backend/services/miniapp_auth_service.py
RESPONSIBILITY: PostgreSQL-based user auth and resolution; app_users upsert via SQL function
SAFE TO MODIFY FOR: auth resolution logic, manager binding, ORM fallback behavior
DO NOT TOUCH WHEN FIXING: deal/billing/expense schema bugs, settings rendering bugs, frontend dropdown bugs
DEPENDS ON: app.database.models (AppUser, Manager, Role), app.core.config, backend.services.telegram_auth, public.upsert_app_user

FILE: backend/services/db_exec.py
RESPONSIBILITY: Low-level SQL execution (call_sql_function, read_sql_view)
SAFE TO MODIFY FOR: SQL error handling, serialization of Decimal/date types
DO NOT TOUCH WHEN FIXING: auth bugs, business-logic bugs (parameters are set in routers)
DEPENDS ON: SQLAlchemy text(), asyncpg

FILE: backend/services/permissions.py
RESPONSIBILITY: Role constants, editable-field maps, verify_role_password
SAFE TO MODIFY FOR: adding new roles, changing editable fields per role, role password env var mapping
DO NOT TOUCH WHEN FIXING: SQL function parameter order, DB schema bugs
DEPENDS ON: OS environment variables (ROLE_PASSWORD_*)

FILE: backend/services/settings_service.py
RESPONSIBILITY: Load reference data from PostgreSQL (active) and Google Sheets (legacy)
SAFE TO MODIFY FOR: adding new enriched fields, fixing PG settings loaders
DO NOT TOUCH WHEN FIXING: deal SQL function params, auth login flow
DEPENDS ON: app.database.models, backend.services.sheets_service (legacy functions)

FILE: backend/schemas/deals.py
RESPONSIBILITY: Request/response schemas for /deals SQL endpoints
SAFE TO MODIFY FOR: adding/removing deal create fields, validating input types
DO NOT TOUCH WHEN FIXING: billing/expense bugs, auth bugs
DEPENDS ON: pydantic

FILE: backend/schemas/billing.py
RESPONSIBILITY: Request schemas for /billing/v2 SQL endpoints
SAFE TO MODIFY FOR: adding/removing billing fields, changing deal_id type handling
DO NOT TOUCH WHEN FIXING: deal create bugs, expense bugs, auth bugs
DEPENDS ON: pydantic

FILE: backend/schemas/expenses.py
RESPONSIBILITY: Request schema for /expenses/v2/create
SAFE TO MODIFY FOR: adding/removing expense fields
DO NOT TOUCH WHEN FIXING: deal/billing bugs, auth bugs
DEPENDS ON: pydantic

FILE: app/database/models.py
RESPONSIBILITY: All ORM table definitions (roles, app_users, managers, clients, deals, billing_entries, expenses, warehouses, etc.)
SAFE TO MODIFY FOR: adding new columns (with matching DB migration), adding relationships
DO NOT TOUCH WHEN FIXING: auth password logic, frontend rendering, SQL function parameter order
DEPENDS ON: SQLAlchemy ORM, PostgreSQL schema

FILE: app/database/database.py
RESPONSIBILITY: Async engine creation, session factory, get_db dependency
SAFE TO MODIFY FOR: connection pool settings, DATABASE_URL parsing
DO NOT TOUCH WHEN FIXING: business logic bugs, auth bugs, schema bugs
DEPENDS ON: app.core.config.settings.database_url

FILE: config/config.py
RESPONSIBILITY: Primary Settings class for backend/ (DATABASE_URL, TELEGRAM_BOT_TOKEN, role passwords, manager IDs/passwords)
SAFE TO MODIFY FOR: adding new env var settings
DO NOT TOUCH WHEN FIXING: deal data bugs, billing data bugs
DEPENDS ON: OS environment / .env file

FILE: app/core/config.py
RESPONSIBILITY: Settings class for app/ (includes app_env flag controlling production vs dev behavior)
SAFE TO MODIFY FOR: adding new env var settings, changing app_env default
DO NOT TOUCH WHEN FIXING: deal data bugs, SQL function parameter order
DEPENDS ON: OS environment / .env file
```

---

## 16. FIX-BOUNDARY GUIDANCE

### Files safe for frontend-only fixes (no backend changes needed)

- `miniapp/` directory (static frontend files — not analysed here)
- `backend/schemas/deals.py`, `backend/schemas/billing.py`, `backend/schemas/expenses.py` — if fixing response shape/validation only
- `backend/models/settings.py` — if fixing settings response models
- `backend/routers/settings.py` — if fixing which reference data is returned

### Files safe for auth-only fixes

- `backend/routers/auth.py`
- `backend/services/miniapp_auth_service.py`
- `backend/services/telegram_auth.py`
- `backend/services/permissions.py` (for role password or role constant changes)
- `config/config.py`, `app/core/config.py`

### Files safe for deals-only fixes

- `backend/routers/deals_sql.py`
- `backend/schemas/deals.py`
- `backend/services/deals_service.py` (ORM `update_deal_pg` function only, if deal update is the target)

### Files safe for billing-only fixes

- `backend/routers/billing_sql.py`
- `backend/schemas/billing.py`

### Files safe for expenses-only fixes

- `backend/routers/expenses_sql.py`
- `backend/schemas/expenses.py`

### High-risk files — must not be changed casually

| File | Risk |
|------|------|
| `backend/main.py` | Router registration order — changing order can cause `/billing/v2` to be intercepted by `/billing/{warehouse}` |
| `backend/services/db_exec.py` | Used by all SQL-function routers; changes affect every SQL call |
| `backend/services/miniapp_auth_service.py` | All protected endpoint auth depends on this; a bug here locks all users out |
| `app/database/models.py` | ORM models reflect live DB schema; column changes without matching migrations break everything |
| `app/database/database.py` | Async session factory; pool configuration errors cause all DB calls to fail |
| `backend/routers/deals_sql.py` (the SQL string in `create_deal`) | Parameter order of `api_create_deal` is manually constructed; any reordering causes FK violations or wrong data |
| `backend/routers/billing_sql.py` (the SQL string in `upsert_billing_entry`) | Same risk as above for 19-parameter billing function |
| `backend/services/permissions.py` | `ALLOWED_ROLES` set is used to accept X-User-Role headers across all SQL routers; removing a role here denies all users with that role |
