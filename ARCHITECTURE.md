# Architecture Documentation — tg_bot_finans

> Telegram Financial Accounting System  
> Stack: Python 3.12, FastAPI, aiogram 3.x, Telegram Mini App, Google Sheets API, Uvicorn

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Backend Architecture](#2-backend-architecture)
3. [Bot Architecture](#3-bot-architecture)
4. [Mini App Architecture](#4-mini-app-architecture)
5. [Google Sheets Integration](#5-google-sheets-integration)
6. [API Endpoints](#6-api-endpoints)
7. [Data Models](#7-data-models)
8. [Environment Variables](#8-environment-variables)
9. [Request Flow (Architecture Flow)](#9-request-flow-architecture-flow)
10. [Example Deal Object](#10-example-deal-object)

---

## 1. Project Structure

```
tg_bot_finans/
│
├── backend/                          # FastAPI application package
│   ├── __init__.py
│   ├── main.py                       # FastAPI app factory + lifespan (bot polling)
│   ├── config.py                     # (legacy stub)
│   ├── dependencies.py               # FastAPI dependency injection helpers
│   ├── models/                       # Pydantic data models
│   │   ├── __init__.py
│   │   ├── common.py                 # SuccessResponse, ErrorResponse
│   │   ├── deal.py                   # DealCreate, DealUpdate, DealResponse
│   │   ├── schemas.py                # Extended schemas (DashboardResponse, JournalEntry, etc.)
│   │   └── settings.py               # SettingsResponse, UserAccessResponse, UserRoleInfo
│   ├── routers/                      # FastAPI route handlers
│   │   ├── __init__.py
│   │   ├── auth.py                   # POST /auth/validate, GET /auth/role
│   │   ├── dashboard.py              # GET /dashboard
│   │   ├── deals.py                  # CRUD for /deal/*
│   │   ├── journal.py                # GET /journal/recent
│   │   └── settings.py               # GET /settings
│   ├── services/                     # Business logic layer
│   │   ├── __init__.py
│   │   ├── auth.py                   # (legacy / unused)
│   │   ├── auth_service.py           # (legacy / unused)
│   │   ├── deal_service.py           # (legacy / unused)
│   │   ├── deals.py                  # (legacy / unused)
│   │   ├── deals_service.py          # Active: CRUD for "Учёт сделок" sheet
│   │   ├── journal_service.py        # Active: audit log writer for "Журнал действий" sheet
│   │   ├── permissions.py            # Role definitions and field-level access control
│   │   ├── settings_service.py       # Active: loads reference data from "Настройки" sheet
│   │   ├── sheets.py                 # (legacy / unused)
│   │   ├── sheets_service.py         # Active: low-level gspread client and header helpers
│   │   └── telegram_auth.py          # Active: Telegram initData HMAC validation
│   ├── data/store.js                 # (Node.js leftover – unused)
│   ├── middleware/auth.js            # (Node.js leftover – unused)
│   ├── permissions/index.js          # (Node.js leftover – unused)
│   ├── routes/                       # (Node.js leftover – unused)
│   ├── tests/                        # (Node.js leftover – unused)
│   ├── server.js                     # (Node.js leftover – unused)
│   ├── package.json                  # (Node.js leftover – unused)
│   └── package-lock.json             # (Node.js leftover – unused)
│
├── bot/                              # aiogram bot package
│   ├── __init__.py
│   ├── bot.py                        # Standalone bot runner (mirrors bot/main.py)
│   ├── handlers.py                   # All aiogram message/callback handlers + Router
│   ├── keyboards.py                  # ReplyKeyboard and InlineKeyboard builders
│   └── main.py                       # Standalone bot entry point (python -m bot.main)
│
├── config/                           # Central configuration
│   ├── __init__.py
│   └── config.py                     # Settings (pydantic-settings) + validate_settings()
│
├── miniapp/                          # Telegram Mini App (static files served by FastAPI)
│   ├── index.html                    # Single-page app shell
│   ├── app.js                        # All Mini App logic (vanilla JS)
│   └── styles.css                    # Mini App styles
│
├── routers/                          # (legacy top-level routers – unused)
│   ├── __init__.py
│   └── deal_router.py
│
├── services/                         # (legacy top-level services – unused)
│   ├── __init__.py
│   ├── deal_service.py
│   ├── journal_service.py
│   └── sheets_service.py
│
├── src/                              # (legacy utility)
│   ├── __init__.py
│   └── settings_parser.py
│
├── frontend/                         # (legacy frontend – unused)
│   ├── index.html
│   ├── css/styles.css
│   └── js/
│       ├── api.js
│       ├── app.js
│       └── permissions.js
│
├── static/                           # (legacy static – unused)
│   └── index.html
│
├── tests/                            # Python test suite
│   ├── __init__.py
│   ├── test_bot_keyboard.py
│   ├── test_deal_service.py
│   ├── test_health_endpoints.py
│   ├── test_journal_service.py
│   ├── test_scenario_verification.py
│   ├── test_settings_parser.py
│   ├── test_sheets_service.py
│   └── test_sheets_utils.py
│
├── app.py                            # (legacy Flask demo – unused)
├── bot.py                            # (legacy top-level bot stub – unused)
├── config.py                         # (legacy top-level config stub – unused)
├── requirements.txt                  # Python dependencies
├── .env.example                      # Environment variables template
└── ARCHITECTURE.md                   # This file
```

---

## 2. Backend Architecture

### Entry Point

The production entry point is:

```
backend/main.py  →  FastAPI app object: `app`
```

Started with Uvicorn:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### FastAPI + aiogram Integration

FastAPI and the Telegram bot **run in the same process** using a single shared event loop. The integration point is the `lifespan` async context manager in `backend/main.py`:

```
Application startup  →  lifespan() runs
  ├── Bot(token=...) is created
  ├── Dispatcher is created with MemoryStorage
  ├── bot/handlers.py Router is registered with the Dispatcher
  └── asyncio.create_task(dp.start_polling(bot, skip_updates=True))
        │
        └── Bot polling runs as a background async task alongside FastAPI
              (not in a separate thread or process)

Application shutdown  →  lifespan() teardown runs
  ├── polling_task.cancel()
  └── bot.session.close()
```

The `app.state.bot_polling_task` stores the polling task handle for lifecycle management.

### FastAPI Application Structure

```
backend/main.py
│
├── Middleware
│   └── CORSMiddleware (allow_origins=["*"])
│
├── Routers (all registered on the `app` object)
│   ├── backend.routers.deals      →  prefix: /deal
│   ├── backend.routers.settings   →  prefix: (none, at /settings)
│   ├── backend.routers.auth       →  prefix: /auth
│   ├── backend.routers.dashboard  →  prefix: /dashboard
│   └── backend.routers.journal    →  prefix: /journal
│
├── Static files mount
│   └── /miniapp  →  miniapp/ directory (html=True)
│
└── Health endpoints
    ├── GET  /health  →  {"status": "ok"}
    ├── HEAD /health  →  200
    ├── GET  /        →  {"status": "ok"}
    └── HEAD /        →  200
```

### Authentication Flow per Request

Every protected endpoint reads the `X-Telegram-Init-Data` HTTP header:

```
Request arrives with X-Telegram-Init-Data header
  │
  ├── telegram_auth.extract_user_from_init_data(init_data)
  │     └── URL-decode → parse query string → JSON-parse "user" field
  │           └── Returns dict: {id, first_name, last_name, username, ...}
  │
  ├── settings_service.get_user_role(user_id)
  │     └── Reads "Настройки" sheet → finds user by telegram_user_id → returns role
  │
  └── Role-based logic applied:
        ├── "no_access"          → 403
        ├── "manager"            → own deals only + business fields
        ├── "accountant"         → all deals + accounting fields
        ├── "operations_director"→ all deals + all fields + analytics
        └── "head_of_sales"      → all deals + all fields + sales analytics
```

---

## 3. Bot Architecture

### Files

| File | Purpose |
|------|---------|
| `bot/handlers.py` | All bot message and callback handlers; exports `router` |
| `bot/keyboards.py` | Keyboard constructors |
| `bot/main.py` | Standalone entry point for development (`python -m bot.main`) |
| `bot/bot.py` | Duplicate standalone entry point |

### Handlers (`bot/handlers.py`)

All handlers are registered on a single `aiogram.Router` instance exported as `router`.

| Handler | Trigger | Response |
|---------|---------|---------|
| `handle_start` | `/start` command | Welcome message with `get_main_keyboard()` (ReplyKeyboard with Mini App button) |
| `handle_help` | `/help` command OR text `"ℹ️ Помощь"` | Help text with `get_inline_webapp_keyboard()` |
| `handle_my_deals` | Text message `"📋 Мои сделки"` | Redirect to Mini App via inline keyboard |
| `handle_my_deals_callback` | Callback data `"my_deals"` | Redirect to Mini App via inline keyboard |
| `handle_help_callback` | Callback data `"help"` | Help text message |

### Keyboards (`bot/keyboards.py`)

#### `get_main_keyboard()` → `ReplyKeyboardMarkup`

```
Row 1: [ Открыть приложение (WebApp: WEBAPP_URL) ]
Row 2: [ 📋 Мои сделки ]  [ ℹ️ Помощь ]
```

#### `get_inline_webapp_keyboard()` → `InlineKeyboardMarkup`

```
Row 1: [ Открыть приложение (WebApp: WEBAPP_URL) ]
Row 2: [ 📋 Мои сделки (callback: my_deals) ]  [ ℹ️ Помощь (callback: help) ]
```

Both keyboards use `WebAppInfo(url=settings.webapp_url)` so Telegram opens the Mini App inline.

### Bot Polling Lifecycle

In **production**: polling starts automatically as part of the FastAPI lifespan (see Backend Architecture above).

In **development** (standalone mode):
```bash
python -m bot.main
```

---

## 4. Mini App Architecture

### Files

| File | Purpose |
|------|---------|
| `miniapp/index.html` | App shell with HTML structure for all tabs |
| `miniapp/app.js` | All Mini App logic (vanilla JS, ~600 lines) |
| `miniapp/styles.css` | All styles |

### Serving

The `miniapp/` directory is served as static files by FastAPI at the `/miniapp` route:

```python
app.mount("/miniapp", StaticFiles(directory=miniapp_dir, html=True), name="miniapp")
```

Telegram opens this URL when the user taps the Mini App button.

### Tabs

The Mini App is a single-page application with three tabs:

| Tab | ID | Content |
|-----|-----|---------|
| Новая сделка | `new-deal` | Deal creation form |
| Мои сделки | `my-deals` | Deal list with filters |
| Настройки | `settings-tab` | Reference data stats + connection status |

### API Communication (`app.js`)

The Mini App communicates with the backend via the `apiFetch` helper:

```javascript
async function apiFetch(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };
  // Telegram initData is always passed for authentication
  const initData = tg?.initData || '';
  if (initData) {
    headers['X-Telegram-Init-Data'] = initData;
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  // ...error handling
  return response.json();
}
```

`API_BASE` is resolved at startup from (in priority order):
1. `<meta name="api-base" content="...">` in `index.html`
2. `window.APP_CONFIG.apiBase` global variable
3. `window.location.origin` (same-origin fallback — works when FastAPI serves the frontend)

### Telegram SDK Initialization

```javascript
const tg = window.Telegram?.WebApp;

function initTelegram() {
  tg.ready();    // signals the Telegram client the app is ready
  tg.expand();   // expands to full screen
  telegramUser = tg.initDataUnsafe?.user || null;
  // Apply color scheme from Telegram (light/dark)
}
```

`tg.initData` (the signed query string) is sent as `X-Telegram-Init-Data` with every API request.

### Key API Calls from Mini App

| Action | Method | Endpoint | Description |
|--------|--------|----------|-------------|
| Load settings | GET | `/settings` | Populates all `<select>` dropdowns |
| Create deal | POST | `/deal/create` | Submits form data |
| Load deals | GET | `/deal/user` or `/deal/filter` | Fetches deal list |
| Check auth | GET | `/auth/role` | Verifies user and gets role |
| Health check | GET | `/health` | Checks API connectivity |

---

## 5. Google Sheets Integration

### Library

`gspread 6.1.2` + `google-auth 2.29.0`

### Authentication

The service account credentials are loaded entirely from the `GOOGLE_SERVICE_ACCOUNT_JSON` environment variable (full JSON content of the Google service account key file). No file on disk is required.

```python
service_account_info = json.loads(settings.google_service_account_json)
creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(settings.google_sheets_spreadsheet_id)
```

Required OAuth2 scopes:
- `https://www.googleapis.com/auth/spreadsheets`
- `https://www.googleapis.com/auth/drive.readonly`

### Spreadsheet Structure (3 worksheets)

| Sheet name | Internal constant | Purpose |
|------------|------------------|---------|
| `Учёт сделок` | `SHEET_DEALS` | All deals (one row per deal) |
| `Настройки` | `SHEET_SETTINGS` | Reference data + user roles |
| `Журнал действий` | `SHEET_JOURNAL` | Audit log of all actions |

### Service Layer

```
backend/services/sheets_service.py    ← Low-level: client init, header helpers, row converters
        │
        ├── backend/services/deals_service.py     ← CRUD for "Учёт сделок"
        ├── backend/services/settings_service.py  ← Reference data from "Настройки"
        └── backend/services/journal_service.py   ← Append-only writes to "Журнал действий"
```

### Column-mapping Strategy

All sheet access is **header-based**, not positional. On every request, `get_header_map(worksheet)` reads the first row and builds a `{column_name: index}` dict. This makes the system resilient to column reordering.

**"Учёт сделок" column map** (Russian header → internal field name):

| Russian Header | Internal Field |
|----------------|----------------|
| ID сделки | deal_id |
| Статус сделки | status |
| Направление бизнеса | business_direction |
| Клиент | client |
| Менеджер | manager |
| Начислено с НДС | charged_with_vat |
| Наличие НДС | vat_type |
| Оплачено | paid |
| Дата начала проекта | project_start_date |
| Дата окончания проекта | project_end_date |
| Дата выставления акта | act_date |
| Переменный расход 1 | variable_expense_1 |
| Переменный расход 2 | variable_expense_2 |
| Бонус менеджера % | manager_bonus_percent |
| Бонус менеджера выплачено | manager_bonus_paid |
| Общепроизводственный расход | general_production_expense |
| Источник | source |
| Документ/ссылка | document_link |
| Комментарий | comment |

### "Настройки" Sheet Layout

The settings sheet uses a **block layout** with section headers in square brackets:

```
[Статусы сделок]
Новая
В работе
Завершена
...

[Направления бизнеса]
Разработка
...

[Клиенты]
...

[Менеджеры]
...

[Наличие НДС]
С НДС
Без НДС

[Источники]
...

[Роли пользователей]
telegram_user_id | full_name | role | active
123456789 | Иван Петров | manager | TRUE
987654321 | Анна Смирнова | accountant | TRUE
```

The `parse_settings_sheet()` function in `settings_service.py` parses this structure into a dict.

### "Журнал действий" Sheet Layout

The journal sheet has a fixed 8-column header row created automatically if the sheet is empty:

```
timestamp | telegram_user_id | full_name | user_role | action | deal_id | changed_fields | payload_summary
```

Every deal creation, update, and permission violation is logged here with a UTC timestamp.

### Deal ID Generation

Deal IDs follow the pattern `DEAL-NNNNNN` (e.g., `DEAL-000042`). They are generated **under a threading lock** (`_deal_id_lock`) to prevent duplicates:

```
1. Lock acquired
2. Read all existing rows from "Учёт сделок"
3. Extract all deal IDs, find maximum numeric suffix
4. next_id = max_suffix + 1
5. Format as DEAL-NNNNNN
6. Append new row
7. Lock released
```

---

## 6. API Endpoints

All endpoints use the `X-Telegram-Init-Data` request header for authentication. The header value is the raw Telegram WebApp `initData` string.

### Deals — `/deal`

| Method | Path | Auth Required | Description |
|--------|------|--------------|-------------|
| POST | `/deal/create` | Any role except `no_access` | Create a new deal |
| GET | `/deal/all` | `accountant`, `operations_director`, `head_of_sales` | Return all deals |
| GET | `/deal/user` | Any role except `no_access` | Return deals for current user (managers see own only) |
| GET | `/deal/filter` | Any role except `no_access` | Filter deals by query params |
| GET | `/deal/{deal_id}` | Any role except `no_access` | Get single deal by ID |
| PUT | `/deal/{deal_id}` | Any role except `no_access` | Update an existing deal (role-based field permissions) |

**Filter query parameters for `GET /deal/filter`:**

| Param | Type | Description |
|-------|------|-------------|
| `manager` | string | Filter by manager name |
| `client` | string | Filter by client name |
| `status` | string | Filter by deal status |
| `business_direction` | string | Filter by business direction |
| `month` | string | Filter by month (YYYY-MM) |
| `paid` | bool | Filter by paid status |

### Auth — `/auth`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/validate` | Validate Telegram initData; return user info + role |
| GET | `/auth/role` | Return role and permissions for the authenticated user |

### Dashboard — `/dashboard`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard` | Return role-aware aggregated dashboard data |

Dashboard data shape varies by role:

- `manager` → total_my_deals, in_progress, completed, total_amount
- `accountant` → awaiting_payment, partially_paid, fully_paid, total_receivable, total_paid, total_deals
- `operations_director` → total_deals, active_deals, total_amount, total_paid, receivable, total_expenses, gross_profit, by_manager
- `head_of_sales` → deals_in_progress, new_deals, completed_deals, total_amount, avg_deal_amount, by_manager

### Settings — `/settings`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/settings` | Load all reference lists from the "Настройки" sheet |

### Journal — `/journal`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/journal/recent` | Return recent audit log entries (managers denied) |

Query params: `limit` (1–200, default 50)

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | `{"status": "ok"}` |
| HEAD | `/health` | 200 |
| GET | `/` | `{"status": "ok"}` |
| HEAD | `/` | 200 |

### Static

| Path | Description |
|------|-------------|
| `/miniapp/*` | Serves the Telegram Mini App static files |

---

## 7. Data Models

### `DealCreate` (Pydantic, `backend/models/deal.py`)

Used as the request body for `POST /deal/create`.

```python
class DealCreate(BaseModel):
    # Required fields
    status: str
    business_direction: str
    client: str
    manager: str
    charged_with_vat: float
    vat_type: str
    project_start_date: str   # YYYY-MM-DD
    project_end_date: str     # YYYY-MM-DD

    # Optional fields
    paid: Optional[float] = None
    act_date: Optional[str] = None
    variable_expense_1: Optional[float] = None
    variable_expense_2: Optional[float] = None
    manager_bonus_percent: Optional[float] = None
    manager_bonus_paid: Optional[float] = None
    general_production_expense: Optional[float] = None
    source: Optional[str] = None
    document_link: Optional[str] = None
    comment: Optional[str] = None
```

### `DealUpdate` (Pydantic, `backend/models/deal.py`)

Used as the request body for `PUT /deal/{deal_id}`. All fields are optional.

### `DealResponse` (Pydantic, `backend/models/deal.py`)

Returned when reading a deal. Contains all fields of `DealCreate` plus `deal_id: str`.

### `SettingsResponse` (Pydantic, `backend/models/settings.py`)

Returned by `GET /settings`:

```python
class SettingsResponse(BaseModel):
    statuses: List[str]
    business_directions: List[str]
    clients: List[str]
    managers: List[str]
    vat_types: List[str]
    sources: List[str]
```

### `UserAccessResponse` (Pydantic, `backend/models/settings.py`)

Returned by `GET /auth/role`:

```python
class UserAccessResponse(BaseModel):
    telegram_user_id: str
    full_name: Optional[str]
    role: str
    active: bool
    editable_fields: List[str]
```

### `SuccessResponse` / `ErrorResponse` (`backend/models/common.py`)

Generic response envelopes used across endpoints.

### Role System (`backend/services/permissions.py`)

| Role | Visible Deals | Editable Fields |
|------|--------------|----------------|
| `manager` | Own deals only | Business fields: status, business_direction, client, manager, charged_with_vat, vat_type, project_start_date, project_end_date, source, document_link, comment |
| `accountant` | All deals | Accounting fields: paid, act_date, variable_expense_1, variable_expense_2, manager_bonus_percent, manager_bonus_paid, general_production_expense |
| `operations_director` | All deals | All fields |
| `head_of_sales` | All deals | All fields |
| `no_access` | None | None |

---

## 8. Environment Variables

Defined in `config/config.py` using `pydantic-settings`. Template in `.env.example`.

### Required Variables

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from `@BotFather` |
| `WEBAPP_URL` | Public HTTPS URL where the Mini App is served (e.g. `https://your-domain.com/miniapp`) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full JSON content of the Google service account key file |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | The Google Spreadsheet ID (from the sheet URL) |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_BASE_URL` | Public URL of the backend API; used by the frontend as a fallback config. If not set, the Mini App uses same-origin. | `""` |

### Validation

`validate_settings()` in `config/config.py` is called at application startup. It raises `RuntimeError` with a clear message if any required variable is missing.

### `.env.example`

```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
WEBAPP_URL=https://your-domain.com/miniapp
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"...","private_key":"...","client_email":"..."}
GOOGLE_SHEETS_SPREADSHEET_ID=your_google_spreadsheet_id_here
API_BASE_URL=https://your-backend-domain.com
```

---

## 9. Request Flow (Architecture Flow)

### Flow 1: Telegram User → Bot → Mini App

```
1. User sends /start to the Telegram bot
   │
   └── aiogram Dispatcher (polling loop) receives the Message
         │
         └── handlers.handle_start() fires
               │
               ├── Sends welcome text message (HTML parse mode)
               └── Sends ReplyKeyboardMarkup with:
                     ├── [Открыть приложение]  ← WebAppInfo(url=WEBAPP_URL)
                     └── [📋 Мои сделки] [ℹ️ Помощь]

2. User taps "Открыть приложение"
   │
   └── Telegram client opens WEBAPP_URL in a WebView
         │
         └── miniapp/index.html loads in Telegram's embedded browser
               │
               └── app.js executes:
                     ├── tg.ready() → signals Telegram the app is ready
                     ├── tg.expand() → expands to full screen
                     ├── initTelegram() → extracts telegramUser from tg.initDataUnsafe
                     ├── loadSettings() → GET /settings → populates form dropdowns
                     └── renderUserAvatar() → shows user initials in header
```

### Flow 2: Mini App → API → Backend → Google Sheets (Create Deal)

```
1. User fills in the deal form and taps "Сохранить сделку"
   │
   └── app.js: handleFormSubmit() fires
         │
         ├── validateForm() → checks required fields
         ├── collectFormData() → builds JSON payload from form fields
         └── apiFetch('/deal/create', { method: 'POST', body: JSON.stringify(dealData) })
               │
               └── HTTP POST to https://backend/deal/create
                     Headers:
                       Content-Type: application/json
                       X-Telegram-Init-Data: <tg.initData>

2. FastAPI receives POST /deal/create
   │
   └── backend/routers/deals.py: create_deal()
         │
         ├── _resolve_user(x_telegram_init_data)
         │     ├── extract_user_from_init_data() → parses user from initData
         │     └── settings_service.get_user_role(user_id)
         │           └── GET "Настройки" sheet → find user by telegram_user_id → return role
         │
         ├── If role == "no_access" → 403 Forbidden
         │
         └── deals_service.create_deal(deal_data, user_id, role, full_name)
               │
               ├── filter_update_payload(role, deal_data) → strip forbidden fields
               ├── If role == "manager": override manager = user's full_name
               ├── _validate_required_fields() → raise ValueError if missing
               ├── Acquire _deal_id_lock
               │     ├── get_worksheet("Учёт сделок")
               │     ├── get_header_map(ws) → read row 1 → build {header: col_index}
               │     ├── Read all rows → extract existing deal IDs
               │     ├── generate_next_deal_id() → DEAL-000042
               │     ├── _prepare_deal_payload() → normalise all fields
               │     ├── _deal_dict_to_row() → convert to ordered list aligned with sheet columns
               │     └── ws.append_row(new_row) → writes to Google Sheets
               │           └── Release lock
               │
               └── append_journal_entry("create_deal", deal_id, ...)
                     └── ws.append_row() to "Журнал действий"

3. Backend returns {"success": true, "deal_id": "DEAL-000042"}
   │
   └── app.js: showSuccessScreen("DEAL-000042")
         └── showToast("Сделка DEAL-000042 успешно создана!")
```

### Flow 3: Mini App → Load Deals

```
1. User switches to "Мои сделки" tab
   │
   └── switchTab("my-deals") → loadDeals()
         │
         └── apiFetch('/deal/user') or apiFetch('/deal/filter', ...)
               Headers: X-Telegram-Init-Data: <tg.initData>

2. FastAPI: GET /deal/user
   │
   ├── _resolve_user() → get role and full_name
   ├── If role == "manager" → deals_service.get_deals_by_user(full_name)
   │     └── GET "Учёт сделок" → filter rows where manager == full_name
   └── If higher role → deals_service.get_all_deals()
         └── GET "Учёт сделок" → return all rows

3. Returns JSON array of deal objects
   │
   └── app.js: renderDeals(deals) → renders deal cards in #deals-list
```

### Flow 4: Auth Validation

```
1. Mini App calls GET /auth/role on startup (settings tab)
   │
   └── apiFetch('/auth/role')
         Headers: X-Telegram-Init-Data: <tg.initData>

2. FastAPI: GET /auth/role
   │
   ├── extract_user_from_init_data(init_data)
   │     └── URL-decode → parse_qsl → JSON-parse "user" field
   ├── settings_service.get_user_role(user_id)
   │     └── GET "Настройки" sheet → roles table → lookup by telegram_user_id
   └── Returns UserAccessResponse:
         { telegram_user_id, full_name, role, active, editable_fields }
```

---

## 10. Example Deal Object

### JSON sent by Mini App (`POST /deal/create` body)

```json
{
  "status": "В работе",
  "business_direction": "Разработка",
  "client": "ООО Рога и Копыта",
  "manager": "Иван Петров",
  "charged_with_vat": 250000.00,
  "vat_type": "С НДС",
  "paid": 125000.00,
  "project_start_date": "2024-01-15",
  "project_end_date": "2024-03-31",
  "act_date": null,
  "variable_expense_1": 15000.00,
  "variable_expense_2": null,
  "manager_bonus_percent": 10.0,
  "manager_bonus_paid": null,
  "general_production_expense": 8000.00,
  "source": "Рекомендация",
  "document_link": "https://docs.google.com/...",
  "comment": "Срочный проект, повышенный приоритет"
}
```

### HTTP Request Example

```
POST /deal/create HTTP/1.1
Host: your-backend-domain.com
Content-Type: application/json
X-Telegram-Init-Data: query_id=AAF...&user=%7B%22id%22%3A123456789%2C...%7D&auth_date=1710000000&hash=abc123...

{
  "status": "В работе",
  "business_direction": "Разработка",
  ...
}
```

### Response from `POST /deal/create`

```json
{
  "success": true,
  "deal_id": "DEAL-000042"
}
```

### Full Deal Object (returned by `GET /deal/{deal_id}`)

```json
{
  "deal_id": "DEAL-000042",
  "status": "В работе",
  "business_direction": "Разработка",
  "client": "ООО Рога и Копыта",
  "manager": "Иван Петров",
  "charged_with_vat": 250000.0,
  "vat_type": "С НДС",
  "paid": 125000.0,
  "project_start_date": "2024-01-15",
  "project_end_date": "2024-03-31",
  "act_date": null,
  "variable_expense_1": 15000.0,
  "variable_expense_2": null,
  "manager_bonus_percent": 10.0,
  "manager_bonus_paid": null,
  "general_production_expense": 8000.0,
  "source": "Рекомендация",
  "document_link": "https://docs.google.com/...",
  "comment": "Срочный проект, повышенный приоритет"
}
```

### Google Sheets Row (what gets written to "Учёт сделок")

The deal is stored as a single row. Column order matches the header row of the sheet. Example values in order:

```
DEAL-000042 | В работе | Разработка | ООО Рога и Копыта | Иван Петров |
250000 | С НДС | 125000 | 2024-01-15 | 2024-03-31 | | 15000 | 0 | 10 | 0 | 8000 |
Рекомендация | https://docs.google.com/... | Срочный проект, повышенный приоритет
```

### Journal Entry Written on Deal Creation

```
2024-01-15 09:30:00 UTC | 123456789 | Иван Петров | manager | create_deal |
DEAL-000042 | | client=ООО Рога и Копыта, status=В работе, charged_with_vat=250000.0
```

---

## Dependencies (`requirements.txt`)

| Package | Version | Purpose |
|---------|---------|---------|
| `aiogram` | 3.7.0 | Telegram Bot framework |
| `fastapi` | ≥0.111.0 | Web framework / API server |
| `uvicorn` | ≥0.30.0 | ASGI server |
| `pydantic-settings` | ≥2.3.0 | Settings management from env vars |
| `gspread` | 6.1.2 | Google Sheets client |
| `google-auth` | 2.29.0 | Google OAuth2 credentials |
| `python-dotenv` | 1.0.1 | `.env` file loading |
| `pytest` | 8.2.0 | Test framework |
| `pytest-asyncio` | 0.23.6 | Async test support |

## How to Start the Project

### Production

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

This single command:
1. Starts the FastAPI HTTP server on port 8000
2. Validates environment variables (`validate_settings()`)
3. Starts the Telegram bot polling loop as an asyncio background task
4. Serves the Mini App static files at `/miniapp`

### Development (bot standalone)

```bash
python -m bot.main
```

Starts only the Telegram bot polling (without the FastAPI HTTP server).

### Environment Setup

```bash
cp .env.example .env
# Edit .env with your values
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
