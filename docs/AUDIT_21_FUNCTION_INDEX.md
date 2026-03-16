# Аудит 21 — Полный индекс функций фронтенда

> **READ-ONLY audit. No code was modified.**
> Scope: `miniapp/app.js` (3 092 lines) and `frontend/js/app.js` + `frontend/js/api.js` + `frontend/js/permissions.js`.

---

## Условные обозначения

| Символ | Значение |
|--------|----------|
| `[M]`  | `miniapp/app.js` |
| `[F]`  | `frontend/js/app.js` |
| `[A]`  | `frontend/js/api.js` |
| `[P]`  | `frontend/js/permissions.js` |

---

## A. frontend/js/api.js — Класс `ApiClient`

### `constructor(baseUrl)` · `[A]` · line 8
- **Purpose:** Initialises the API client; stores `baseUrl`, sets `userId = null`.
- **Called from:** `[F]` `App.constructor` (once at startup via `new ApiClient('/api')`).
- **Calls:** nothing.

### `setUser(userId)` · `[A]` · line 13
- **Purpose:** Sets the `userId` value that will be injected as `X-User-Id` header on every request.
- **Called from:** `[F]` `App._setActiveUser()`.
- **Calls:** nothing.

### `_headers()` · `[A]` · line 17
- **Purpose:** Returns a plain header object `{Content-Type, X-User-Id}`.
- **Called from:** `[A]` `_request()`.
- **Calls:** nothing.

### `_request(method, path, body)` · `[A]` · line 23
- **Purpose:** Core `fetch` wrapper. Throws an `Error` when `response.ok` is false.
- **Called from:** All public methods of `ApiClient` (`getMe`, `getDemoUsers`, `getDeals`, etc.).
- **Calls:** `_headers()`, `fetch()`.

### `getMe()` · `[A]` · line 44
- **Purpose:** GET `/api/me` — fetch the current user record.
- **Called from:** `[F]` `App._setActiveUser()`.
- **Calls:** `_request()`.

### `getDemoUsers()` · `[A]` · line 45
- **Purpose:** GET `/api/demo-users` — fetch the demo user list for the selector.
- **Called from:** `[F]` `App._setupUser()`.
- **Calls:** `_request()`.

### `getDeals()` · `[A]` · line 49
- **Purpose:** GET `/api/deals` — list all deals for the active user.
- **Called from:** `[F]` `DealsScreen.load()`.
- **Calls:** `_request()`.

### `getDeal(id)` · `[A]` · line 50
- **Purpose:** GET `/api/deals/{id}` — fetch a single deal.
- **Called from:** `[F]` `DealsScreen._openDeal()`.
- **Calls:** `_request()`.

### `createDeal(data)` · `[A]` · line 51
- **Purpose:** POST `/api/deals` — create a new deal.
- **Called from:** `[F]` `#form-add-deal` submit handler.
- **Calls:** `_request()`.

### `updateDeal(id, data)` · `[A]` · line 52
- **Purpose:** PATCH `/api/deals/{id}` — update an existing deal.
- **Called from:** `[F]` `DealsScreen._saveDeal()`.
- **Calls:** `_request()`.

### `deleteDeal(id)` · `[A]` · line 53
- **Purpose:** DELETE `/api/deals/{id}` — delete a deal after user confirmation.
- **Called from:** `[F]` `DealsScreen._deleteDeal()`.
- **Calls:** `_request()`.

### `getJournal()` · `[A]` · line 57
- **Purpose:** GET `/api/journal` — fetch journal entries.
- **Called from:** `[F]` `JournalScreen.load()`.
- **Calls:** `_request()`.

### `createJournalEntry(data)` · `[A]` · line 58
- **Purpose:** POST `/api/journal` — write a journal entry.
- **Called from:** not used by any visible call-site in the frontend (reserved for future use).
- **Calls:** `_request()`.

### `getAnalyticsSummary()` · `[A]` · line 62
- **Purpose:** GET `/api/analytics/summary` — fetch KPI summary.
- **Called from:** `[F]` `AnalyticsScreen.load()` (parallel with `getAnalyticsByMonth`).
- **Calls:** `_request()`.

### `getAnalyticsByMonth()` · `[A]` · line 63
- **Purpose:** GET `/api/analytics/deals-by-month` — monthly deal breakdown.
- **Called from:** `[F]` `AnalyticsScreen.load()` (parallel with `getAnalyticsSummary`).
- **Calls:** `_request()`.

---

## B. frontend/js/permissions.js — Класс `Permissions`

### `Permissions.constructor(role)` · `[P]` · line ~20
- **Purpose:** Stores `role`; maps to the `PERMISSION_MATRIX` constant.
- **Called from:** `[F]` `App._setActiveUser()`.
- **Calls:** nothing.

### `has(permission)` · `[P]`
- **Purpose:** Returns `true` if the matrix entry for the current role has the named permission set to `true`.
- **Called from:** all convenience methods below.
- **Calls:** nothing.

### `canViewAllDeals()`, `canEditSalesFields()`, `canEditAccountingFields()`, `canViewJournal()`, `canViewAnalytics()`, `canCreateDeals()`, `canDeleteDeals()`, `canViewSettings()` · `[P]`
- **Purpose:** Convenience wrappers that delegate to `has()`.
- **Called from:** `[F]` `App._buildTabs()`, `DealsScreen.load()`, `DealsScreen._renderModal()`.
- **Calls:** `has()`.

### `applyFormRestrictions(formEl)` · `[P]`
- **Purpose:** Iterates over `[data-perm]` elements inside a form; sets `readonly`/`disabled` and adds `field--readonly` class for fields the current role may not edit.
- **Called from:** `[F]` `DealsScreen._renderModal()`.
- **Calls:** `has()`.

---

## C. frontend/js/app.js — Классы `App`, `DealsScreen`, `JournalScreen`, `AnalyticsScreen`, `SettingsScreen`

### `App.constructor()` · `[F]` · line ~50
- **Purpose:** Creates `ApiClient`, initialises `perms = null`, `currentUser = null`, sets up `activeTab` and `screens` map.
- **Called from:** global `DOMContentLoaded` handler (line 567).
- **Calls:** `new ApiClient('/api')`.

### `App.init()` · `[F]` · line ~60
- **Purpose:** Entry point — sets up user selector, builds tabs, navigates to deals.
- **Called from:** `App.constructor()`.
- **Calls:** `_setupUser()`, `_buildTabs()`, `_navigate('deals')`.

### `App._setupUser()` · `[F]` · line ~80
- **Purpose:** Fetches demo users via `api.getDemoUsers()`, renders `#demo-user-select`, calls `_setActiveUser` with the first user.
- **Called from:** `App.init()`.
- **Calls:** `api.getDemoUsers()`, `_setActiveUser()`.

### `App._setActiveUser(userId)` · `[F]` · line ~100
- **Purpose:** Sets `api.userId`, fetches `/api/me`, creates `Permissions(role)`, updates header UI.
- **Called from:** `App._setupUser()`, `#demo-user-select` change handler.
- **Calls:** `api.setUser()`, `api.getMe()`, `new Permissions()`.

### `App._buildTabs()` · `[F]` · line ~120
- **Purpose:** Creates tab buttons based on `perms.canViewJournal()`, `canViewAnalytics()`, `canViewSettings()`.
- **Called from:** `App.init()`.
- **Calls:** `perms.canViewJournal()`, `perms.canViewAnalytics()`, `perms.canViewSettings()`.

### `App._navigate(tabId)` · `[F]` · line ~140
- **Purpose:** Shows the correct screen panel; calls `screens[tabId].load()`.
- **Called from:** `.tab-btn` click handler, `App.init()`.
- **Calls:** `screens[tabId].load()`.

### `DealsScreen.load()` · `[F]` · line ~200
- **Purpose:** Fetches all deals, renders deal cards; controls visibility of `#btn-add-deal`.
- **Called from:** `App._navigate('deals')`.
- **Calls:** `api.getDeals()`, `_render()`, `perms.canCreateDeals()`.

### `DealsScreen._render(deals)` · `[F]` · line ~215
- **Purpose:** Builds deal card list; attaches click listeners for `_openDeal()`.
- **Called from:** `DealsScreen.load()`.
- **Calls:** `_openDeal()`.

### `DealsScreen._openDeal(id)` · `[F]` · line ~230
- **Purpose:** Fetches deal by id, calls `_renderModal(deal)`, shows `#deal-modal`.
- **Called from:** `.deal-card` click handler.
- **Calls:** `api.getDeal()`, `_renderModal()`, `perms.applyFormRestrictions()`.

### `DealsScreen._renderModal(deal)` · `[F]` · line ~250
- **Purpose:** Builds the deal edit modal with two fieldsets (sales / accounting); applies permission restrictions.
- **Called from:** `DealsScreen._openDeal()`.
- **Calls:** `perms.applyFormRestrictions()`, `perms.canDeleteDeals()`.

### `DealsScreen._saveDeal(id, formEl)` · `[F]` · line ~320
- **Purpose:** Collects `[data-field]` elements (skips disabled), PATCHes `/api/deals/{id}`.
- **Called from:** `#btn-save-deal` click handler.
- **Calls:** `api.updateDeal()`.

### `DealsScreen._deleteDeal(id)` · `[F]` · line ~350
- **Purpose:** Shows `window.confirm`; if confirmed calls DELETE via `api.deleteDeal()`.
- **Called from:** `#btn-delete-deal` click handler.
- **Calls:** `api.deleteDeal()`.

### `JournalScreen.load()` · `[F]` · line ~400
- **Purpose:** Fetches journal entries, renders a list with date, type, description, amount.
- **Called from:** `App._navigate('journal')`.
- **Calls:** `api.getJournal()`.

### `AnalyticsScreen.load()` · `[F]` · line ~440
- **Purpose:** Parallel fetches of summary + by-month data, renders three sections (Deals, Finance, Monthly).
- **Called from:** `App._navigate('analytics')`.
- **Calls:** `api.getAnalyticsSummary()`, `api.getAnalyticsByMonth()`.

### `SettingsScreen.load()` · `[F]` · line ~500
- **Purpose:** Renders user permission table.
- **Called from:** `App._navigate('settings')`.
- **Calls:** nothing asynchronous (renders static data).

---

## D. miniapp/app.js — Полный индекс функций

> Lines refer to `miniapp/app.js`.

### CONFIG & INIT

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 1 | `initTelegram()` | 31 | Initialises Telegram WebApp SDK; sets `telegramUser`; applies dark theme; calls `renderUserAvatar()`. | `init()` | `renderUserAvatar()`, `tg.ready()`, `tg.expand()` |
| 2 | `renderUserAvatar(user)` | 51 | Populates `#user-avatar` with initials from Telegram user profile. | `initTelegram()` | `getInitials()`, `setEl()` |
| 3 | `getInitials(first, last)` | 59 | Returns 1–2 uppercase initials from first/last name. | `renderUserAvatar()` | nothing |
| 4 | `getTelegramInitData()` | 65 | Returns `tg.initData` string (or empty string). | `apiFetch()` | nothing |
| 5 | `apiFetch(path, options)` | 72 | Universal `fetch` wrapper; injects `X-Telegram-Init-Data`, `X-Telegram-Id`, `X-User-Role` headers; throws on HTTP errors. | Every async function that calls the API | `getTelegramInitData()`, `fetch()` |
| 6 | `init()` | 1476 | Application entry point on `DOMContentLoaded`; checks saved auth state; starts auth flow or calls `enterApp()`. | `document.DOMContentLoaded` | `initTelegram()`, `initTabs()`, `initDealForm()`, `initMyDeals()`, `initModal()`, `initMonthClose()`, `enterApp()`, `showAuthScreen()` |

### TABS & NAVIGATION

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 7 | `initTabs()` | 127 | Attaches click listeners to all `.tab-btn` elements (legacy tab system). | `init()` | `switchTab()` |
| 8 | `switchTab(tabId)` | 137 | Shows/hides `.tab-panel` by ID; triggers lazy-loads for `my-deals` and `settings-tab`. | `.tab-btn` click, `initDealForm()` | `loadDeals()`, `checkConnections()`, `renderUserInfoCard()` |
| 9 | `buildTabs(role)` | 1722 | Renders role-specific navigation buttons into `#main-tab-nav` from `ROLE_TABS`. | `enterApp()` | `switchMainTab()` |
| 10 | `switchMainTab(tabId)` | 1741 | Shows/hides `.tab-panel`; triggers side-effects per tab (dashboard load, receivables load, settings refresh). | `.tab-btn` click (main nav), `enterApp()`, `initSubnav()` | `checkConnections()`, `renderUserInfoCard()`, `loadClientsSettings()`, `loadManagersSettings()`, `loadDirectionsSettings()`, `loadStatusesSettings()`, `loadOwnerDashboard()`, `loadReceivables()` |
| 11 | `initSubnav()` | 1788 | Attaches click listeners to `.subnav-btn` elements inside the Finances tab; handles sub-panel switching. | `enterApp()` | `loadDeals()`, `loadDealsForEdit()`, `switchMainTab()` |
| 12 | `switchSubnav(subId)` | 904 | Switches active sub-panel within the Finances tab. | `initDealEdit()` (back button), `enterApp()` | nothing |

### SETTINGS & REFERENCE DATA

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 13 | `loadSettings()` | 173 | GETs `/settings/enriched`; caches in `state.enrichedSettings`; calls `populateSelects()` and `updateSettingsStats()`. Falls back to hardcoded defaults on error. | `enterApp()` | `apiFetch()`, `populateSelects()`, `updateSettingsStats()`, `showToast()` |
| 14 | `populateSelects(data)` | 208 | Distributes reference-data arrays to all `<select>` elements across every feature section. Handles `{id,name}` objects and plain strings. | `loadSettings()` | `fillSelect()` |
| 15 | `fillSelect(id, options, hasAll)` | 264 | Clears and repopulates a `<select>` by ID; handles `{id,name}` objects (value=id) and plain strings; restores prior selection. | `populateSelects()` | nothing |
| 16 | `populateSelectFromObjects(selectEl, items)` | 297 | Populates a `<select>` element (by reference, not ID) with `{id, name}` objects; uses `deal_name` as label fallback. | `loadDealsFiltered()`, `initDependentDealDropdowns()` | nothing |
| 17 | `loadDealsFiltered(dealSelectId, directionId, clientId)` | 315 | GETs `/deals?business_direction_id=X&client_id=Y`; populates the given deal `<select>`. | `initDependentDealDropdowns()` reload callback | `apiFetch()`, `populateSelectFromObjects()` |
| 18 | `initDependentDealDropdowns(dirSelectId, clientSelectId, dealSelectId)` | 343 | Wires direction + client `change` events to trigger `loadDealsFiltered()` for billing/expense deal selects. | `initBillingForm()`, `initExpensesForm()` | `loadDealsFiltered()`, `populateSelectFromObjects()` |
| 19 | `updateSettingsStats(data)` | 363 | Updates counter badges (`cnt-statuses`, `cnt-clients`, etc.) in the Settings tab. | `loadSettings()` | `setEl()` |

### DEAL FORM — New Deal

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 20 | `initDealForm()` | 373 | Binds all event listeners for the new-deal form: submit, clear, navigation buttons, live summary, VAT label, VAT calculation. | `init()` | `handleFormSubmit()`, `clearForm()`, `showForm()`, `switchTab()`, `updateSummary()`, `updateChargedLabel()` (inline), `updateDealVat()` (inline) |
| 21 | `updateSummary()` | 429 | Reads client, amount, status, manager values and updates `#deal-summary` live-preview card. | `change` events on `#client`, `#charged_with_vat`, `#status`, `#manager` | `getFieldValue()`, `formatCurrency()`, `setEl()` |
| 22 | `handleFormSubmit(e)` | 447 | Form submit handler: validates → collects SQL data → POSTs `/deals/create` → shows success screen or toast. Requires `state.enrichedSettings`. | `#deal-form` submit event | `validateForm()`, `collectFormDataSql()`, `setSubmitting()`, `apiFetch()`, `showSuccessScreen()`, `showToast()` |
| 23 | `validateForm()` | 487 | Checks 8 required fields; marks `field--error` classes; returns error array. | `handleFormSubmit()` | `getFieldValue()` |
| 24 | `collectFormData()` | 522 | Collects form data as **string/text** values (legacy, unused by current submit path). | not called in current submit flow | `getFieldValue()` |
| 25 | `collectFormDataSql()` | 560 | Collects form data as **integer IDs** for SQL-function endpoints (`/deals/create`). | `handleFormSubmit()` | `getFieldValue()` |
| 26 | `setSubmitting(isLoading)` | 594 | Toggles `#submit-btn` disabled state and shows/hides spinner. | `handleFormSubmit()` | nothing |
| 27 | `clearForm()` | 607 | Resets `#deal-form`, clears validation error states, hides summary card. | `#clear-btn` click, `showForm()` | `showToast()` |
| 28 | `showSuccessScreen(dealId)` | 625 | Hides form, shows `#success-screen` with deal ID. | `handleFormSubmit()` | `setEl()` |
| 29 | `showForm()` | 636 | Hides success screen, shows form, clears it. | `#new-deal-btn` click | `clearForm()` |

### MY DEALS — List & Filter

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 30 | `initMyDeals()` | 650 | Binds `#refresh-deals-btn` click and `#filter-status`, `#filter-client`, `#filter-month` change events. | `init()` | `loadDeals()`, `renderDeals()` |
| 31 | `loadDeals()` | 662 | GETs `/deals`; stores in `state.deals`; calls `renderDeals()`. Guards against concurrent calls. | `initMyDeals()`, `switchTab()`, `initSubnav()` | `apiFetch()`, `showDealsLoading()`, `clearDealsList()`, `renderDeals()`, `showToast()` |
| 32 | `renderDeals()` | 686 | Filters `state.deals` by status, client, month; renders cards into `#deals-list`. | `loadDeals()`, filter `change` events | `createDealCard()`, `clearDealsList()`, `showDealsEmpty()` |
| 33 | `createDealCard(deal)` | 716 | Creates a deal card DOM element; binds 👁 (openDealModal) and 📌 (copyToClipboard) action buttons; card click also opens modal. | `renderDeals()` | `formatCurrency()`, `formatDate()`, `escHtml()`, `openDealModal()`, `copyToClipboard()` |
| 34 | `showDealsLoading(show)` | 771 | Shows/hides `#deals-loading` spinner. | `loadDeals()` | nothing |
| 35 | `showDealsEmpty(show)` | 776 | Shows/hides `#deals-empty` placeholder. | `renderDeals()`, `clearDealsList()` | nothing |
| 36 | `clearDealsList()` | 781 | Clears `#deals-list` innerHTML and hides empty state. | `loadDeals()`, `renderDeals()` | `showDealsEmpty()` |

### DEAL EDITING

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 37 | `initDealEdit()` | 790 | Binds `#edit-deal-select` change, `#edit-deal-save-btn` click, `#edit-deal-back-btn` click. | `enterApp()` | `onEditDealSelected()`, `saveEditedDeal()`, `switchSubnav()` |
| 38 | `loadDealsForEdit()` | 807 | GETs `/deals`; populates `#edit-deal-select` dropdown with deal_id + client + status labels. | `initSubnav()` (edit-deal-sub switch) | `apiFetch()`, `showToast()` |
| 39 | `onEditDealSelected(dealId)` | 825 | GETs `/deals/{dealId}`; pre-fills edit form fields (`edit-status`, expense fields, bonus, comment). | `#edit-deal-select` change | `apiFetch()`, `showToast()` |
| 40 | `saveEditedDeal()` | 857 | Collects only changed fields; PATCHes `/deals/update/{dealId}`. | `#edit-deal-save-btn` click | `apiFetch()`, `showToast()` |
| 41 | `switchSubnav(subId)` | 904 | Activates a sub-panel within `#tab-finances`. | `initDealEdit()` (back btn), `initSubnav()` | nothing |

### DEAL MODAL — Detail View

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 42 | `openDealModal(dealId)` | 918 | Looks up deal in `state.deals` (or fetches `/deals/{dealId}`); calls `renderDealDetail()`; shows `#deal-modal`. | `.deal-card` click, `[data-action="view"]` button click | `apiFetch()`, `renderDealDetail()`, `showToast()` |
| 43 | `closeDealModal()` | 945 | Hides `#deal-modal`; clears `#modal-body`. | `#modal-close-btn` click, overlay click, `Escape` keydown | nothing |
| 44 | `renderDealDetail(deal)` | 951 | Renders 6 sections (Основное, Финансы, Маржинальность, Сроки, Расходы, Дополнительно) into `#modal-body`. | `openDealModal()` | `escHtml()`, `formatCurrency()`, `formatDate()` |
| 45 | `initModal()` | 1036 | Binds `#modal-close-btn` click, overlay click, and `document keydown` (Escape) to close modal. | `init()` | `closeDealModal()` |

### SETTINGS — Status & Connectivity

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 46 | `checkConnections()` | 1056 | Checks Telegram SDK availability and calls `/health` + `/settings`; updates status dots. | `switchTab('settings-tab')`, `switchMainTab('settings-tab')` | `apiFetch()`, `setConnectionStatus()` |
| 47 | `setConnectionStatus(key, ok, text)` | 1090 | Updates `#dot-{key}` and `#status-{key}` elements with ok/error CSS classes. | `checkConnections()` | nothing |
| 48 | `renderUserInfoCard()` | 1105 | Renders Telegram user fields (ID, name, username, language) into `#user-info-content`. | `switchTab('settings-tab')`, `switchMainTab('settings-tab')`, `enterApp()` | `escHtml()` |

### TOAST & UTILITIES

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 49 | `showToast(message, type, duration)` | 1132 | Creates a toast notification in `#toast-container`; auto-removes after `duration` ms. | Used throughout | nothing |
| 50 | `getFieldValue(id)` | 1161 | Returns trimmed value of an `<input>` or `<select>` by ID. | `collectFormData()`, `collectFormDataSql()`, `updateSummary()`, `validateForm()` | nothing |
| 51 | `setEl(id, value)` | 1166 | Sets `textContent` of element by ID. | `renderUserAvatar()`, `updateSummary()`, `updateSettingsStats()`, `showSuccessScreen()`, `enterApp()` | nothing |
| 52 | `escHtml(str)` | 1171 | HTML-escapes a value (`&`, `<`, `>`, `"`, `'`). | `createDealCard()`, `renderDealDetail()`, `renderUserInfoCard()`, `showToast()`, `updateUserInfoWithRole()` | nothing |
| 53 | `formatCurrency(value)` | 1181 | Formats a number as Russian RUB using `Intl.NumberFormat`. | `updateSummary()`, `createDealCard()`, `renderDealDetail()`, `loadOwnerDashboard()` | nothing |
| 54 | `formatDate(dateStr)` | 1191 | Parses a date string and formats as `DD.MM.YYYY` using `Intl.DateTimeFormat ru-RU`. | `createDealCard()`, `renderDealDetail()` | nothing |
| 55 | `copyToClipboard(text)` | 1206 | Copies text to clipboard via `navigator.clipboard` (with `execCommand` fallback); shows toast. | `[data-action="copy"]` button, `createDealCard()` | `showToast()` |

### SETTINGS MANAGEMENT — CRUD UI

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 56 | `initSettingsManagement()` | 1231 | Binds Add/Refresh buttons for clients, managers, directions, statuses. | `enterApp()` | `addClient()`, `loadClientsSettings()`, `addManager()`, `loadManagersSettings()`, `addDirection()`, `loadDirectionsSettings()`, `addStatus()`, `loadStatusesSettings()` |
| 57 | `loadClientsSettings()` | 1264 | GETs `/settings/clients`; renders list into settings panel. | `#refresh-clients-btn`, `initSettingsManagement()`, `switchMainTab('settings-tab')` | `apiFetch()`, `renderRefList()`, `showToast()` |
| 58 | `addClient()` | 1283 | Reads `#new-client-name`, POSTs `/settings/clients`; reloads list. | `#add-client-btn` click | `apiFetch()`, `loadClientsSettings()`, `showToast()` |
| 59 | `deleteClient(clientId, clientName)` | 1297 | Confirms then DELETEs `/settings/clients/{clientId}`; reloads list. | Delete button in client list | `apiFetch()`, `loadClientsSettings()`, `showToast()` |
| 60 | `loadManagersSettings()` | 1309 | GETs `/settings/managers`; renders list. | `#refresh-managers-btn`, `switchMainTab('settings-tab')` | `apiFetch()`, `renderRefList()`, `showToast()` |
| 61 | `addManager()` | 1326 | Reads `#new-manager-name`, POSTs `/settings/managers`; reloads list. | `#add-manager-btn` click | `apiFetch()`, `loadManagersSettings()`, `showToast()` |
| 62 | `deleteManager(managerId, managerName)` | 1342 | Confirms then DELETEs `/settings/managers/{managerId}`; reloads list. | Delete button in manager list | `apiFetch()`, `loadManagersSettings()`, `showToast()` |
| 63 | `loadDirectionsSettings()` | 1354 | GETs `/settings/directions`; renders plain-string list. | `#refresh-directions-btn`, `switchMainTab('settings-tab')` | `apiFetch()`, `renderRefList()`, `showToast()` |
| 64 | `addDirection()` | 1370 | Reads `#new-direction-name`, POSTs `/settings/directions`; reloads list. | `#add-direction-btn` click | `apiFetch()`, `loadDirectionsSettings()`, `showToast()` |
| 65 | `deleteDirection(direction)` | 1384 | Confirms then DELETEs `/settings/directions/{direction}`; reloads list. | Delete button in direction list | `apiFetch()`, `loadDirectionsSettings()`, `showToast()` |
| 66 | `loadStatusesSettings()` | 1396 | GETs `/settings/statuses`; renders plain-string list. | `#refresh-statuses-btn`, `switchMainTab('settings-tab')` | `apiFetch()`, `renderRefList()`, `showToast()` |
| 67 | `addStatus()` | 1413 | Reads `#new-status-name`, POSTs `/settings/statuses`; reloads list. | `#add-status-btn` click | `apiFetch()`, `loadStatusesSettings()`, `showToast()` |
| 68 | `deleteStatus(status)` | 1427 | Confirms then DELETEs `/settings/statuses/{status}`; reloads list. | Delete button in status list | `apiFetch()`, `loadStatusesSettings()`, `showToast()` |
| 69 | `renderRefList(listId, emptyId, items, itemMapper)` | 1439 | Generic list renderer: maps items using `itemMapper`, adds delete buttons. | `loadClientsSettings()`, `loadManagersSettings()`, `loadDirectionsSettings()`, `loadStatusesSettings()` | nothing |

### AUTH SYSTEM

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 70 | `showAuthScreen()` | 1574 | Shows `#auth-screen`; hides `#app-main`; calls `initAuthHandlers()`. | `init()` | `initAuthHandlers()` |
| 71 | `initAuthHandlers()` | 1583 | Binds role buttons (`.role-btn`), back button, submit button, and Enter key on password input. | `showAuthScreen()` | `doLogin()` |
| 72 | `doLogin()` | 1619 | Reads selected role and password; POSTs `/auth/miniapp-login` (Telegram) or `/auth/role-login` (fallback); stores credentials; calls `enterApp()`. | `#auth-submit-btn` click, `#auth-password` Enter key | `apiFetch()`, `enterApp()`, `showToast()` |
| 73 | `enterApp(role)` | 1677 | Shows main app; calls `buildTabs()`, `loadSettings()`; shows first tab; wires logout; initialises all feature handlers. | `doLogin()`, `init()` (if saved role) | `buildTabs()`, `loadSettings()`, `switchMainTab()`, `renderUserInfoCard()`, `updateUserInfoWithRole()`, `initBillingForm()`, `initExpensesForm()`, `initDealEdit()`, `initReportsHandlers()`, `initJournalHandlers()`, `initSubnav()`, `initSettingsManagement()`, `initDashboardHandlers()`, `initReceivablesHandlers()` |
| 74 | `buildTabs(role)` | 1722 | See §TABS above. | `enterApp()` | `switchMainTab()` |
| 75 | `updateUserInfoWithRole(role, roleLabel)` | 1777 | Prepends a "Роль" row to `#user-info-content`. | `enterApp()` | `escHtml()` |

### BILLING FORM

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 76 | `calcBillingTotals(prefix)` | 1824 | Computes `totalNoPen` and `totalWithPen` for old-format billing (p1 / p2). | `input` events on billing amount fields | nothing |
| 77 | `calcBillingTotalsV2()` | 1838 | Computes VAT-aware totals (no-penalty and with-penalty) for new billing format (bv2). | `input` events on bv2 fields | nothing |
| 78 | `updateBillingInputLabels()` | 1878 | Updates unit-label text next to shipments/storage/returns fields based on current format. | `switchBillingFormat()` | nothing |
| 79 | `switchBillingFormat(fmt)` | 1901 | Shows/hides `bv2`, `p1`, `p2` form sections based on selected billing format. | `#billing-format` change | `updateBillingInputLabels()`, `calcBillingTotalsV2()`, `calcBillingTotals()` |
| 80 | `initBillingForm()` | 1914 | Wires all billing form events; initialises dependent dropdowns for payment and billing sections. | `enterApp()` | `switchBillingFormat()`, `calcBillingTotals()`, `calcBillingTotalsV2()`, `loadBillingEntry()`, `saveBilling()`, `markPayment()`, `initDependentDealDropdowns()` |
| 81 | `loadBillingEntry()` | 1957 | Reads warehouse, client, month, period; GETs `/billing/v2/search` (enriched) or `/billing/search` (legacy); calls `preloadBillingForm()`. | `#billing-load-btn` click | `apiFetch()`, `preloadBillingForm()`, `showToast()` |
| 82 | `preloadBillingForm(data)` | 2019 | Populates billing form fields from a loaded billing record. Handles both new-format (bv2) and old-format (p1/p2) field sets. | `loadBillingEntry()` | nothing |
| 83 | `clearBillingForm()` | 2060 | Resets all billing form fields. | not called directly (available but unused in current visible code) | nothing |
| 84 | `saveBilling()` | 2076 | Collects billing form data; POSTs to `/billing/v2/upsert` (enriched) or `/billing/{warehouse}` (legacy). | `#billing-save-btn` click | `apiFetch()`, `showToast()` |
| 85 | `markPayment()` | 2195 | Reads deal_id and amount; POSTs `/billing/v2/payment/mark`; shows remaining_amount toast. | `#payment-mark-btn` click | `apiFetch()`, `showToast()` |

### EXPENSES FORM

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 86 | `updateExpenseCat2(cat1Val, cat2SelectId, cat2FieldId)` | 2232 | Repopulates cat2 `<select>` based on selected cat1 using `EXPENSE_CATS_L2` map. | `#expense-cat1` change | nothing |
| 87 | `updateExpenseCommentVisibility(cat1Val, cat2Val, commentFieldId, requiredMarkId)` | 2248 | Shows/hides the expense comment field depending on `COMMENT_REQUIRED_L2` set membership. | `#expense-cat1` change, `#expense-cat2` change | nothing |
| 88 | `initExpensesForm()` | 2261 | Wires cat1/cat2 change events, amount/VAT input events, and save/load/bulk buttons. | `enterApp()` | `updateExpenseCat2()`, `updateExpenseCommentVisibility()`, `updateCalc()` (inline), `saveExpense()`, `loadExpenses()`, `addBulkRow()`, `saveBulkExpenses()`, `initDependentDealDropdowns()` |
| 89 | `addBulkRow()` | 2335 | Appends a new row to `#bulk-expenses-form` with cat1, cat2, comment, amount, VAT, deal selects; wires its change events. | `#bulk-add-row-btn` click | `updateExpenseCat2()`, `updateExpenseCommentVisibility()` |
| 90 | `removeBulkRow(idx)` | 2407 | Removes `#bulk-row-{idx}` from the DOM. | Delete button inside bulk row | nothing |
| 91 | `saveBulkExpenses()` | 2417 | Validates all bulk rows; POSTs `/expenses/v2/create` for each row; shows count toast. | `#bulk-save-btn` click | `apiFetch()`, `showToast()` |
| 92 | `saveExpense()` | 2472 | Validates cat1, amount, comment; computes `amount_without_vat`; POSTs `/expenses/v2/create`. | `#expense-save-btn` click | `apiFetch()`, `showToast()` |
| 93 | `loadExpenses()` | 2531 | GETs `/expenses/v2`; renders each entry into `#expenses-list`. | `#load-expenses-btn` click | `apiFetch()`, `showToast()`, `formatCurrency()`, `escHtml()` |

### REPORTS

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 94 | `initReportsHandlers()` | 2584 | Attaches click listeners to all `[data-report]` buttons. | `enterApp()` | `downloadReport()` |
| 95 | `downloadReport(reportType, fmt)` | 2594 | Constructs report URL based on type/format/filters; triggers file download via `window.open`. | `[data-report]` button click | `apiFetch()` (for billing-by-client), `getFieldValue()` |

### JOURNAL

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 96 | `initJournalHandlers()` | 2643 | Binds `#load-journal-btn` click. | `enterApp()` | `loadJournal()` |
| 97 | `loadJournal()` | 2648 | GETs `/journal?limit=50`; renders entries (action, timestamp, user, entity, deal_id, details) into `#journal-list`. | `#load-journal-btn` click | `apiFetch()`, `escHtml()`, `showToast()` |

### DASHBOARD

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 98 | `initDashboardHandlers()` | 2696 | Binds `#load-dashboard-btn` click and `#apply-dashboard-filter-btn` click. | `enterApp()` | `loadOwnerDashboard()` |
| 99 | `loadOwnerDashboard()` | 2704 | GETs `/dashboard/summary?month=X`; aggregates rows into KPI cards and warehouse/client breakdowns. | `#load-dashboard-btn`, `#apply-dashboard-filter-btn`, `switchMainTab('tab-dashboard')` | `apiFetch()`, `formatCurrency()`, `escHtml()`, `showToast()` |

### RECEIVABLES

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 100 | `initReceivablesHandlers()` | 2807 | Binds load button, apply-filter button, and `[data-report]` buttons in the receivables section. | `enterApp()` | `loadReceivables()`, `downloadReport()` |
| 101 | `loadReceivables()` | 2822 | GETs `/receivables?month=X`; renders status KPIs and breakdowns by client/warehouse/month. | `#load-receivables-btn`, `#apply-receivables-filter-btn`, `switchMainTab('tab-receivables')` | `apiFetch()`, `formatCurrency()`, `escHtml()`, `showToast()` |

### MONTH CLOSE

| # | Function | Line | Purpose | Called from | Calls |
|---|----------|------|---------|-------------|-------|
| 102 | `initMonthClose()` | 2916 | Binds dry-run, archive, cleanup, close, and load-batches buttons. | `init()` | `runMonthArchive()`, `runMonthCleanup()`, `runMonthClose()`, `loadArchiveBatches()` |
| 103 | `_getMonthCloseParams()` | 2941 | Reads `#month-close-year` and `#month-close-month` inputs; returns `{year, month}`. | `runMonthArchive()`, `runMonthCleanup()`, `runMonthClose()` | nothing |
| 104 | `_showMonthCloseResult(resultEl, data, error)` | 2949 | Populates a result element with operation outcome or error text. | `runMonthArchive()`, `runMonthCleanup()`, `runMonthClose()`, `loadArchiveBatches()` | `escHtml()` |
| 105 | `runMonthArchive(dryRun)` | 2990 | POSTs `/month/archive` with `{year, month, dry_run}`; shows result. | `#month-close-dry-run-btn`, `#month-close-archive-btn` | `_getMonthCloseParams()`, `apiFetch()`, `_showMonthCloseResult()`, `showToast()` |
| 106 | `runMonthCleanup()` | 3017 | POSTs `/month/cleanup` with `{year, month}`; shows result. | `#month-close-cleanup-btn` | `_getMonthCloseParams()`, `apiFetch()`, `_showMonthCloseResult()`, `showToast()` |
| 107 | `runMonthClose()` | 3042 | POSTs `/month/close` with `{year, month}`; shows result. | `#month-close-close-btn` | `_getMonthCloseParams()`, `apiFetch()`, `_showMonthCloseResult()`, `showToast()` |
| 108 | `loadArchiveBatches()` | 3068 | GETs `/month/batches`; renders batch records. | `#month-close-load-batches-btn` | `apiFetch()`, `_showMonthCloseResult()`, `showToast()` |

---

*Generated: 2026-03-16 · Audit section 21 of 23*
