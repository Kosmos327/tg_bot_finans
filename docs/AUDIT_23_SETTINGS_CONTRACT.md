# Аудит 23 — Аудит контракта настроек (Settings Contract Audit)

> **READ-ONLY audit. No code was modified.**
> This section maps every field the frontend **expects** from the backend against what the backend **actually returns**, identifies inconsistencies, and explains which mismatches are most likely to cause empty dropdowns or broken forms.

---

## Scope

| Component | File |
|-----------|------|
| Primary mini-app frontend | `miniapp/app.js` |
| Legacy web frontend | `frontend/js/app.js` |
| Settings service (enriched) | `backend/services/settings_service.py` (lines 526–608) |
| Settings router | `backend/routers/settings.py` |

---

## 1. The `/settings/enriched` endpoint — the single source of truth

### What the backend returns

Source: `settings_service.load_enriched_settings_pg()` (lines 526–608):

```json
{
  "statuses":            [{"id": int, "name": str}, ...],
  "business_directions": [{"id": int, "name": str}, ...],
  "vat_types":           [{"id": int, "name": str}, ...],
  "sources":             [{"id": int, "name": str}, ...],
  "clients":             [{"id": int, "name": str}, ...],
  "managers":            [{"id": int, "name": str}, ...],
  "warehouses":          [{"id": int, "name": str, "code": str}, ...],
  "expense_categories":  [
    {
      "id": int, "name": str,
      "sub_categories": [{"id": int, "name": str}, ...]
    }, ...
  ]
}
```

### What `populateSelects()` expects (lines 208–255)

| Dropdown element(s) | Field accessed | Expected type | Backend supplies | Match? |
|--------------------|----------------|---------------|-----------------|--------|
| `#status`, `#edit-status`, `#filter-status` | `data.statuses` | `{id, name}[]` | ✅ `{id, name}[]` | ✅ |
| `#business_direction`, `#payment-direction-select`, `#expense-direction-select` | `data.business_directions` | `{id, name}[]` | ✅ `{id, name}[]` | ✅ |
| `#client`, `#billing-client-select`, `#filter-client`, `#payment-client-select`, `#expense-client-select`, `#report-client-select` | `data.clients` | `{id, name}[]` | ✅ `{id, name}[]` | ✅ |
| `#manager` | `data.managers` | `{id, name}[]` | ✅ `{id, name}[]` | ✅ |
| `#vat_type` | `data.vat_types` | `{id, name}[]` | ✅ `{id, name}[]` (hardcoded fallback if DB empty) | ✅ |
| `#source` | `data.sources` | `{id, name}[]` | ✅ `{id, name}[]` | ✅ |
| `#billing-warehouse` | `data.warehouses` | `{id, name, code}[]` | ✅ `{id, name, code}[]` | ✅ |
| `#expense-cat1` | `data.expense_categories` | `{id, name, sub_categories}[]` | ✅ `{id, name, sub_categories: [{id, name}]}[]` | ✅ |

**Overall `/settings/enriched` contract: fully aligned.**

---

## 2. `/settings/clients` CRUD endpoint

### What the backend returns

Source: `clients_service._client_to_dict()`:

```json
{"client_id": str, "client_name": str, "created_at": "YYYY-MM-DD HH:MM:SS"}
```

### What the frontend reads in `loadClientsSettings()` (lines 1264–1296)

```javascript
items.map(item => ({
  id: item.client_id,
  name: item.client_name,
  onDelete: () => deleteClient(item.client_id, item.client_name)
}))
```

| Field expected | Field returned | Match? | Notes |
|---------------|----------------|--------|-------|
| `item.client_id` | `client_id` (string) | ✅ | Backend converts `int` to `str` via `str(client.id)` |
| `item.client_name` | `client_name` | ✅ | |
| `item.created_at` | `created_at` | ✅ (unused) | Not displayed in the UI list |

**Contract: fully aligned.**

---

## 3. `/settings/managers` CRUD endpoint

### What the backend returns

Source: `managers_service._manager_to_dict()`:

```json
{"manager_id": str, "manager_name": str, "role": str, "created_at": "YYYY-MM-DD HH:MM:SS"}
```

### What the frontend reads in `loadManagersSettings()` (lines 1309–1354)

```javascript
items.map(item => ({
  id: item.manager_id,
  name: item.manager_name,
  onDelete: () => deleteManager(item.manager_id, item.manager_name)
}))
```

| Field expected | Field returned | Match? | Notes |
|---------------|----------------|--------|-------|
| `item.manager_id` | `manager_id` (string) | ✅ | |
| `item.manager_name` | `manager_name` | ✅ | |
| `item.role` | `role` | ✅ (unused) | Not displayed in the management UI |

**Contract: fully aligned.**

---

## 4. `/settings/directions` and `/settings/statuses` — plain strings

### What the backend returns

Both endpoints return `["string1", "string2", ...]` — plain string arrays.

### What the frontend reads in `loadDirectionsSettings()` and `loadStatusesSettings()`

```javascript
items.map(item => ({ id: item, name: item, onDelete: () => deleteDirection(item) }))
```

- The `fillSelect()` function handles plain strings with `option.value = opt; option.textContent = opt;`.
- **⚠️ RISK:** When the frontend is using enriched settings (IDs), `#filter-status` and `#business_direction` dropdowns have numeric ID values. But `renderDeals()` (line 691) compares `deal.status !== statusFilter` using **the string value from the filter select**. After enriched load, `#filter-status` will contain **numeric IDs** as values, but `deal.status` in the list response is likely a **string name**. This means the status filter will never match and will always show all deals or show an empty list.

---

## 5. Deal creation payload — `/deals/create`

### What `collectFormDataSql()` sends (lines 560–591)

```json
{
  "status_id": int,
  "business_direction_id": int,
  "client_id": int,
  "manager_id": int,
  "charged_with_vat": float,
  "vat_type_id": int,
  "vat_rate": float,
  "paid": float,
  "project_start_date": "YYYY-MM-DD",
  "project_end_date": "YYYY-MM-DD",
  "act_date": "YYYY-MM-DD" | null,
  "variable_expense_1_without_vat": float | null,
  "variable_expense_2_without_vat": float | null,
  "production_expense_without_vat": float | null,
  "manager_bonus_percent": float | null,
  "source_id": int | null,
  "document_link": str | null,
  "comment": str | null
}
```

### Backend SQL function expectation (via `deals_sql.py`)

The endpoint calls `public.create_deal(...)` PostgreSQL function with matching parameter names. The field names match the SQL function signature.

| Frontend field | Backend expects | Match? | Risk |
|---------------|-----------------|--------|------|
| `status_id` | integer FK to `deal_statuses` | ✅ | None |
| `business_direction_id` | integer FK to `business_directions` | ✅ | None |
| `client_id` | integer FK to `clients` | ✅ | None |
| `manager_id` | integer FK to `managers` | ✅ | None |
| `vat_type_id` | integer FK to `vat_types` | ✅ | None |
| `source_id` | integer FK to `sources` | ✅ | None |
| `production_expense_without_vat` | matches SQL param | ✅ | Frontend uses fallback: `floatVal('general_production_expense') \|\| floatVal('production_expense_with_vat')`. If neither field exists in the HTML, value is null. |

**⚠️ RISK:** `collectFormDataSql()` silently passes `production_expense_without_vat` as the **VAT-inclusive** `production_expense_with_vat` value when `general_production_expense` is empty (line 586). The SQL function receives a potentially wrong value without any warning.

---

## 6. Deal display — `/deals` list response

### What `renderDealDetail()` expects (lines 951–1014)

The modal reads these fields from `deal` object returned by `/deals`:

| Field | Section | Used as |
|-------|---------|---------|
| `deal.status` | Основное | string name |
| `deal.business_direction` | Основное | string name |
| `deal.client` | Основное | string name |
| `deal.manager` | Основное | string name |
| `deal.charged_with_vat` | Финансы | float → formatCurrency |
| `deal.vat_rate` | Финансы | float (× 100 to get %) |
| `deal.vat_amount` | Финансы | float → formatCurrency |
| `deal.amount_without_vat` | Финансы | float → formatCurrency |
| `deal.vat_type` | Финансы | string name |
| `deal.paid` | Финансы | float → formatCurrency |
| `deal.marginal_income` | Маржинальность | float → formatCurrency |
| `deal.gross_profit` | Маржинальность | float → formatCurrency |
| `deal.manager_bonus_amount` | Маржинальность | float → formatCurrency |
| `deal.project_start_date` | Сроки | date string → formatDate |
| `deal.project_end_date` | Сроки | date string → formatDate |
| `deal.act_date` | Сроки | date string → formatDate |
| `deal.variable_expense_1` | Расходы | float → formatCurrency |
| `deal.variable_expense_1_with_vat` | Расходы | float → formatCurrency |
| `deal.variable_expense_1_without_vat` | Расходы | float → formatCurrency |
| `deal.variable_expense_2` | Расходы | float → formatCurrency |
| `deal.variable_expense_2_with_vat` | Расходы | float → formatCurrency |
| `deal.variable_expense_2_without_vat` | Расходы | float → formatCurrency |
| `deal.production_expense_with_vat` | Расходы | float → formatCurrency |
| `deal.production_expense_without_vat` | Расходы | float → formatCurrency |
| `deal.manager_bonus_percent` | Расходы | float → `${val}%` |
| `deal.manager_bonus_paid` | Расходы | float → formatCurrency |
| `deal.general_production_expense` | Расходы | float → formatCurrency |
| `deal.source` | Дополнительно | string |
| `deal.document_link` | Дополнительно | string |
| `deal.comment` | Дополнительно | string |
| `deal.created_at` | Дополнительно | string |

All `null` / empty fields are silently skipped (line 1017), so missing fields don't cause errors but result in empty sections.

### What `createDealCard()` expects from the `/deals` list (lines 716–769)

| Field | Used for |
|-------|---------|
| `deal.deal_id` | Card ID badge, action button `data-id` |
| `deal.status` | Status badge text and `data-status` attribute |
| `deal.client` | Card title |
| `deal.business_direction` | Meta info |
| `deal.manager` | Meta info |
| `deal.project_start_date` | Date range |
| `deal.project_end_date` | Date range |
| `deal.charged_with_vat` | Amount display |
| `deal.comment` | Tooltip |

### What `renderDeals()` filter reads (lines 686–699)

```javascript
if (statusFilter && deal.status !== statusFilter) return false;
if (clientFilter && deal.client !== clientFilter) return false;
if (monthFilter) {
  const startDate = deal.project_start_date || '';
  if (!startDate.startsWith(monthFilter)) return false;
}
```

**⚠️ HIGH RISK — Client filter mismatch:**
- `#filter-client` is populated from `data.clients` via `fillSelect('filter-client', data.clients, true)`.
- When enriched settings are loaded, `option.value = String(opt.id)` (e.g., `"42"`).
- The filter compares `deal.client !== clientFilter`, but `deal.client` from the `/deals` API response is a **string name** (e.g., `"ООО Ромашка"`), not a numeric ID.
- **Result:** The client filter will never match any deal when enriched settings are active — all deals will be hidden when a client filter is selected.

**⚠️ HIGH RISK — Status filter mismatch:**
- Same issue: `#filter-status` gets numeric ID values from enriched settings.
- `deal.status` in the response is a **string name** (e.g., `"Завершена"`), not an ID.
- **Result:** The status filter will never match any deal when enriched settings are active.

---

## 7. Deal editing — `/deals/update/{dealId}`

### What `saveEditedDeal()` sends (lines 857–902)

```json
{
  "status": "string name",
  "variable_expense_1_with_vat": float,
  "variable_expense_2_with_vat": float,
  "production_expense_with_vat": float,
  "general_production_expense": float,
  "manager_bonus_pct": float,
  "comment": "string"
}
```

### What `onEditDealSelected()` reads from `/deals/{dealId}` (lines 825–855)

```javascript
setVal('edit-status', deal.status);
setVal('edit-variable-expense-1-with-vat', deal.variable_expense_1_with_vat);
setVal('edit-variable-expense-2-with-vat', deal.variable_expense_2_with_vat);
setVal('edit-production-expense-with-vat', deal.production_expense_with_vat);
setVal('edit-general-production-expense', deal.general_production_expense);
setVal('edit-manager-bonus-pct', deal.manager_bonus_pct);
setVal('edit-comment', deal.comment);
```

| Field read from GET | Field sent in PATCH | Consistent? | Risk |
|--------------------|---------------------|-------------|------|
| `deal.status` (string name) | `payload.status` (string name) | ✅ | `#edit-status` is populated from enriched data with **numeric IDs**. The GET response sets `el.value = deal.status` (string name) which won't match any option by value — the `<select>` will show blank. When saved, `statusEl.value` returns the blank/default value, so `payload.status` will be empty and the field will be omitted from the PATCH. |
| `deal.manager_bonus_pct` | `payload.manager_bonus_pct` | ✅ (field name matches) | — |
| `deal.variable_expense_1_with_vat` | `payload.variable_expense_1_with_vat` | ✅ | — |
| `deal.production_expense_with_vat` | `payload.production_expense_with_vat` | ✅ | — |
| `deal.general_production_expense` | `payload.general_production_expense` | ✅ | — |

**⚠️ MEDIUM RISK — Edit status dropdown:**
When enriched settings are loaded, `#edit-status` options have **numeric ID values**. But `onEditDealSelected()` sets `el.value = deal.status` (a string like `"Завершена"`). Since no `<option>` has `value="Завершена"`, the select will remain on the placeholder. Editing will appear to succeed, but status will not be sent unless the user manually re-selects it.

---

## 8. Billing form — field contract

### `/billing/v2/search` response → `preloadBillingForm()`

| Field read by frontend | Expected in response | Risk |
|-----------------------|---------------------|------|
| `data.shipments_with_vat` | float | None if field missing — silently skipped |
| `data.units_count` | integer | None |
| `data.storage_with_vat` | float | None |
| `data.pallets_count` | integer | None |
| `data.returns_pickup_with_vat` | float | None |
| `data.returns_trips_count` | integer | None |
| `data.additional_services_with_vat` | float | None |
| `data.penalties` | float | None |
| `data.payment_status` | string | None |
| `data.payment_amount` | float | None |
| `data.payment_date` | date string | None |

### `/billing/v2/upsert` request payload

Frontend sends `{client_id, warehouse_id, month, period, shipments_with_vat, units_count, storage_with_vat, pallets_count, returns_pickup_with_vat, returns_trips_count, additional_services_with_vat, penalties}`.

Backend SQL function expects matching parameter names. Contract is aligned.

### `/billing/v2/payment/mark` request payload

Frontend sends: `{deal_id: string, payment_amount: float}` (lines 2195–2218).

Per stored memory: `BillingPaymentMarkRequest` schema accepts `deal_id` as **string** and converts to integer ID internally.

| Frontend field | Schema field | Match? |
|---------------|-------------|--------|
| `deal_id` (string) | `deal_id` (str, converted to int) | ✅ |
| `payment_amount` (float) | `payment_amount` | ✅ |

---

## 9. Expenses form — field contract

### `/expenses/v2/create` request payload

Frontend sends:
```json
{
  "category_level_1": str,
  "category_level_2": str | null,
  "comment": str | null,
  "amount_without_vat": float,
  "vat_rate": float | null,
  "deal_id": int | str
}
```

The `category_level_1` value is set from `#expense-cat1.value`, which is populated with `cat.name` (not `cat.id`) via:
```javascript
cat1Items.push({ id: cat.name, name: cat.name });
```
(line 252 — `id` is the category **name string**, not the integer ID).

**⚠️ MEDIUM RISK:** Expense categories are stored as `{id: cat.name, name: cat.name}` in the dropdown — using `name` as both `id` and `name`. This is intentional (the API accepts name strings), but means the integer IDs from `expense_categories[].id` are never used. If the backend later requires integer IDs for expense categories, this will break silently.

---

## 10. Summary of risks and mismatches

| # | Severity | Component | Field(s) | Description | Effect |
|---|----------|-----------|----------|-------------|--------|
| R1 | 🔴 HIGH | My Deals filter | `#filter-client`, `deal.client` | Filter select stores numeric IDs from enriched settings; `/deals` list response returns string names. Comparison `deal.client !== clientFilter` always fails. | **Client filter shows no results** when enriched settings are loaded. |
| R2 | 🔴 HIGH | My Deals filter | `#filter-status`, `deal.status` | Same issue — status filter stores numeric IDs; deal objects have string names. | **Status filter shows no results** when enriched settings are loaded. |
| R3 | 🟠 MEDIUM | Edit Deal form | `#edit-status`, `deal.status` | `#edit-status` options have numeric values; `onEditDealSelected()` tries to set the element value to a string status name which doesn't match any option. Select appears blank. | **Status not sent in PATCH** unless user manually re-selects it. |
| R4 | 🟠 MEDIUM | New Deal form | `production_expense_without_vat` | Falls back to `production_expense_with_vat` value if `general_production_expense` is empty (line 586). The field name says "without VAT" but receives a "with VAT" value. | **Silent data corruption** — production expense stored with wrong value. |
| R5 | 🟡 LOW | Expense categories | `#expense-cat1` value | Category `id` is set to `cat.name` string, not integer. If backend later requires integer IDs, this breaks. | Currently harmless (API accepts names); future migration risk. |
| R6 | 🟡 LOW | Settings fallback | Hardcoded `statuses`, `business_directions`, `vat_types`, `sources` | If `/settings/enriched` fails, fallback uses hardcoded plain strings (lines 190–199). These strings are used as option values — not IDs. Subsequent `/deals/create` call would fail because `status_id`, `business_direction_id`, etc. expect integers. | **Form submission fails** when enriched settings are unavailable and fallback is active. |
| R7 | 🟡 LOW | Billing save | `saveBilling()` legacy path | Uses `warehouseVal` (numeric ID string) as URL path parameter `/billing/{warehouse}`. The legacy endpoint expects a warehouse **name**, not an ID. | **404 or wrong warehouse** when falling through to legacy path with enriched data. |
| R8 | 🟡 LOW | `loadDealsForEdit()` | `d.deal_id` for display | Uses `d.deal_id` for the option label, but the GET `/deals` response in SQL-first mode may return `d.id` (integer) instead of `d.deal_id` (string like `D-2024-001`). If `d.deal_id` is undefined, options show as undefined. | **Edit dropdown shows `undefined —`** labels for deals. |
| R9 | 🟢 INFO | Warehouse billing label | `w.code || ''` + uppercase | `populateSelects()` formats warehouse as `${(w.code||'').toUpperCase()} — ${w.name}`. If `code` is null/empty, label shows `" — Warehouse Name"`. | Minor cosmetic issue. |

---

## 11. Fields frontend expects — entity-by-entity

### Clients
| Context | Fields expected | Source |
|---------|----------------|--------|
| Deal form dropdowns | `{id: int, name: str}` | `/settings/enriched` → `clients[]` |
| Settings management list | `{client_id: str, client_name: str, created_at: str}` | `/settings/clients` |
| Deal list / modal display | `deal.client` (string name) | `/deals` list response |
| Client filter comparison | string name | `state.deals[].client` |

### Deals
| Context | Fields expected | Source |
|---------|----------------|--------|
| My deals list cards | `deal_id, status, client, business_direction, manager, project_start_date, project_end_date, charged_with_vat, comment` | `/deals` |
| Deal detail modal | All 30 fields listed in Section 6 above | `/deals/{id}` |
| Edit deal dropdown | `deal_id, client, status` | `/deals` |
| Edit deal form pre-fill | `status, variable_expense_1_with_vat, variable_expense_2_with_vat, production_expense_with_vat, general_production_expense, manager_bonus_pct, comment` | `/deals/{id}` |
| Billing / expense deal selects | `{id, deal_name, client}` (via `loadDealsFiltered`) | `/deals` |

### Directions
| Context | Fields expected | Source |
|---------|----------------|--------|
| Deal form `#business_direction` | `{id: int, name: str}` | `/settings/enriched` → `business_directions[]` |
| Settings management list | plain `str` | `/settings/directions` |
| Dependent dropdown filter param | `business_direction_id` (int, URL param) | used in `/deals?business_direction_id=X` |

### Warehouses
| Context | Fields expected | Source |
|---------|----------------|--------|
| Billing form `#billing-warehouse` | `{id: int, code: str, name: str}` | `/settings/enriched` → `warehouses[]` |
| Legacy billing endpoint path | warehouse name string | Not used when enriched data is available |

### Managers
| Context | Fields expected | Source |
|---------|----------------|--------|
| Deal form `#manager` | `{id: int, name: str}` | `/settings/enriched` → `managers[]` |
| Settings management list | `{manager_id: str, manager_name: str, role: str, created_at: str}` | `/settings/managers` |
| Deal display | `deal.manager` (string name) | `/deals` response |

### Expense categories
| Context | Fields expected | Source |
|---------|----------------|--------|
| `#expense-cat1` options | `{id: cat.name, name: cat.name}` — name used as value | `/settings/enriched` → `expense_categories[]` |
| `EXPENSE_CATS_L2` map | `{cat.name.toLowerCase(): [sub.name, ...]}` | Built from `expense_categories[].sub_categories[].name` |
| `saveExpense()` payload | `category_level_1` (string name), `category_level_2` (string name) | Form values |

---

## 12. Which mismatches are most likely responsible for empty dropdowns or broken forms

### Empty client/status filters (R1, R2) — **Most likely observed bug**

**Root cause:** `fillSelect()` correctly stores integer IDs as option values for enriched data. But `renderDeals()` compares filter values (integer ID strings) against `deal.client` and `deal.status` (string names from API response). The comparison `"42" !== "ООО Ромашка"` always fails.

**Fix direction (without modifying code here):** Either (a) populate filter selects with string names as values (not IDs), or (b) compare `deal.client_id` and `deal.status_id` numeric fields from the response.

### Blank edit-status selector (R3) — **Medium-visibility bug**

**Root cause:** `#edit-status` is populated with enriched numeric ID options, but `onEditDealSelected()` sets `el.value = deal.status` (a Russian name string). No option matches, so the dropdown shows the placeholder.

**Fix direction:** Either populate `#edit-status` with string name values, or resolve the deal's status name to its ID before setting `el.value`.

### Form submission fails in fallback mode (R6) — **Latent error on DB outage**

**Root cause:** When `/settings/enriched` fails, `state.enrichedSettings` is set to `null` and `handleFormSubmit()` throws `"Справочники не загружены..."` error immediately (line 465). The form is effectively unusable when the database is unreachable.

### Production expense wrong VAT (R4) — **Silent data error**

**Root cause:** Line 586 `floatVal('general_production_expense') || floatVal('production_expense_with_vat')` — if the HTML form only has `production_expense_with_vat` input (and not `general_production_expense`), the VAT-inclusive value is silently stored as the `production_expense_without_vat` SQL parameter. No error is shown.

---

*Generated: 2026-03-16 · Audit section 23 of 23*
