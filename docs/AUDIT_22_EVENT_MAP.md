# Аудит 22 — Полная карта событий UI

> **READ-ONLY audit. No code was modified.**
> Scope: `miniapp/app.js` (primary), `frontend/js/app.js` (legacy web frontend).
> All selectors prefixed `#` are element IDs; `.` are class selectors; `document` / `window` are global targets.

---

## Условные обозначения

| Символ | Значение |
|--------|----------|
| `[M]`  | `miniapp/app.js` |
| `[F]`  | `frontend/js/app.js` |
| ✅     | Standard / expected flow |
| ⚠️     | Potential risk or side-effect |

---

## 1. Startup events (DOMContentLoaded / window load)

| # | Target | Event | Handler | Result |
|---|--------|-------|---------|--------|
| 1 | `document` | `DOMContentLoaded` | `init()` `[M:1504]` | Calls `initTelegram()`, `initTabs()`, `initDealForm()`, `initMyDeals()`, `initModal()`, `initMonthClose()`; checks localStorage for `user_role`; routes to `enterApp()` or `showAuthScreen()`. |
| 2 | `window` | `DOMContentLoaded` | `async () => new App()` `[F:567]` | Creates the `App` instance for the legacy web frontend; triggers `app.init()` which sets up demo user selector, tabs, and loads the Deals screen. |

---

## 2. Authentication events

| # | Selector / Element | Event | Handler | Result |
|---|-------------------|-------|---------|--------|
| 3 | `.role-btn` (each) | `click` | anonymous `[M:1588]` | Highlights selected role button; shows the password input step (`#auth-step-password`); stores selected role in a local variable. |
| 4 | `#auth-back-btn` | `click` | anonymous `[M:1609]` | Returns to role-selection step (`#auth-step-role`); hides password step. |
| 5 | `#auth-submit-btn` | `click` | `doLogin()` `[M:1671]` | Reads role + password; POSTs `/auth/miniapp-login` (Telegram) or `/auth/role-login` (fallback); on success stores `user_role`, `user_role_label`, `telegram_id` in localStorage and calls `enterApp(role)`. On failure shows `#auth-error`. |
| 6 | `#auth-password` | `keydown` (Enter) | `doLogin()` `[M:1672]` | Same as clicking `#auth-submit-btn` — triggers login when user presses Enter in the password field. |
| 7 | `#logout-btn` | `click` | anonymous `[M:1699]` | Removes `user_role`, `user_role_label`, `telegram_id` from localStorage; calls `location.reload()`. |
| 8 | `#demo-user-select` | `change` | `_setActiveUser(sel.value)` `[F:110]` | Sets the active API user; fetches `/api/me`; creates new `Permissions` object; rebuilds tab visibility. |

---

## 3. Tab switch events (Main navigation)

| # | Selector / Element | Event | Handler | Result |
|---|-------------------|-------|---------|--------|
| 9 | `.tab-btn` (legacy, `[F]`) | `click` | `app._navigate(tabId)` `[F:148]` | Activates selected tab panel; calls `screen[tabId].load()` to fetch data for the screen. |
| 10 | `.tab-btn` (legacy, `[M]`) | `click` | `switchTab(tabId)` `[M:130]` | Updates active state on tab buttons; shows matching `.tab-panel`; if `my-deals` tab and cache empty → calls `loadDeals()`; if `settings-tab` → calls `checkConnections()` + `renderUserInfoCard()`. |
| 11 | `.tab-btn` (main nav, injected by `buildTabs`) | `click` | `switchMainTab(btn.dataset.tab)` `[M:1737]` | Role-aware tab switch; shows correct `.tab-panel`; triggers side-effects: `settings-tab` refreshes all CRUD lists + connections; `tab-dashboard` calls `loadOwnerDashboard()`; `tab-receivables` calls `loadReceivables()`. |

---

## 4. Sub-navigation events (Finances tab)

| # | Selector / Element | Event | Handler | Result |
|---|-------------------|-------|---------|--------|
| 12 | `.subnav-btn` (each) | `click` | anonymous `[M:1790]` | Toggles active `.subnav-btn`; shows/hides `new-deal-sub`, `my-deals-sub`, `edit-deal-sub`; if switching to `my-deals-sub` and cache empty → `loadDeals()`; if `edit-deal-sub` → `loadDealsForEdit()`. |
| 13 | `#view-deals-btn` (in success screen) | `click` | anonymous `[M:1813]` | Calls `switchMainTab('tab-finances')`; programmatically clicks `.subnav-btn[data-sub="my-deals-sub"]`. |
| 14 | `#view-deals-btn` (in deal form) | `click` | `() => switchTab('my-deals')` `[M:382]` | Switches legacy tab to `my-deals`; triggers `loadDeals()` if cache empty. |
| 15 | `#edit-deal-back-btn` | `click` | `() => switchSubnav('my-deals-sub')` `[M:801]` | Returns to the My Deals sub-panel from the edit-deal sub-panel. |

---

## 5. Deal form — New Deal

| # | Selector / Element | Event | Handler | Result |
|---|-------------------|-------|---------|--------|
| 16 | `#deal-form` | `submit` | `handleFormSubmit(e)` `[M:379]` | Prevents default; validates required fields; collects SQL IDs via `collectFormDataSql()`; POSTs `/deals/create`; on success shows success screen + toast; on failure shows error toast. ⚠️ Aborts if `state.enrichedSettings` is null. |
| 17 | `#clear-btn` | `click` | `clearForm()` `[M:380]` | Resets form; clears validation error states; hides `#deal-summary`. |
| 18 | `#new-deal-btn` | `click` | `showForm()` `[M:381]` | Hides success screen; shows deal form; calls `clearForm()`. |
| 19 | `#client` | `change` | `updateSummary()` `[M:387]` | Updates live-preview `#deal-summary` card with current client / amount / status / manager values. |
| 20 | `#charged_with_vat` | `change` | `updateSummary()` `[M:387]` | Same as above. |
| 21 | `#status` | `change` | `updateSummary()` `[M:387]` | Same as above. |
| 22 | `#manager` | `change` | `updateSummary()` `[M:387]` | Same as above. |
| 23 | `#vat_type` | `change` | `updateChargedLabel()` (inline) `[M:404]` | Updates the label text of the "Начислено" field based on whether VAT is included or not. |
| 24 | `#charged_with_vat` | `input` | `updateDealVat()` (inline) `[M:425]` | Recalculates and displays `vatAmount` and `amountNoVat` in `#deal-vat-calc` row. |
| 25 | `#vat_rate` | `input` | `updateDealVat()` (inline) `[M:426]` | Same as above. |
| 26 | `#submit-btn` (inside `#deal-form`) | — | — | No direct listener; triggered by form `submit` event on `#deal-form`. |

---

## 6. My Deals — list & filters

| # | Selector / Element | Event | Handler | Result |
|---|-------------------|-------|---------|--------|
| 27 | `#refresh-deals-btn` | `click` | `() => loadDeals()` `[M:653]` | Clears `state.deals` cache; GETs `/deals`; re-renders deal cards. |
| 28 | `#filter-status` | `change` | `renderDeals()` `[M:658]` | Client-side filter: re-renders `state.deals` filtered by selected status. |
| 29 | `#filter-client` | `change` | `renderDeals()` `[M:658]` | Client-side filter: re-renders `state.deals` filtered by selected client. ⚠️ Filters by `deal.client` (string name), not numeric ID — mismatch risk if enriched data returns IDs. |
| 30 | `#filter-month` | `change` | `renderDeals()` `[M:658]` | Client-side filter: matches `project_start_date.startsWith(YYYY-MM)`. |
| 31 | `.deal-card` (dynamically created) | `click` | `() => openDealModal(deal.deal_id)` `[M:766]` | Opens deal detail modal for the clicked deal. |
| 32 | `[data-action="view"]` button (inside card) | `click` | `() => openDealModal(id)` `[M:757-762]` | Same as card click but prevents event from bubbling to card. |
| 33 | `[data-action="copy"]` button (inside card) | `click` | `() => copyToClipboard(id)` `[M:757-763]` | Copies deal_id to clipboard; shows success toast. Prevents bubbling. |

---

## 7. Deal editing

| # | Selector / Element | Event | Handler | Result |
|---|-------------------|-------|---------|--------|
| 34 | `#edit-deal-select` | `change` | `onEditDealSelected(value)` `[M:793]` | GETs `/deals/{dealId}`; populates edit form fields. |
| 35 | `#edit-deal-save-btn` | `click` | `saveEditedDeal()` `[M:797]` | Collects only changed fields; PATCHes `/deals/update/{dealId}`; shows success/error toast. |

---

## 8. Deal modal — detail view

| # | Selector / Element | Event | Handler | Result |
|---|-------------------|-------|---------|--------|
| 36 | `#modal-close-btn` | `click` | `closeDealModal()` `[M:1040]` | Hides `#deal-modal`; clears `#modal-body`. |
| 37 | `#deal-modal` (overlay background) | `click` | `(e) => { if (e.target === modal) closeDealModal() }` `[M:1042]` | Closes modal only when clicking the backdrop (not modal content). |
| 38 | `document` | `keydown` (Escape) | `closeDealModal()` `[M:1048]` | Keyboard shortcut to close the deal modal. |

---

## 9. Legacy web frontend — Deal modal (`[F]`)

| # | Selector / Element | Event | Handler | Result |
|---|-------------------|-------|---------|--------|
| 39 | `.deal-card` (dynamically created) | `click` | `this._openDeal(card.dataset.id)` `[F:227]` | Fetches deal; renders edit modal with permission restrictions. |
| 40 | `#btn-close-modal` | `click` | anonymous `[F:336]` | Hides `#deal-modal`. |
| 41 | `#btn-delete-deal` | `click` | `this._deleteDeal(id)` `[F:341]` | Confirms via `window.confirm`; DELETEs `/api/deals/{id}`; closes modal; reloads deals. |
| 42 | `#btn-save-deal` | `click` | `this._saveDeal(id, formEl)` `[F:346]` | Collects `[data-field]` elements (skips disabled); PATCHes `/api/deals/{id}`; closes modal; reloads deals. |
| 43 | `#btn-add-deal` | `click` | anonymous `[F:542]` | Removes `hidden` class from `#add-deal-modal`. |
| 44 | `#btn-cancel-add-deal` | `click` | anonymous `[F:543]` | Adds `hidden` class to `#add-deal-modal`. |
| 45 | `#form-add-deal` | `submit` | async handler `[F:546]` | Creates deal via `api.createDeal()`; shows success screen; hides modal. |

---

## 10. Billing form events

| # | Selector / Element | Event | Handler | Result |
|---|-------------------|-------|---------|--------|
| 46 | `#billing-format` | `change` | `switchBillingFormat(value)` `[M:1918]` | Shows/hides `bv2`, `p1`, `p2` sections; updates input labels; recalculates totals. |
| 47 | `#p1-shipments`, `#p1-storage`, `#p1-returns`, `#p1-extra`, `#p1-penalties` | `input` | `() => calcBillingTotals('p1')` `[M:1925]` | Recalculates p1 `totalNoPen` and `totalWithPen`; updates display fields. |
| 48 | `#p2-shipments`, `#p2-storage`, `#p2-returns`, `#p2-extra`, `#p2-penalties` | `input` | `() => calcBillingTotals('p2')` `[M:1929]` | Same for p2. |
| 49 | `#bv2-shipments-with-vat`, `#bv2-storage-with-vat`, `#bv2-returns-pickup-with-vat`, `#bv2-additional-services-with-vat`, `#bv2-penalties` | `input` | `calcBillingTotalsV2()` `[M:1938]` | Recalculates VAT-aware totals for new format. |
| 50 | `#billing-load-btn` | `click` | `loadBillingEntry()` `[M:1943]` | GETs `/billing/v2/search` or `/billing/search`; populates form via `preloadBillingForm()`. |
| 51 | `#billing-save-btn` | `click` | `saveBilling()` `[M:1947]` | POSTs `/billing/v2/upsert` (enriched) or `/billing/{warehouse}` (legacy). |
| 52 | `#payment-mark-btn` | `click` | `markPayment()` `[M:1954]` | Reads deal_id + amount; POSTs `/billing/v2/payment/mark`; shows remaining amount toast. |
| 53 | `#payment-direction-select` | `change` | reload callback (via `initDependentDealDropdowns`) `[M:1914]` | GETs `/deals?business_direction_id=X` to refresh the payment deal dropdown. |
| 54 | `#payment-client-select` | `change` | reload callback (via `initDependentDealDropdowns`) `[M:1914]` | GETs `/deals?client_id=Y` to refresh the payment deal dropdown. |

---

## 11. Expenses form events

| # | Selector / Element | Event | Handler | Result |
|---|-------------------|-------|---------|--------|
| 55 | `#expense-cat1` | `change` | `updateExpenseCat2()` + `updateExpenseCommentVisibility()` `[M:2268]` | Repopulates `#expense-cat2` from `EXPENSE_CATS_L2`; shows/hides comment field. |
| 56 | `#expense-cat2` | `change` | `updateExpenseCommentVisibility()` `[M:2277]` | Shows/hides comment field based on `COMMENT_REQUIRED_L2`. |
| 57 | `#expense-amount` | `input` | `updateCalc()` (inline) `[M:2310]` | Recomputes `amount_without_vat` and `vat_amount` display fields. |
| 58 | `#expense-vat-rate` | `input` | `updateCalc()` (inline) `[M:2311]` | Same. |
| 59 | `#expense-vat` | `input` | `updateCalc()` (inline) `[M:2312]` | Same. |
| 60 | `#expense-save-btn` | `click` | `saveExpense()` `[M:2319]` | Validates; POSTs `/expenses/v2/create`. |
| 61 | `#load-expenses-btn` | `click` | `loadExpenses()` `[M:2323]` | GETs `/expenses/v2`; renders expense list. |
| 62 | `#bulk-add-row-btn` | `click` | `addBulkRow()` `[M:2327]` | Adds a new dynamic bulk-expense row to the form. |
| 63 | `#bulk-save-btn` | `click` | `saveBulkExpenses()` `[M:2330]` | Validates all rows; POSTs `/expenses/v2/create` for each; shows count toast. |
| 64 | `#expense-direction-select` | `change` | reload callback (via `initDependentDealDropdowns`) `[M:2261]` | Refreshes expense deal dropdown filtered by direction. |
| 65 | `#expense-client-select` | `change` | reload callback (via `initDependentDealDropdowns`) `[M:2261]` | Refreshes expense deal dropdown filtered by client. |
| 66 | Cat1 select inside each bulk row | `change` | `updateExpenseCat2()` + `updateExpenseCommentVisibility()` `[M:2390]` | Same cat2/comment logic as the single-expense form, applied to the dynamic row. |
| 67 | Cat2 select inside each bulk row | `change` | `updateExpenseCommentVisibility()` `[M:2398]` | Same comment visibility logic for the dynamic row. |
| 68 | Delete button inside each bulk row | `click` | `removeBulkRow(idx)` `[M:2407 region]` | Removes the row from the DOM. |

---

## 12. Reports events

| # | Selector / Element | Event | Handler | Result |
|---|-------------------|-------|---------|--------|
| 69 | `[data-report]` buttons (Reports tab) | `click` | `downloadReport(type, fmt)` `[M:2586]` | Builds report URL; opens via `window.open` for download. For `billing-by-client` reads `#report-client-select` value. |
| 70 | `[data-report]` buttons (Receivables tab) | `click` | `downloadReport(type, fmt)` `[M:2816]` | Same mechanism wired separately for receivables section. |

---

## 13. Journal events

| # | Selector / Element | Event | Handler | Result |
|---|-------------------|-------|---------|--------|
| 71 | `#load-journal-btn` | `click` | `loadJournal()` `[M:2645]` | GETs `/journal?limit=50`; renders entries into `#journal-list`. |

---

## 14. Dashboard events

| # | Selector / Element | Event | Handler | Result |
|---|-------------------|-------|---------|--------|
| 72 | `#load-dashboard-btn` | `click` | `loadOwnerDashboard()` `[M:2698]` | GETs `/dashboard/summary?month=X`; renders KPI cards and breakdowns. |
| 73 | `#apply-dashboard-filter-btn` | `click` | `loadOwnerDashboard()` `[M:2701]` | Same — re-fetches with current month filter value. |

---

## 15. Receivables events

| # | Selector / Element | Event | Handler | Result |
|---|-------------------|-------|---------|--------|
| 74 | `#load-receivables-btn` | `click` | `loadReceivables()` `[M:2809]` | GETs `/receivables?month=X`; renders status KPIs and breakdowns. |
| 75 | `#apply-receivables-filter-btn` | `click` | `loadReceivables()` `[M:2812]` | Same — re-fetches with current month filter value. |

---

## 16. Settings CRUD events

| # | Selector / Element | Event | Handler | Result |
|---|-------------------|-------|---------|--------|
| 76 | `#add-client-btn` | `click` | `addClient()` `[M:1235]` | Reads `#new-client-name`; POSTs `/settings/clients`; reloads list. |
| 77 | `#refresh-clients-btn` | `click` | `loadClientsSettings()` `[M:1236]` | GETs `/settings/clients`; re-renders client management list. |
| 78 | Delete button (per client row) | `click` | `deleteClient(clientId, name)` `[M:renderRefList]` | Confirms; DELETEs `/settings/clients/{id}`; reloads list. |
| 79 | `#add-manager-btn` | `click` | `addManager()` `[M:1241]` | Reads `#new-manager-name`; POSTs `/settings/managers`; reloads list. |
| 80 | `#refresh-managers-btn` | `click` | `loadManagersSettings()` `[M:1242]` | GETs `/settings/managers`; re-renders manager management list. |
| 81 | Delete button (per manager row) | `click` | `deleteManager(managerId, name)` `[M:renderRefList]` | Confirms; DELETEs `/settings/managers/{id}`; reloads list. |
| 82 | `#add-direction-btn` | `click` | `addDirection()` `[M:1247]` | Reads `#new-direction-name`; POSTs `/settings/directions`; reloads list. |
| 83 | `#refresh-directions-btn` | `click` | `loadDirectionsSettings()` `[M:1248]` | GETs `/settings/directions`; re-renders direction management list. |
| 84 | Delete button (per direction row) | `click` | `deleteDirection(direction)` `[M:renderRefList]` | Confirms; DELETEs `/settings/directions/{direction}`; reloads list. |
| 85 | `#add-status-btn` | `click` | `addStatus()` `[M:1253]` | Reads `#new-status-name`; POSTs `/settings/statuses`; reloads list. |
| 86 | `#refresh-statuses-btn` | `click` | `loadStatusesSettings()` `[M:1254]` | GETs `/settings/statuses`; re-renders status management list. |
| 87 | Delete button (per status row) | `click` | `deleteStatus(status)` `[M:renderRefList]` | Confirms; DELETEs `/settings/statuses/{status}`; reloads list. |

---

## 17. Month Close events

| # | Selector / Element | Event | Handler | Result |
|---|-------------------|-------|---------|--------|
| 88 | `#month-close-dry-run-btn` | `click` | `() => runMonthArchive(true)` `[M:2922]` | POSTs `/month/archive` with `{dry_run: true}`; shows preview result. |
| 89 | `#month-close-archive-btn` | `click` | `() => runMonthArchive(false)` `[M:2926]` | POSTs `/month/archive` with `{dry_run: false}`; performs actual archive. |
| 90 | `#month-close-cleanup-btn` | `click` | `runMonthCleanup()` `[M:2930]` | POSTs `/month/cleanup`; shows result. |
| 91 | `#month-close-close-btn` | `click` | `runMonthClose()` `[M:2934]` | POSTs `/month/close`; shows result. |
| 92 | `#month-close-load-batches-btn` | `click` | `loadArchiveBatches()` `[M:2938]` | GETs `/month/batches`; renders batch records. |

---

## Summary by event type

### Click events (total: 69)
Auth (5) · Tab navigation (4) · Sub-navigation (4) · Deal form (3) · My Deals (3) · Deal editing (2) · Deal modal (2) · Legacy frontend (6) · Billing (4) · Expenses (5) · Reports (2) · Journal (1) · Dashboard (2) · Receivables (2) · Settings CRUD (12) · Month Close (5) · Misc (7)

### Submit events (total: 2)
`#deal-form` `[M]` · `#form-add-deal` `[F]`

### Change events (total: 17)
`#demo-user-select` (user switch) · `#billing-format` · `#expense-cat1`, `#expense-cat2` (+ bulk row variants) · `#filter-status`, `#filter-client`, `#filter-month` · `#edit-deal-select` · `#vat_type` · `#client`, `#charged_with_vat`, `#status`, `#manager` (live summary) · `#payment-direction-select`, `#payment-client-select`, `#expense-direction-select`, `#expense-client-select` (dependent dropdowns)

### Input events (total: 10)
`#charged_with_vat` (VAT calc) · `#vat_rate` (VAT calc) · 5× billing amount fields (p1/p2/bv2 totals) · `#expense-amount`, `#expense-vat-rate`, `#expense-vat` (expense calc)

### Keydown events (total: 2)
`document` keydown Escape → `closeDealModal()` · `#auth-password` keydown Enter → `doLogin()`

### Startup events (total: 2)
`document` DOMContentLoaded → `init()` `[M]` · `window` DOMContentLoaded → `new App()` `[F]`

---

*Generated: 2026-03-16 · Audit section 22 of 23*
