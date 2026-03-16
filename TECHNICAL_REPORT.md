# Technical Report: Telegram Mini App – Finance ERP
## Sections 12, 16, 17, 18, 19, 20

> **Basis:** All statements in this report are derived exclusively from direct code inspection.
> Every file path, function name, variable, and line reference corresponds to real code found in the repository.
> Where something cannot be confirmed from the code, this is explicitly stated.

---

## 12. ERROR HANDLING

### 12.1 How the Frontend Handles API Errors

There are **two separate frontend applications** in this repository with different error-handling implementations:

#### A. `miniapp/app.js` — Active Mini App

Core API function: **`apiFetch(path, options)`** (lines 72–110).

```js
// miniapp/app.js:97-106
if (!response.ok) {
  let errorDetail = `HTTP ${response.status}`;
  try {
    const err = await response.json();
    const rawDetail = err.detail || err.error;
    if (rawDetail !== undefined && rawDetail !== null) {
      errorDetail = typeof rawDetail === 'string' ? rawDetail : JSON.stringify(rawDetail);
    }
  } catch (_) {}
  throw new Error(errorDetail);
}
```

- Reads `err.detail` first (FastAPI default), then `err.error` as fallback.
- If `rawDetail` is not a string (e.g. a Pydantic validation array of error objects), it uses `JSON.stringify`, which produces valid JSON text instead of the `[object Object]` string that JavaScript's default `.toString()` would yield on a plain object.
- Non-JSON responses are silently swallowed by `catch (_) {}`.
- Always throws an `Error`; never returns an error object.

#### B. `frontend/js/api.js` — Legacy Frontend (ApiClient class)

Core API function: **`ApiClient._request(method, path, body)`** (lines 23–40).

```js
// frontend/js/api.js:30-36
const data = await res.json().catch(() => ({}));
if (!res.ok) {
  const err = new Error(data.error || `HTTP ${res.status}`);
  err.status = res.status;
  err.data = data;
  throw err;
}
```

- Reads only `data.error`. Does **not** read `data.detail`, which is FastAPI's standard error field.
- If `data.error` is an **object** (not a string), then `new Error(objectValue)` will produce a message of `[object Object]` — see Section 12.2.
- No JSON stringification for non-string values.

---

### 12.2 Where `[object Object]` Can Appear

#### Location 1: `frontend/js/api.js`, `ApiClient._request()`, line 33

```js
const err = new Error(data.error || `HTTP ${res.status}`);
```

- If the backend returns `{ "error": { "code": 500, "detail": "..." } }` (an object, not a string), `new Error({...})` produces `[object Object]` as `err.message`.
- This message is then passed to `showToast(e.message, 'error')` in `frontend/js/app.js` and displayed raw.
- FastAPI returns `{ "detail": "..." }` by default, not `{ "error": "..." }`. Since `ApiClient` reads `data.error` and FastAPI sends `data.detail`, most errors will fall through to the `HTTP ${res.status}` fallback, not the object path. However, the pattern is fragile.

#### Location 2 (not present in `miniapp/app.js`):

The active `miniapp/app.js` uses `JSON.stringify` for non-string `rawDetail`, so `[object Object]` is handled correctly there. No `[object Object]` risk exists in `miniapp/app.js`.

---

### 12.3 Current Helper Functions for Errors

#### `miniapp/app.js`

| Function | Purpose |
|---|---|
| `apiFetch(path, options)` | Central fetch wrapper; throws `Error` with string message on non-OK responses |
| `showToast(message, type, duration)` | Displays toast notification; uses `escHtml()` for safe rendering |
| `escHtml(str)` | Sanitizes strings for innerHTML injection |

`showToast` (lines 1132–1156) creates new DOM elements per toast, appends to `#toast-container`, auto-removes after `duration` ms. Types: `success`, `error`, `warning`, `default`.

#### `frontend/js/app.js`

| Function | Purpose |
|---|---|
| `showToast(msg, type)` | Sets `#toast` textContent directly; toggles visibility class |
| `showLoading(show)` | Shows/hides `#loading` element |

`frontend/js/app.js:37-42`:
```js
function showToast(msg, type = 'info') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `toast toast--${type} toast--visible`;
  setTimeout(() => t.classList.remove('toast--visible'), 3000);
}
```

This replaces the previous toast text (only one toast at a time). Incompatible with the miniapp's per-element toast system.

---

### 12.4 Alert / Notification / Toast Usage

- **`miniapp/app.js`**: Uses only `showToast()`. No `alert()` calls anywhere (except `confirm()` used for destructive confirmations: `deleteClient`, `deleteManager`, `deleteDirection`, `deleteStatus`, `runMonthArchive`).
- **`frontend/js/app.js`**: Uses `showToast()` and `confirm()` for delete confirmation in `DealsScreen._deleteDeal()` (line 376).
- **No `alert()` calls found** in either main frontend file.

---

### 12.5 Inconsistent Error Patterns

1. **Two error field names**: `miniapp/app.js` reads `err.detail || err.error`; `frontend/js/api.js` reads only `data.error`. FastAPI sends `detail`. The miniapp is correct; the legacy frontend always falls back to `HTTP ${status}`.

2. **Two toast implementations**: `miniapp/app.js` dynamically creates per-toast elements with `container.appendChild(toast)`; `frontend/js/app.js` overwrites a single `#toast` element's `textContent`. They are incompatible and cannot coexist on the same page.

3. **`AnalyticsScreen.load()` in `frontend/js/app.js` (line 437)**: Uses `Promise.all([...])` without a try-catch at the function level. Error bubbles up to `App._navigate()` which wraps in `try-catch`, so it is handled — but the error message is generic.

4. **`loadBillingEntry()` dual-path** (`miniapp/app.js`, lines 1957–2017): The legacy path (`else` branch) has its own `apiFetch` call with an early `return`. The v2 path continues after. The `statusEl` error message and toast are duplicated between both paths with slightly different text patterns.

5. **`downloadReport()` (`miniapp/app.js`, lines 2594–2638)**: Uses raw `fetch(...)` instead of `apiFetch(...)`. Error handling is manual:
   ```js
   const err = await response.json().catch(() => ({}));
   throw new Error(err.detail || `HTTP ${response.status}`);
   ```
   This reads `err.detail` correctly but bypasses the centralized `apiFetch` helper.

6. **`loadJournal()` (`miniapp/app.js`, lines 2648–2691)**: Passes extra `X-User-Role` header manually via `options.headers`, rather than relying on `apiFetch`'s header injection from `localStorage`. This is inconsistent but functionally equivalent.

7. **`loadReceivables()` (`miniapp/app.js`, lines 2822–2910)**: Also passes `X-User-Role` explicitly, same inconsistency.

---

### 12.6 Missing try-catch Blocks

- **`miniapp/app.js`, `init()` (line 1476)**: Calls `enterApp(savedRole)` with `await` but no try-catch around it. If `enterApp` throws (e.g. `loadSettings` fails), the error is unhandled — the page silently breaks without user feedback. `loadSettings` itself has an internal try-catch with fallback, so this is mostly safe, but it's not guaranteed.

- **`miniapp/app.js`, `enterApp()` calls `buildTabs(role)`, `switchMainTab(firstTab.id)`, etc.** (lines 1677–1720): No try-catch wrapping. If DOM elements are missing or `ROLE_TABS[role]` is undefined, errors are silently swallowed (but `ROLE_TABS` has fallback to `ROLE_TABS.manager`).

- **`frontend/js/app.js`, `App._setupUser()` (lines 76–83)**: Calls `this.api.getDemoUsers()` with no try-catch. This is wrapped by `App.init()` which has a try-catch — again, safe but error message is generic.

- **`miniapp/app.js`, `saveBulkExpenses()` (line 2452–2469)**: Sends multiple individual `apiFetch('/expenses/v2/create', ...)` calls in a loop without per-item error recovery. One failure stops the entire batch; already-saved rows are not rolled back or reported.

---

## 16. LEGACY / DEAD / CONFLICTING CODE

### 16.1 Old Code Still Present but Likely Unused

#### `backend/services/deals_service.py` — Full Sheets-Based CRUD (lines 1–747)

- Contains complete `create_deal()`, `update_deal()`, `get_deal_by_id()`, `get_all_deals()`, `get_deals_by_user()`, `get_deals_filtered()` — all using Google Sheets via `get_worksheet()`.
- **All of these call `sheets_service.get_worksheet()`**, which now raises `NotImplementedError("Google Sheets support has been removed.")`.
- PostgreSQL-based `create_deal_pg`, `get_deal_by_id_pg`, etc. are defined from line ~748 onward and are the functions actually called by the backend routers.
- The Sheets-based functions remain in the file, taking up hundreds of lines, but are dead since any call to them will raise `NotImplementedError` immediately.

#### `backend/routers/billing.py` — Explicitly Marked DEPRECATED

The file docstring (lines 1–23) reads:
> `DEPRECATED: New code should use the SQL-function-based endpoints in billing_sql.py`

Still fully registered in `backend/main.py` (line 117: `app.include_router(billing.router)`). Routes: `GET/POST /billing/{warehouse}`, `GET /billing/{warehouse}/{client_name}`, `GET /billing/search`, `POST /billing/payment`.

The legacy `/billing/payment` route (distinct from `/billing/v2/payment/mark`) remains live.

#### `frontend/` directory — Entire separate frontend application

`frontend/js/app.js` implements `App`, `DealsScreen`, `JournalScreen`, `AnalyticsScreen`, `SettingsScreen` classes using `ApiClient` from `frontend/js/api.js`. All API calls use `/api/*` prefix:
- `GET /api/me`
- `GET /api/demo-users`
- `GET /api/deals`, `GET /api/deals/{id}`, `POST /api/deals`, `PATCH /api/deals/{id}`, `DELETE /api/deals/{id}`
- `GET /api/journal`, `POST /api/journal`
- `GET /api/analytics/summary`, `GET /api/analytics/deals-by-month`

**None of these endpoints exist in `backend/main.py`** or any registered router. The `frontend/` app cannot communicate with the backend in any way. It is either a prototype, a different project, or was built for a different backend version.

#### `miniapp/app.js`, `collectFormData()` (lines 522–554)

This function collects form values as plain text strings (status name, direction name, client name, manager name) — the "old" format for the legacy `/deal/create` endpoint. It is **never called** anywhere. The active submit handler (`handleFormSubmit`, line 447) calls `collectFormDataSql()` instead. `collectFormData()` is dead code.

---

### 16.2 Duplicated Functions

| Function | File A | File B | Note |
|---|---|---|---|
| `showToast()` | `miniapp/app.js:1132` | `frontend/js/app.js:37` | Different signatures and implementations |
| `showLoading()` | `miniapp/app.js` (inline via `setEl`/`style`) | `frontend/js/app.js:44` | Different element IDs |
| `formatDate()` | `miniapp/app.js:1191` | `frontend/js/app.js:32` | Different logic (miniapp returns `null` for empty, frontend returns `'—'`) |
| `formatMoney()` / `formatCurrency()` | `frontend/js/app.js:28` | `miniapp/app.js:1181` | Different function names, same purpose |
| `_resolve_user()` | `backend/routers/deals_sql.py:35` | `backend/routers/billing_sql.py:34` | Identical implementations, not shared |

The `_resolve_user()` helper is copy-pasted verbatim between `deals_sql.py` and `billing_sql.py`. Both take `(db, x_telegram_id)` and return `(user_id, role, full_name)`. They should be extracted to a shared module.

---

### 16.3 Conflicting Endpoint Paths

The routing order in `backend/main.py` is critical and documented:

```python
# backend/main.py:110-120
# SQL-function/view based routers must be registered BEFORE legacy routers
app.include_router(deals_sql.router)      # prefix: /deals
app.include_router(expenses_sql.router)   # prefix: /expenses/v2
app.include_router(billing_sql.router)    # prefix: /billing/v2
app.include_router(month_close.router)    # prefix: /month
# Legacy routers (DEPRECATED)
app.include_router(billing.router)        # prefix: /billing
app.include_router(expenses.router)       # prefix: /expenses (or similar)
```

`billing.router` has prefix `/billing`. If registered before `billing_sql.router` (prefix `/billing/v2`), then `GET /billing/v2/search` would be caught by `billing.router`'s `GET /billing/{warehouse}` route (treating `v2` as the warehouse name). The current ordering prevents this. This is an active latent conflict — reordering the routers would silently break all v2 billing endpoints.

---

### 16.4 Old Google Sheets Related Remnants

1. **`backend/services/sheets_service.py`** (entire file): All Google Sheets sheet name constants are still defined: `SHEET_DEALS`, `SHEET_SETTINGS`, `SHEET_BILLING_MSK`, `SHEET_BILLING_NSK`, `SHEET_BILLING_EKB`, `BILLING_SHEETS`, etc. (lines 17–36). These are imported by `deals_service.py`. The actual functions (`get_spreadsheet`, `get_worksheet`, etc.) all `raise NotImplementedError`.

2. **`backend/services/deals_service.py`** (lines 1–747): Imports from `sheets_service.py`, references `SHEET_DEALS`, `get_worksheet`, `get_header_map`, etc. — all legacy Sheets API patterns.

3. **`miniapp/app.js`, `checkConnections()` (line 1082)**:
   ```js
   // Google Sheets (check settings endpoint)
   try {
     await apiFetch('/settings');
     setConnectionStatus('sheets', true, 'Подключено');
   } catch (_) {
     setConnectionStatus('sheets', false, 'Ошибка');
   }
   ```
   The HTML elements `dot-sheets` and `status-sheets` in the Settings tab are labelled "Google Sheets" in the UI, but the check calls `/settings` (the PostgreSQL settings endpoint). The "Google Sheets" label is misleading — the underlying storage is no longer Google Sheets but the label was never updated.

4. **`backend/services/billing_service.py`**: Contains Sheets-based billing CRUD. The module docstring (lines 1–40) describes Google Sheets column formats ("billing_msk / billing_nsk / billing_ekb sheets"). Its public API (`get_billing_entries`, `get_billing_entry`, `search_billing_entry`, `upsert_billing_entry`) is imported by `backend/routers/billing.py`. Since `sheets_service.get_worksheet()` now raises `NotImplementedError`, all functions in `billing_service.py` that call it will fail at runtime.

5. **`BILLING_INPUT_MODE_OLD = 'Старый (p1/p2)'`** (`miniapp/app.js`, line 24): This constant is defined but never used in the code. `BILLING_INPUT_MODE_WITH_VAT` and `BILLING_INPUT_MODE_WITHOUT_VAT` are used in the legacy billing path (`saveBilling()`, line 2141–2142). `BILLING_INPUT_MODE_OLD` is dead.

---

### 16.5 Commented-Out Logic

No significant commented-out logic blocks found in the main files. The codebase uses docstrings and inline `// DEPRECATED`, `// Legacy`, `// Fallback` comments rather than commented-out code.

---

### 16.6 Temporary Hacks / Suspicious Patterns

1. **`miniapp/app.js`, `saveBilling()` (line 2109)**:
   ```js
   units_count: pVal('bv2-units') != null ? (parseInt(pVal('bv2-units')) || null) : null,
   ```
   The outer `!= null` guard is redundant. `pVal()` already returns `null` for empty inputs (since `parseFloat('')` returns `NaN`, and `NaN || null` is `null`). The inner `|| null` handles the NaN case by itself, making the outer check unnecessary. The logic is correct but needlessly complex.

2. **`miniapp/app.js`, `collectFormDataSql()` (line 586)**:
   ```js
   production_expense_without_vat: floatVal('general_production_expense') || floatVal('production_expense_with_vat'),
   ```
   Falls back to `production_expense_with_vat` when `general_production_expense` is missing/zero, and sends it as `_without_vat`. This sends a value that may include VAT labeled as "without VAT" — a silent data quality issue.

3. **`miniapp/app.js`, `renderDeals()` `clientFilter` comparison (line 693)**:
   ```js
   if (clientFilter && deal.client !== clientFilter) return false;
   ```
   The `clientFilter` value depends on which function last populated `#filter-client`. After `loadSettings()` (enriched), the filter options have numeric ID strings as values. After `loadClientsSettings()` (plain names), options have string names. The comparison therefore alternates between comparing a text name against a numeric ID vs. comparing two text names, depending on the load order. This is also noted as a confirmed UI bug in Section 17 (Bug 4).

---

### 16.7 Unused Variables / Files

- **`miniapp/app.js` `state.isLoadingDeals` (line 121)**: Correctly used as a guard in `loadDeals()`.
- **`frontend/js/permissions.js`**: Defines `ROLES`, `ROLE_LABELS`, `PERMISSION_MATRIX`, `Permissions` class — all for the `frontend/` app which is unused. This file is never loaded by `miniapp/index.html`.
- **`static/index.html`**: Top-level `static/` directory with an HTML file. Its purpose could not be determined from the code inspected; the file was not read. **TODO: Investigate** — this may be a third entry point, a legacy placeholder, or a health-check page.
- **`miniapp/app.js` `summaryItems` variable** (line 2982): Declared but never actually populated with items in `_showMonthCloseResult()` (the push calls exist but `summaryItems` only matters if `first.dry_run !== undefined`). This is correct but the variable is always empty unless the dry_run flag is present in data.

---

## 17. CURRENT BUGS VISIBLE FROM THE CODE

### Bug 1: Legacy Frontend (`frontend/`) Calls Non-Existent API Endpoints

- **File**: `frontend/js/api.js` (lines 44–63), `frontend/js/app.js`
- **Function**: `ApiClient.getMe()`, `ApiClient.getDemoUsers()`, `ApiClient.getDeals()`, etc.
- **Exact reason**: All API methods use paths like `/api/me`, `/api/demo-users`, `/api/deals`, `/api/analytics/summary`. **None of these paths are registered in `backend/main.py`** or any included router. The backend serves routes at `/deals`, `/settings`, `/auth`, etc. — no `/api/*` prefix exists.
- **Likely effect in UI**: On load, `App.init()` → `_setupUser()` → `this.api.getDemoUsers()` → `GET /api/demo-users` → 404. `showToast('Ошибка инициализации: HTTP 404', 'error')` is shown. The entire `frontend/index.html` app is broken and cannot display any data.

---

### Bug 2: `frontend/js/api.js` `ApiClient._request()` — Object Error Detail Shows `[object Object]`

- **File**: `frontend/js/api.js:33`
- **Function**: `ApiClient._request(method, path, body)`
- **Exact reason**: `new Error(data.error || 'HTTP ${res.status}')` — if `data.error` is a non-string object, the Error message will be `[object Object]` because JavaScript's `Error` constructor calls `.toString()` on its argument.
- **Likely effect in UI**: `showToast('[object Object]', 'error')` is displayed to the user instead of a real error message. (Since the backend sends `detail`, not `error`, this would fall back to `HTTP ${status}` in most cases, but if a custom error object is sent, `[object Object]` appears.)

---

### Bug 3: `loadClientsSettings()` Overwrites Enriched Client IDs with Plain Names

- **File**: `miniapp/app.js` (lines 1264–1281)
- **Function**: `loadClientsSettings()`
- **Exact reason**:
  ```js
  const clientNames = clients.map(c => c.client_name);
  fillSelect('client', clientNames);       // ← plain string values, not IDs
  fillSelect('filter-client', clientNames, true);
  if (state.settings) state.settings.clients = clientNames;
  ```
  After `loadSettings()` runs at startup and populates `#client` with `{id, name}` objects (numeric IDs as values), calling `loadClientsSettings()` (which happens whenever the Settings tab is opened) replaces the select options with plain string names. `collectFormDataSql()` then does `client_id: intVal('client')` → `parseInt('МегаКо', 10)` → `NaN` → `null`. The POST to `/deals/create` with `client_id: null` will fail validation (field is required: `client_id: int = Field(...)`).
- **Likely effect in UI**: After visiting the Settings tab, attempting to create a new deal results in a 422 validation error: `"client_id: field required"` or `"value is not a valid integer"`.

---

### Bug 4: Status Filter in `renderDeals()` Broken with Enriched Settings

- **File**: `miniapp/app.js` (line 692)
- **Function**: `renderDeals()`
- **Exact reason**:
  ```js
  const statusFilter = document.getElementById('filter-status')?.value || '';
  if (statusFilter && deal.status !== statusFilter) return false;
  ```
  When `/settings/enriched` loads, `fillSelect('filter-status', data.statuses || [], true)` is called. If `data.statuses` contains `{id, name}` objects, then option values are numeric ID strings (e.g. `"1"`, `"2"`). `deal.status` returned by `GET /deals` view is a human-readable text string (e.g. `"Новая"`). So `"Новая" !== "1"` is always true, meaning **the status filter hides all deals** when any status is selected.
- **Likely effect in UI**: Selecting any status filter in the "My Deals" tab causes the list to appear empty even when matching deals exist.

---

### Bug 5: Deal Edit Status Select Pre-population Fails with Enriched Settings

- **File**: `miniapp/app.js` (line 843)
- **Function**: `onEditDealSelected(dealId)`
- **Exact reason**:
  ```js
  setVal('edit-status', deal.status);  // deal.status = "Новая" (string)
  ```
  `#edit-status` is populated by `fillSelect('edit-status', data.statuses || [])` which, with enriched settings, has option values as numeric ID strings. `selectElement.value = "Новая"` has no effect when no option has that value. The select defaults to the first option.
- **Likely effect in UI**: When editing a deal, the status dropdown shows the wrong (first) status instead of the deal's current status.

---

### Bug 6: `saveEditedDeal()` Sends Status ID String Where Text Name is Expected

- **File**: `miniapp/app.js` (lines 866–869)
- **Function**: `saveEditedDeal()`
- **Exact reason**:
  ```js
  const statusEl = document.getElementById('edit-status');
  if (statusEl?.value) payload.status = statusEl.value;
  ```
  `statusEl.value` is the enriched numeric ID (`"1"`) not the text name. This is sent to `PATCH /deals/update/{deal_id}` which uses `DealUpdate.status: Optional[str]`. The backend stores `"1"` as the status string in the database, corrupting the status field.
- **Likely effect in UI**: After saving, the deal shows status `"1"` in the list instead of the correct status name.

---

### Bug 7: `saveBulkExpenses()` — Zero VAT Rate Sends With-VAT Amount as Without-VAT

- **File**: `miniapp/app.js` (line 2444)
- **Function**: `saveBulkExpenses()`
- **Exact reason**:
  ```js
  amount_without_vat: vatRate ? amount / (1 + vatRate) : amount,
  ```
  When `vatRate` is 0 (not entered), the raw `amount` (which was entered as "Сумма с НДС" per the field label) is sent as `amount_without_vat`. No VAT deduction occurs. Same pattern in `saveExpense()` (line 2501) which uses `amount - vat` as fallback — slightly different behavior.
- **Likely effect in UI**: Expenses without an explicit VAT rate have an overstated `amount_without_vat`. The two expense save functions (`saveExpense` and `saveBulkExpenses`) handle the zero-VAT case differently, creating data inconsistency.

---

### Bug 8: `markPayment()` Does Not Pass `payment_date`

- **File**: `miniapp/app.js` (lines 2195–2218)
- **Function**: `markPayment()`
- **Exact reason**:
  ```js
  body: JSON.stringify({ deal_id: dealId, payment_amount: amount }),
  ```
  The `BillingPaymentMarkRequest` schema (`backend/schemas/billing.py:43-48`) accepts `payment_date: Optional[date] = None`. The frontend never includes a payment date. This is not a crash, but means all payments are recorded without a date.
- **Likely effect in UI**: Payment dates are always `null`/`None` in the database. Reports that filter or display by payment date will show no date.

---

### Potential Issue (Requires Investigation): `loadDealsForEdit()` Uses Text `deal_id` for API Lookup

- **File**: `miniapp/app.js` (lines 807–823, 825–855)
- **Function**: `loadDealsForEdit()`, `onEditDealSelected(dealId)`
- **Observed pattern**:
  ```js
  // loadDealsForEdit:
  opt.value = d.deal_id;  // e.g. "DEAL-0001" (text ID from view)
  // onEditDealSelected:
  const deal = await apiFetch(`/deals/${dealId}`);  // GET /deals/DEAL-0001
  ```
  In `deals_sql.py` `get_deal()` (line 226): `int(deal_id)` will fail for text codes like "DEAL-0001", so the backend falls back to `WHERE deal_id = :deal_id` (text column match). Whether this works depends on whether `public.v_api_deals` exposes a `deal_id` text column. The view schema is not visible in the backend Python code — it is defined in the database.
- **Status**: Requires database schema verification. If `v_api_deals` does not have a `deal_id` text column, every deal edit would fail with HTTP 404. If the column exists, this path works correctly.

---

### Bug 10: `AnalyticsScreen` in `frontend/js/app.js` — Missing await Guard

- **File**: `frontend/js/app.js` (lines 436–442)
- **Function**: `AnalyticsScreen.load()`
- **Exact reason**:
  ```js
  const [summary, byMonth] = await Promise.all([
    this.app.api.getAnalyticsSummary(),
    this.app.api.getAnalyticsByMonth(),
  ]);
  this._render(summary, byMonth);
  ```
  Then `_render()` line 445 destructures: `const { deals: ds, journal: js } = summary;`. If `summary` does not contain a `deals` key, `ds` is `undefined`, and `ds.total` (line 451) throws `TypeError: Cannot read property 'total' of undefined`.
- **Likely effect in UI**: Analytics screen throws unhandled error, shows "Ошибка" toast. (Moot since the entire `frontend/` app is broken per Bug 1.)

---

### Bug 11: Race Condition — `loadSettings()` Caching vs. Parallel Calls

- **File**: `miniapp/app.js` (lines 173–206)
- **Function**: `loadSettings()`
- **Exact reason**:
  ```js
  if (state.settings) return state.settings;
  ```
  The cache check is synchronous but multiple concurrent callers (e.g. if `enterApp()` is called while a previous `loadSettings()` is still in-flight) will all pass the cache check (since `state.settings` is still `null`) and send parallel requests to `/settings/enriched`. This is a classic check-then-act race condition in async JavaScript.
- **Likely effect in UI**: Multiple simultaneous requests to `/settings/enriched` on app load. Usually harmless (idempotent endpoint) but wastes bandwidth and could cause flicker if `populateSelects()` is called multiple times.

---

## 18. WHAT IS ALREADY IMPLEMENTED VS PARTIALLY IMPLEMENTED VS MISSING

### A. Fully Implemented

- **Deal creation** via `POST /deals/create` → `public.api_create_deal(...)`, with enriched settings (numeric IDs), validation, and role check. Frontend collects data via `collectFormDataSql()`. Backend schemas in `DealCreateRequest`. ✅
- **Deal list** via `GET /deals` → `public.v_api_deals` view. Role-based filtering (managers see only their own deals). Frontend renders via `createDealCard()`. ✅
- **Deal detail view** via `GET /deals/{deal_id}` with integer and text-ID fallback. Frontend modal via `openDealModal()` → `renderDealDetail()`. ✅
- **Settings enriched endpoint** `GET /settings/enriched` returning `{id, name}` objects. Used as single source of truth for frontend dropdowns. ✅
- **Settings CRUD** (clients, managers, directions, statuses): Full CRUD in `backend/routers/settings.py` with PostgreSQL backing. Frontend settings management in `initSettingsManagement()`. ✅
- **Authentication** via two paths: `/auth/miniapp-login` (Telegram context) and `/auth/role-login` (password fallback). localStorage-based session persistence. ✅
- **Billing upsert** via `POST /billing/v2/upsert` → `public.api_upsert_billing_entry(...)`. Frontend `saveBilling()` routes to this when enriched settings are active. ✅
- **Billing search** via `GET /billing/v2/search` with ID-based filters. Frontend `loadBillingEntry()` routes to v2 when enriched settings available. ✅
- **Expenses creation** via `POST /expenses/v2/create`. Single and bulk entry. ✅
- **Toast notification system** in `miniapp/app.js` with XSS-safe rendering via `escHtml()`. ✅
- **Role-based tab visibility** via `ROLE_TABS` map and `buildTabs(role)`. ✅
- **Telegram WebApp integration**: `initTelegram()`, `getTelegramInitData()`, user avatar from initData. ✅
- **Month close operations** via `runMonthArchive()`, `runMonthCleanup()`, `runMonthClose()` in `miniapp/app.js`. Backend endpoints in `month_close.py`. ✅
- **Journal viewing** via `GET /journal?limit=50`. ✅
- **Dashboard** via `GET /dashboard/summary`. ✅
- **Receivables** via `GET /receivables`. ✅
- **Dependent dropdowns** (direction → client → deal) via `initDependentDealDropdowns()` + `loadDealsFiltered()`. ✅

---

### B. Partially Implemented

- **Deal editing** via `PATCH /deals/update/{deal_id}`: Backend is fully implemented. Frontend `saveEditedDeal()` is implemented but broken by the status ID/name mismatch (Bugs 5 and 6). Edit status dropdown never shows correct value and may corrupt status on save. ⚠️

- **Deal filtering on deals list**: Frontend `renderDeals()` supports status, client, month filters. Status filter is broken when enriched settings are active (Bug 4). Client filter works when plain names are used. Month filter has no server-side equivalent — all filtering is purely client-side. ⚠️

- **Billing search (legacy path)**: Falls back to `GET /billing/search?warehouse=...&client=...` when enriched settings are unavailable. This uses `billing_service.search_billing_entry()` which calls Sheets service stubs — will raise `NotImplementedError`. Fallback path is broken. ⚠️

- **Billing save (old p1/p2 format)**: `saveBilling()` with `fmt === 'old'` posts to `POST /billing/{warehouse}` (legacy router). This calls `billing_service.upsert_billing_entry()` which calls Sheets stubs. Old format billing save is broken. ⚠️

- **Reports download** (`downloadReport()`): Calls `/reports/warehouse/{wh}`, `/reports/billing-by-month`, `/reports/billing-by-client`. Backend router `reports.py` exists. Whether these endpoints actually generate valid data from PostgreSQL or still use Sheets is not confirmed from the code read. ⚠️

- **Payment date in `markPayment()`**: The UI has no date field for payment, so all payments are stored without a date (Bug 8). ⚠️

- **Bulk expense saving**: Works for individual items but fails atomically (no rollback). ⚠️

---

### C. Missing / Broken

- **`frontend/` application**: All API calls go to `/api/*` which don't exist. The entire `frontend/index.html` app is permanently broken in its current form. ❌

- **`collectFormData()` function** (`miniapp/app.js:522`): Dead code. Never called. The function it was supposed to replace `collectFormDataSql()` for is gone. ❌

- **Status dropdown pre-population in deal edit**: When enriched settings are active, `onEditDealSelected()` cannot set the correct status in `#edit-status` (Bug 5). ❌

- **Legacy billing `GET /billing/search`**: The endpoint exists in `billing.py` but calls `billing_service.search_billing_entry()` which uses Sheets. Raises `NotImplementedError` if called. ❌

- **Manager-level filter for deal loading**: `loadDeals()` calls `GET /deals` with no query params. The backend auto-filters by `manager_telegram_id` for managers. But if the Telegram user is not authenticated (localStorage-only auth), no `X-Telegram-Id` is set and the server returns 403. ❌

- **`BILLING_INPUT_MODE_OLD` constant** (`miniapp/app.js:24`): Defined but never used. ❌

- **Google Sheets connection indicator** in settings: `checkConnections()` uses "sheets" labels for what is now a PostgreSQL settings endpoint. The label is misleading and the concept of "Google Sheets connectivity" no longer applies. ❌

---

## 19. RECOMMENDED REFACTOR MAP

> Based strictly on what the current code shows. No code is written here.

### Priority 1 — Fix Critical Bugs (Production-Breaking)

1. **Fix `loadClientsSettings()` to preserve enriched IDs** (`miniapp/app.js:1274`):
   - Instead of `fillSelect('client', clientNames)` with plain strings, populate with `{id, name}` objects just as `loadSettings()` does. This is the most dangerous bug — it silently breaks deal creation after any Settings tab visit.

2. **Fix status filter comparison in `renderDeals()`** (`miniapp/app.js:692`):
   - Compare `deal.status_id` vs. the numeric filter value, OR compare `deal.status` (text) vs. the option's `data-name` attribute instead of the option's `value`.

3. **Fix `onEditDealSelected()` status pre-population** (`miniapp/app.js:843`):
   - Set the select by `status_id` (numeric) from the API response, not by `status` text name. Requires the API view to return `status_id`.

4. **Fix `saveEditedDeal()` to send `status_id`** (`miniapp/app.js:868`):
   - The `PATCH /deals/update/{deal_id}` endpoint currently uses `DealUpdate.status: Optional[str]` (text name). Either: (a) update the endpoint to accept `status_id: Optional[int]`, or (b) make the frontend look up the status name from the enriched settings map before sending.

### Priority 2 — Fix Inconsistencies (High Risk)

5. **Standardize all API calls to go through `apiFetch()`** (`miniapp/app.js:downloadReport`, `loadJournal`, `loadReceivables`):
   - `downloadReport()` uses raw `fetch()` and manually handles headers. This bypasses the centralized auth header injection.

6. **Extract `_resolve_user()` into a shared module**:
   - The function is copied verbatim between `deals_sql.py` and `billing_sql.py`. Extract to `backend/services/miniapp_auth_service.py` or `backend/dependencies.py`.

7. **Fix `collectFormDataSql()` VAT fallback** (`miniapp/app.js:586`):
   - `floatVal('general_production_expense') || floatVal('production_expense_with_vat')` sends a with-VAT value as `production_expense_without_vat`. The field name mismatch should be resolved.

### Priority 3 — Cleanup (Reduced Maintenance Risk)

8. **Remove `collectFormData()` dead function** (`miniapp/app.js:522`).

9. **Remove or correctly label the Google Sheets connection indicator** (`miniapp/app.js:1082`): Rename `dot-sheets` / `status-sheets` to `dot-db` / `status-db`, change the connection check to something more meaningful (e.g. `GET /health`).

10. **Remove `BILLING_INPUT_MODE_OLD` unused constant** (`miniapp/app.js:24`).

11. **Remove or archive the `frontend/` directory**: It is unreachable from the active backend. If it is a prototype, move to a separate branch or mark clearly as non-functional.

### Priority 4 — Backend Alignment

12. **`DealUpdate` model (`backend/models/deal.py`)**: Consider adding `status_id: Optional[int]` to align with the SQL-first approach. Currently it only accepts `status: Optional[str]` (name-based), inconsistent with `DealCreateRequest.status_id: int`.

13. **Billing router (`backend/routers/billing.py`)**: After confirming all v2 endpoints cover all use cases, remove the deprecated router to prevent the routing order fragility issue.

14. **`deals_service.py` Sheets-based functions (lines 1–747)**: Remove the entire non-`_pg` section of the file once the PG migration is confirmed complete. The Sheets functions will always raise `NotImplementedError`, so they are both dead code and misleading.

### Critical Contracts Between Frontend and Backend That Need Alignment

| Contract | Current State | Risk |
|---|---|---|
| Status field: text name vs. ID | Frontend (edit) sends text name to `DealUpdate.status`; creation uses `status_id: int` | Data corruption in edit |
| Client ID in deal creation | `collectFormDataSql()` sends `client_id: intVal('client')`. After `loadClientsSettings()`, values are text names → `NaN` | 422 error, deal creation blocked |
| Filter comparison | Frontend compares `deal.status` (text) vs. `filter-status` value (enriched ID string) | Status filter always returns empty list |
| Auth header consistency | Some calls use `X-User-Role`, others use `X-Telegram-Id`; `apiFetch` injects both from localStorage | Auth may fail for certain roles |

---

## 20. FINAL TECHNICAL SUMMARY

### 20.1 Architecture Overview

The project is a **Telegram Mini App** for a logistics/finance ERP, consisting of:

**Backend**: Python FastAPI application in `backend/` served via `backend/main.py`.
- **Dual routing layer**: SQL-function-based routers (`deals_sql.py`, `billing_sql.py`, `expenses_sql.py`, `month_close.py`) are the primary layer; legacy name-based routers (`billing.py`, `expenses.py`) are preserved for backward compatibility but marked deprecated.
- **PostgreSQL access**: Async SQLAlchemy via `app.database.database.py`. SQL functions and views called through `backend/services/db_exec.py` (`call_sql_function`, `call_sql_function_one`, `read_sql_view`).
- **Authentication**: Dual auth — `X-Telegram-Id` header (primary, resolves via `app_users` table) and `X-User-Role` header (password-based fallback for non-Telegram contexts).
- **Settings endpoint**: `GET /settings/enriched` returns `{id, name}` objects for all reference data (statuses, directions, clients, managers, warehouses, expense categories). This is the single source of truth for frontend dropdowns.
- **Google Sheets**: Fully removed. `sheets_service.py` contains only stubs that raise `NotImplementedError`.

**Frontend (Active)**: `miniapp/` directory — `index.html`, `app.js`, `styles.css`.
- Single 3000+ line JavaScript file with no module system.
- Role-based tab/feature visibility via `ROLE_TABS` map.
- `apiFetch()` as the central HTTP client with auth header injection.
- Enriched settings loaded on login, cached in `state.enrichedSettings`.

**Frontend (Inactive)**: `frontend/` directory — `index.html`, `js/app.js`, `js/api.js`, `js/permissions.js`.
- Entirely separate application using `ApiClient` class targeting `/api/*` endpoints.
- These endpoints do not exist in the backend. The entire `frontend/` app is broken.

---

### 20.2 Main Weak Points

1. **Dual frontend apps**: The `frontend/` app is non-functional and creates maintenance confusion. Any engineer unfamiliar with the codebase will spend time investigating why two HTML apps exist.

2. **Enriched settings vs. plain name collision**: `loadSettings()` populates dropdowns with numeric IDs; `loadClientsSettings()` (and `loadManagersSettings()`) overwrites with plain strings. This breaks deal creation after Settings tab is visited.

3. **Status ID/name contract mismatch**: Deal creation uses `status_id: int`; deal editing uses `status: str`. The same enriched-settings select is used for both, but the backend contracts are different.

4. **Legacy code volume**: Half of `deals_service.py` (lines 1–747) is dead Sheets-based code. `billing.py` is deprecated but still registered. Unclear which service functions are active.

5. **`_resolve_user()` duplication**: The same authentication helper is copy-pasted across multiple router files with no abstraction.

6. **No module system in frontend**: All 3000+ lines of `miniapp/app.js` are in one file. No imports/exports. Global function namespace pollution. Hard to test or maintain.

---

### 20.3 The Most Dangerous Mismatches

| # | Mismatch | Where | Consequence |
|---|---|---|---|
| 1 | `loadClientsSettings()` replaces enriched IDs with plain names | `miniapp/app.js:1274` | Deal creation fails (422) after any Settings tab visit |
| 2 | `deal.status` (text) compared to enriched filter value (ID) | `miniapp/app.js:692` | Status filter always shows empty list |
| 3 | `DealUpdate.status: str` vs. enriched dropdown sending numeric ID | `miniapp/app.js:868` + `backend/models/deal.py:64` | Status field corrupted to "1" after any edit |
| 4 | `frontend/` endpoints use `/api/*` prefix | `frontend/js/api.js` | Entire frontend/ app broken on load |
| 5 | Legacy `/billing/search` calls Sheets stubs | `billing.py` → `billing_service.py` | 500 `NotImplementedError` if legacy path is hit |
| 6 | SQL-function router ordering in `backend/main.py` | `backend/main.py:112-120` | If reordered, `/billing/v2/*` silently matched by `/billing/{warehouse}` |

---

### 20.4 What Another Engineer Must Know Before Editing This App

1. **There are two frontend applications.** `miniapp/` is the active one. `frontend/` is broken and not served to users. Do not confuse them.

2. **The Settings tab visit breaks deal creation.** `loadClientsSettings()` at `miniapp/app.js:1274` overwrites enriched client IDs with plain names. Any workflow that involves visiting Settings before creating a deal will silently fail at submission.

3. **Router registration order in `backend/main.py` is critical.** SQL-function routers must be registered before legacy routers. If you add a new router or change the order, `/billing/v2/*` paths may be swallowed by `/billing/{warehouse}`.

4. **Google Sheets has been removed.** `sheets_service.py` only has stubs. Any function calling `get_worksheet()` will raise `NotImplementedError`. The legacy `billing.py` router and the Sheets-based half of `deals_service.py` are dead but still present. Do not re-activate them.

5. **`/settings/enriched` is the authoritative reference data source.** All dropdowns should be populated from this endpoint's `{id, name}` objects. Do not mix plain-string and ID-based population for the same select element.

6. **Authentication uses two headers:** `X-Telegram-Id` (primary, for SQL-function routers) and `X-User-Role` (fallback, used by some legacy endpoints). When in a Telegram context, `telegramUser.id` is stored in `localStorage.telegram_id` after login. `apiFetch()` injects both headers automatically.

7. **`collectFormData()` in `miniapp/app.js:522` is dead code.** The active deal creation function is `collectFormDataSql()`. Do not confuse them.

8. **Tests pass (401 tests) but test against mocks/in-memory state.** The tests do not exercise the live PostgreSQL views or SQL functions. A passing test suite does not guarantee that the UI flows described above work end-to-end.

9. **The `frontend/` app uses a different error-reading convention** (`data.error`) from the miniapp (`data.detail || data.error`) and from FastAPI's default (`detail`). When working in `frontend/js/api.js`, errors will always fall back to `HTTP ${status}` because FastAPI sends `detail`, not `error`.

10. **Month-close, Dashboard, and Receivables endpoints** (`/month/...`, `/dashboard/summary`, `/receivables`) exist in the backend routers but their underlying SQL views/functions are not confirmed from the code to be present in the database schema. If the PostgreSQL functions don't exist, these will return 500 errors.
