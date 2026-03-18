# Technical Report: Finance ERP Telegram Mini App

**Sections covered:** 5 (API Layer) · 6 (Settings / Dropdown Logic) · 13 (Authorization / User Context) · 15 (Configuration)

---

## Section 5 — API Layer

### Overview

The backend exposes **two parallel API surfaces** served by a single FastAPI application (`backend/main.py`):

| Surface | Router files | URL prefix | Backing storage |
|---------|-------------|-----------|----------------|
| **Modern SQL-first** | `deals_sql.py`, `expenses_sql.py`, `billing_sql.py`, `month_close.py` | `/deals`, `/expenses/v2`, `/billing/v2`, `/month` | PostgreSQL views & SQL functions |
| **Legacy** | `deals.py`, `billing.py`, `expenses.py` | `/deal`, `/billing`, `/expenses` | PostgreSQL ORM (legacy, preserved for backward compat) |

All routers are registered in `backend/main.py` lines 105–120. **SQL-first routers are registered before legacy routers** to prevent `/billing/{warehouse}` from matching `/billing/v2/*` paths.

A separate minimal app (`app/main.py`, v3.0.0) exists but is not used by the Mini App; it registers `managers`, `clients`, `deals`, `billing`, `expenses`, `reports` under `app/routers/`.

---

### Error Handling Pattern

All SQL-first routers follow the same pattern:

```python
try:
    return await read_sql_view(db, "public.v_api_*", ...)
except RuntimeError as exc:
    raise HTTPException(status_code=500, detail=str(exc)) from exc
```

`403` is returned when `X-Telegram-Id` header is missing or maps to no active user. `422` is returned by Pydantic on malformed request bodies.

---

### Endpoint Reference

#### Deals — `backend/routers/deals_sql.py` · prefix `/deals`

**GET `/deals`** — `list_deals()`

- **Auth**: `X-Telegram-Id` header (required)
- **Query params**: `manager_id: int`, `client_id: int`, `status_id: int`, `business_direction_id: int` (all optional)
- **Role logic**: `manager` role → automatically filtered to their own deals via `manager_telegram_id = :tid`; higher roles receive all deals or can apply the optional filters
- **Response**: `List[Dict]` — rows from `public.v_api_deals` view
- **Error**: `403` if no auth; `500` if DB error

**POST `/deals/create`** — `create_deal()`

- **Auth**: `X-Telegram-Id` header (required)
- **Request body**: `DealCreateRequest` (file `backend/schemas/deals.py` lines 12–33):

```python
class DealCreateRequest(BaseModel):
    status_id: int
    business_direction_id: int
    client_id: int
    manager_id: int
    charged_with_vat: Decimal
    charged_without_vat: Optional[Decimal] = None
    vat_type_id: Optional[int] = None
    vat_rate: Optional[Decimal] = None
    paid: Optional[Decimal] = Decimal("0")
    project_start_date: Optional[date] = None
    project_end_date: Optional[date] = None
    act_date: Optional[date] = None
    variable_expense_1_without_vat: Optional[Decimal] = None
    variable_expense_2_without_vat: Optional[Decimal] = None
    production_expense_without_vat: Optional[Decimal] = None
    manager_bonus_percent: Optional[Decimal] = None
    source_id: Optional[int] = None
    document_link: Optional[str] = None
    comment: Optional[str] = None
```

- **Response**: `Dict` — created deal record from `public.api_create_deal()` SQL function
- **Error**: `403` no auth; `500` DB error

**POST `/deals/pay`** — `pay_deal()`

- **Auth**: `X-Telegram-Id` header (required)
- **Request body** (`backend/schemas/deals.py`):

```python
class DealPayRequest(BaseModel):
    deal_id: Union[int, str]
    payment_amount: Decimal
    payment_date: Optional[date] = None
```

- **Response**: `Dict` from `public.api_pay_deal()`
- **Error**: `403` no auth; `500` DB error

**GET `/deals/{deal_id}`** — `get_deal()`

- **Auth**: `X-Telegram-Id` header (required)
- **Path param**: `deal_id` (int or string coerced to int)
- **Response**: Single deal `Dict` from `public.v_api_deals` filtered by `id = :deal_id`
- **Error**: `403` no auth; `404` if not found; `500` DB error

**PATCH `/deals/update/{deal_id}`** — `update_deal()`

- **Auth**: `X-Telegram-Id` header (required)
- **Path param**: `deal_id`
- **Request body**: `DealUpdate` — all fields optional (`backend/schemas/deals.py`)
- **Response**: `{"success": True, "deal_id": str}`
- **Error**: `403` no auth; `500` DB error

---

#### Settings — `backend/routers/settings.py` · no prefix

**GET `/settings`** — `get_settings()`

- **Auth**: None
- **Response**: `SettingsResponse` — `{statuses: List[str], business_directions: List[str], clients: List[str], managers: List[str], vat_types: List[str], sources: List[str]}`

**GET `/settings/enriched`** — `get_settings_enriched()`

- **Auth**: None
- **Response**: `Dict[str, Any]` with `{id, name}` objects (see Section 6 for full structure)
- **Error**: `500` with detail string

**GET `/settings/clients`** — `list_clients()`

- **Auth**: None
- **Response**: `List[Dict[str, Any]]`

**POST `/settings/clients`** — `create_client()`

- **Auth**: Optional `X-Telegram-Init-Data` + `X-User-Role`
- **Request body**: `ClientCreate(client_name: str)`
- **Response**: `Dict` with `client_id`

**PUT `/settings/clients/{client_id}`** — `update_client()`

- **Auth**: Optional
- **Request body**: `ClientUpdate(client_name: str)`
- **Response**: `Dict`

**DELETE `/settings/clients/{client_id}`** — `delete_client()`

- **Auth**: Optional
- **Response**: `{"success": True, "client_id": str}`

**GET `/settings/managers`** — `list_managers()`

- **Auth**: None
- **Response**: `List[Dict[str, Any]]`

**POST `/settings/managers`** — `create_manager()`

- **Auth**: Optional
- **Request body**: `ManagerCreate(manager_name: str, role: Optional[str])`
- **Response**: `Dict` with `manager_id`

**PUT `/settings/managers/{manager_id}`** — `update_manager()`

- **Auth**: Optional
- **Request body**: `ManagerUpdate(manager_name: str, role: Optional[str])`
- **Response**: `Dict`

**DELETE `/settings/managers/{manager_id}`** — `delete_manager()`

- **Auth**: Optional
- **Response**: `{"success": True, "manager_id": str}`

**GET `/settings/directions`** — `list_directions()`

- **Auth**: None
- **Response**: `List[str]`

**POST `/settings/directions`** — `add_direction()`

- **Request body**: `DirectionItem(value: str)`
- **Response**: `List[str]`

**DELETE `/settings/directions/{direction}`** — `remove_direction()`

- **Response**: `List[str]`

**GET `/settings/statuses`** — `list_statuses()`

- **Auth**: None
- **Response**: `List[str]`

**POST `/settings/statuses`** — `add_status()`

- **Request body**: `StatusItem(value: str)`
- **Response**: `List[str]`

**DELETE `/settings/statuses/{status}`** — `remove_status()`

- **Response**: `List[str]`

---

#### Authentication — `backend/routers/auth.py` · prefix `/auth`

**POST `/auth/miniapp-login`** — `miniapp_login_endpoint()`

- **Auth**: None (this is the login endpoint)
- **Request body**:

```python
class MiniAppLoginRequest(BaseModel):
    telegram_id: int
    full_name: str
    username: Optional[str] = None
    selected_role: str
    password: str
```

- **Response**:

```python
class MiniAppLoginResponse(BaseModel):
    user_id: int
    telegram_id: int
    full_name: str
    username: Optional[str] = None
    role: str
```

- **Errors**: `400` unknown role; `403` wrong password; `422` validation; `500` DB unavailable

**POST `/auth/role-login`** — `role_login()`

- **Request body**: `RoleLoginRequest(role: str, password: str)`
- **Response**: `RoleLoginResponse` — contains `role`, `label`, `editable_fields`

**POST `/auth/validate`** — `validate_auth()`

- **Auth**: `X-Telegram-Init-Data` header (Telegram initData HMAC-validated)
- **Response**: `{"valid": bool, "user": dict, "role": str, "full_name": str, "editable_fields": list}`

**GET `/auth/role`** — `get_user_role()`

- **Auth**: `X-Telegram-Init-Data` header
- **Response**: `UserAccessResponse` — role + permissions

---

#### Billing (SQL-first) — `backend/routers/billing_sql.py` · prefix `/billing/v2`

**GET `/billing/v2`** — `list_billing()`

- **Auth**: `X-Telegram-Id` header (required)
- **Query params**: `client_id: int`, `warehouse_id: int`, `month: str` (YYYY-MM format)
- **Response**: `List[Dict]` from `public.v_api_billing` view
- **Error**: `403` no auth; `500` DB error

**GET `/billing/v2/search`** — `search_billing()`

- **Auth**: `X-Telegram-Id` header (required)
- **Query params**: `warehouse_id: int`, `client_id: int`, `month: str`, `period: Optional[str]`
- **Response**: billing data `Dict` or `{"found": False}`
- **Error**: `403` no auth; `500` DB error

**POST `/billing/v2/upsert`** — `upsert_billing_entry()`

- **Auth**: `X-Telegram-Id` header (required)
- **Request body** (`backend/schemas/billing.py` lines 12–32):

```python
class BillingUpsertRequest(BaseModel):
    client_id: int
    warehouse_id: int
    month: str              # YYYY-MM
    period: Optional[str] = None
    shipments_with_vat: Optional[Decimal] = None
    shipments_without_vat: Optional[Decimal] = None
    units_count: Optional[int] = None
    storage_with_vat: Optional[Decimal] = None
    storage_without_vat: Optional[Decimal] = None
    pallets_count: Optional[int] = None
    returns_pickup_with_vat: Optional[Decimal] = None
    returns_pickup_without_vat: Optional[Decimal] = None
    returns_trips_count: Optional[int] = None
    additional_services_with_vat: Optional[Decimal] = None
    additional_services_without_vat: Optional[Decimal] = None
    penalties: Optional[Decimal] = None
    vat_type_id: Optional[int] = None
    comment: Optional[str] = None
```

- **Response**: `Dict` from `public.api_upsert_billing_entry()`
- **Error**: `403` no auth; `500` DB error

**POST `/billing/v2/pay`** — `pay_billing_entry()`

- **Auth**: `X-Telegram-Id` header (required)
- **Request body** (`backend/schemas/billing.py` lines 34–42):

```python
class BillingPayRequest(BaseModel):
    billing_entry_id: int
    payment_amount: Decimal
    payment_date: Optional[date] = None
```

- **Response**: `Dict` from `public.api_pay_billing_entry()`
- **Error**: `403` no auth; `500` DB error

**POST `/billing/v2/payment/mark`** — `mark_deal_payment()`

- **Auth**: `X-Telegram-Id` header (required)
- **Request body** (`backend/schemas/billing.py` lines 42–49):

```python
class BillingPaymentMarkRequest(BaseModel):
    deal_id: str            # string, coerced to int internally
    payment_amount: Decimal
```

- **Response**: `Dict` from `public.api_pay_deal()`
- **Error**: `403` no auth; `500` DB error

---

#### Expenses (SQL-first) — `backend/routers/expenses_sql.py` · prefix `/expenses/v2`

**GET `/expenses/v2`** — `list_expenses()`

- **Auth**: `X-Telegram-Id` header (required)
- **Query params**: `deal_id: Optional[int]`
- **Response**: `List[Dict]` from `public.v_api_expenses` view
- **Error**: `403` no auth; `500` DB error

**POST `/expenses/v2/create`** — `create_expense()`

- **Auth**: `X-Telegram-Id` header (required)
- **Request body** (`backend/schemas/expenses.py` lines 11–24):

```python
class ExpenseCreateRequest(BaseModel):
    deal_id: Optional[int] = None
    category_level_1_id: Optional[int] = None
    category_level_2_id: Optional[int] = None
    amount_without_vat: Decimal
    vat_type_id: Optional[int] = None
    vat_rate: Optional[Decimal] = None
    comment: Optional[str] = None
    # Legacy string fields (preserved for backward compat)
    expense_type: Optional[str] = None
    category_level_1: Optional[str] = None
    category_level_2: Optional[str] = None
```

- **Response**: `Dict` from `public.api_create_expense()`
- **Error**: `403` no auth; `500` DB error

---

#### Month Close — `backend/routers/month_close.py` · prefix `/month`

All endpoints require `X-Telegram-Id` header.

**POST `/month/archive`** — `archive_month()`

- **Request body**: `{"year": int, "month": int}`
- **Response**: `List[Dict]` — archived deal records

**POST `/month/cleanup`** — `cleanup_month()`

- **Request body**: `{"year": int, "month": int}`
- **Response**: `List[Dict]`

**POST `/month/close`** — `close_month()`

- **Request body**: `{"year": int, "month": int}`
- **Response**: `List[Dict]`

**GET `/month/archive-batches`** — `list_archive_batches()`

- **Query params**: `year: int`, `month: int`
- **Response**: `List[Dict]` — archive batch metadata

**GET `/month/archived-deals`** — `list_archived_deals()`

- **Query params**: `year: int`, `month: int`
- **Response**: `List[Dict]` — archived deals

---

#### Dashboard — `backend/routers/dashboard.py` · prefix `/dashboard`

**GET `/dashboard`** — `dashboard()`

- **Auth**: `X-Telegram-Id` or `X-Telegram-Init-Data` (optional; returns `403` if no valid user)
- **Response**: `Dict[str, Any]` — role-aware aggregated stats:
  - `manager` → `_build_manager_summary()` — own deals totals
  - `accountant`/`accounting` → `_build_accountant_summary()` — receivables
  - `operations_director`/`head_of_sales` → `_build_operations_summary()` — full ops view
  - `admin` → `_build_operations_summary()`

**GET `/dashboard/owner`** — `owner_dashboard()`

- **Auth**: `X-Telegram-Id` (required; requires `operations_director`, `accounting`, or `admin` role)
- **Query params**: `month: Optional[str]` (YYYY-MM)
- **Response**: merged `_build_owner_summary()` + `_build_billing_summary()` dict

**GET `/dashboard/summary`** — `dashboard_summary()`

- **Auth**: `X-Telegram-Id` (required)
- **Response**: `List[Dict]` from `public.v_dashboard_summary` view

---

#### Journal — `backend/routers/journal.py` · prefix `/journal`

**GET `/journal/recent`** — `get_recent_journal()`

- **Auth**: `X-Telegram-Init-Data` or `X-User-Role` (optional)
- **Response**: `List[Dict]` — recent audit log entries, role-filtered

**GET `/journal`** — `get_journal()`

- **Auth**: Optional
- **Response**: `List[Dict]` — full audit log

**POST `/journal`** — `add_journal_entry()`

- **Auth**: Optional
- **Response**: `Dict` — created journal entry

---

#### Receivables — `backend/routers/receivables.py` · prefix `/receivables`

**GET `/receivables`** — unnamed handler

- **Auth**: `X-Telegram-Id` header (required)
- **Response**: `Dict[str, Any]` — receivables summary

---

#### Reports — `backend/routers/reports.py` · prefix `/reports`

All endpoints require `X-Telegram-Id` or `X-Telegram-Init-Data`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/reports/warehouse/{warehouse}` | Per-warehouse billing report |
| GET | `/reports/clients` | Client-level report |
| GET | `/reports/expenses` | Expense breakdown |
| GET | `/reports/profit` | Profit report |
| GET | `/reports/warehouse-revenue` | Warehouse revenue |
| GET | `/reports/paid-deals` | Paid deals |
| GET | `/reports/unpaid-deals` | Unpaid deals |
| GET | `/reports/paid-billing` | Paid billing entries |
| GET | `/reports/unpaid-billing` | Unpaid billing entries |
| GET | `/reports/billing-by-month` | Billing by month |
| GET | `/reports/billing-by-client` | Billing by client |
| GET | `/reports/debt-by-client` | Debt by client |
| GET | `/reports/debt-by-warehouse` | Debt by warehouse |
| GET | `/reports/overdue-payments` | Overdue payments |
| GET | `/reports/partially-paid-billing` | Partially paid billing |
| GET | `/reports/open-deals` | Open deals |
| GET | `/reports/manager-performance` | Manager performance |
| GET | `/reports/client-profitability` | Client profitability |
| GET | `/reports/warehouse-billing` | Warehouse billing |
| GET | `/reports/expense-structure` | Expense structure |

---

#### Legacy Billing — `backend/routers/billing.py` · prefix `/billing`

**Preserved for backward compatibility; deprecated.**

| Method | Path | Function |
|--------|------|----------|
| GET | `/billing/search` | `search_billing()` |
| GET | `/billing/{warehouse}` | `get_billing_by_warehouse()` |
| GET | `/billing/{warehouse}/{client_name}` | `get_billing_entry()` |
| POST | `/billing/{warehouse}` | `upsert_billing()` |
| POST | `/billing/payment/mark` | `mark_payment()` |

---

#### Legacy Deals — `backend/routers/deals.py` · prefix `/deal`

**Preserved for backward compatibility; deprecated.**

| Method | Path | Function |
|--------|------|----------|
| POST | `/deal/create` | `create_deal()` |
| GET | `/deal/all` | `get_all_deals()` |
| GET | `/deal/user` | `get_user_deals()` |
| GET | `/deal/filter` | `get_filtered_deals()` |
| GET | `/deal/{deal_id}` | `get_deal()` |
| PUT | `/deal/{deal_id}` | `update_deal()` |
| PATCH | `/deal/update/{deal_id}` | `patch_deal()` |

---

#### Legacy Expenses — `backend/routers/expenses.py` · prefix `/expenses`

**Deprecated.**

| Method | Path | Function |
|--------|------|----------|
| POST | `/expenses` | `create_expense()` |
| POST | `/expenses/bulk` | `create_bulk_expenses()` |
| GET | `/expenses` | `list_expenses()` |

---

#### Health Checks — `backend/main.py`

| Method | Path | Response |
|--------|------|----------|
| GET | `/` | `{"status": "ok"}` |
| HEAD | `/` | `200 OK` |
| GET | `/health` | `{"status": "ok"}` |
| HEAD | `/health` | `200 OK` |

---

### Dependency Injection

All SQL-first and dashboard endpoints receive an `AsyncSession` via:

```python
from app.database.database import get_db
db: AsyncSession = Depends(get_db)
```

File: `app/database/database.py`.

---

---

## Section 6 — Settings / Dropdown Logic

### `GET /settings/enriched` — Implementation

**File**: `backend/routers/settings.py` lines 65–77

```python
@router.get("/settings/enriched", response_model=Dict[str, Any])
async def get_settings_enriched(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    try:
        return await settings_service.load_enriched_settings_pg(db)
    except Exception as exc:
        logger.error("Error loading enriched settings: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
```

Delegates entirely to `backend/services/settings_service.py` → `load_enriched_settings_pg(db)`.

---

### Response Structure

**File**: `backend/services/settings_service.py` lines 526–608

The complete response shape returned by `load_enriched_settings_pg()`:

```python
{
    "statuses": [
        {"id": int, "name": str},
        ...
    ],
    "business_directions": [
        {"id": int, "name": str},
        ...
    ],
    "vat_types": [
        {"id": int, "name": str},
        ...
    ],
    "sources": [
        {"id": int, "name": str},
        ...
    ],
    "clients": [
        {"id": int, "name": str},
        ...
    ],
    "managers": [
        {"id": int, "name": str},
        ...
    ],
    "warehouses": [
        {"id": int, "name": str, "code": str},
        ...
    ],
    "expense_categories": [
        {
            "id": int,
            "name": str,
            "sub_categories": [
                {"id": int, "name": str},
                ...
            ]
        },
        ...
    ]
}
```

**Field names used by backend**:

- `id` — numeric PK
- `name` — display label
- `code` — warehouse short code (e.g., `"MSK"`, `"NSK"`, `"EKB"`)
- `sub_categories` — nested list of level-2 expense categories

**VAT types fallback**: if the `vat_types` table is empty, the backend hardcodes:

```python
vat_types = [{"id": 1, "name": "С НДС"}, {"id": 2, "name": "Без НДС"}]
```

(`backend/services/settings_service.py` line 551)

---

### How the Frontend Loads Settings

**File**: `miniapp/app.js` function `loadSettings()` (lines 173–206)

```javascript
async function loadSettings() {
  if (state.settings) return state.settings;   // cached
  try {
    const enriched = await apiFetch('/settings/enriched');
    state.enrichedSettings = enriched;
    state.settings = enriched;
    populateSelects(enriched);
    updateSettingsStats(enriched);
    return enriched;
  } catch (err) {
    showToast('Ошибка загрузки справочников. Используются значения по умолчанию.', 'warning');
    const fallback = { /* hardcoded Russian strings, NOT {id,name} objects */ };
    state.settings = fallback;
    // NOTE: does NOT call populateSelects with fallback
  }
}
```

- Called once at app init; result is cached in `state.settings` and `state.enrichedSettings`.
- On success: calls `populateSelects(enriched)` which fills all dropdowns.
- On failure: stores plain-string fallback arrays in `state.settings` but **does not populate form dropdowns** — forms become non-submittable (blocked at submit time via `if (!state.enrichedSettings)` guard).

---

### `populateSelects()` — Dropdown Filling

**File**: `miniapp/app.js` lines 208–256

```javascript
function populateSelects(data) {
  fillSelect('status',              data.statuses || []);
  fillSelect('business_direction',  data.business_directions || []);
  fillSelect('client',              data.clients || []);
  fillSelect('manager',             data.managers || []);
  fillSelect('vat_type',            data.vat_types || []);
  fillSelect('source',              data.sources || []);
  fillSelect('billing-client-select', data.clients || []);

  if (data.warehouses && data.warehouses.length > 0) {
    fillSelect('billing-warehouse', data.warehouses.map(w => ({
      id: w.id,
      name: `${(w.code || '').toUpperCase()} — ${w.name}`,
    })));
  }

  if (data.expense_categories && data.expense_categories.length > 0) {
    const cat1Items = [];
    data.expense_categories.forEach(cat => {
      const key = cat.name.toLowerCase();
      EXPENSE_CATS_L2[key] = (cat.sub_categories || []).map(sc => sc.name);
      cat1Items.push({ id: cat.name, name: cat.name });  // id = string name
    });
    fillSelect('expense-cat1', cat1Items);
  }
}
```

---

### `fillSelect()` — Option Population Helper

**File**: `miniapp/app.js` lines 264–291

```javascript
function fillSelect(id, options, hasAll = false) {
  const select = document.getElementById(id);
  if (!select) return;

  const currentValue = select.value;
  const firstOption = select.options[0];   // keep placeholder option
  select.innerHTML = '';
  if (firstOption) select.appendChild(firstOption);

  options.forEach(opt => {
    const option = document.createElement('option');
    if (opt && typeof opt === 'object' && 'id' in opt) {
      option.value    = String(opt.id);      // numeric ID sent to API
      option.textContent = opt.name;         // label shown to user
      option.dataset.name = opt.name;
    } else {
      option.value    = opt;
      option.textContent = opt;
    }
    select.appendChild(option);
  });

  if (currentValue) select.value = currentValue;
}
```

---

### Complete Dropdown Population Map

| HTML element ID | Data source key | Field used as `value` | Field used as label |
|---|---|---|---|
| `status` | `data.statuses` | `id` (int) | `name` |
| `business_direction` | `data.business_directions` | `id` (int) | `name` |
| `client` | `data.clients` | `id` (int) | `name` |
| `manager` | `data.managers` | `id` (int) | `name` |
| `vat_type` | `data.vat_types` | `id` (int) | `name` |
| `source` | `data.sources` | `id` (int) | `name` |
| `billing-client-select` | `data.clients` | `id` (int) | `name` |
| `billing-warehouse` | `data.warehouses` | `id` (int) | `"CODE — Name"` (composed) |
| `expense-cat1` | `data.expense_categories` | `name` **(string, not numeric ID)** | `name` |
| `payment-direction-select` | `data.business_directions` | `id` (int) | `name` |
| `payment-client-select` | `data.clients` | `id` (int) | `name` |
| `payment-deal-select` | dynamic `/deals` API call | `d.id` | `d.deal_name \|\| d.client \|\| "Сделка #N"` |

---

### Dependent Dropdown Logic

**File**: `miniapp/app.js` `initDependentDealDropdowns()` lines 343–361

```javascript
function initDependentDealDropdowns(dirSelectId, clientSelectId, dealSelectId) {
  const dirEl    = document.getElementById(dirSelectId);
  const clientEl = document.getElementById(clientSelectId);
  const dealEl   = document.getElementById(dealSelectId);

  const reload = () => {
    const dirId    = dirEl.value    || null;
    const clientId = clientEl.value || null;
    if (dirId || clientId) {
      loadDealsFiltered(dealSelectId, dirId, clientId);
    } else {
      populateSelectFromObjects(dealEl, []);
    }
  };

  dirEl.addEventListener('change', reload);
  clientEl.addEventListener('change', reload);
}
```

`loadDealsFiltered()` (lines 362–385) calls:

```javascript
apiFetch(`/deals?business_direction_id=${directionId}&client_id=${clientId}`)
```

and maps the result to `{id: d.id, name: d.deal_name || d.client || "Сделка #N"}`.

---

### Known Bugs / Mismatches

1. **Expense category L1 uses string name as `id`** (`miniapp/app.js` line 252):
   `cat1Items.push({ id: cat.name, name: cat.name })` — the `value` attribute of `expense-cat1` options is a string (e.g., `"Операционные расходы"`), not the numeric `cat.id`. All other enriched dropdowns store a numeric ID as the option value. As a result, when the expense create form is submitted, `category_level_1_id` receives a `null`/`undefined` value (since the submitted string cannot be coerced to `int`) and the backend falls back to the legacy `category_level_1` string field instead. This means the SQL function `public.api_create_expense()` receives a string name rather than an integer FK, which is a contract mismatch with the schema's `category_level_1_id: Optional[int]` field.

2. **Warehouse `code` may be empty**: the warehouse display name is composed as `` `${(w.code || '').toUpperCase()} — ${w.name}` ``. When a warehouse record has `code = null` or `code = ""` in the database, the rendered dropdown label is `" — WarehouseName"` (leading separator with no code). The backend schema does not enforce non-null `code`, so any warehouse without a code silently produces a visually broken label in the UI.

3. **Fallback values break form submission**: when `/settings/enriched` fails, the fallback stored in `state.settings` contains plain Russian strings (not `{id, name}` objects). The `populateSelects` function is NOT called with the fallback data. Form selects remain empty; the submit guard (`if (!state.enrichedSettings)`) blocks deal creation — which is the intended defensive behavior — but no user-visible indicator is shown that the form is permanently broken until page reload.

4. **`payment-direction-select` and `payment-client-select` depend on `state.enrichedSettings`**: these selects are populated in the payment tab initialization by reading `state.enrichedSettings.business_directions` and `state.enrichedSettings.clients`. Because `state.enrichedSettings` is only set when `loadSettings()` succeeds, on a settings-load failure these two selects are never populated. The tab renders but neither dropdown has any options, and no error or warning is displayed to the user.

---

---

## Section 13 — Authorization / User Context

### Authentication Architecture

The Mini App uses **two concurrent auth mechanisms** depending on context:

| Mechanism | Header(s) | Used for | Validated by |
|---|---|---|---|
| Telegram-ID lookup | `X-Telegram-Id` | All SQL-first endpoints | DB lookup against `app_users.telegram_id` |
| Telegram initData HMAC | `X-Telegram-Init-Data` | Legacy auth endpoints, `/auth/validate`, `/auth/role` | HMAC-SHA256 against bot token |
| Role + password login | POST `/auth/miniapp-login` | Mini App first-time login | Password compared to env var |

There is **no token/session issued**: after `POST /auth/miniapp-login`, the Mini App stores the `telegram_id` in `localStorage` and sends it in `X-Telegram-Id` on every subsequent request. The backend re-queries the `app_users` table on every request. This means:

- There is no way to invalidate access without setting `is_active = false` in the `app_users` table.
- Any code that can read `localStorage` (e.g., injected scripts from a compromised page) can obtain the `telegram_id` and impersonate the user.
- Every authenticated API call incurs at least two DB queries (one to look up `app_users`, one to look up `roles`).

---

### Step 1: First-time Login (Password-based)

**Frontend** (`miniapp/app.js` login form submit handler):

```javascript
const resp = await apiFetch('/auth/miniapp-login', {
  method: 'POST',
  body: JSON.stringify({
    telegram_id: telegramUser.id,
    full_name:   telegramUser.first_name + ' ' + (telegramUser.last_name || ''),
    username:    telegramUser.username,
    selected_role: roleSelect.value,
    password:    passwordInput.value,
  }),
});
localStorage.setItem('telegram_id', String(telegramUser.id));
localStorage.setItem('user_role',   resp.role);
```

**Backend** (`backend/routers/auth.py` → `backend/services/miniapp_auth_service.py`):

1. Looks up `Role` record in DB by `code = selected_role`.
2. Calls `_verify_role_password(selected_role, password)` — compares against env var.
3. Calls `_upsert_app_user_sql()` — inserts/updates `app_users` via `public.upsert_app_user()` SQL function.
4. If `selected_role == "manager"`, calls `_ensure_manager_record()` to auto-create a `managers` row.
5. Returns `MiniAppLoginResponse`.

---

### `_verify_role_password()` — Password Validation

**File**: `backend/services/miniapp_auth_service.py`

```python
def _verify_role_password(role: str, password: str) -> bool:
    mapping = {
        "manager":             settings.role_password_manager,
        "operations_director": settings.role_password_operations_director,
        "accounting":          settings.role_password_accounting,
        "admin":               settings.role_password_admin,
    }
    expected = mapping.get(role)
    if expected is None:
        return False          # unknown role → deny
    return expected == password
```

Passwords are compared **as plain strings** (no hashing). The role password values are loaded from environment variables at startup and held in memory for the lifetime of the process. Configured via env vars (see Section 15).

---

### Step 2: Per-request Auth via `X-Telegram-Id`

**File**: `backend/routers/deals_sql.py` lines 35–55

```python
async def _resolve_user(
    db: AsyncSession,
    x_telegram_id: Optional[str],
) -> tuple:
    if not x_telegram_id:
        return None, NO_ACCESS_ROLE, ""
    try:
        tid = int(x_telegram_id.strip())
    except (ValueError, TypeError):
        return None, NO_ACCESS_ROLE, ""

    user = await get_user_by_telegram_id(db, tid)   # queries app_users
    if user is None:
        return None, NO_ACCESS_ROLE, ""

    role = await get_role_code(db, user.role_id)     # queries roles
    return user.id, role or NO_ACCESS_ROLE, user.full_name
```

The same `_resolve_user()` pattern (or equivalent inline code) is used in `deals_sql.py`, `billing_sql.py`, `expenses_sql.py`, `month_close.py`, `dashboard.py`, and `receivables.py`.

The `app_users` table columns used: `telegram_id`, `role_id`, `full_name`, `is_active`.

---

### Telegram initData Validation (Legacy path)

**File**: `backend/services/telegram_auth.py`

```python
def validate_telegram_init_data(init_data: str, bot_token: str) -> bool:
    parsed = dict(parse_qsl(unquote(init_data), keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(key=b"WebAppData", msg=bot_token.encode(), digestmod=hashlib.sha256).digest()
    computed_hash = hmac.new(key=secret_key, msg=data_check_string.encode(), digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed_hash, received_hash)
```

Follows the official Telegram Mini App initData validation algorithm. Used by `POST /auth/validate` and `GET /auth/role`.

---

### Frontend User Context Storage

**File**: `miniapp/app.js`

In-memory:

```javascript
let telegramUser = null;   // set from window.Telegram.WebApp.initDataUnsafe.user
const state = {
    settings: null,
    enrichedSettings: null,
    deals: [],
    currentTab: 'new-deal',
    isSubmitting: false,
    isLoadingDeals: false,
};
```

`localStorage` keys:

| Key | Value | Purpose |
|-----|-------|---------|
| `telegram_id` | integer string | Sent as `X-Telegram-Id` on every API call |
| `user_role` | role code string | Sent as `X-User-Role` on every API call |

---

### Header Construction in `apiFetch()`

**File**: `miniapp/app.js` lines 72–95

```javascript
async function apiFetch(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers };

  const initData = getTelegramInitData();   // tg.initData (may be empty outside Telegram)
  if (initData) headers['X-Telegram-Init-Data'] = initData;

  if (!headers['X-Telegram-Id']) {
    const telegramId = telegramUser?.id || localStorage.getItem('telegram_id');
    if (telegramId) headers['X-Telegram-Id'] = String(telegramId);
  }

  if (!headers['X-User-Role']) {
    const savedRole = localStorage.getItem('user_role');
    if (savedRole) headers['X-User-Role'] = savedRole;
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  // ...
  return response.json();
}
```

Three headers are sent simultaneously on every request:

- `X-Telegram-Init-Data` — raw Telegram initData string (only available inside Telegram client)
- `X-Telegram-Id` — numeric Telegram user ID (from live `telegramUser` or localStorage fallback)
- `X-User-Role` — role code from localStorage

---

### Role-Based UI (Frontend)

**File**: `frontend/js/permissions.js`

```javascript
class Permissions {
  constructor(role) {
    this.role = role || 'no_access';
    this.roleLabel = ROLE_LABELS[role] || 'Unknown';
  }

  canViewDeals()     { return ['manager', 'accountant', 'operations_director', 'admin'].includes(this.role); }
  canEditBilling()   { return ['manager', 'admin'].includes(this.role); }
  canViewJournal()   { return ['operations_director', 'admin'].includes(this.role); }
  canViewAnalytics() { return ['accounting', 'operations_director', 'admin'].includes(this.role); }
}
```

Note: the `frontend/` directory contains a separate SPA distinct from `miniapp/`. The `miniapp/app.js` does its own inline tab/section visibility toggling based on the stored role.

---

### Role-Based Backend Access

**File**: `backend/services/permissions.py` lines 21–47

```python
ALLOWED_ROLES = frozenset({
    "manager", "accountant", "accounting",
    "operations_director", "head_of_sales", "admin",
})

NO_ACCESS_ROLE = "no_access"

ROLE_VISIBLE_DATA = {
    "manager":             "own",   # filtered to their telegram_id
    "accountant":          "all",
    "accounting":          "all",
    "operations_director": "all",
    "head_of_sales":       "all",
    "admin":               "all",
    NO_ACCESS_ROLE:        "none",
}

ROLE_EDITABLE_FIELDS = {
    "manager":             _BUSINESS_FIELDS,
    "accountant":          _ACCOUNTING_FIELDS,
    "operations_director": _ALL_FIELDS,
    "head_of_sales":       _ALL_FIELDS,
    "accounting":          _ACCOUNTING_FIELDS,
    "admin":               _ALL_FIELDS,
    NO_ACCESS_ROLE:        frozenset(),
}
```

---

### `app_users` Database Model

**File**: `app/database/models.py`

Relevant columns used by auth:

| Column | Type | Purpose |
|--------|------|---------|
| `id` | int PK | Internal user ID |
| `telegram_id` | bigint unique | Telegram user ID — lookup key |
| `full_name` | str | Display name |
| `username` | str nullable | Telegram username |
| `role_id` | int FK → `roles.id` | Role reference |
| `is_active` | bool | Active flag — inactive users are treated as no-access |
| `updated_at` | datetime | Last upsert timestamp |

---

---

## Section 15 — Configuration

### API Base URL

**Frontend** (`miniapp/app.js` lines 10–18):

```javascript
const API_BASE = (function () {
  const meta = document.querySelector('meta[name="api-base"]');
  if (meta && meta.content) return meta.content.replace(/\/$/, '');
  if (window.APP_CONFIG && window.APP_CONFIG.apiBase) return window.APP_CONFIG.apiBase;
  return window.location.origin;   // default: same origin
})();
```

Priority order:

1. `<meta name="api-base" content="...">` in `miniapp/index.html`
2. `window.APP_CONFIG.apiBase` global override
3. `window.location.origin` (same-origin fallback — works when backend serves the frontend at the same host)

The `miniapp/index.html` currently has `content=""` (empty), so the same-origin fallback is used in practice.

---

### `app/core/config.py` — Settings Class

```python
class Settings(BaseSettings):
    database_url: str = os.getenv("DATABASE_URL", "")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    webapp_url: str = os.getenv("WEBAPP_URL", "")
    api_base_url: str = os.getenv("API_BASE_URL", "")

    # Controls ORM fallback: 'production' disables it
    app_env: str = os.getenv("APP_ENV", "development")

    # Role passwords (plain text, compared at login)
    role_password_manager: str = os.getenv("ROLE_PASSWORD_MANAGER", "")
    role_password_operations_director: str = os.getenv("ROLE_PASSWORD_OPERATIONS_DIRECTOR", "")
    role_password_accounting: str = os.getenv("ROLE_PASSWORD_ACCOUNTING", "")
    role_password_admin: str = os.getenv("ROLE_PASSWORD_ADMIN", "")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
```

Instantiated as a module-level singleton: `settings = Settings()`.

---

### `config/config.py` — validate_settings()

**File**: `config/config.py`

`validate_settings()` checks that `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, and `WEBAPP_URL` are non-empty. Called inside `lifespan()` in `backend/main.py` (line 35) — **not at import time**, to allow test imports without a real DB.

---

### `backend/config.py` — Legacy Configuration

Retained for the Google Sheets legacy layer and role constants:

```python
SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")
SHEET_DEALS    = "Учёт сделок"
SHEET_SETTINGS = "Настройки"
SHEET_JOURNAL  = "Журнал действий"

BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN", "")
MINI_APP_URL = os.getenv("WEBAPP_URL", "")

ROLE_MANAGER             = "manager"
ROLE_ACCOUNTANT          = "accountant"
ROLE_OPERATIONS_DIRECTOR = "operations_director"
ROLE_HEAD_OF_SALES       = "head_of_sales"
```

Also defines column index constants for the Sheets layout (`DEAL_COL_*`, `JOURNAL_COL_*`, `SETTINGS_COL_*`).

---

### `backend/main.py` — Application Setup

```python
RUN_BOT: bool = os.getenv("RUN_BOT", "false").lower() == "true"

app = FastAPI(
    title="Финансовая система API",
    description="Backend API для Telegram Mini App учёта сделок",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/miniapp", StaticFiles(directory="miniapp", html=True), name="miniapp")
```

Key env vars consumed at startup:

| Variable | Default | Purpose |
|----------|---------|---------|
| `RUN_BOT` | `"false"` | Start aiogram polling alongside API |
| `DATABASE_URL` | — | PostgreSQL async connection string |
| `TELEGRAM_BOT_TOKEN` | — | Bot token (required if `RUN_BOT=true`) |
| `WEBAPP_URL` | — | Public HTTPS URL of Mini App |
| `APP_ENV` | `"development"` | Controls ORM fallback behavior |
| `ROLE_PASSWORD_MANAGER` | `""` | Password for `manager` role login |
| `ROLE_PASSWORD_OPERATIONS_DIRECTOR` | `""` | Password for `operations_director` role login |
| `ROLE_PASSWORD_ACCOUNTING` | `""` | Password for `accounting` role login |
| `ROLE_PASSWORD_ADMIN` | `""` | Password for `admin` role login |

---

### Telegram WebApp SDK Configuration

**File**: `miniapp/index.html`

```html
<script src="https://telegram.org/js/telegram-web-app.js"></script>
```

**File**: `miniapp/app.js` lines 28–49

```javascript
const tg = window.Telegram?.WebApp;
let telegramUser = null;

function initTelegram() {
  if (!tg) {
    console.warn('Telegram WebApp SDK not available');
    return;
  }
  tg.ready();
  tg.expand();
  if (tg.colorScheme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
  telegramUser = tg.initDataUnsafe?.user || null;
  if (telegramUser) renderUserAvatar(telegramUser);
}
```

The app gracefully degrades when run outside the Telegram client (`!tg` branch).

---

### Hardcoded Values

| Location | Value | Purpose |
|----------|-------|---------|
| `backend/services/settings_service.py:551` | `[{"id":1,"name":"С НДС"},{"id":2,"name":"Без НДС"}]` | VAT type fallback when DB is empty |
| `backend/services/settings_service.py:66–74` | `_DEFAULTS` dict with Russian-language strings | Per-section fallback when DB query returns nothing |
| `miniapp/app.js:20–22` | `'Новый (с НДС)'`, `'Новый (без НДС)'`, `'Старый (p1/p2)'` | Billing input mode constants |
| `miniapp/app.js:189–204` | Russian status/direction/vat_type strings | Frontend fallback when `/settings/enriched` fails |
| `backend/config.py:8–9` | `"Учёт сделок"`, `"Настройки"`, `"Журнал действий"` | Google Sheets tab names (legacy) |

---

### Environment-Dependent Logic

1. **`APP_ENV=production`** disables the ORM fallback in `miniapp_auth_service._upsert_app_user_sql()`:

   ```python
   is_prod = getattr(settings, "app_env", "development").lower() == "production"
   if is_prod:
       raise RuntimeError("Login unavailable: public.upsert_app_user() SQL function is not accessible.")
   ```

   In non-production environments, if `public.upsert_app_user()` fails, the service falls back to direct ORM writes.

2. **`RUN_BOT=true`** starts aiogram Telegram bot long-polling alongside the FastAPI server (inside `lifespan()`). Default is `false`.

3. **`DATABASE_URL` missing**: `validate_settings()` raises a `ValueError` at startup listing all missing variables.

---

### Mock / Test Values

**Test files** (`tests/test_smoke.py` lines 14–18, `tests/test_new_features.py` lines 22–30):

```python
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("WEBAPP_URL", "http://localhost")
os.environ.setdefault("DATABASE_URL", "postgresql://user:password@localhost:5432/test")
os.environ.setdefault("ROLE_PASSWORD_MANAGER", "1")
os.environ.setdefault("ROLE_PASSWORD_ADMIN", "12345")
```

All test files must use **identical values** for the `ROLE_PASSWORD_*` variables to avoid test isolation failures (a documented convention in this project).

**`.env.example`** (repository root):

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
WEBAPP_URL=https://your-domain.com/miniapp
DATABASE_URL=postgresql://user:password@host:5432/database
API_BASE_URL=https://your-backend-domain.com
ROLE_PASSWORD_MANAGER=your_manager_password
ROLE_PASSWORD_OPERATIONS_DIRECTOR=your_operations_director_password
ROLE_PASSWORD_ACCOUNTING=your_accounting_password
ROLE_PASSWORD_ADMIN=your_admin_password
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
RUN_BOT=false
APP_ENV=development
```
