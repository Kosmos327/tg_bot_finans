# MINI APP FRONTEND ARCHITECTURE AUDIT

**Produced from source code only. No guesses. No changes.**

---

## 1. MINI APP FILE TREE

### Active Mini App files

| File | Purpose |
|------|---------|
| `miniapp/index.html` | Main HTML entry point for the active Mini App; contains all tab panels, forms, modals, and auth screens as inline HTML |
| `miniapp/app.js` | Sole JS runtime for the active Mini App; handles auth, API calls, state, tab switching, deals, billing, expenses, settings, reports, journal, dashboard, receivables, month-close |
| `miniapp/styles.css` | All CSS for the active Mini App; 1 743 lines, responsive, supports Telegram dark-mode via `data-theme` attribute |

### Legacy frontend files (NOT the active Mini App)

| File | Purpose |
|------|---------|
| `frontend/index.html` | Legacy HTML shell for an older Mini App prototype; uses Node.js `ApiClient` at `localhost:3000`, not the FastAPI backend |
| `frontend/js/app.js` | Legacy JS runtime for `frontend/index.html`; class-based App/DealsScreen/JournalScreen/AnalyticsScreen/SettingsScreen; calls `/api/*` endpoints on a separate Node.js backend |
| `frontend/js/api.js` | Legacy API client class (`ApiClient`); calls `/api/me`, `/api/deals`, `/api/journal`, `/api/analytics/*`, uses `X-User-Id` header |
| `frontend/js/permissions.js` | Legacy permission matrix (roles: admin/sales/accounting/viewer); used only by `frontend/js/app.js` |
| `frontend/css/styles.css` | Legacy CSS for `frontend/index.html` |

### Static file (separate, legacy)

| File | Purpose |
|------|---------|
| `static/index.html` | Standalone single-file Telegram Mini App prototype (self-contained HTML+CSS+JS); calls `/deal/*` and `/settings/*` endpoints on the FastAPI backend; not served automatically |

### Backend routers directly called by the active Mini App (`miniapp/app.js`)

| File | Prefix | Purpose |
|------|--------|---------|
| `backend/routers/auth.py` | `/auth` | Login endpoints (`/miniapp-login`, `/role-login`) |
| `backend/routers/settings.py` | (none) | `/settings/enriched`, `/settings/clients`, `/settings/managers`, `/settings/directions`, `/settings/statuses` |
| `backend/routers/deals_sql.py` | `/deals` | `GET /deals`, `GET /deals/{deal_id}`, `POST /deals/create`, `PATCH /deals/update/{deal_id}` |
| `backend/routers/billing_sql.py` | `/billing/v2` | `GET /billing/v2/search`, `POST /billing/v2/upsert`, `POST /billing/v2/payment/mark` |
| `backend/routers/billing.py` | `/billing` | `GET /billing/search` (legacy fallback), `POST /billing/{warehouse}` (legacy fallback), `POST /billing/payment/mark` (never called by active miniapp) |
| `backend/routers/expenses_sql.py` | `/expenses/v2` | `GET /expenses/v2`, `POST /expenses/v2/create` |
| `backend/routers/reports.py` | `/reports` | All `/reports/*` download endpoints |
| `backend/routers/journal.py` | `/journal` | `GET /journal?limit=50` |
| `backend/routers/dashboard.py` | `/dashboard` | `GET /dashboard/summary` |
| `backend/routers/receivables.py` | `/receivables` | `GET /receivables` |
| `backend/routers/month_close.py` | `/month` | `POST /month/archive`, `POST /month/cleanup`, `POST /month/close`, `GET /month/archive-batches` |
| `backend/main.py` | `/health` | `GET /health` (connection check from Settings tab) |

---

## 2. ENTRY POINTS

### Main HTML entry point
**`miniapp/index.html`**

Served by FastAPI via:
```python
app.mount("/miniapp", StaticFiles(directory=_miniapp_dir, html=True), name="miniapp")
```
URL: `<origin>/miniapp/`

### Main JS entry point
**`miniapp/app.js`**

Loaded via `<script src="app.js"></script>` at the bottom of `miniapp/index.html`.

No module bundler. All code is in one file, `'use strict'` at the top.

### Initialization chain
1. `document.addEventListener('DOMContentLoaded', init)` — line 1820 of `app.js`
2. `init()` calls, in order:
   - `initTelegram()` — attaches Telegram SDK, reads `tg.initDataUnsafe.user`
   - `initTabs()` — binds `.tab-btn` click handlers (legacy tab switch, only used for the old `frontend/`)
   - `initDealForm()` — binds form submit and clear handlers
   - `initMyDeals()` — binds filter and refresh handlers
   - `initModal()` — binds deal detail modal close handlers
   - `initMonthClose()` — binds month-close button handlers
   - `loginWithTelegram()` — calls `POST /auth/miniapp-login` if Telegram context is available
   - Auth state check → `showAuthScreen()` or `enterApp(role)`
3. `enterApp(role)` completes initialization:
   - `buildTabs(role)` — renders role-specific tab bar
   - `loadSettings()` — fetches `/settings/enriched`
   - `switchMainTab(firstTab.id)` — shows first tab
   - `initBillingForm()`, `initExpensesForm()`, `initDealEdit()`, `initReportsHandlers()`, `initJournalHandlers()`, `initSubnav()`, `initSettingsManagement()`, `initDashboardHandlers()`, `initReceivablesHandlers()`

---

## 3. STATE AND SESSION

### Global state object
```js
const state = {
  settings: null,           // raw response from /settings/enriched
  enrichedSettings: null,   // normalized {id,name} version of settings
  deals: [],                // cached deals array for My Deals tab
  currentTab: 'new-deal',   // currently active tab ID
  isSubmitting: false,      // deal form submit lock
  isLoadingDeals: false,    // deals loading lock
  _loadingJournal: false,   // journal loading lock (set inline, not in declaration)
};
```

### localStorage keys

| Key | Written by | Read by | Cleared by |
|-----|-----------|---------|-----------|
| `user_role` | `doLogin()`, `loginWithTelegram()` | `hasLocalAuth()`, `getAuthHeaders()`, `init()`, `enterApp()`, `collectFormDataSql()`, `saveBilling()`, `loadReceivables()`, `loadOwnerDashboard()` | logout button handler in `enterApp()` |
| `user_role_label` | `doLogin()` | `enterApp()` | logout button handler |
| `telegram_id` | `loginWithTelegram()`, `doLogin()` | `getAuthHeaders()`, `init()` | logout button handler |
| `user_id` | `doLogin()` (role-login path only) | not read in app.js | logout button handler |
| `user_name` | `doLogin()` (role-login path only) | not read in app.js | logout button handler |
| `manager_id` | `doLogin()` (role-login, manager role only) | `populateSelects()`, `collectFormDataSql()` | logout button handler |

### Auth headers sent on every API call (`getAuthHeaders()`)
- `X-Telegram-Init-Data`: value of `tg.initData` when SDK is present
- `X-Telegram-Id`: `telegramUser.id` OR `localStorage.getItem('telegram_id')`
- `X-User-Role`: `localStorage.getItem('user_role')`

### Module-level variables
- `let tg = null` — assigned in `initTelegram()`; reference to `window.Telegram.WebApp`
- `let telegramUser = null` — assigned in `initTelegram()`; value of `tg.initDataUnsafe?.user`

---

## 4. TAB / SCREEN ARCHITECTURE

### Auth screen

| Element | ID |
|---------|----|
| Entire auth overlay | `auth-screen` |
| Role selection step | `auth-step-role` |
| Manager selection step | `auth-step-manager` |
| Password input step | `auth-step-password` |
| Password input | `auth-password` |
| Error message | `auth-error` |
| Submit button | `auth-submit-btn` |
| Back button (password→role) | `auth-back-btn` |
| Back button (manager→role) | `auth-manager-back-btn` |

**Init function**: `initAuthHandlers()` called from `showAuthScreen()`  
**Login API**: `POST /auth/miniapp-login` (Telegram mode) or `POST /auth/role-login` (browser mode)

### Main app wrapper

| Element | ID |
|---------|----|
| Entire main app wrapper | `app-main` |
| Tab navigation bar | `main-tab-nav` |
| Role label in header | `header-role-label` |
| User avatar | `user-avatar` |

### Tab: Финансы (`tab-finances`)

**Roles that see it**: manager, operations_director, accounting, admin, accountant, head_of_sales

Sub-tabs rendered as subnav buttons (`#finances-subnav`):

| Sub-tab | Panel ID | Init function | Load function |
|---------|----------|---------------|--------------|
| 🆕 Новая сделка | `new-deal-sub` | `initDealForm()` | — |
| 📂 Мои сделки | `my-deals-sub` | `initMyDeals()` | `loadDeals()` |
| ✏️ Редактировать | `edit-deal-sub` | `initDealEdit()` | `loadDealsForEdit()` |

**API**: `GET /deals` (load), `POST /deals/create` (create), `GET /deals/{deal_id}` (detail/edit load), `PATCH /deals/update/{deal_id}` (edit save)

### Tab: Billing (`tab-billing`)

**Roles that see it**: manager, operations_director, admin

**Init function**: `initBillingForm()`  
**Load function**: `loadBillingEntry()` (triggered by button `billing-load-btn`)  
**Save function**: `saveBilling()` (triggered by button `billing-save-btn`)  
**Payment function**: `markPayment()` (triggered by button `payment-mark-btn`)

**API**: `GET /billing/v2/search` (primary), `GET /billing/search` (legacy fallback), `POST /billing/v2/upsert` (primary save), `POST /billing/{warehouse}` (legacy fallback), `POST /billing/v2/payment/mark`

### Tab: Расходы (`tab-expenses`)

**Roles that see it**: manager, operations_director, accounting, admin, accountant

**Init function**: `initExpensesForm()`  
**Save single**: `saveExpense()` → `POST /expenses/v2/create`  
**Save bulk**: `saveBulkExpenses()` → `POST /expenses/v2/create` (one call per row)  
**Load list**: `loadExpenses()` → `GET /expenses/v2`

### Tab: Отчёты (`tab-reports`)

**Roles that see it**: operations_director, accounting, admin, accountant, head_of_sales

**Init function**: `initReportsHandlers()`  
**Download function**: `downloadReport(reportType, fmt)` → `GET /reports/{reportType}?fmt=...`

### Tab: Журнал (`tab-journal`)

**Roles that see it**: operations_director, accounting, admin

**Init function**: `initJournalHandlers()`  
**Load function**: `loadJournal()` → `GET /journal?limit=50`

### Tab: Дашборд (`tab-dashboard`)

**Roles that see it**: operations_director, accounting, admin, accountant

**Init function**: `initDashboardHandlers()`  
**Load function**: `loadOwnerDashboard()` → `GET /dashboard/summary`  
**Auto-load**: triggered on `switchMainTab('tab-dashboard')`

### Tab: Долги / Дебиторка (`tab-receivables`)

**Roles that see it**: operations_director, accounting, admin, accountant

**Init function**: `initReceivablesHandlers()`  
**Load function**: `loadReceivables()` → `GET /receivables`  
**Auto-load**: triggered on `switchMainTab('tab-receivables')`

### Tab: Закрытие месяца (`tab-month-close`)

**Roles that see it**: operations_director, admin

**Init function**: `initMonthClose()`  
**API**: `POST /month/archive`, `POST /month/cleanup`, `POST /month/close`, `GET /month/archive-batches`

### Tab: Настройки (`settings-tab`)

**Roles that see it**: all roles

**Init function**: `initSettingsManagement()`  
**Auto-load on switch**: `loadClientsSettings()`, `loadManagersSettings()`, `loadDirectionsSettings()`, `loadStatusesSettings()`  
**Connection check**: `checkConnections()` → `GET /health`, `GET /settings`  
**API**: `/settings/clients` (CRUD), `/settings/managers` (CRUD), `/settings/directions` (CRUD), `/settings/statuses` (CRUD)

---

## 5. DEALS FLOW

### New Deal Form (`new-deal-sub`)

**HTML elements**:
- Form: `#deal-form`
- Status select: `#status` (value = numeric ID from enriched settings)
- Direction select: `#business_direction` (value = numeric ID)
- Client select: `#client` (value = numeric ID)
- Manager select: `#manager` (value = numeric ID; auto-filled from `localStorage.getItem('manager_id')` for manager role)
- Amount input: `#charged_with_vat` (float, required)
- VAT type select: `#vat_type` (value = numeric ID)
- VAT rate input: `#vat_rate` (float, 0–1 fraction)
- Paid input: `#paid`
- Start date: `#project_start_date` (date, required)
- End date: `#project_end_date` (date, required)
- Act date: `#act_date` (optional)
- Variable expense 1: `#variable_expense_1`
- Variable expense 2: `#variable_expense_2`
- Variable expense 1 with VAT: `#variable_expense_1_with_vat`
- Variable expense 2 with VAT: `#variable_expense_2_with_vat`
- Production expense with VAT: `#production_expense_with_vat`
- Manager bonus %: `#manager_bonus_percent`
- Manager bonus paid: `#manager_bonus_paid`
- General production expense: `#general_production_expense`
- Source select: `#source`
- Document link: `#document_link`
- Comment: `#comment`
- Submit button: `#submit-btn`
- Clear button: `#clear-btn`
- Live VAT calc row: `#deal-vat-calc`, `#deal-calc-vat-amount`, `#deal-calc-amount-no-vat`
- Summary card: `#deal-summary`, `#sum-client`, `#sum-amount`, `#sum-status`, `#sum-manager`
- Success screen: `#success-screen`, `#success-deal-id`

**JS functions**:
- `initDealForm()` — binds all form event handlers
- `handleFormSubmit(e)` — form submit handler; calls `validateForm()` then `collectFormDataSql()` then `POST /deals/create`
- `validateForm()` — checks required fields and that critical selects have numeric IDs
- `collectFormDataSql()` — builds payload with `status_id`, `business_direction_id`, `client_id`, `manager_id` (int IDs), and float fields
- `collectFormData()` — legacy string-based payload builder; **not called anywhere in the active code path**
- `updateSummary()` — updates `#deal-summary` card on field changes
- `setSubmitting(bool)` — shows/hides spinner on submit button
- `clearForm()` — resets form fields and error states
- `showSuccessScreen(dealId)` — hides form, shows success message
- `showForm()` — restores form after success screen

**Backend endpoint**: `POST /deals/create` (in `backend/routers/deals_sql.py`)

**Request payload** (from `collectFormDataSql()`):
```json
{
  "status_id": <int>,
  "business_direction_id": <int>,
  "client_id": <int>,
  "manager_id": <int>,
  "charged_with_vat": <float>,
  "vat_type_id": <int>,
  "vat_rate": <float|null>,
  "paid": <float>,
  "project_start_date": "YYYY-MM-DD",
  "project_end_date": "YYYY-MM-DD",
  "act_date": "YYYY-MM-DD|null",
  "variable_expense_1_without_vat": <float|null>,
  "variable_expense_2_without_vat": <float|null>,
  "production_expense_without_vat": <float|null>,
  "manager_bonus_percent": <float|null>,
  "source_id": <int|null>,
  "document_link": <string|null>,
  "comment": <string|null>
}
```

**Response fields expected by frontend**:
- `result.deal_id` OR `result.id` OR `result.deal?.id` — displayed in success screen

### My Deals List (`my-deals-sub`)

**HTML elements**:
- List container: `#deals-list`
- Loading state: `#deals-loading`
- Empty state: `#deals-empty`
- Refresh button: `#refresh-deals-btn`
- Status filter: `#filter-status` (value = numeric ID or empty)
- Client filter: `#filter-client` (value = numeric ID or empty)
- Month filter: `#filter-month` (YYYY-MM string)

**JS functions**:
- `initMyDeals()` — binds refresh and filter change handlers
- `loadDeals()` — fetches `GET /deals`, stores in `state.deals`, calls `renderDeals()`
- `renderDeals()` — filters `state.deals` in memory and renders deal cards
- `createDealCard(deal)` — builds deal card DOM element; binds view/copy actions
- `openDealModal(dealId)` — opens deal detail modal
- `showDealsLoading(bool)`, `showDealsEmpty(bool)`, `clearDealsList()` — UI state helpers

**Backend endpoint**: `GET /deals` (in `backend/routers/deals_sql.py`)

**Response fields used by frontend** (from deal object):
- `deal.deal_id` — displayed as ID
- `deal.status` — used for filter and status badge
- `deal.client`, `deal.client_id` — client name/ID
- `deal.business_direction` — direction label
- `deal.manager` — manager name
- `deal.charged_with_vat` — amount display
- `deal.project_start_date`, `deal.project_end_date` — date range
- `deal.comment` — comment bubble

### Edit Deal (`edit-deal-sub`)

**HTML elements**:
- Deal selector: `#edit-deal-select`
- Edit form body: `#edit-deal-form-body`
- Status: `#edit-status`
- Var expense 1 w/ VAT: `#edit-variable-expense-1-with-vat`
- Var expense 2 w/ VAT: `#edit-variable-expense-2-with-vat`
- Production expense w/ VAT: `#edit-production-expense-with-vat`
- General production expense: `#edit-general-production-expense`
- Manager bonus %: `#edit-manager-bonus-pct`
- Comment: `#edit-comment`
- Save button: `#edit-deal-save-btn`
- Back button: `#edit-deal-back-btn`
- Save actions container: `#edit-deal-save-actions`

**JS functions**:
- `initDealEdit()` — binds select-change, save, and back button handlers
- `loadDealsForEdit()` — fetches `GET /deals`, populates `#edit-deal-select`
- `onEditDealSelected(dealId)` — fetches `GET /deals/{deal_id}`, populates edit fields
- `saveEditedDeal()` — collects changed fields, sends `PATCH /deals/update/{deal_id}`

**Backend endpoints**:
- `GET /deals` — list for dropdown
- `GET /deals/{deal_id}` — load deal for editing
- `PATCH /deals/update/{deal_id}` (in `backend/routers/deals_sql.py`)

**Request payload** for PATCH (only changed fields included):
```json
{
  "status": <string|undefined>,
  "variable_expense_1_with_vat": <float|undefined>,
  "variable_expense_2_with_vat": <float|undefined>,
  "production_expense_with_vat": <float|undefined>,
  "general_production_expense": <float|undefined>,
  "manager_bonus_pct": <float|undefined>,
  "comment": <string|undefined>
}
```

**Response fields expected by frontend** (from `GET /deals/{deal_id}`):
- `deal.status`, `deal.variable_expense_1_with_vat`, `deal.variable_expense_2_with_vat`, `deal.production_expense_with_vat`, `deal.general_production_expense`, `deal.manager_bonus_pct`, `deal.comment`

### Deal Detail Modal

**HTML elements**:
- Modal overlay: `#deal-modal`
- Modal sheet: `.modal-sheet` inside overlay
- Title: `#modal-title`
- Body: `#modal-body`
- Close button: `#modal-close-btn`

**JS functions**:
- `openDealModal(dealId)` — looks up deal in `state.deals` first, fetches `GET /deals/{dealId}` if not cached
- `renderDealDetail(deal)` — generates HTML sections for all deal fields
- `closeDealModal()` — hides modal, restores body scroll

**Response fields rendered in modal** (`renderDealDetail`):
`status`, `business_direction`, `client`, `manager`, `charged_with_vat`, `vat_rate`, `vat_amount`, `amount_without_vat`, `vat_type`, `paid`, `marginal_income`, `gross_profit`, `manager_bonus_amount`, `project_start_date`, `project_end_date`, `act_date`, `variable_expense_1`, `variable_expense_1_with_vat`, `variable_expense_1_without_vat`, `variable_expense_2`, `variable_expense_2_with_vat`, `variable_expense_2_without_vat`, `production_expense_with_vat`, `production_expense_without_vat`, `manager_bonus_percent`, `manager_bonus_paid`, `general_production_expense`, `source`, `document_link`, `comment`, `created_at`

---

## 6. BILLING FLOW

### Filters

**HTML elements**:
- Warehouse select: `#billing-warehouse` (value = numeric warehouse ID from enriched settings)
- Client select: `#billing-client-select` (value = numeric client ID)
- Month input: `#billing-month` (YYYY-MM)
- Period select: `#billing-half` (`""` = full month, `"p1"` = 1–15, `"p2"` = 16–end)
- Input mode select: `#billing-format` (`"new"` = with-VAT, `"new-no-vat"` = without-VAT, `"old"` = p1/p2)
- Load button: `#billing-load-btn`
- Search status: `#billing-search-status`

### Loading Billing Data

**JS function**: `loadBillingEntry()`

**Primary path** (enriched settings loaded, numeric IDs available):
- Calls `GET /billing/v2/search?warehouse_id={int}&client_id={int}[&month=...][&period=...]`
- On `result.found === true`: calls `preloadBillingForm(result)`

**Legacy fallback** (string warehouse/client values):
- Calls `GET /billing/search?warehouse={string}&client={string}[&month=...][&period=...]`
- On `result.found === true`: calls `preloadBillingForm(result)`

**`preloadBillingForm(data)`** — fills form fields from API response:

New format fields: `data.shipments_with_vat`, `data.units_count`, `data.storage_with_vat`, `data.pallets_count`, `data.returns_pickup_with_vat`, `data.returns_trips_count`, `data.additional_services_with_vat`, `data.penalties`, `data.payment_status`, `data.payment_amount`, `data.payment_date`

Old format fields: `data.p1_shipments_amount`, `data.p1_units`, `data.p1_storage_amount`, `data.p1_pallets`, `data.p1_returns_amount`, `data.p1_returns_trips`, `data.p1_extra_services`, `data.p1_penalties`, (same set for p2_*)

### Saving Billing

**JS function**: `saveBilling()`

**Primary path** (enriched settings, new/new-no-vat format):
- Endpoint: `POST /billing/v2/upsert`
- Request payload (null fields omitted):
```json
{
  "client_id": <int>,
  "warehouse_id": <int>,
  "month": "YYYY-MM",
  "period": "p1|p2|undefined",
  "shipments_with_vat": <float|null>,
  "shipments_without_vat": <float|null>,
  "units_count": <int|null>,
  "storage_with_vat": <float|null>,
  "storage_without_vat": <float|null>,
  "pallets_count": <int|null>,
  "returns_pickup_with_vat": <float|null>,
  "returns_pickup_without_vat": <float|null>,
  "returns_trips_count": <int|null>,
  "additional_services_with_vat": <float|null>,
  "additional_services_without_vat": <float|null>,
  "penalties": <float|null>
}
```
Note: for `"new"` format, `*_with_vat` fields are populated; for `"new-no-vat"` format, `*_without_vat` fields are populated.

**Legacy fallback** (old p1/p2 format only):
- Endpoint: `POST /billing/{warehouse}`
- Payload: `{ client_name, p1: {...}, p2: {...} }`
- Note: if format is `"new"` or `"new-no-vat"` and numeric IDs were unavailable, the function aborts with an error toast instead of calling the legacy endpoint.

### Marking Payment

**JS function**: `markPayment()`

**HTML elements**:
- Direction filter: `#payment-direction-select`
- Client filter: `#payment-client-select`
- Deal selector: `#payment-deal-select` (populated by `loadDealsFiltered()`)
- Payment amount: `#payment-amount`

**Endpoint**: `POST /billing/v2/payment/mark`

**Request payload**:
```json
{
  "deal_id": "<string>",
  "payment_amount": <float>
}
```

**Response fields expected**: `result.remaining_amount` — displayed in toast

### Billing Totals Calculation (client-side)

- Old format: `calcBillingTotals(prefix)` — computes `total-no-pen` and `total-with-pen` for p1/p2
- New format: `calcBillingTotalsV2()` — computes `bv2-total-no-vat`, `bv2-total-vat`, `bv2-total-with-vat`

---

## 7. EXPENSES FLOW

### Single Expense Form

**HTML elements**:
- Direction filter: `#expense-direction-select`
- Client filter: `#expense-client-select`
- Deal selector: `#expense-deal-select` (populated via `loadDealsFiltered()`)
- Category L1: `#expense-cat1` (value = numeric ID from enriched settings, or name string as fallback)
- Category L2: `#expense-cat2` (shown/hidden based on L1; value = numeric ID or name string)
- Category L2 field container: `#expense-cat2-field`
- Comment: `#expense-comment`
- Comment field container: `#expense-comment-field`
- Comment required mark: `#expense-comment-required`
- Amount with VAT: `#expense-amount`
- VAT rate: `#expense-vat-rate` (fraction, 0–1)
- VAT amount (manual): `#expense-vat`
- VAT calc display: `#expense-calc-vat-amount`, `#expense-calc-no-vat`
- Save button: `#expense-save-btn`
- Load list button: `#load-expenses-btn`
- Expenses list: `#expenses-list`
- Loading state: `#expenses-loading`
- Empty state: `#expenses-empty`

### Filters

The expense form does not have dedicated date/month filters. Filtering is limited to direction/client/deal dropdowns (dependent chained dropdowns that trigger `loadDealsFiltered()`).

### Save/Update Flow

**JS function**: `saveExpense()`

**Endpoint**: `POST /expenses/v2/create`

**Request payload**:
```json
{
  "category_level_1_id": <int|undefined>,
  "category_level_2_id": <int|undefined>,
  "category_level_1": "<string|undefined>",
  "category_level_2": "<string|undefined>",
  "comment": "<string|undefined>",
  "deal_id": <int|undefined>,
  "amount_without_vat": <float>,
  "vat_rate": <float|undefined>
}
```

Comment is required when: L1 = "другое", OR L2 ∈ {"другое", "упаковочный материал"} (checked via `COMMENT_REQUIRED_L2` Set)

### Bulk Entry Flow

**JS function**: `saveBulkExpenses()`

Each row in `#bulk-rows-container` calls `POST /expenses/v2/create` individually.

Bulk row fields per row `idx`: `bulk-cat1-{idx}`, `bulk-cat2-{idx}`, `bulk-comment-{idx}`, `bulk-amount-{idx}`, `bulk-vat-rate-{idx}`, `bulk-deal-id-{idx}`

### Load Expenses List

**JS function**: `loadExpenses()` → `GET /expenses/v2`

**Response fields used**:
- `e.category_level_1`, `e.category_level_2`, `e.category`, `e.expense_type`
- `e.comment`
- `e.amount_with_vat`, `e.amount`, `e.amount_without_vat`, `e.vat_amount`, `e.vat`
- `e.date`, `e.created_at`
- `e.deal_id`

### Category Lookup Maps (module-level constants)

| Constant | Purpose |
|----------|---------|
| `EXPENSE_CATS_L2` | Name-keyed static map: L1 name → L2 name array (fallback when enriched settings unavailable) |
| `EXPENSE_CATS_L2_BY_ID` | ID-keyed dynamic map: numeric L1 ID → `[{id,name}]` array (populated from enriched settings) |
| `EXPENSE_CAT_L1_NAME_TO_ID` | L1 name (lowercase) → numeric ID |
| `EXPENSE_CAT_L1_ID_TO_NAME` | numeric ID string → L1 name (lowercase) |
| `EXPENSE_CAT_L2_NAME_TO_ID` | L2 name (lowercase) → numeric ID |
| `EXPENSE_CAT_L2_ID_TO_NAME` | numeric ID string → L2 name (lowercase) |

---

## 8. SETTINGS FLOW

### Loading Settings on App Init

**JS function**: `loadSettings()` → `GET /settings/enriched`

Raw response stored in `state.settings`. Normalized `{id,name}` version stored in `state.enrichedSettings` via `normalizeSettings(data)`.

**`normalizeSettings(data)` field mapping**:
```
statuses: data.statuses → [{id, name}] (handles both plain strings and objects)
clients: data.clients → [{id, name|client_name}]
managers: data.managers → [{id, name|manager_name}]
directions: data.business_directions|data.directions → [{id, name}]
warehouses: data.warehouses → [{id, name, code}]
expense_categories: data.expense_categories (passed through)
vat_types: data.vat_types (passed through)
```

**Fallback** (if `/settings/enriched` fails): hardcoded string lists; `state.enrichedSettings` is set to `null`; dropdown values will be strings instead of IDs; SQL endpoints will fail validation if used.

### `populateSelects(data)` — select population map

| Select ID | Source field |
|-----------|-------------|
| `#status` | `data.statuses` |
| `#business_direction` | `data.business_directions` |
| `#client` | `data.clients` |
| `#manager` | `data.managers` |
| `#vat_type` | `data.vat_types` |
| `#source` | `data.sources` |
| `#billing-client-select` | `state.enrichedSettings.clients` (or `FALLBACK_CLIENTS = []`) |
| `#payment-client-select` | same |
| `#expense-client-select` | same |
| `#report-client-select` | same |
| `#filter-client` | same (with blank "Все" option) |
| `#payment-direction-select` | `data.business_directions` |
| `#expense-direction-select` | same |
| `#billing-warehouse` | `state.enrichedSettings.warehouses` (or `FALLBACK_WAREHOUSES = []`) |
| `#edit-status` | `data.statuses` |
| `#filter-status` | `data.statuses` (with blank "Все" option) |
| `#expense-cat1` | `data.expense_categories` (id/name objects) |

Additionally, `localStorage.getItem('manager_id')` is auto-selected in `#manager` select when role is manager.

### Clients (Settings Tab)

**Init**: `initSettingsManagement()` → `loadClientsSettings()`

**API**:
- `GET /settings/clients` → response items: `{client_id, client_name}`
- `POST /settings/clients` → body: `{client_name: string}`
- `DELETE /settings/clients/{client_id}`

**After load**: re-populates `#client`, `#filter-client`, `#billing-client-select`, `#payment-client-select`, `#expense-client-select`, `#report-client-select` with `{id: client_id, name: client_name}`

### Managers (Settings Tab)

**API**:
- `GET /settings/managers` → response items: `{manager_id, manager_name, role}`
- `POST /settings/managers` → body: `{manager_name: string, role: string}`
- `DELETE /settings/managers/{manager_id}`

**After load**: re-populates `#manager` with `{id: manager_id, name: manager_name}`

### Directions (Settings Tab)

**API**:
- `GET /settings/directions` → response: `string[]`
- `POST /settings/directions` → body: `{value: string}`
- `DELETE /settings/directions/{direction}`

**After load**: populates `#business_direction`, `#payment-direction-select`, `#expense-direction-select` from `state.enrichedSettings.business_directions` (ID objects) — NOT from the string array returned by `/settings/directions`.

### Statuses (Settings Tab)

**API**:
- `GET /settings/statuses` → response: `string[]`
- `POST /settings/statuses` → body: `{value: string}`
- `DELETE /settings/statuses/{status}`

**After load**: populates `#status`, `#edit-status`, `#filter-status` from `state.enrichedSettings.statuses` (ID objects) — NOT from the string array returned by `/settings/statuses`.

### Warehouses

Warehouses are NOT managed from the Settings tab. They are loaded exclusively from `GET /settings/enriched` and normalized in `state.enrichedSettings.warehouses`. The `#billing-warehouse` select is populated from there.

### Connection Status (Settings Tab)

**HTML**: `#dot-telegram`, `#status-telegram`, `#dot-api`, `#status-api`, `#dot-sheets`, `#status-sheets`

**JS function**: `checkConnections()` called from `switchMainTab('settings-tab')` and `initTabs()`

- Telegram status: `hasTelegramAuthContext()` or `hasLocalAuth()`
- API status: `GET /health`
- Справочники status: `GET /settings`

### Settings Stats Display

`#cnt-statuses`, `#cnt-clients`, `#cnt-managers`, `#cnt-directions` — updated by `updateSettingsStats(data)` on settings load

---

## 9. API MAP

| JS Function | Endpoint URL | Method | Purpose | Tab/Screen | Active/Legacy |
|-------------|-------------|--------|---------|------------|---------------|
| `loginWithTelegram()` | `/auth/miniapp-login` | POST | Telegram auto-login on startup | Auth | Active |
| `doLogin()` (Telegram path) | `/auth/miniapp-login` | POST | Manual login with Telegram context | Auth screen | Active |
| `doLogin()` (browser path) | `/auth/role-login` | POST | Manual login without Telegram | Auth screen | Active |
| `loadSettings()` | `/settings/enriched` | GET | Load all reference data with IDs | App init | Active |
| `checkConnections()` | `/health` | GET | API health check | Settings tab | Active |
| `checkConnections()` | `/settings` | GET | Справочники health check | Settings tab | Active |
| `loadClientsSettings()` | `/settings/clients` | GET | Load clients list for settings mgmt | Settings tab | Active |
| `addClient()` | `/settings/clients` | POST | Add new client | Settings tab | Active |
| `deleteClient()` | `/settings/clients/{client_id}` | DELETE | Delete client | Settings tab | Active |
| `loadManagersSettings()` | `/settings/managers` | GET | Load managers list | Settings tab | Active |
| `addManager()` | `/settings/managers` | POST | Add new manager | Settings tab | Active |
| `deleteManager()` | `/settings/managers/{manager_id}` | DELETE | Delete manager | Settings tab | Active |
| `loadDirectionsSettings()` | `/settings/directions` | GET | Load directions list | Settings tab | Active |
| `addDirection()` | `/settings/directions` | POST | Add direction | Settings tab | Active |
| `deleteDirection()` | `/settings/directions/{direction}` | DELETE | Delete direction | Settings tab | Active |
| `loadStatusesSettings()` | `/settings/statuses` | GET | Load statuses list | Settings tab | Active |
| `addStatus()` | `/settings/statuses` | POST | Add status | Settings tab | Active |
| `deleteStatus()` | `/settings/statuses/{status}` | DELETE | Delete status | Settings tab | Active |
| `handleFormSubmit()` | `/deals/create` | POST | Create new deal | Finances tab | Active |
| `loadDeals()` | `/deals` | GET | Load deal list | Finances tab | Active |
| `loadDealsFiltered()` | `/deals?business_direction_id=&client_id=` | GET | Load deals for dropdowns (billing/expenses) | Billing, Expenses | Active |
| `loadDealsForEdit()` | `/deals` | GET | Load deals for edit dropdown | Finances tab | Active |
| `onEditDealSelected()` | `/deals/{deal_id}` | GET | Load single deal for editing | Finances tab | Active |
| `openDealModal()` | `/deals/{deal_id}` | GET | Load deal detail (if not in cache) | Finances tab | Active |
| `saveEditedDeal()` | `/deals/update/{deal_id}` | PATCH | Save deal edits | Finances tab | Active |
| `loadBillingEntry()` | `/billing/v2/search` | GET | Load existing billing record | Billing tab | Active (primary) |
| `loadBillingEntry()` | `/billing/search` | GET | Load billing (legacy fallback) | Billing tab | Legacy (fallback) |
| `saveBilling()` | `/billing/v2/upsert` | POST | Save billing (new format, IDs available) | Billing tab | Active (primary) |
| `saveBilling()` | `/billing/{warehouse}` | POST | Save billing (old p1/p2 format only) | Billing tab | Legacy (fallback for old format) |
| `markPayment()` | `/billing/v2/payment/mark` | POST | Mark payment on a deal | Billing tab | Active |
| `loadExpenses()` | `/expenses/v2` | GET | Load expense list | Expenses tab | Active |
| `saveExpense()` | `/expenses/v2/create` | POST | Save single expense | Expenses tab | Active |
| `saveBulkExpenses()` | `/expenses/v2/create` | POST | Save bulk expenses (one per row) | Expenses tab | Active |
| `downloadReport()` | `/reports/{type}?fmt=...` | GET | Download report as CSV/XLSX | Reports tab | Active |
| `loadJournal()` | `/journal?limit=50` | GET | Load action journal | Journal tab | Active |
| `loadOwnerDashboard()` | `/dashboard/summary` | GET | Load dashboard KPIs | Dashboard tab | Active |
| `loadReceivables()` | `/receivables` | GET | Load receivables data | Receivables tab | Active |
| `runMonthArchive()` | `/month/archive` | POST | Archive month (dry-run or real) | Month Close tab | Active |
| `runMonthCleanup()` | `/month/cleanup` | POST | Clean staging for month | Month Close tab | Active |
| `runMonthClose()` | `/month/close` | POST | Close month permanently | Month Close tab | Active |
| `loadArchiveBatches()` | `/month/archive-batches` | GET | Load archive batch list | Month Close tab | Active |

---

## 10. DOM MAP

### Deal Form Fields

| DOM ID | Type | Purpose |
|--------|------|---------|
| `deal-form` | form | New deal form wrapper |
| `status` | select | Deal status (numeric ID value) |
| `business_direction` | select | Business direction (numeric ID value) |
| `client` | select | Client (numeric ID value) |
| `manager` | select | Manager (numeric ID value) |
| `charged_with_vat` | number input | Amount with VAT (required) |
| `vat_type` | select | VAT type (numeric ID value) |
| `vat_rate` | number input | VAT rate fraction (optional) |
| `paid` | number input | Amount paid |
| `project_start_date` | date input | Project start date (required) |
| `project_end_date` | date input | Project end date (required) |
| `act_date` | date input | Act date (optional) |
| `variable_expense_1` | number input | Variable expense 1 (without VAT) |
| `variable_expense_2` | number input | Variable expense 2 (without VAT) |
| `variable_expense_1_with_vat` | number input | Variable expense 1 with VAT |
| `variable_expense_2_with_vat` | number input | Variable expense 2 with VAT |
| `production_expense_with_vat` | number input | Production expense with VAT |
| `manager_bonus_percent` | number input | Manager bonus % |
| `manager_bonus_paid` | number input | Manager bonus paid amount |
| `general_production_expense` | number input | General production expense |
| `source` | select | Deal source |
| `document_link` | url input | Document link |
| `comment` | textarea | Deal comment |
| `submit-btn` | button | Form submit |
| `clear-btn` | button | Clear form |
| `deal-summary` | section | Live summary card |
| `deal-vat-calc` | div | Live VAT calculation row |
| `status-error`, `business_direction-error`, `client-error`, `manager-error`, `charged_with_vat-error`, `vat_type-error`, `project_start_date-error`, `project_end_date-error` | span | Per-field error messages |

### Edit Deal Fields

| DOM ID | Type | Purpose |
|--------|------|---------|
| `edit-deal-select` | select | Choose deal to edit |
| `edit-status` | select | Edit: status |
| `edit-variable-expense-1-with-vat` | number input | Edit: var expense 1 with VAT |
| `edit-variable-expense-2-with-vat` | number input | Edit: var expense 2 with VAT |
| `edit-production-expense-with-vat` | number input | Edit: production expense with VAT |
| `edit-general-production-expense` | number input | Edit: general production expense |
| `edit-manager-bonus-pct` | number input | Edit: manager bonus % |
| `edit-comment` | text input | Edit: comment |
| `edit-deal-save-btn` | button | Save deal edits |

### Billing Fields

| DOM ID | Type | Purpose |
|--------|------|---------|
| `billing-warehouse` | select | Warehouse filter (numeric ID) |
| `billing-client-select` | select | Client filter (numeric ID) |
| `billing-month` | month input | Month filter |
| `billing-half` | select | Period (p1/p2/empty) |
| `billing-format` | select | Input mode (new/new-no-vat/old) |
| `billing-load-btn` | button | Load existing billing record |
| `billing-save-btn` | button | Save billing |
| `billing-search-status` | div | Search status message |
| `bv2-shipments-with-vat` | number input | Shipments (with VAT field label updated dynamically) |
| `bv2-units` | number input | Units count |
| `bv2-storage-with-vat` | number input | Storage |
| `bv2-pallets` | number input | Pallets |
| `bv2-returns-pickup-with-vat` | number input | Returns pickup |
| `bv2-returns-trips` | number input | Returns trips |
| `bv2-additional-with-vat` | number input | Additional services |
| `bv2-penalties` | number input | Penalties |
| `bv2-payment-status` | select | Payment status |
| `bv2-payment-amount` | number input | Payment amount |
| `bv2-payment-date` | date input | Payment date |
| `bv2-total-no-vat`, `bv2-total-vat`, `bv2-total-with-vat` | strong | Live billing totals |
| `p1-shipments` … `p1-penalties` | number inputs | Period 1 fields |
| `p2-shipments` … `p2-penalties` | number inputs | Period 2 fields |
| `payment-direction-select` | select | Payment: direction filter |
| `payment-client-select` | select | Payment: client filter |
| `payment-deal-select` | select | Payment: deal selector |
| `payment-amount` | number input | Payment: amount |
| `payment-mark-btn` | button | Mark payment |

### Expense Fields

| DOM ID | Type | Purpose |
|--------|------|---------|
| `expense-direction-select` | select | Expense: direction filter |
| `expense-client-select` | select | Expense: client filter |
| `expense-deal-select` | select | Expense: deal selector |
| `expense-cat1` | select | Category level 1 (numeric ID or name) |
| `expense-cat2` | select | Category level 2 (numeric ID or name) |
| `expense-comment` | text input | Expense comment |
| `expense-amount` | number input | Amount with VAT |
| `expense-vat-rate` | number input | VAT rate fraction |
| `expense-vat` | number input | VAT amount (manual entry, alternative to rate) |
| `expense-save-btn` | button | Save expense |
| `expense-calc-vat-amount`, `expense-calc-no-vat` | strong | Live VAT calculation |

### Auth/Login Fields

| DOM ID | Type | Purpose |
|--------|------|---------|
| `auth-screen` | div | Auth screen wrapper |
| `auth-step-role` | div | Role selection buttons |
| `auth-step-manager` | div | Manager selection buttons |
| `auth-step-password` | div | Password entry step |
| `auth-password` | password input | Password field |
| `auth-error` | div | Auth error message |
| `auth-submit-btn` | button | Login submit |
| `auth-back-btn` | button | Go back from password step |
| `auth-manager-back-btn` | button | Go back from manager step |
| `auth-role-label` | strong | Displays selected role label |

### Settings Fields

| DOM ID | Type | Purpose |
|--------|------|---------|
| `cnt-statuses`, `cnt-clients`, `cnt-managers`, `cnt-directions` | span | Settings stats counts |
| `new-client-name` | text input | New client name input |
| `add-client-btn` | button | Add client |
| `refresh-clients-btn` | button | Reload clients |
| `clients-list-settings` | div | Clients ref list |
| `clients-empty-settings` | div | Clients empty state |
| `new-manager-name` | text input | New manager name |
| `new-manager-role` | select | New manager role |
| `add-manager-btn` | button | Add manager |
| `managers-list-settings` | div | Managers ref list |
| `new-direction-name` | text input | New direction name |
| `add-direction-btn` | button | Add direction |
| `directions-list-settings` | div | Directions ref list |
| `new-status-name` | text input | New status name |
| `add-status-btn` | button | Add status |
| `statuses-list-settings` | div | Statuses ref list |
| `dot-telegram`, `status-telegram` | div/span | Telegram connection status |
| `dot-api`, `status-api` | div/span | API server connection status |
| `dot-sheets`, `status-sheets` | div/span | Settings DB connection status |
| `user-info-card`, `user-info-content` | section/div | Current user info card |
| `logout-btn` | button | Switch role / logout |

### Dropdown / Select Elements (complete list)

| Select ID | Populated from | First populated in |
|-----------|---------------|-------------------|
| `#status` | `/settings/enriched` statuses | `populateSelects()` |
| `#business_direction` | `/settings/enriched` business_directions | `populateSelects()` |
| `#client` | `/settings/enriched` clients | `populateSelects()` |
| `#manager` | `/settings/enriched` managers | `populateSelects()` |
| `#vat_type` | `/settings/enriched` vat_types | `populateSelects()` |
| `#source` | `/settings/enriched` sources | `populateSelects()` |
| `#edit-status` | `/settings/enriched` statuses | `populateSelects()` |
| `#filter-status` | `/settings/enriched` statuses | `populateSelects()` |
| `#filter-client` | enriched clients | `populateSelects()` |
| `#billing-warehouse` | enriched warehouses `{id, "CODE — name"}` | `populateSelects()` |
| `#billing-client-select` | enriched clients | `populateSelects()` |
| `#payment-client-select` | enriched clients | `populateSelects()` |
| `#payment-direction-select` | enriched directions | `populateSelects()` |
| `#expense-client-select` | enriched clients | `populateSelects()` |
| `#expense-direction-select` | enriched directions | `populateSelects()` |
| `#report-client-select` | enriched clients | `populateSelects()` |
| `#expense-cat1` | enriched `expense_categories` | `populateSelects()` |
| `#expense-cat2` | sub-cats of selected L1 | `updateExpenseCat2()` |
| `#payment-deal-select` | `GET /deals` (filtered) | `loadDealsFiltered()` |
| `#expense-deal-select` | `GET /deals` (filtered) | `loadDealsFiltered()` |
| `#edit-deal-select` | `GET /deals` | `loadDealsForEdit()` |
| `#billing-half` | hardcoded HTML options | static HTML |
| `#billing-format` | hardcoded HTML options | static HTML |
| `#report-warehouse` | hardcoded HTML options | static HTML |

---

## 11. LEGACY VS ACTIVE LOGIC

### Active paths

- All API calls through `apiFetch()` — sends `X-Telegram-Init-Data`, `X-Telegram-Id`, `X-User-Role` headers
- `POST /deals/create` — SQL-function endpoint (deals_sql.py)
- `GET /deals`, `GET /deals/{deal_id}`, `PATCH /deals/update/{deal_id}` — SQL endpoints (deals_sql.py)
- `POST /billing/v2/upsert` — active path when enriched settings loaded
- `GET /billing/v2/search` — active path when enriched settings loaded
- `POST /billing/v2/payment/mark` — always active
- `POST /expenses/v2/create`, `GET /expenses/v2` — always active
- Enriched settings (`/settings/enriched`) as the single source of truth for all reference data
- Role-based tab visibility via `ROLE_TABS` map
- Dependent dropdown chain: direction → client → deal

### Legacy paths (fallback, only reached when enriched settings fail)

- `GET /billing/search` — string-based billing search; reached when `state.enrichedSettings` is null or IDs are not numeric
- `POST /billing/{warehouse}` — reached only for old p1/p2 format; **never reached for new/new-no-vat formats** (app aborts with error toast instead)
- String-based fallback in `populateSelects()` (plain string options) — reached when `/settings/enriched` call fails
- `EXPENSE_CATS_L2` static map — fallback when `EXPENSE_CATS_L2_BY_ID` is empty (enriched settings not loaded)
- `collectFormData()` function — never called; defined but unused; legacy string-based payload builder

### Dead code

- `collectFormData()` — defined at line 712, never called anywhere in the active code path
- `frontend/` directory — entire directory is a legacy prototype; not served by the FastAPI backend and calls a separate Node.js backend at `localhost:3000`

### Dangerous to touch

- `populateSelects()` — touches all dropdown elements at once; any change risks breaking multiple forms simultaneously
- `loadSettings()` / `normalizeSettings()` — single point of failure for all reference data; if enriched settings normalization is wrong, all dropdowns break
- The `fillSelect()` function — used for every single dropdown; used from both `populateSelects()` and from individual settings management loaders; the `currentValue` restore logic can silently fail if option set changes
- The `ROLE_TABS` map — determines which tabs each role can see; incorrect entries break entire role access

### Partially migrated to v2 endpoints

- Billing: `saveBilling()` has both v2 (active) and legacy path (old p1/p2 format)
- `loadBillingEntry()`: v2 is primary; legacy fallback is preserved
- Expenses: fully on v2 (`/expenses/v2`)
- Deals: fully on SQL endpoints (`/deals`, `/deals/create`, etc.)

---

## 12. FILE RESPONSIBILITY MATRIX

---

**FILE**: `miniapp/index.html`

**RESPONSIBILITY**: HTML skeleton for the active Mini App; contains all screens (auth, app-main), all tab panels (tab-finances, tab-billing, tab-expenses, tab-reports, tab-journal, tab-dashboard, tab-receivables, settings-tab, tab-month-close), all form inputs, all modal elements, and the `<script src="app.js">` tag that loads the runtime.

**SAFE TO MODIFY FOR**: adding or removing form fields, adding new tab panels, changing label text, adjusting placeholder text, HTML structure changes that don't rename IDs referenced in app.js.

**DO NOT TOUCH WHEN FIXING**: backend SQL logic, auth flow, API endpoint behaviour, CSS-only issues (those are in styles.css).

**DEPENDS ON**: `miniapp/styles.css`, `miniapp/app.js`, `https://telegram.org/js/telegram-web-app.js`

---

**FILE**: `miniapp/app.js`

**RESPONSIBILITY**: sole JavaScript runtime for the active Mini App; Telegram SDK init; localStorage auth state; all API calls; deal form collection and submission; billing form collection and submission; expense form handling; settings management (CRUD for clients/managers/directions/statuses); tab and subnav switching; deal editing; reports download; journal loading; dashboard loading; receivables loading; month-close operations; toast notifications; DOM manipulation.

**SAFE TO MODIFY FOR**: frontend-only bugs, dropdown logic, request payload construction, rendering issues, auth flow bugs, VAT calculation logic, filter logic, form validation.

**DO NOT TOUCH WHEN FIXING**: backend SQL stored procedures, database schema, backend auth validation logic.

**DEPENDS ON**: `miniapp/index.html` (all DOM IDs), backend endpoints (`/auth/*`, `/settings/*`, `/deals/*`, `/billing/*`, `/expenses/*`, `/reports/*`, `/journal`, `/dashboard/*`, `/receivables`, `/month/*`, `/health`)

---

**FILE**: `miniapp/styles.css`

**RESPONSIBILITY**: all visual styling for the active Mini App; Telegram theme variable support; dark mode via `[data-theme="dark"]`; responsive layout; component styles (cards, buttons, forms, tabs, modals, toasts, deal cards, expense rows, journal rows, kpi cards, billing totals, etc.).

**SAFE TO MODIFY FOR**: visual/layout bugs, dark mode issues, component appearance.

**DO NOT TOUCH WHEN FIXING**: any logic bugs, API issues, auth issues.

**DEPENDS ON**: `miniapp/index.html` (class names)

---

**FILE**: `frontend/index.html`

**RESPONSIBILITY**: HTML for a legacy prototype Mini App; uses `frontend/js/permissions.js`, `frontend/js/api.js`, `frontend/js/app.js`; NOT connected to FastAPI backend; calls `localhost:3000`.

**SAFE TO MODIFY FOR**: nothing in the active system — this file is legacy and not served by the active backend.

**DO NOT TOUCH WHEN FIXING**: any production bugs.

**DEPENDS ON**: a separate Node.js backend at `localhost:3000` (not present in this repository)

---

**FILE**: `frontend/js/app.js`

**RESPONSIBILITY**: legacy Mini App class-based runtime for `frontend/index.html`; App, DealsScreen, JournalScreen, AnalyticsScreen, SettingsScreen classes; uses `ApiClient` from `frontend/js/api.js`.

**SAFE TO MODIFY FOR**: nothing in the active system — this is legacy code.

**DO NOT TOUCH WHEN FIXING**: any production bugs.

**DEPENDS ON**: `frontend/js/api.js`, `frontend/js/permissions.js`, Node.js backend

---

**FILE**: `frontend/js/api.js`

**RESPONSIBILITY**: legacy `ApiClient` class for `frontend/js/app.js`; calls `/api/me`, `/api/deals`, `/api/journal`, `/api/analytics/*` on `localhost:3000`; sends `X-User-Id` header.

**SAFE TO MODIFY FOR**: nothing in the active system.

**DO NOT TOUCH WHEN FIXING**: any production bugs.

**DEPENDS ON**: Node.js backend at `localhost:3000`

---

**FILE**: `frontend/js/permissions.js`

**RESPONSIBILITY**: legacy permission matrix (roles: admin/sales/accounting/viewer); `Permissions` class; `applyFormRestrictions()` for `data-perm` attributes; **role set does not match the active Mini App roles**.

**SAFE TO MODIFY FOR**: nothing in the active system.

**DO NOT TOUCH WHEN FIXING**: any production bugs.

**DEPENDS ON**: nothing

---

**FILE**: `static/index.html`

**RESPONSIBILITY**: self-contained single-file Telegram Mini App prototype with inline CSS and JS; calls `/deal/*` and `/settings/*` FastAPI endpoints; NOT served automatically by the backend's StaticFiles mount (only `miniapp/` is mounted).

**SAFE TO MODIFY FOR**: nothing in the active system — not served.

**DO NOT TOUCH WHEN FIXING**: any production bugs.

**DEPENDS ON**: `backend/routers/deals.py` (`/deal/*`), `backend/routers/settings.py`

---

**FILE**: `backend/routers/deals_sql.py`

**RESPONSIBILITY**: active deal endpoints (`GET /deals`, `POST /deals/create`, `GET /deals/{deal_id}`, `PATCH /deals/update/{deal_id}`, `POST /deals/pay`); calls PostgreSQL SQL functions via `backend/services/db_exec.py`.

**SAFE TO MODIFY FOR**: deal data bugs, field mapping between frontend payload and SQL function.

**DO NOT TOUCH WHEN FIXING**: frontend form rendering bugs, CSS issues.

**DEPENDS ON**: `backend/services/db_exec.py`, `backend/services/miniapp_auth_service.py`, PostgreSQL SQL functions

---

**FILE**: `backend/routers/billing_sql.py`

**RESPONSIBILITY**: active billing endpoints (`GET /billing/v2`, `GET /billing/v2/search`, `POST /billing/v2/upsert`, `POST /billing/v2/payment/mark`); SQL-function-based.

**SAFE TO MODIFY FOR**: billing data bugs, field mapping, payment mark logic.

**DO NOT TOUCH WHEN FIXING**: frontend form rendering, dropdown logic.

**DEPENDS ON**: `backend/services/db_exec.py`, `backend/services/miniapp_auth_service.py`, `backend/schemas/billing.py`

---

**FILE**: `backend/routers/expenses_sql.py`

**RESPONSIBILITY**: active expenses endpoints (`GET /expenses/v2`, `POST /expenses/v2/create`); SQL-function-based.

**SAFE TO MODIFY FOR**: expense data bugs.

**DO NOT TOUCH WHEN FIXING**: frontend rendering.

**DEPENDS ON**: `backend/services/db_exec.py`, `backend/services/miniapp_auth_service.py`

---

**FILE**: `backend/routers/settings.py`

**RESPONSIBILITY**: all settings endpoints (`GET /settings/enriched`, `/settings/clients` CRUD, `/settings/managers` CRUD, `/settings/directions` CRUD, `/settings/statuses` CRUD, `GET /settings`); normalization of reference data for Mini App.

**SAFE TO MODIFY FOR**: reference data structure bugs, adding new fields to enriched response.

**DO NOT TOUCH WHEN FIXING**: frontend billing/deal form rendering.

**DEPENDS ON**: `backend/services/settings_service.py`

---

**FILE**: `backend/routers/auth.py`

**RESPONSIBILITY**: Mini App authentication (`POST /auth/miniapp-login`, `POST /auth/role-login`, `POST /auth/validate`, `GET /auth/role`); resolves Telegram users to app_users records.

**SAFE TO MODIFY FOR**: auth bugs, password validation, manager identity resolution.

**DO NOT TOUCH WHEN FIXING**: frontend rendering, billing logic.

**DEPENDS ON**: `backend/services/miniapp_auth_service.py`, `backend/services/auth_service.py`, `config/config.py`

---

**FILE**: `backend/routers/billing.py`

**RESPONSIBILITY**: LEGACY billing endpoints (`GET /billing/search`, `GET /billing/{warehouse}`, `POST /billing/{warehouse}`, `POST /billing/payment/mark`); kept for backward compatibility.

**SAFE TO MODIFY FOR**: old p1/p2 format bugs only; the active Mini App only reaches these endpoints via the old p1/p2 format path.

**DO NOT TOUCH WHEN FIXING**: new format billing bugs (those are in billing_sql.py).

**DEPENDS ON**: `backend/services/billing_service.py`

---

**FILE**: `backend/routers/month_close.py`

**RESPONSIBILITY**: month-close operations (`POST /month/archive`, `POST /month/cleanup`, `POST /month/close`, `GET /month/archive-batches`).

**SAFE TO MODIFY FOR**: month-close logic bugs.

**DO NOT TOUCH WHEN FIXING**: deal/billing/expense bugs.

**DEPENDS ON**: `backend/services/db_exec.py`, `backend/services/miniapp_auth_service.py`

---

## 13. FINAL BUG-FIXING GUIDANCE

### Frontend-only files

- `miniapp/app.js` — all frontend logic; safe to fix: rendering, form validation, payload construction, dropdown population, auth flow UI, filter logic, VAT calculations
- `miniapp/index.html` — safe to fix: HTML structure, DOM IDs, form field names
- `miniapp/styles.css` — safe to fix: visual/layout issues only

### Backend-only files

- `backend/routers/deals_sql.py`, `backend/routers/billing_sql.py`, `backend/routers/expenses_sql.py` — safe to fix: SQL call bugs, response field mapping, auth errors on those specific endpoints
- `backend/routers/settings.py` — safe to fix: enriched settings response structure
- `backend/routers/auth.py` — safe to fix: authentication/authorization bugs
- `backend/services/miniapp_auth_service.py` — safe to fix: user resolution from Telegram initData
- `backend/services/settings_service.py` — safe to fix: data returned by settings endpoints

### High-risk files (changing them can break multiple features simultaneously)

1. **`miniapp/app.js` — `populateSelects()`**: touches every dropdown in the app; a logic error here breaks deals form, billing form, expense form, and filter selects at once.
2. **`miniapp/app.js` — `loadSettings()` / `normalizeSettings()`**: if enriched settings fail to normalize, all dropdowns return string values instead of IDs, and all SQL function endpoints reject the requests.
3. **`miniapp/app.js` — `fillSelect()`**: used by every dropdown population path; the `currentValue` restore logic can silently lose the user's current selection.
4. **`miniapp/app.js` — `apiFetch()`**: all network calls go through this; changes to auth headers here affect every single API call.
5. **`backend/routers/settings.py` — `/settings/enriched`**: the single source of truth for all reference data in the frontend; if the response structure changes, the entire Mini App's dropdown population breaks.
6. **`backend/main.py` — router registration order**: SQL routers MUST be registered before legacy routers; changing the order causes `/billing/v2/*` paths to be captured by `/billing/{warehouse}`.

### How future fixes should be constrained

- **Frontend rendering bug** (wrong text, wrong option, wrong field visible): fix only in `miniapp/app.js` at the specific render function. Do not touch backend.
- **Wrong value sent to backend** (wrong field name in payload, wrong ID sent): fix only `collectFormDataSql()`, `saveBilling()`, `saveExpense()`, or `saveEditedDeal()` in `miniapp/app.js`. Do not touch backend unless the schema is wrong.
- **Dropdown not populated** or **wrong options**: fix `populateSelects()` or the specific settings load function (`loadClientsSettings()` etc.) in `miniapp/app.js`, or fix `GET /settings/enriched` in `backend/routers/settings.py` — determine which layer is at fault first.
- **Backend SQL error** (stored procedure fails, wrong data persisted): fix only the relevant `_sql.py` router or the SQL function in the database. Do not touch frontend.
- **Auth failure** (403, wrong role, missing telegram_id): fix `backend/routers/auth.py` or `backend/services/miniapp_auth_service.py`. On the frontend, only `loginWithTelegram()` and `doLogin()` in `miniapp/app.js` are involved.
- **Legacy files** (`frontend/`, `static/index.html`, `backend/routers/billing.py` for new format, `backend/routers/expenses.py`): do NOT modify for production bug fixes unless the bug is specifically in the legacy flow (old p1/p2 billing format, or the `static/index.html` prototype).
