# Technical Report: Telegram Mini App — Finance ERP System

> **Scope:** Sections 1–4 as requested.
> All statements are based on real files and real code only.
> "I cannot confirm this from the code" is used where evidence is missing.

---

## 1. PROJECT OVERVIEW

### What This Mini App Does

This is a **Telegram Mini App** for a Finance ERP system (all UI text is in Russian). It covers the full lifecycle of deals, billing, expenses, reporting, and month-end accounting operations for a logistics/warehousing business.

Core functional areas:

- **Deals (Сделки)** — create, view, edit, and filter deals with full financial fields (revenue with/without VAT, expenses, manager bonuses, etc.)
- **Billing** — warehouse billing data entry (shipments, storage, returns, penalties) in two formats: legacy `p1/p2` periods and new VAT-inclusive/exclusive format
- **Expenses** — single and bulk entry of operating expenses with two-level categorisation and VAT handling
- **Reports** — download 11 report types in CSV and XLSX format (warehouse, clients, expenses, profit, receivables, billing by month/client, etc.)
- **Journal** — read-only action log (last 50 entries)
- **Owner Dashboard** — KPI summary with warehouse and client breakdowns, filterable by month
- **Receivables** — debtor control with breakdown by client, warehouse, and month
- **Month Close** — dry-run archive, real archive, cleanup, and close operations for a given year/month
- **Settings** — CRUD management of clients, managers, directions, and statuses; connection status diagnostics; current-user info

### Which Files are Responsible for Frontend Logic

There are **two separate Mini App implementations** in this repository:

| Implementation | Directory | Status |
|---|---|---|
| **Primary (production)** | `miniapp/` | Served by the backend at `/miniapp` |
| **Prototype/demo** | `frontend/` | Not served by the backend; standalone |

The `miniapp/` implementation is the one integrated with the FastAPI backend. The `frontend/` implementation is a simpler proof-of-concept.

### How the Mini App is Launched

The FastAPI backend (`backend/main.py`, line 123–125) mounts the `miniapp/` directory as a `StaticFiles` endpoint at the `/miniapp` URL prefix:

```python
_miniapp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "miniapp")
if os.path.isdir(_miniapp_dir):
    app.mount("/miniapp", StaticFiles(directory=_miniapp_dir, html=True), name="miniapp")
```

Users open the Mini App through a Telegram bot that sends a Web App button pointing to the deployed `/miniapp` URL.

### Single-Page App or Multi-Screen App

The `miniapp/` implementation is a **single-page app (SPA)** with **multiple tabs and sub-navigation panels**. There is no page navigation; all screens are shown/hidden via `style.display` manipulation in JavaScript. The HTML file (`miniapp/index.html`) contains all screens as hidden `<div>` elements.

The `frontend/` implementation follows the same SPA pattern with four named screens: `screen-deals`, `screen-journal`, `screen-analytics`, `screen-settings`.

### How Telegram WebApp API is Used

In `miniapp/app.js` (lines 28–48):

```js
const tg = window.Telegram?.WebApp;
let telegramUser = null;

function initTelegram() {
  if (!tg) { console.warn('Telegram WebApp SDK not available'); return; }
  tg.ready();
  tg.expand();
  if (tg.colorScheme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
  telegramUser = tg.initDataUnsafe?.user || null;
  if (telegramUser) { renderUserAvatar(telegramUser); }
}
```

API usage summary:
- `tg.ready()` — signals to Telegram that the app is ready to be shown
- `tg.expand()` — expands the Mini App to full screen
- `tg.colorScheme` — used to apply dark/light theme via `data-theme` attribute
- `tg.initDataUnsafe?.user` — used to extract the Telegram user object (id, first_name, last_name, username, language_code)
- `tg.initData` — raw initData string sent to the backend in the `X-Telegram-Init-Data` header on every API request (function `getTelegramInitData()`)

In `frontend/index.html`, the Telegram SDK is loaded but `frontend/js/app.js` does not use `window.Telegram.WebApp` at all. That implementation has a demo-user switcher instead.

### Where Initialization Starts

In `miniapp/app.js`, the very last line of the file (line 1504):

```js
document.addEventListener('DOMContentLoaded', init);
```

The `init()` function (lines 1476–1502) is the application entry point.

In `frontend/js/app.js`, the equivalent is (line 567–572):

```js
window.addEventListener('DOMContentLoaded', async () => {
  const app = new App();
  window._app = app;
  await app.init();
  initAddDealModal(app);
});
```

---

## 2. FILE STRUCTURE OF THE MINI APP

### Primary Implementation: `miniapp/`

| File | Size | Purpose | Used? |
|---|---|---|---|
| `miniapp/index.html` | 599 lines | Main HTML entry point. Contains the auth screen (`#auth-screen`) and the full main app (`#app-main`) including all tab panels. The Telegram SDK script tag and `app.js` link are here. | ✅ Active — served at `/miniapp` |
| `miniapp/app.js` | 3092 lines | Monolithic JavaScript file containing all application logic: Telegram init, auth flow, settings loading, deal form, billing form, expenses form, deal editing, deal modal, settings management, journal, reports, dashboard, receivables, month-close, utilities. | ✅ Active — sole JS file for the miniapp |
| `miniapp/styles.css` | 1743 lines | Global stylesheet. Covers layout, components (cards, forms, fields, buttons, modals, toasts, tabs, sub-nav), deal cards, billing, expenses, journal, dashboard/receivables, month-close, auth screen, dark theme via `[data-theme="dark"]`. | ✅ Active |

### Prototype Implementation: `frontend/`

| File | Size | Purpose | Used? |
|---|---|---|---|
| `frontend/index.html` | 121 lines | HTML entry point for the prototype. Four screens (deals, journal, analytics, settings). Loads `permissions.js`, `api.js`, `app.js`. Telegram SDK tag present. | ⚠️ Not served by backend — standalone prototype |
| `frontend/js/permissions.js` | 131 lines | Frontend permissions matrix. Defines `ROLES`, `ROLE_LABELS`, `PERMISSION_MATRIX` (4 roles: admin, sales, accounting, viewer), and the `Permissions` class with `applyFormRestrictions()`. Exports to `window.Permissions`, `window.ROLES`, `window.ROLE_LABELS`. | ⚠️ Used only by `frontend/js/app.js` |
| `frontend/js/api.js` | 66 lines | `ApiClient` class wrapping `fetch`. Methods: `getMe()`, `getDemoUsers()`, `getDeals()`, `getDeal(id)`, `createDeal(data)`, `updateDeal(id, data)`, `deleteDeal(id)`, `getJournal()`, `createJournalEntry(data)`, `getAnalyticsSummary()`, `getAnalyticsByMonth()`. Uses `X-User-Id` header. Base URL hardcoded to `http://localhost:3000`. Exports to `window.ApiClient`. | ⚠️ Used only by `frontend/js/app.js` |
| `frontend/js/app.js` | 572 lines | Prototype app logic: `App`, `DealsScreen`, `JournalScreen`, `AnalyticsScreen`, `SettingsScreen` classes. Demo-user selector. No Telegram WebApp integration. | ⚠️ Prototype only |
| `frontend/css/styles.css` | (not measured) | Prototype stylesheet | ⚠️ Prototype only |

### Other Static Files

| File | Purpose | Used? |
|---|---|---|
| `static/index.html` | ~38 KB HTML file. Contents not fully read; appears to be another standalone frontend variant. | ⚠️ Not served by the backend at a known mount point — likely unused or legacy |

### Backend Files (referenced by Mini App)

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI app. Mounts `miniapp/` at `/miniapp`. Registers all routers. |
| `backend/routers/auth.py` | Auth endpoints: `POST /auth/miniapp-login`, `POST /auth/role-login`, `POST /auth/validate`, `GET /auth/role` |
| `backend/routers/settings.py` | `GET /settings/enriched`, `GET /settings/clients`, `GET /settings/managers`, `GET /settings/directions`, `GET /settings/statuses`, `POST`/`DELETE` CRUD variants |
| `backend/routers/deals_sql.py` | `POST /deals/create`, `GET /deals`, `GET /deals/{deal_id}`, `PATCH /deals/update/{deal_id}` — SQL-function based |
| `backend/routers/billing_sql.py` | `GET /billing/v2/search`, `POST /billing/v2/upsert`, `POST /billing/v2/payment/mark` |
| `backend/routers/expenses_sql.py` | `POST /expenses/v2/create`, `GET /expenses/v2` |
| `backend/routers/billing.py` | Legacy `POST /billing/{warehouse}`, `GET /billing/search` |
| `backend/routers/expenses.py` | Legacy `POST /expenses`, `GET /expenses` |
| `backend/routers/reports.py` | `GET /reports/{type}` endpoints for CSV/XLSX download |
| `backend/routers/journal.py` | `GET /journal` |
| `backend/routers/dashboard.py` | `GET /dashboard/summary` |
| `backend/routers/receivables.py` | `GET /receivables` |
| `backend/routers/month_close.py` | `POST /month/archive`, `POST /month/cleanup`, `POST /month/close`, `GET /month/archive-batches` |
| `backend/services/miniapp_auth_service.py` | Core login logic: role password validation, `upsert_app_user()` SQL call, manager auto-binding |
| `backend/services/settings_service.py` | Settings data provider; `GET /settings/enriched` returns `{id, name}` objects |
| `backend/services/db_exec.py` | SQL execution helpers: `call_sql_function`, `call_sql_function_one`, `read_sql_view` |

### Node.js / JavaScript Backend (Legacy)

| File | Purpose | Used? |
|---|---|---|
| `backend/server.js` | Express.js server (Node.js) | ⚠️ Legacy — Python FastAPI backend is the active backend |
| `backend/data/store.js` | In-memory data store (Node.js) | ⚠️ Legacy |
| `backend/middleware/auth.js` | Node.js auth middleware | ⚠️ Legacy |
| `backend/permissions/index.js` | Node.js permissions matrix | ⚠️ Legacy |
| `backend/routes/analytics.js` | Node.js analytics routes | ⚠️ Legacy |
| `backend/routes/deals.js` | Node.js deals routes | ⚠️ Legacy |
| `backend/routes/journal.js` | Node.js journal routes | ⚠️ Legacy |
| `backend/package.json` | Node.js package manifest | ⚠️ Legacy |

---

## 3. ENTRY POINTS AND INITIALIZATION FLOW

### `miniapp/` — Primary Implementation

#### Step 1: HTML loads, Telegram SDK is fetched

`miniapp/index.html` line 9:
```html
<script src="https://telegram.org/js/telegram-web-app.js"></script>
```
This is in `<head>` with no `defer` or `async`, so it blocks HTML parsing until downloaded and executed. `window.Telegram.WebApp` is available by the time `app.js` runs.

#### Step 2: `app.js` is parsed and executed

`miniapp/index.html` line 597:
```html
<script src="app.js"></script>
```
At parse time, the following top-level statements execute immediately:

1. `const API_BASE = (function () { ... })()` — resolves the backend URL (IIFE, lines 10–18)
2. Three billing input mode constants defined (lines 21–23)
3. `const tg = window.Telegram?.WebApp` — captures Telegram SDK (line 28)
4. `let telegramUser = null` — global user object (line 29)
5. `const state = { ... }` — global app state (lines 115–122)
6. `const EXPENSE_CATS_L2 = { ... }` — static category mapping (lines 2223–2228)
7. `const COMMENT_REQUIRED_L2 = new Set(...)` — static set (line 2230)
8. `let _bulkRowIndex = 0` — counter for bulk expense rows (line 2333)
9. Various function declarations (`initTelegram`, `apiFetch`, `loadSettings`, etc.)

#### Step 3: `DOMContentLoaded` fires → `init()` is called

```js
document.addEventListener('DOMContentLoaded', init);  // line 1504
```

#### Step 4: `init()` execution (lines 1476–1502)

```js
async function init() {
  initTelegram();        // Telegram SDK setup
  initTabs();            // tab button click handlers
  initDealForm();        // deal form event listeners
  initMyDeals();         // my-deals filter/refresh handlers
  initModal();           // deal detail modal close handlers
  initMonthClose();      // month-close button handlers

  const savedRole = localStorage.getItem('user_role');

  if (savedRole && telegramUser && !localStorage.getItem('telegram_id')) {
    localStorage.removeItem('user_role');
    localStorage.removeItem('user_role_label');
    showAuthScreen();
    return;
  }

  if (savedRole) {
    await enterApp(savedRole);  // skip auth if role is already stored
  } else {
    showAuthScreen();           // show auth screen
  }
}
```

#### Step 5a: Auth Screen (first-time or cleared session)

`showAuthScreen()` (line 1574) shows `#auth-screen` and hides `#app-main`, then calls `initAuthHandlers()`.

`initAuthHandlers()` (lines 1583–1675) sets up:
- Click handlers on `.role-btn` buttons (one per role: manager, operations_director, accounting, admin)
- Back button handler
- Submit button and Enter key handler for `doLogin()`

`doLogin()` (lines 1619–1668) selects one of two paths:

**Path A — Telegram context available** (`telegramUser` is set):
```js
const result = await apiFetch('/auth/miniapp-login', {
  method: 'POST',
  body: JSON.stringify({
    telegram_id: telegramUser.id,
    full_name: ...,
    username: telegramUser.username || null,
    selected_role: selectedRole,
    password,
  }),
});
role = result.role;
localStorage.setItem('telegram_id', String(telegramUser.id));
```

**Path B — No Telegram context** (dev/testing):
```js
const result = await apiFetch('/auth/role-login', {
  method: 'POST',
  body: JSON.stringify({ role: selectedRole, password }),
});
role = result.role;
```

On success: `localStorage.setItem('user_role', role)` and `localStorage.setItem('user_role_label', roleLabel)`, then `enterApp(role)`.

#### Step 5b: Returning session

If `savedRole` found in `localStorage`, `enterApp(savedRole)` is called directly — no password prompt.

#### Step 6: `enterApp(role)` (lines 1677–1720)

```js
async function enterApp(role) {
  // Show app, hide auth
  authScreen.style.display = 'none';
  appMain.style.display = 'block';

  setEl('header-role-label', roleLabel);
  buildTabs(role);             // build role-specific tab navigation
  await loadSettings();        // FIRST DATA LOAD: GET /settings/enriched
  switchMainTab(firstTab.id);  // show first permitted tab

  // Setup logout, user info display, and all feature handlers:
  initBillingForm();
  initExpensesForm();
  initDealEdit();
  initReportsHandlers();
  initJournalHandlers();
  initSubnav();
  initSettingsManagement();
  initDashboardHandlers();
  initReceivablesHandlers();
}
```

#### `API_BASE` — where it is defined and used

Defined as an IIFE at the top of `miniapp/app.js` (lines 10–18):
```js
const API_BASE = (function () {
  // 1. Check meta tag: <meta name="api-base" content="...">
  const meta = document.querySelector('meta[name="api-base"]');
  if (meta && meta.content) return meta.content.replace(/\/$/, '');
  // 2. Check global config: window.APP_CONFIG.apiBase
  if (window.APP_CONFIG && window.APP_CONFIG.apiBase) return window.APP_CONFIG.apiBase;
  // 3. Default: same origin
  return window.location.origin;
})();
```

In `miniapp/index.html` the meta tag is:
```html
<meta name="api-base" content="" />
```
The `content` is empty, so resolution falls through to `window.APP_CONFIG.apiBase` (not defined in any loaded script) and finally to `window.location.origin`.

`API_BASE` is used in:
- `apiFetch(path, options)` (line 92): `` `${API_BASE}${path}` ``
- `downloadReport(reportType, fmt)` (line 621): `` `${API_BASE}${url}` `` via a direct `fetch()` call (not `apiFetch`)

#### First Data Load

Triggered inside `enterApp(role)` by `await loadSettings()` (line 1691), which calls:
```js
const enriched = await apiFetch('/settings/enriched');
state.enrichedSettings = enriched;
state.settings = enriched;
populateSelects(enriched);
updateSettingsStats(enriched);
```

`GET /settings/enriched` returns `{id, name}` objects for: `statuses`, `business_directions`, `clients`, `managers`, `vat_types`, `sources`, `warehouses`, `expense_categories`.

On success, all `<select>` dropdowns across the entire app are populated via `fillSelect()` and `populateSelectFromObjects()`.

On failure, a fallback with hardcoded string arrays is used:
```js
const fallback = {
  statuses: ['Новая', 'В работе', 'Завершена', 'Отменена', 'Приостановлена'],
  business_directions: ['ФФ МСК', 'ФФ НСК', 'ФФ ЕКБ', 'ТЛК', 'УТЛ'],
  clients: [], managers: [], vat_types: ['С НДС', 'Без НДС'],
  sources: ['Рекомендация', 'Сайт', 'Реклама', 'Холодный звонок', 'Другое'],
  warehouses: [], expense_categories: [],
};
```
When fallback is used, `state.enrichedSettings` is `null`, and the app falls back to legacy text-based API calls instead of SQL-function endpoints.

#### `apiFetch` — How Headers Are Attached

Every API call goes through `apiFetch(path, options)` (lines 72–110), which automatically attaches:
- `Content-Type: application/json`
- `X-Telegram-Init-Data: <tg.initData>` (if available)
- `X-Telegram-Id: <telegramUser.id>` or `localStorage.getItem('telegram_id')` (if available and not already set in options)
- `X-User-Role: <localStorage.getItem('user_role')>` (if available and not already set in options)

### `frontend/` — Prototype Implementation

#### Step 1: Telegram SDK loads (but is not used)

`frontend/index.html` line 9: Telegram SDK is loaded, but `frontend/js/app.js` does not reference `window.Telegram.WebApp`.

#### Step 2: Scripts load in order

Lines 116–118 of `frontend/index.html`:
```html
<script src="js/permissions.js"></script>
<script src="js/api.js"></script>
<script src="js/app.js"></script>
```

`permissions.js` runs first (exports `Permissions`, `ROLES`, `ROLE_LABELS` to `window`).
`api.js` runs second (exports `ApiClient` to `window`).
`app.js` runs third.

#### Step 3: `DOMContentLoaded` fires

```js
window.addEventListener('DOMContentLoaded', async () => {
  const app = new App();
  window._app = app;
  await app.init();
  initAddDealModal(app);
});
```

#### Step 4: `App.init()` (lines 60–73)

```js
async init() {
  showLoading(true);
  try {
    await this._setupUser();   // fetch demo users, set default user
    this._buildTabs();         // build tab navigation
    this._initScreens();       // create DealsScreen, JournalScreen, etc.
    this._navigate('deals');   // show deals screen and load data
  } catch (e) {
    showToast('Ошибка инициализации: ' + e.message, 'error');
  } finally {
    showLoading(false);
  }
}
```

`_setupUser()` calls `GET /api/demo-users` and `GET /api/me`. The `ApiClient` base URL is hardcoded to `http://localhost:3000` (line 52 of `frontend/js/app.js`).

#### miniapp initData Sent to Backend

- **`miniapp/app.js`**: Yes. `tg?.initData` is sent in the `X-Telegram-Init-Data` header on every request via `apiFetch`.
- **`frontend/js/app.js`**: No. initData is never sent. Auth uses `X-User-Id` header only.

---

## 4. STATE MANAGEMENT

### Global State Object

`miniapp/app.js` defines a single global plain object `state` (lines 115–122):

```js
const state = {
  settings: null,          // cached result of GET /settings/enriched (also used as fallback)
  enrichedSettings: null,  // same data as settings, but null when fallback was used
  deals: [],               // array of deal objects loaded from GET /deals
  currentTab: 'new-deal',  // currently active tab/sub-tab ID (updated by switchTab)
  isSubmitting: false,     // deal form submit lock
  isLoadingDeals: false,   // deals-list load lock
};
```

### Additional Global Variables (Scattered State)

| Variable | Type | Location | Purpose |
|---|---|---|---|
| `tg` | `const` | Line 28 | `window.Telegram?.WebApp` — Telegram SDK handle |
| `telegramUser` | `let` | Line 29 | `tg.initDataUnsafe?.user` — Telegram user object (id, first_name, last_name, username, language_code) |
| `_bulkRowIndex` | `let` | Line 2333 | Counter for generating unique IDs for bulk expense rows |
| `EXPENSE_CATS_L2` | `const` | Lines 2223–2228 | Static map of expense category L1→L2 sub-categories. Can be overwritten by settings loaded from DB (line 251). |
| `COMMENT_REQUIRED_L2` | `const` | Line 2230 | `Set` of L2 category values that require a mandatory comment |

### `localStorage` Persistence

| Key | Value | Set By | Read By |
|---|---|---|---|
| `user_role` | Role string (`manager`, `operations_director`, `accounting`, `admin`) | `doLogin()`, line 1658 | `init()` (line 1485), `apiFetch()` (line 89), `loadJournal()`, `loadReceivables()`, `downloadReport()`, `saveBilling()` |
| `user_role_label` | Human-readable role name | `doLogin()`, line 1659 | `enterApp()` (line 1684) |
| `telegram_id` | Telegram user ID as string | `doLogin()` path A (line 1646) | `apiFetch()` (line 83), `init()` (line 1490) |

### State Initialization

- `state.settings` and `state.enrichedSettings` are set in `loadSettings()` — called from `enterApp()` on every login.
- `state.deals` is set in `loadDeals()` — called lazily when the "my deals" sub-nav is first opened or the refresh button is clicked. It is also reset to `[]` after a successful deal creation (line 478).
- `state.currentTab` is set by `switchTab()` (line 156) on every tab switch.
- `state.isSubmitting` and `state.isLoadingDeals` are set as boolean guards in `setSubmitting()` and `loadDeals()` respectively.

### State Updates

| Field | Updated In | Trigger |
|---|---|---|
| `state.settings` | `loadSettings()` | `enterApp()`, i.e., on every login |
| `state.enrichedSettings` | `loadSettings()` | Same; set to `null` when fallback is used |
| `state.deals` | `loadDeals()` | Manual refresh, lazy load on "my deals" tab open, reset to `[]` after deal creation |
| `state.currentTab` | `switchTab()` | Tab button click |
| `state.isSubmitting` | `setSubmitting(true/false)` | Deal form submit start/end |
| `state.isLoadingDeals` | `loadDeals()` | Deals load start/end |

### State in `frontend/js/app.js` (Prototype)

The prototype uses **class-instance state** rather than a global object:

```js
class App {
  constructor() {
    this.api = new ApiClient('http://localhost:3000');
    this.perms = null;       // Permissions instance
    this.currentUser = null; // user object from GET /api/me
    this.activeTab = 'deals';
    this.screens = {};       // { deals: DealsScreen, journal: JournalScreen, ... }
  }
}

class DealsScreen {
  constructor(app) {
    this.app = app;
    this.deals = [];         // loaded deal array
    this.selectedDeal = null;
  }
}
```

State in the prototype is **object-instance scoped** and not centralised. Each screen class manages its own data.

### State-Related Observations

1. **Dual settings fields**: `state.settings` and `state.enrichedSettings` always hold the same value when the DB is reachable (`populateSelects` uses `state.settings`), but `state.enrichedSettings` is set to `null` in the fallback path (line 201) while `state.settings` holds the fallback object. Code that needs to decide between SQL-function and legacy API endpoints checks `state.enrichedSettings` (lines 1975–1976, 2097–2099). If `state.enrichedSettings` is `null`, legacy endpoints are used.

2. **`state.deals` used as cache**: `openDealModal(dealId)` (line 926) first tries `state.deals.find(d => d.deal_id === dealId)` before making an API call. The cache is only populated after `loadDeals()` is explicitly triggered — it is **not** populated by the deal list on the "Edit Deal" sub-panel, which issues its own `GET /deals` call independently.

3. **Filter mismatch bug**: `renderDeals()` (line 686) filters by `deal.client` (string), but when enriched settings are active, `filter-client` dropdown values are numeric IDs (not client name strings). The filter condition `deal.client !== clientFilter` will never match since `deal.client` is a name string and `clientFilter` is an ID string. This is a latent bug when enriched settings are loaded.

4. **No state reset on logout**: The `logout-btn` handler (line 1699–1703) removes `localStorage` keys and calls `location.reload()`. This resets the in-memory `state` object via a full page reload, which is correct but relies on reload rather than explicit reset.

5. **`_bulkRowIndex` never resets on form clear**: `clearForm()` does not reset `_bulkRowIndex`. However, after a successful bulk save `_bulkRowIndex = 0` is called (line 2466).

6. **`EXPENSE_CATS_L2` mutation**: The constant `EXPENSE_CATS_L2` is mutated at line 251 when enriched settings are loaded:
   ```js
   EXPENSE_CATS_L2[key] = (cat.sub_categories || []).map(sc => sc.name);
   ```
   This is declared `const` but its properties can still be overwritten at runtime (JavaScript `const` only prevents reassignment, not mutation). If the settings endpoint returns categories, `EXPENSE_CATS_L2` silently switches from the hardcoded values to the DB values. The hardcoded values act as a fallback only until the first successful `loadSettings()`.
