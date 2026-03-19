# Technical Architecture Overview

## 1. Repository Structure

```
tg_bot_finans/
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── README.md
├── requirements.txt
│
├── app/                            ← NEW PostgreSQL-based FastAPI backend (v3.0)
│   ├── __init__.py
│   ├── main.py                     ← FastAPI entrypoint (app.main:app)
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py               ← Settings (DATABASE_URL, role passwords, etc.)
│   ├── crud/
│   │   ├── __init__.py
│   │   ├── billing.py
│   │   ├── clients.py
│   │   ├── deals.py
│   │   ├── expenses.py
│   │   └── managers.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── database.py             ← AsyncSession + engine setup
│   │   ├── models.py               ← All SQLAlchemy ORM models
│   │   └── schemas.py              ← Pydantic schemas
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── billing.py
│   │   ├── clients.py
│   │   ├── deals.py
│   │   ├── expenses.py
│   │   ├── managers.py
│   │   └── reports.py
│   └── services/
│       ├── __init__.py
│       ├── billing_service.py
│       ├── deal_service.py
│       ├── expense_service.py
│       └── journal_service.py
│
├── backend/                        ← ACTIVE FastAPI backend (v2.0, Dockerfile target)
│   ├── __init__.py
│   ├── config.py
│   ├── dependencies.py
│   ├── main.py                     ← FastAPI entrypoint (backend.main:app)
│   ├── data/
│   │   └── store.js
│   ├── middleware/
│   │   └── auth.js
│   ├── models/
│   │   ├── __init__.py
│   │   ├── common.py
│   │   ├── deal.py
│   │   ├── schemas.py
│   │   └── settings.py
│   ├── permissions/
│   │   └── index.js
│   ├── routes/                     ← Node.js Express routes (legacy/unused)
│   │   ├── analytics.js
│   │   ├── deals.js
│   │   └── journal.js
│   ├── routers/                    ← FastAPI routers
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── billing.py
│   │   ├── dashboard.py
│   │   ├── deals.py
│   │   ├── expenses.py
│   │   ├── journal.py
│   │   ├── receivables.py
│   │   ├── reports.py
│   │   └── settings.py
│   ├── server.js                   ← Node.js Express server (legacy/unused)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── auth_service.py
│   │   ├── billing_service.py
│   │   ├── clients_service.py
│   │   ├── deal_service.py
│   │   ├── deals.py
│   │   ├── deals_service.py        ← Deal CRUD (delegates to sheets_service stubs)
│   │   ├── expenses_service.py
│   │   ├── journal_service.py
│   │   ├── managers_service.py
│   │   ├── miniapp_auth_service.py ← Mini App auth (PostgreSQL-backed)
│   │   ├── permissions.py          ← Role/permission definitions
│   │   ├── reports_service.py
│   │   ├── settings_service.py     ← Settings (formerly Google Sheets; now stubbed)
│   │   ├── sheets.py
│   │   ├── sheets_service.py       ← Deprecated Google Sheets stubs
│   │   ├── telegram_auth.py        ← Telegram initData validator
│   │   └── managers_service.py
│   ├── package.json
│   ├── package-lock.json
│   └── tests/
│       ├── deals.test.js
│       └── permissions.test.js
│
├── bot/                            ← Telegram bot (aiogram v3)
│   ├── __init__.py
│   ├── bot.py
│   ├── handlers.py
│   └── keyboards.py
│
├── config/
│   ├── __init__.py
│   └── config.py                   ← Shared config + validate_settings()
│
├── frontend/                       ← Legacy plain JS frontend (Node.js server era)
│   ├── css/
│   │   └── styles.css
│   ├── index.html
│   └── js/
│       ├── api.js
│       ├── app.js
│       └── permissions.js
│
├── miniapp/                        ← PRIMARY Telegram Mini App frontend
│   ├── app.js                      ← ~2600-line SPA (vanilla JS)
│   ├── index.html
│   └── styles.css
│
├── routers/
│   ├── __init__.py
│   └── deal_router.py
│
├── services/
│   ├── __init__.py
│   ├── deal_service.py
│   ├── journal_service.py
│   └── sheets_service.py
│
├── src/
│   ├── __init__.py
│   └── settings_parser.py
│
├── static/
│   └── index.html
│
├── tests/                          ← Python test suite (pytest)
│   ├── __init__.py
│   ├── test_bot_keyboard.py
│   ├── test_deal_service.py
│   ├── test_health_endpoints.py
│   ├── test_journal_service.py
│   ├── test_miniapp_auth.py
│   ├── test_new_features.py
│   ├── test_scenario_verification.py
│   ├── test_settings_parser.py
│   ├── test_sheets_service.py
│   └── test_sheets_utils.py
│
├── app.py                          ← LEGACY Flask app (Google Sheets era)
├── bot.py                          ← Legacy bot entry
└── config.py                       ← Legacy config
```

---

## 2. Backend Architecture

### Active entrypoint (Dockerfile CMD)

**File:** `backend/main.py`

```
Module import path: backend.main:app

FastAPI instance: app = FastAPI(
    title="Финансовая система API",
    description="Backend API для Telegram Mini App учёта сделок",
    version="2.0.0",
    lifespan=lifespan,
)
```

`app = FastAPI(...)` is on **line 89** of `backend/main.py`.

### Secondary entrypoint (PostgreSQL-native, v3.0)

**File:** `app/main.py`

```
Module import path: app.main:app

FastAPI instance: app = FastAPI(
    title="Финансовая система API",
    description="Backend API для Telegram Mini App учёта сделок (PostgreSQL)",
    version="3.0.0",
)
```

`app = FastAPI(...)` is on **line 28** of `app/main.py`.

### Registered routers in `backend/main.py`

| Router prefix | File |
|---|---|
| `/deal` | `backend/routers/deals.py` |
| `/settings` | `backend/routers/settings.py` |
| `/auth` | `backend/routers/auth.py` |
| `/dashboard` | `backend/routers/dashboard.py` |
| `/journal` | `backend/routers/journal.py` |
| `/billing` | `backend/routers/billing.py` |
| `/expenses` | `backend/routers/expenses.py` |
| `/reports` | `backend/routers/reports.py` |
| `/receivables` | `backend/routers/receivables.py` |

Static files are served from `/miniapp` if the `miniapp/` directory exists.

---

## 3. Server Startup Configuration

### Dockerfile (primary runtime)

**File:** `Dockerfile`

```dockerfile
FROM python:3.12-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Startup command:** `uvicorn backend.main:app --host 0.0.0.0 --port 8000`

**Exposed port:** `8000`

No Procfile or start.sh is present. The Dockerfile CMD is the sole runtime command definition.

### Local development

Per the docstring in `app/main.py`:

```
uvicorn app.main:app --reload
```

---

## 4. Database Layer

### Connection configuration

| Item | Detail |
|---|---|
| Engine | PostgreSQL (asyncpg driver) |
| ORM | SQLAlchemy 2.0 (async) |
| Migration | Alembic 1.13.1 |
| Connection string env var | `DATABASE_URL` |

**Files involved:**

| File | Role |
|---|---|
| `app/core/config.py` | Loads `DATABASE_URL` from environment via `pydantic-settings` |
| `app/database/database.py` | Creates `AsyncEngine` and `AsyncSessionLocal`; exposes `get_db()` dependency |
| `app/database/models.py` | All SQLAlchemy ORM models (see table list below) |
| `config/config.py` | Shared config used by `backend/main.py`; also loads `DATABASE_URL` |

### `DATABASE_URL` loading flow

1. `config/config.py` calls `load_dotenv()` then `pydantic-settings` reads `DATABASE_URL` from environment.
2. `app/core/config.py` does the same independently (the `app/` module has its own config).
3. At startup, `backend/main.py` calls `validate_settings()` (in `config/config.py`) inside the `lifespan` context — this raises `RuntimeError` if `DATABASE_URL` is absent.

### AsyncSession setup (`app/database/database.py`)

```python
engine = create_async_engine(
    _DATABASE_URL,    # postgresql+asyncpg://...
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### SQLAlchemy ORM models (`app/database/models.py`)

| Model | Table | Purpose |
|---|---|---|
| `Role` | `roles` | Role lookup (code, name) |
| `Warehouse` | `warehouses` | Warehouse reference |
| `BusinessDirection` | `business_directions` | Business directions |
| `DealStatus` | `deal_statuses` | Deal status lookup |
| `VatType` | `vat_types` | VAT type lookup |
| `Source` | `sources` | Lead source lookup |
| `ExpenseCategoryLevel1` | `expense_categories_level_1` | Expense categories (top level) |
| `ExpenseCategoryLevel2` | `expense_categories_level_2` | Expense categories (sub-level) |
| `AppUser` | `app_users` | Authenticated Mini App users |
| `Manager` | `managers` | Sales managers (linked to Telegram users) |
| `Client` | `clients` | Clients |
| `Deal` | `deals` | Deals (financial transactions) |
| `BillingEntry` | `billing_entries` | Billing/invoice entries per client/warehouse |
| `Expense` | `expenses` | Expenses linked to deals |
| `JournalEntry` | `journal_entries` | Audit log of all actions |

---

## 5. Authentication Flow

### Endpoints

#### `POST /auth/miniapp-login` (primary Mini App login)

**Router file:** `backend/routers/auth.py`  
**Service file:** `backend/services/miniapp_auth_service.py`

Flow:
1. Mini App posts `{ telegram_id, full_name, username, selected_role, password }`.
2. Router calls `miniapp_login(db, ...)`.
3. `miniapp_login` queries `roles` table by `code = selected_role`. Raises `ValueError` if not found.
4. `_verify_role_password()` checks the password against `settings.role_password_<role>` (environment variable). Raises `PermissionError` if wrong or unconfigured.
5. `_upsert_app_user()` creates or updates the `app_users` row for the `telegram_id`.
6. If `selected_role == "manager"`, `_ensure_manager_record()` creates or updates a row in the `managers` table.
7. Returns `{ user_id, telegram_id, full_name, username, role }`.
8. Frontend stores `telegram_id` and `user_role` in `localStorage`.

**Tables touched:** `roles`, `app_users`, `managers`  
**DB session:** injected via `Depends(get_db)` from `app.database.database`

#### `POST /auth/role-login` (fallback – no Telegram context)

**Router file:** `backend/routers/auth.py`  
**Service:** inline, uses `verify_role_password()` from `backend/services/permissions.py`

Flow:
1. Mini App posts `{ role, password }` (no `telegram_id`).
2. Router validates `role in ALLOWED_ROLES` and calls `verify_role_password(role, password)`.
3. Returns `{ success: true, role, role_label }` on match.
4. No database writes; no session token. Role is stored in `localStorage` only.

#### `POST /auth/validate` (Telegram initData validation, legacy path)

Validates the raw `X-Telegram-Init-Data` header using HMAC-SHA256 against `TELEGRAM_BOT_TOKEN`.  
Returns the user's role from the in-memory `settings_service` (previously backed by Google Sheets).

#### `GET /auth/role`

Returns role + permissions for the user identified by `X-Telegram-Init-Data` header.

### Role password configuration

Role passwords are set as environment variables and loaded by `config/config.py`:

| Role | Environment variable |
|---|---|
| `manager` | `ROLE_PASSWORD_MANAGER` |
| `operations_director` | `ROLE_PASSWORD_OPERATIONS_DIRECTOR` |
| `accounting` | `ROLE_PASSWORD_ACCOUNTING` |
| `admin` | `ROLE_PASSWORD_ADMIN` |

---

## 6. Deal Creation Flow

### `POST /deal/create`

**Router file:** `backend/routers/deals.py`  
**Service file:** `backend/services/deals_service.py`

Step-by-step:

1. **User resolution** (`_resolve_user()`):
   - Primary: `X-Telegram-Id` header → `get_user_by_telegram_id(db, telegram_id)` → `app_users` table.
   - Fallback: `X-Telegram-Init-Data` header → `extract_user_from_init_data()` → `settings_service` in-memory map.
   - Returns `(user_id_str, role_code, full_name)`. Returns `("", "no_access", "")` on failure.

2. **Authorization check**: if `role == "no_access"` → HTTP 403 with message:
   > "Access denied: user not found or not active. Please log in via /auth/miniapp-login first."

3. **Deal creation**: `deals_service.create_deal(deal_data, telegram_user_id, user_role, full_name)`.
   - The service reads and writes to the `deals` data store.
   - Note: `deals_service.py` currently imports from `sheets_service.py`, which is a **stub** (Google Sheets has been removed). Write operations are effectively no-ops unless the `app/` PostgreSQL path is wired up in a future refactor.

4. Returns `{ success: true, deal_id: "..." }`.

**Models touched:** `app_users` (read), `roles` (read via `get_role_code`)

---

## 7. Frontend Architecture

### Mini App (`miniapp/`)

| Property | Value |
|---|---|
| Framework | Vanilla JavaScript (no build step, no React/Vue) |
| Entry HTML | `miniapp/index.html` |
| Main script | `miniapp/app.js` (~2600 lines, single file SPA) |
| Served at | `/miniapp` (mounted as StaticFiles by FastAPI) |

**`apiFetch` function** (line ~65 of `miniapp/app.js`):

```javascript
async function apiFetch(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  const initData = getTelegramInitData();
  if (initData) headers['X-Telegram-Init-Data'] = initData;
  // Primary auth header
  if (!headers['X-Telegram-Id']) {
    const telegramId = telegramUser?.id || localStorage.getItem('telegram_id');
    if (telegramId) headers['X-Telegram-Id'] = String(telegramId);
  }
  // Stored role
  if (!headers['X-User-Role']) {
    const savedRole = localStorage.getItem('user_role');
    if (savedRole) headers['X-User-Role'] = savedRole;
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  ...
}
```

The `API_BASE` is resolved from (in priority order):
1. `<meta name="api-base">` tag in `index.html`
2. `window.APP_CONFIG.apiBase`
3. `window.location.origin` (same-origin default)

**`doLogin` function** (line ~1452 of `miniapp/app.js`):

```javascript
const doLogin = async () => {
  if (telegramUser) {
    // Primary: POST /auth/miniapp-login (creates/updates app_users record)
    const result = await apiFetch('/auth/miniapp-login', { method: 'POST', body: ... });
    localStorage.setItem('telegram_id', String(telegramUser.id));
  } else {
    // Fallback: POST /auth/role-login (no DB write)
    const result = await apiFetch('/auth/role-login', { method: 'POST', body: ... });
  }
  localStorage.setItem('user_role', role);
  localStorage.setItem('user_role_label', roleLabel);
  await enterApp(role);
};
```

**`X-Telegram-Id` header** is attached automatically in every `apiFetch` call from:
- `telegramUser.id` (live Telegram WebApp SDK object), or
- `localStorage.getItem('telegram_id')` (persisted after first login).

### Legacy frontend (`frontend/`)

Plain JS + `frontend/js/api.js` — uses `X-User-Id` header (not `X-Telegram-Id`). Communicates with a Node.js Express `/api/...` route namespace. **Not used in the current deployment.**

---

## 8. Deployment Architecture

### Dockerfile summary

```dockerfile
FROM python:3.12-bookworm         # stable Debian base
WORKDIR /app
RUN apt-get update && apt-get install -y curl   # health-check dependency
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build steps

1. Base image: `python:3.12-bookworm`
2. System packages: `curl` (for potential health checks)
3. Python dependencies installed from `requirements.txt`
4. Full project source copied
5. Port 8000 exposed
6. Runtime: `uvicorn backend.main:app`

### Key runtime dependencies (`requirements.txt`)

```
aiogram==3.7.0              # Telegram bot
fastapi==0.111.0            # Web framework
uvicorn[standard]==0.30.1   # ASGI server
sqlalchemy==2.0.30          # ORM
asyncpg==0.29.0             # Async PostgreSQL driver
pydantic==2.7.4
pydantic-settings==2.3.0
python-dotenv==1.0.1
alembic==1.13.1             # DB migrations
orjson==3.11.6
httpx==0.27.0
openpyxl==3.1.5             # Excel report export
pytest==8.2.0
pytest-asyncio==0.23.6
```

### Environment variables expected at runtime

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | **Yes** | PostgreSQL connection string (`postgresql://user:pass@host:5432/db`) |
| `TELEGRAM_BOT_TOKEN` | Only when `RUN_BOT=true` | Telegram bot token |
| `WEBAPP_URL` | No (warning if missing) | Public HTTPS URL of the Mini App |
| `API_BASE_URL` | No | Public backend URL (frontend fallback) |
| `ROLE_PASSWORD_MANAGER` | No (login fails without it) | Password for `manager` role |
| `ROLE_PASSWORD_OPERATIONS_DIRECTOR` | No | Password for `operations_director` role |
| `ROLE_PASSWORD_ACCOUNTING` | No | Password for `accounting` role |
| `ROLE_PASSWORD_ADMIN` | No | Password for `admin` role |
| `RUN_BOT` | No (default: `false`) | Set `true` to run Telegram bot polling inline |

---

## 9. Observed Runtime Errors

### "Error loading ASGI app" (uvicorn startup error)

**Subsystem:** uvicorn / Python import chain  
**Cause:** Occurs when `uvicorn backend.main:app` fails to import `backend.main`. The most common cause in this project is a missing `DATABASE_URL` environment variable. The `validate_settings()` call inside the `lifespan()` context will raise `RuntimeError: Missing required environment variable: DATABASE_URL`, which terminates uvicorn before it can serve requests.  
**Fix:** Set `DATABASE_URL` in the environment before starting the container.

### "user not found or not active" (HTTP 403)

**Subsystem:** `backend/routers/deals.py` → `_resolve_user_db()`  
**Cause:** A request arrives at a protected endpoint (e.g. `POST /deal/create`) with an `X-Telegram-Id` header, but the `telegram_id` is not present in the `app_users` table, or the user's `is_active` flag is `False`.  
**Fix:** The user must call `POST /auth/miniapp-login` first to register themselves in `app_users`. After a successful login, subsequent requests with the same `X-Telegram-Id` will resolve correctly.

### SQL errors related to settings tables

**Subsystem:** `backend/services/settings_service.py` + `backend/services/sheets_service.py`  
**Cause:** `settings_service.py` originally queried a "Настройки" Google Sheets worksheet. After the Google Sheets removal, `sheets_service.py` was replaced with stubs that raise `SheetsError` / `SheetNotFoundError`. Any code path that still calls `get_worksheet(SHEET_SETTINGS)` will raise a `SheetsError`, which surfaces as an HTTP 500 in the API and a logged error. The settings data (statuses, roles mapping, etc.) that was previously loaded from the sheet is now empty/default, which can cause reference validation failures.  
**Fix:** Migrate `settings_service.py` lookups to the PostgreSQL reference tables (`roles`, `deal_statuses`, `business_directions`, `sources`, `vat_types`, `warehouses`) via `app.crud` or direct SQLAlchemy queries. The `app/` module already has the full ORM model for all reference tables.

### Dual-backend confusion (v2 vs v3)

**Subsystem:** Repository structure  
**Cause:** The repository contains two FastAPI backends:
- `backend/main.py` (v2.0) — used by the Dockerfile; auth uses PostgreSQL via `app.database`, but deal CRUD still delegates to `sheets_service` stubs.
- `app/main.py` (v3.0) — fully PostgreSQL-native; has its own routers and CRUD layer.

This creates an inconsistency: authentication is fully PostgreSQL-backed (via `app.database.models.AppUser`), but deal data persistence is not. The `deals_service.create_deal()` call will succeed at the router level but will not actually persist any data to PostgreSQL.

---

*Generated: 2026-03-14*
