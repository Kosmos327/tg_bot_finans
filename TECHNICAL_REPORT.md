# Технический отчёт: Telegram Mini App — Финансовая система ERP

> **Дата**: 2026-03-16  
> **Режим**: READ-ONLY анализ кода  
> **Охват**: Секции 7 (Screen-by-Screen UI), 8 (Deals Flow), 9 (Billing Flow), 10 (Expenses Flow), 11 (Dashboard & Reports), 14 (Rendering Architecture)

---

## 7. SCREEN-BY-SCREEN UI LOGIC

### Основной файл приложения

- **Файл**: `miniapp/index.html` (599 строк) + `miniapp/app.js` (3092 строки) + `miniapp/styles.css` (1743 строки)
- **Вспомогательный UI**: `frontend/index.html` + `frontend/js/app.js` + `frontend/js/api.js` + `frontend/js/permissions.js` — это **другая, более старая** (или параллельная) версия фронтенда; в анализе ниже используется `miniapp/` как актуальная версия.

---

### 7.1 Экран авторизации (`auth-screen`)

**Где рендерится**: `miniapp/index.html`, элемент `<div id="auth-screen">` (строки 15–40). Показывается до входа в приложение.

**Функции**:
- `showAuthScreen()` — показывает `auth-screen`, скрывает `app-main`
- `initAuthHandlers()` — навешивает обработчики на кнопки ролей, кнопку «Назад», кнопку «Войти», поле пароля (Enter)
- `doLogin()` (async, определена внутри `initAuthHandlers()`) — выполняет вход
- `enterApp(role)` — скрывает экран авторизации, показывает основное приложение

**Форма**:
- Шаг 1: выбор роли — 4 кнопки `.role-btn` с `data-role`:
  - `manager`, `operations_director`, `accounting`, `admin`
- Шаг 2: ввод пароля — `<input type="password" id="auth-password">`
- Элементы: `#auth-role-label`, `#auth-error`, `#auth-submit-btn`, `#auth-back-btn`

**Логика входа (doLogin)**:
- Если `telegramUser` присутствует → POST `/auth/miniapp-login` с телом:
  ```json
  {
    "telegram_id": <int>,
    "full_name": "<string>",
    "username": "<string|null>",
    "selected_role": "<role_code>",
    "password": "<string>"
  }
  ```
  Ответ: `{ "role": "...", ... }` → `localStorage.setItem('telegram_id', ...)` + `localStorage.setItem('user_role', ...)`
- Если нет Telegram-контекста → POST `/auth/role-login` с телом `{ role, password }`  
  Ответ: `{ "success": true, "role": "...", "role_label": "..." }`
- При ошибке: показывает `#auth-error` с текстом «Неверный пароль»
- Состояние сохраняется в `localStorage` (`user_role`, `user_role_label`, `telegram_id`)

**Валидация**: минимальная — просто проверяет, что `selectedRole` и `password` непустые.

**API-вызовы**: `POST /auth/miniapp-login` (основной) или `POST /auth/role-login` (fallback).

---

### 7.2 Главная навигация (таб-бар)

**Где рендерится**: `<nav class="tab-nav" id="main-tab-nav">` в `index.html`

**Функция**: `buildTabs(role)` — динамически генерирует кнопки навигации через `innerHTML` на основе константы `ROLE_TABS`:

```js
// Константа ROLE_TABS в app.js (строки 1520–1572)
const ROLE_TABS = {
  manager:             [tab-finances, tab-billing, tab-expenses, settings-tab],
  operations_director: [tab-finances, tab-dashboard, tab-receivables, tab-billing, tab-expenses, tab-reports, tab-journal, tab-month-close, settings-tab],
  accounting:          [tab-finances, tab-dashboard, tab-receivables, tab-expenses, tab-reports, tab-journal, settings-tab],
  admin:               [tab-finances, tab-dashboard, tab-receivables, tab-billing, tab-expenses, tab-reports, tab-journal, tab-month-close, settings-tab],
  accountant:          [tab-finances, tab-dashboard, tab-receivables, tab-expenses, tab-reports, settings-tab],
  head_of_sales:       [tab-finances, tab-reports, settings-tab],
}
```

**Переключение**: `switchMainTab(tabId)` — показывает/скрывает `.tab-panel` через `style.display`, выставляет класс `active` и `aria-selected`. При переключении:
- на `settings-tab` → вызывает `checkConnections()`, `renderUserInfoCard()`, `loadClientsSettings()`, `loadManagersSettings()`, `loadDirectionsSettings()`, `loadStatusesSettings()`
- на `tab-dashboard` → вызывает `loadOwnerDashboard()`
- на `tab-receivables` → вызывает `loadReceivables()`

---

### 7.3 Экран «Финансы» (`tab-finances`)

**Где рендерится**: `<div id="tab-finances" class="tab-panel">` (index.html, строки 60–189)

**Структура**: содержит 3 суб-навигационных панели с кнопками `.subnav-btn[data-sub=...]`:
- `new-deal-sub` — форма создания сделки
- `my-deals-sub` — список сделок
- `edit-deal-sub` — редактирование сделки

**Функции**: `initSubnav()` — навешивает `click` на каждую `.subnav-btn`, переключает видимость `[id$="-sub"]`.

---

#### 7.3.1 Суб-панель «Новая сделка» (`new-deal-sub`)

**Форма**: `<form id="deal-form">` — 5 секций:

| Секция | Поля |
|--------|------|
| Основное | `status` (select), `business_direction` (select), `client` (select), `manager` (select) |
| Финансы | `charged_with_vat` (number), `vat_type` (select), `vat_rate` (number), `paid` (number) |
| Сроки | `project_start_date` (date), `project_end_date` (date), `act_date` (date) |
| Расходы и бонусы | `variable_expense_1`, `variable_expense_2`, `variable_expense_1_with_vat`, `variable_expense_2_with_vat`, `production_expense_with_vat`, `manager_bonus_percent`, `manager_bonus_paid`, `general_production_expense` |
| Дополнительно | `source` (select), `document_link` (url), `comment` (textarea) |

**Кнопки**:
- `#submit-btn` «Сохранить сделку» — триггерит submit
- `#clear-btn` «Очистить форму» — вызывает `clearForm()`

**Функции обработки**:
- `initDealForm()` — навешивает `submit` → `handleFormSubmit()`, `click` на clear/new/view
- `handleFormSubmit(e)` — вызывает `validateForm()`, затем `collectFormDataSql()`, POST `/deals/create`
- `validateForm()` — проверяет 8 обязательных полей: `status`, `business_direction`, `client`, `manager`, `charged_with_vat`, `vat_type`, `project_start_date`, `project_end_date`
- `collectFormDataSql()` — собирает данные с **числовыми ID** из enriched settings
- `updateSummary()` — live-обновление «итог сделки» (секция `#deal-summary`)
- Live-расчёт НДС: слушает `input` на `charged_with_vat` и `vat_rate`, обновляет `#deal-calc-vat-amount` и `#deal-calc-amount-no-vat`

**Экран успеха**: `#success-screen` — показывается после успешного создания (`showSuccessScreen(dealId)`); содержит кнопки «Создать ещё сделку» (`showForm()`) и «Мои сделки» (`switchMainTab('tab-finances')` + клик по суб-навигации).

**API-вызов**: `POST /deals/create`

**Payload** (из `collectFormDataSql()`):
```json
{
  "status_id": <int>,
  "business_direction_id": <int>,
  "client_id": <int>,
  "manager_id": <int>,
  "charged_with_vat": <float>,
  "vat_type_id": <int|null>,
  "vat_rate": <float|null>,
  "paid": <float|0>,
  "project_start_date": "<YYYY-MM-DD>|null",
  "project_end_date": "<YYYY-MM-DD>|null",
  "act_date": "<YYYY-MM-DD>|null",
  "variable_expense_1_without_vat": <float|null>,
  "variable_expense_2_without_vat": <float|null>,
  "production_expense_without_vat": <float|null>,
  "manager_bonus_percent": <float|null>,
  "source_id": <int|null>,
  "document_link": "<string>|null",
  "comment": "<string>|null"
}
```

**Показ ошибок**: `showToast(message, 'error')` + заполнение `<span class="field-error" id="{field}-error">` и добавление класса `field--error`.

---

#### 7.3.2 Суб-панель «Мои сделки» (`my-deals-sub`)

**Данные**: загружаются в `state.deals[]`

**Фильтры**:
- `#filter-status` (select) — по статусу
- `#filter-client` (select) — по клиенту
- `#filter-month` (input[type=month]) — по месяцу начала проекта

**Кнопки**:
- `#refresh-deals-btn` «Обновить» → `loadDeals()`

**Функции**:
- `initMyDeals()` — навешивает обработчики
- `loadDeals()` — GET `/deals`, сохраняет в `state.deals`, вызывает `renderDeals()`
- `renderDeals()` — применяет клиентскую фильтрацию, создаёт карточки через `createDealCard(deal)`, вставляет в `#deals-list`

**Карточка сделки** (`createDealCard`): рендерится через `innerHTML` с эскейпингом. Поля: `deal_id`, `status`, `client`, `business_direction`, `manager`, `project_start_date`, `project_end_date`, `charged_with_vat`, `comment`. Кнопки: «👁 Открыть» → `openDealModal(id)`, «📌» → `copyToClipboard(id)`.

**Состояния UI**: `#deals-loading`, `#deals-empty`, `#deals-list`

---

#### 7.3.3 Суб-панель «Редактировать сделку» (`edit-deal-sub`)

**Форма**: выбор сделки из `#edit-deal-select` + поля: `edit-status`, `edit-variable-expense-1-with-vat`, `edit-variable-expense-2-with-vat`, `edit-production-expense-with-vat`, `edit-general-production-expense`, `edit-manager-bonus-pct`, `edit-comment`

**Функции**:
- `initDealEdit()` — навешивает `change` на `#edit-deal-select`, `click` на save/back
- `loadDealsForEdit()` — GET `/deals`, заполняет `#edit-deal-select`
- `onEditDealSelected(dealId)` — GET `/deals/{dealId}`, заполняет поля
- `saveEditedDeal()` — PATCH `/deals/update/{dealId}` с телом изменённых полей

---

### 7.4 Модальное окно сделки (`#deal-modal`)

**Где рендерится**: `<div id="deal-modal" class="modal-overlay">` (index.html, строки 586–592)

**Функции**:
- `openDealModal(dealId)` — ищет сделку в `state.deals` → если нет, GET `/deals/{dealId}`. Вставляет `renderDealDetail(deal)` в `#modal-body`, показывает оверлей.
- `closeDealModal()` — скрывает модал, снимает блокировку `body.overflow`
- `renderDealDetail(deal)` — строит HTML из 6 секций: Основное, Финансы, Маржинальность, Сроки, Расходы и бонусы, Дополнительно. Использует `escHtml()` и `formatCurrency()`.
- `initModal()` — навешивает `click` на `#modal-close-btn`, на оверлей (закрыть по клику вне), `keydown Escape`

**Данные в модале**: все поля из `public.v_api_deals`, включая расчётные (`marginal_income`, `gross_profit`, `vat_amount`, `amount_without_vat`, `variable_expense_1_without_vat`, `variable_expense_2_without_vat`, etc.)

---

### 7.5 Экран «Billing» (`tab-billing`)

**Где рендерится**: `<div id="tab-billing" class="tab-panel">` (index.html, строки 192–304)

**Секции**:
1. Фильтры: `#billing-warehouse`, `#billing-client-select`, `#billing-month`, `#billing-half`, `#billing-format`
2. Форма ввода (новый формат): `#billing-section-new` — поля Отгрузки, Хранение, Возвраты, Доп. услуги, Штрафы, Итого, Статус/сумма/дата оплаты
3. Форма ввода (старый формат): `#billing-section-old` — поля p1 и p2
4. Отметка оплаты: зависимые дропдауны `payment-direction-select` → `payment-client-select` → `payment-deal-select`, поле `payment-amount`, кнопка «Отметить оплату»

**Кнопки**:
- `#billing-load-btn` → `loadBillingEntry()`
- `#billing-save-btn` → `saveBilling()`
- `#payment-mark-btn` → `markPayment()`

Подробно см. **Секция 9**.

---

### 7.6 Экран «Расходы» (`tab-expenses`)

**Где рендерится**: `<div id="tab-expenses" class="tab-panel">` (index.html, строки 307–356)

**Секции**:
1. Единичный расход
2. Пакетный ввод (`#bulk-rows-container`)
3. Список расходов (`#expenses-list`)

Подробно см. **Секция 10**.

---

### 7.7 Экран «Отчёты» (`tab-reports`)

**Где рендерится**: `<div id="tab-reports" class="tab-panel">` (index.html, строки 359–376)

**Функция**: `initReportsHandlers()` — делегирует `click` на все `[data-report]` кнопки → `downloadReport(reportType, fmt)`

**Доступные отчёты** (12 типов):

| data-report | Описание | Доп. фильтр |
|-------------|----------|-------------|
| `warehouse` | По складу | `#report-warehouse` (msk/nsk/ekb) |
| `clients` | По клиентам | — |
| `expenses` | По расходам | — |
| `profit` | По прибыли | — |
| `warehouse-revenue` | Выручка складов | — |
| `paid-deals` | Оплаченные сделки | — |
| `unpaid-deals` | Неоплаченные сделки | — |
| `paid-billing` | Оплаченный биллинг | — |
| `unpaid-billing` | Неоплаченный биллинг | — |
| `billing-by-month` | Биллинг по месяцу | `#report-month` (input[type=month]) |
| `billing-by-client` | Биллинг по клиенту | `#report-client-select` (select) |
| `debt-by-client` | Долг по клиентам | — |
| `debt-by-warehouse` | Долг по складам | — |
| `overdue-payments` | Просроченные платежи | — |
| `partially-paid-billing` | Частично оплаченный биллинг | — |

Каждый отчёт: 2 кнопки (CSV и XLSX) с `data-fmt="csv"` / `data-fmt="xlsx"`.

---

### 7.8 Экран «Журнал» (`tab-journal`)

**Где рендерится**: `<div id="tab-journal" class="tab-panel">` (index.html, строки 379–386)

**Кнопки**: `#load-journal-btn` → `loadJournal()`

**Функция**: `loadJournal()` — GET `/journal?limit=50`, рендерит через `innerHTML`. Отображаемые поля: `action`, `timestamp`, `user` / `full_name` / `telegram_user_id`, `entity`, `entity_id`, `deal_id`, `details` / `payload_summary`.

**Состояния**: `#journal-loading`, `#journal-list`, `#journal-empty`

**Примечание**: фильтрации нет; всегда загружает последние 50 записей.

---

### 7.9 Экран «Дашборд» (`tab-dashboard`)

**Где рендерится**: `<div id="tab-dashboard" class="tab-panel">` (index.html, строки 389–414)

**Фильтр**: `#dashboard-month-filter` (input[type=month]) + кнопка `#apply-dashboard-filter-btn`

**Кнопки**: `#load-dashboard-btn` → `loadOwnerDashboard()`

**Функции**: `initDashboardHandlers()` + `loadOwnerDashboard()`. Подробно см. **Секция 11**.

---

### 7.10 Экран «Дебиторская задолженность» (`tab-receivables`)

**Где рендерится**: `<div id="tab-receivables" class="tab-panel">` (index.html, строки 417–455)

**Фильтр**: `#receivables-month-filter` + `#apply-receivables-filter-btn`

**Кнопка**: `#load-receivables-btn` → `loadReceivables()`

**API**: GET `/receivables?month=YYYY-MM` с заголовком `X-User-Role`

**Отображаемые данные**:
- KPI: `total_debt`, `status_summary.paid/partial/unpaid/overdue`
- Долг по клиентам: `data.debt_by_client` (объект `{client: amount}`)
- Долг по складам: `data.debt_by_warehouse`
- Долг по месяцам: `data.debt_by_month`
- Встроенные отчёты: `debt-by-client`, `debt-by-warehouse`, `overdue-payments`, `partially-paid-billing`

---

### 7.11 Экран «Настройки» (`settings-tab`)

**Где рендерится**: `<div id="settings-tab" class="tab-panel">` (index.html, строки 458–547)

**Секции**:
1. Справочники (счётчики: `#cnt-statuses`, `#cnt-clients`, `#cnt-managers`, `#cnt-directions`)
2. Клиенты — список + форма добавления (`#new-client-name` + кнопка `#add-client-btn`)
3. Менеджеры — список + форма (`#new-manager-name`, `#new-manager-role` + кнопка `#add-manager-btn`)
4. Направления — список + форма (`#new-direction-name` + кнопка `#add-direction-btn`)
5. Статусы — список + форма (`#new-status-name` + кнопка `#add-status-btn`)
6. Статус подключений: Telegram Auth, API сервер, Google Sheets
7. Текущий пользователь (`#user-info-card`) + кнопка «Сменить роль» (logout)

**Функции**: `initSettingsManagement()`, `loadClientsSettings()`, `addClient()`, `deleteClient()`, `loadManagersSettings()`, `addManager()`, `deleteManager()`, `loadDirectionsSettings()`, `addDirection()`, `deleteDirection()`, `loadStatusesSettings()`, `addStatus()`, `deleteStatus()`, `renderRefList()`, `checkConnections()`, `renderUserInfoCard()`

**API-вызовы**:
- GET `/settings/clients`, POST `/settings/clients`, DELETE `/settings/clients/{id}`
- GET `/settings/managers`, POST `/settings/managers`, DELETE `/settings/managers/{id}`
- GET `/settings/directions`, POST `/settings/directions`, DELETE `/settings/directions/{name}`
- GET `/settings/statuses`, POST `/settings/statuses`, DELETE `/settings/statuses/{name}`
- GET `/health` (ping API)
- GET `/settings` (ping Google Sheets)

---

### 7.12 Экран «Закрытие месяца» (`tab-month-close`)

**Где рендерится**: `<div id="tab-month-close" class="tab-panel">` (index.html, строки 550–582)

**Поля**: `#month-close-year` (number), `#month-close-month` (number 1–12), `#month-close-comment` (text)

**Кнопки**:
- `#month-close-dry-run-btn` → `runMonthArchive(true)` (dry-run)
- `#month-close-archive-btn` → `runMonthArchive(false)` (реальное архивирование, требует confirm)
- `#month-close-cleanup-btn` → `runMonthCleanup()` (требует confirm)
- `#month-close-close-btn` → `runMonthClose()` (требует confirm)
- `#month-close-load-batches-btn` → `loadArchiveBatches()`

**API-вызовы**:
- POST `/month/archive` `{ year, month, dry_run }`
- POST `/month/cleanup` `{ year, month }`
- POST `/month/close` `{ year, month, comment }`
- GET `/month/archive-batches?year=&month=`

**Права доступа**: только `operations_director` и `admin` (ограничение на бэкенде в `month_close.py`)

---

## 8. DEALS FLOW

### 8.1 Загрузка списка сделок

**Функция**: `loadDeals()` в `app.js` (строки 662–684)

```js
async function loadDeals() {
  if (state.isLoadingDeals) return;  // защита от двойного запроса
  state.isLoadingDeals = true;
  showDealsLoading(true);
  clearDealsList();
  try {
    const deals = await apiFetch(`/deals`);
    state.deals = deals;
    renderDeals();
  } catch (err) { ... }
}
```

**Endpoint**: `GET /deals` (`deals_sql.py`, строки 62–121)

**Backend-логика**:
- Резолвит пользователя из `X-Telegram-Id` через `app_users`
- `manager` → фильтрует по `manager_telegram_id = :tid` из `public.v_api_deals`
- Остальные роли → может принимать `?manager_id=`, `?client_id=`, `?status_id=`, `?business_direction_id=`
- Читает из `public.v_api_deals` (SQL-вью), сортировка `created_at DESC`

**Фронтенд**: `params` в `loadDeals()` — **пустой** `URLSearchParams()`, т.е. никаких query-параметров не передаётся. Фильтрация статуса, клиента и месяца — **клиентская** в `renderDeals()`.

---

### 8.2 Форма создания сделки

**Функция**: `handleFormSubmit(e)` (строки 447–485) → `collectFormDataSql()` (строки 560–592)

**Путь**:
1. `validateForm()` — проверяет 8 обязательных полей
2. Проверяет `state.enrichedSettings` — бросает ошибку если не загружено
3. `collectFormDataSql()` — читает `<select>.value` как числовые ID из enriched settings
4. POST `/deals/create`
5. На успех: `showSuccessScreen(dealId)` + `showToast(..., 'success')` + `state.deals = []`

**Payload** (`collectFormDataSql()`):
```json
{
  "status_id": <int>,
  "business_direction_id": <int>,
  "client_id": <int>,
  "manager_id": <int>,
  "charged_with_vat": <float>,
  "vat_type_id": <int|null>,
  "vat_rate": <float|null>,
  "paid": <float|0>,
  "project_start_date": "<YYYY-MM-DD>|null",
  "project_end_date": "<YYYY-MM-DD>|null",
  "act_date": "<YYYY-MM-DD>|null",
  "variable_expense_1_without_vat": <float|null>,
  "variable_expense_2_without_vat": <float|null>,
  "production_expense_without_vat": <float|null>,
  "manager_bonus_percent": <float|null>,
  "source_id": <int|null>,
  "document_link": "<string>|null",
  "comment": "<string>|null"
}
```

**Примечание**: `collectFormData()` (строки 522–554) — устаревшая функция, принимающая **текстовые значения**. Она **не вызывается** при submit; вызывается только `collectFormDataSql()`.

**Backend** (`deals_sql.py`, строки 124–165):
```sql
SELECT * FROM public.api_create_deal(
  :status_id, :business_direction_id, :client_id, :manager_id,
  :charged_with_vat, :charged_without_vat, :vat_type_id, :vat_rate,
  :paid, :project_start_date, :project_end_date, :act_date,
  :variable_expense_1_without_vat, :variable_expense_2_without_vat,
  :production_expense_without_vat, :manager_bonus_percent,
  :source_id, :document_link, :comment
)
```

Ответ: полная запись сделки. Фронтенд читает `result.deal_id || result.id || result.deal?.id`.

---

### 8.3 Просмотр/редактирование сделки

**Просмотр**: `openDealModal(dealId)` (строки 918–943) → GET `/deals/{dealId}` если нет в `state.deals`

**Редактирование**:
- `loadDealsForEdit()` → GET `/deals` → заполняет `#edit-deal-select`
- `onEditDealSelected(dealId)` → GET `/deals/{dealId}` → заполняет поля редактирования (строки 825–855)
- `saveEditedDeal()` → PATCH `/deals/update/{dealId}` с payload:
  ```json
  {
    "status": "<string>",
    "variable_expense_1_with_vat": <float>,
    "variable_expense_2_with_vat": <float>,
    "production_expense_with_vat": <float>,
    "general_production_expense": <float>,
    "manager_bonus_pct": <float>,
    "comment": "<string>"
  }
  ```
  Пустые поля **не включаются** в payload.

**Backend** (`deals_sql.py`, строки 261–329): `PATCH /deals/update/{deal_id}` — не использует SQL-функцию, использует ORM-метод `deals_service.update_deal_pg()`. Managers могут редактировать только свои сделки.

---

### 8.4 Фильтрация сделок

**Клиентская фильтрация** в `renderDeals()` (строки 686–714):
```js
if (statusFilter && deal.status !== statusFilter) return false;
if (clientFilter && deal.client !== clientFilter) return false;
if (monthFilter && !startDate.startsWith(monthFilter)) return false;
```

**Проблема**: `statusFilter` и `clientFilter` сравниваются с **текстовыми** полями (`deal.status`, `deal.client`) из API, но в дропдаунах `#filter-status` и `#filter-client` после загрузки enriched settings хранятся **числовые ID** (`option.value = opt.id`). При обычном выборе из фильтра по клиенту будет сравниваться `"42"` (ID) с `"ООО Ромашка"` (имя). **Это потенциальный баг**: фильтрация по статусу и клиенту может не работать корректно при enriched settings.

**Серверная фильтрация**: при загрузке через `loadDealsFiltered(dealSelectId, directionId, clientId)` (строки 315–335) — GET `/deals?business_direction_id=&client_id=`.

---

### 8.5 Зависимые дропдауны

**Функция**: `initDependentDealDropdowns(dirSelectId, clientSelectId, dealSelectId)` (строки 343–361) — используется в 2 местах:
1. Billing: `initDependentDealDropdowns('payment-direction-select', 'payment-client-select', 'payment-deal-select')`
2. Expenses: `initDependentDealDropdowns('expense-direction-select', 'expense-client-select', 'expense-deal-select')`

**Логика**: при изменении direction или client вызывает `loadDealsFiltered(dealSelectId, dirId, clientId)` → GET `/deals?business_direction_id=&client_id=`.

---

### 8.6 Отображение успеха/ошибки

| Событие | Метод |
|---------|-------|
| Успех создания | `showToast(`Сделка ${dealId} успешно создана!`, 'success')` + `showSuccessScreen(dealId)` |
| Ошибка создания | `showToast(`Ошибка при сохранении: ${err.message}`, 'error')` |
| Ошибка загрузки | `showToast(`Ошибка загрузки сделок: ${err.message}`, 'error')` |
| Ошибка валидации | `showToast('Пожалуйста, заполните обязательные поля', 'error')` + inline поля ошибок |

---

## 9. BILLING FLOW

### 9.1 Загрузка billing-записи

**Функция**: `loadBillingEntry()` (строки 1957–2017)

**Зависимые входные данные**: `#billing-warehouse`, `#billing-client-select`, `#billing-month`, `#billing-half`, `#billing-format`

**Роутинг**:
- Если `state.enrichedSettings` загружен и warehouse/client — числовые ID → **SQL-путь**: GET `/billing/v2/search?warehouse_id=&client_id=[&month=][&period=]`
- Иначе → **Legacy-путь**: GET `/billing/search?warehouse=&client=[&month=][&period=]` с заголовком `X-User-Role`

**Ответ** (оба пути): `{ found: true, ...поля }` или `{ found: false }`

**На успех**: `preloadBillingForm(result)` — заполняет поля формы, пересчитывает итоги

**На «не найдено»**: `clearBillingForm()` + `showToast('Новая запись — введите данные', 'default')`

**Backend** (`billing_sql.py`, строки 181–243): `GET /billing/v2/search` — читает `public.v_api_billing` по `client_id`, `warehouse_id`, `month`, `period`. Требует хотя бы один фильтр.

---

### 9.2 Создание/обновление billing

**Функция**: `saveBilling()` (строки 2076–2193)

**Путь выбора формата**:
- `#billing-format` = `"new"` или `"new-no-vat"` + enriched settings (числовые ID) → POST `/billing/v2/upsert`
- Иначе → POST `/billing/{warehouse}` (legacy)

**Payload для `/billing/v2/upsert`**:
```json
{
  "client_id": <int>,
  "warehouse_id": <int>,
  "month": "<YYYY-MM>|undefined",
  "period": "<p1|p2>|undefined",
  "shipments_with_vat": <float|null>,
  "units_count": <int|null>,
  "storage_with_vat": <float|null>,
  "pallets_count": <int|null>,
  "returns_pickup_with_vat": <float|null>,
  "returns_trips_count": <int|null>,
  "additional_services_with_vat": <float|null>,
  "penalties": <float|null>
}
```
Null-значения удаляются перед отправкой (`Object.keys(body).forEach(k => body[k] == null && delete body[k])`).

**Payload для legacy `/billing/{warehouse}` (новый формат)**:
```json
{
  "client": "<name>",
  "month": "<YYYY-MM>|undefined",
  "period": "<p1|p2>|undefined",
  "input_mode": "Новый (с НДС)" | "Новый (без НДС)",
  "shipments_with_vat": ...,
  "units_count": ...,
  "storage_with_vat": ...,
  "pallets_count": ...,
  "returns_pickup_with_vat": ...,
  "returns_trips_count": ...,
  "additional_services_with_vat": ...,
  "penalties": ...,
  "payment_status": ...,
  "payment_amount": ...,
  "payment_date": ...
}
```

**Payload для legacy `/billing/{warehouse}` (старый формат p1/p2)**:
```json
{
  "client_name": "<name>",
  "p1": { "shipments_amount", "units", "storage_amount", "pallets", "returns_amount", "returns_trips", "extra_services", "penalties" },
  "p2": { ... }
}
```

**Backend** (`billing_sql.py`, строки 96–138): POST `/billing/v2/upsert` → `public.api_upsert_billing_entry(...)`.

---

### 9.3 Отметка оплаты по сделке

**Функция**: `markPayment()` (строки 2195–2218)

**Входные данные**: `#payment-deal-select` (ID сделки), `#payment-amount`

**Endpoint**: POST `/billing/v2/payment/mark`

**Payload**:
```json
{
  "deal_id": "<string>",
  "payment_amount": <float>
}
```

**Ответ**: `{ remaining_amount: <float>, ... }` — отображается в toast: «Оплата X ₽ отмечена. Остаток: Y ₽»

**Backend** (`billing_sql.py`, строки 246–307): конвертирует `deal_id` в integer, вызывает `public.api_pay_deal(deal_id, payment_amount, payment_date)`.

**Примечание**: `payment_date` не передаётся из формы (нет поля) → всегда `null` в `BillingPaymentMarkRequest`.

---

### 9.4 Фильтры billing

- `#billing-warehouse`: select с 3 жёстко заданными значениями (`msk`, `nsk`, `ekb`) → заменяются на числовые ID из enriched settings при инициализации
- `#billing-client-select`: заполняется из `data.clients` enriched settings
- `#billing-month`: input[type=month]
- `#billing-half`: `""` / `"p1"` / `"p2"`
- `#billing-format`: `"new"` / `"new-no-vat"` / `"old"` → переключает видимость секций через `switchBillingFormat(fmt)`

---

### 9.5 Расчёт итогов billing

**Для нового формата** (`calcBillingTotalsV2()`, строки 1838–1876):
- VAT_RATE = `0.20` (жёстко задано)
- В режиме `new` (с НДС): `noVat = entered / (1 + 0.20)`, `vat = entered - noVat`
- В режиме `new-no-vat`: `noVat = entered`, `vat = 0`
- `totalNoVat -= penalties` — штрафы вычитаются из суммы без НДС
- Обновляет: `#bv2-total-no-vat`, `#bv2-total-vat`, `#bv2-total-with-vat`, и `*-no-vat-calc` для каждой услуги

**Для старого формата** (`calcBillingTotals(prefix)`, строки 1824–1836):
- `totalNoPen = shipments + storage + returns + extra`
- `totalWithPen = totalNoPen - penalties`

**Таблица billing**: отдельной таблицы нет — данные отображаются в форме. Листинг всех записей — через GET `/billing/v2` (отдельный эндпоинт, не используется в текущем UI фронтенда для отображения).

---

## 10. EXPENSES FLOW

### 10.1 Загрузка списка расходов

**Функция**: `loadExpenses()` (строки 2531–2578)

**Endpoint**: GET `/expenses/v2`

**Backend** (`expenses_sql.py`, строки 52–82): читает `public.v_api_expenses`, опциональный `?deal_id=`.

**Фронтенд**: не передаёт никаких фильтров. Рендерит через `innerHTML` в `#expenses-list`.

**Отображаемые поля**: `category_level_1`, `category_level_2`, `comment`, `amount_with_vat` / `amount`, `amount_without_vat`, `vat_amount` / `vat`, `date` / `created_at`, `deal_id`.

---

### 10.2 Создание одного расхода

**Функция**: `saveExpense()` (строки 2472–2529)

**Endpoint**: POST `/expenses/v2/create`

**Payload**:
```json
{
  "category_level_1": "<string>",
  "category_level_2": "<string>|undefined",
  "comment": "<string>|undefined",
  "deal_id": <int>|undefined,
  "amount_without_vat": <float>,
  "vat_rate": <float>|undefined
}
```

Расчёт `amount_without_vat`: если задан `vat_rate` → `amount / (1 + vat_rate)`, иначе `amount - vat`.

**Бэкенд** (`expenses_sql.py`, строки 85–123): `public.api_create_expense(deal_id, category_level_1_id, category_level_2_id, amount_without_vat, vat_type_id, vat_rate, comment, created_by)`.

**Несоответствие**: фронтенд отправляет строки `category_level_1` / `category_level_2`, а схема `ExpenseCreateRequest` также принимает `category_level_1_id` / `category_level_2_id`. SQL-функция ожидает ID. Фронтенд **не передаёт числовые ID** для категорий — передаёт текстовые названия. Это потенциальная несовместимость с SQL-функцией.

---

### 10.3 Логика категорий

**Уровень 1** (`expense-cat1`): жёстко заданные варианты в HTML:
- `логистика`, `наёмный персонал`, `расходники`, `другое`

Дополнительно, при загрузке enriched settings с `data.expense_categories` → пересоздаёт опции из БД и обновляет `EXPENSE_CATS_L2` map.

**Уровень 2** (`expense-cat2`): динамически заполняется по выбору L1 из `EXPENSE_CATS_L2`:
```js
const EXPENSE_CATS_L2 = {
  'логистика':       ['Забор возвратов', 'Отвоз FBO', 'Отвоз FBS', 'Другое'],
  'наёмный персонал': ['Погрузочно-разгрузочные работы', 'Упаковка товара', 'Другое'],
  'расходники':      ['Упаковочный материал', 'Паллеты', 'Короба', 'Пломбы'],
  'другое':          [],
};
```

**Показ поля «Комментарий»**: `updateExpenseCommentVisibility()` — появляется если:
- L1 = `"другое"`, или
- L2 содержится в `COMMENT_REQUIRED_L2 = Set(['другое', 'упаковочный материал'])`

Обязательность комментария: `showToast('Комментарий обязателен для выбранной категории', 'error')`.

---

### 10.4 Пакетный ввод расходов

**Функция**: `addBulkRow()` (строки 2335–2405) — добавляет строку `#bulk-row-{idx}` в `#bulk-rows-container`

Каждая строка: `bulk-cat1-{idx}`, `bulk-cat2-{idx}` (скрыт), `bulk-comment-{idx}` (скрыт), `bulk-amount-{idx}`, `bulk-vat-rate-{idx}`, `bulk-deal-id-{idx}`

**Сохранение**: `saveBulkExpenses()` (строки 2417–2470) — итерирует строки, валидирует L1 и amount, отправляет **последовательно** через цикл `for...of`. Endpoint: POST `/expenses/v2/create` для каждой строки.

**Payload для каждой строки** (идентичен одиночному расходу):
```json
{
  "category_level_1": "<string>",
  "category_level_2": "<string>|undefined",
  "comment": "<string>|undefined",
  "amount_without_vat": <float>,
  "vat_rate": <float>|undefined,
  "deal_id": <int>|undefined
}
```

---

### 10.5 Зависимость direction/client/deal в расходах

`initDependentDealDropdowns('expense-direction-select', 'expense-client-select', 'expense-deal-select')` — при выборе направления или клиента загружает сделки через GET `/deals?business_direction_id=&client_id=`.

**Статус**: реализовано полностью.

---

## 11. DASHBOARD AND REPORTS

### 11.1 Загрузка данных дашборда

**Функции**: `initDashboardHandlers()` (строки 2696–2702) + `loadOwnerDashboard()` (строки 2704–2802)

**Endpoint**: GET `/dashboard/summary[?month=YYYY-MM]`

**Backend** (`dashboard.py`, строки 388–421): читает `public.v_dashboard_summary`. Доступно только для ролей `operations_director`, `accounting`, `admin`. Используется `X-Telegram-Id` для авторизации.

**Примечание о несоответствии**: существует также `GET /dashboard/owner` (`dashboard.py`, строки 327–362), который использует устаревшую логику через `deals_service.get_all_deals()` (Google Sheets). Фронтенд использует **только** `/dashboard/summary` (SQL view).

---

### 11.2 Виджеты дашборда

**Фронтенд** агрегирует строки из `/dashboard/summary` на клиентской стороне:

| Виджет | Поля из строк |
|--------|---------------|
| `#dashboard-kpis` — 7 KPI-карточек | `total_revenue_with_vat`, `total_revenue_without_vat`, `total_expenses`, `gross_profit`, `total_debt`, `paid_billing_count`, `unpaid_billing_count` |
| `#dashboard-warehouse-list` — по складам | `warehouse` / `warehouse_code`, `billing_total_with_vat`, `paid_count`, `unpaid_count` |
| `#dashboard-clients-list` — топ-10 клиентов | `client`, `total_revenue_with_vat` — сортировка по убыванию, top 10 |

**Структура данных**: `v_dashboard_summary` — вью, возвращающее строки. Фронтенд агрегирует суммы через `parseFloat(r.xxx || r.yyy || 0)` — попытка смэппить несколько возможных имён полей (признак нестабильного контракта API).

---

### 11.3 Дашборд дебиторской задолженности

**Endpoint**: GET `/receivables[?month=YYYY-MM]` (с заголовком `X-User-Role`)

**Функция**: `loadReceivables()` (строки 2822–2910)

Ожидаемая структура ответа:
```json
{
  "total_debt": <float>,
  "status_summary": { "paid": <int>, "partial": <int>, "unpaid": <int>, "overdue": <int> },
  "debt_by_client": { "<client>": <float>, ... },
  "debt_by_warehouse": { "<wh>": <float>, ... },
  "debt_by_month": { "<YYYY-MM>": <float>, ... }
}
```

---

### 11.4 Доступные отчёты и их endpoint-ы

| `data-report` | Endpoint на бэкенде |
|---------------|---------------------|
| `warehouse` | `GET /reports/warehouse/{warehouse}?fmt=csv\|xlsx` |
| `clients` | `GET /reports/clients?fmt=...` |
| `expenses` | `GET /reports/expenses?fmt=...` |
| `profit` | `GET /reports/profit?fmt=...` |
| `warehouse-revenue` | `GET /reports/warehouse-revenue?fmt=...` |
| `paid-deals` | `GET /reports/paid-deals?fmt=...` |
| `unpaid-deals` | `GET /reports/unpaid-deals?fmt=...` |
| `paid-billing` | `GET /reports/paid-billing?fmt=...` |
| `unpaid-billing` | `GET /reports/unpaid-billing?fmt=...` |
| `billing-by-month` | `GET /reports/billing-by-month?month=&fmt=...` |
| `billing-by-client` | `GET /reports/billing-by-client?client=&fmt=...` |
| `debt-by-client` | `GET /reports/debt-by-client?fmt=...` |
| `debt-by-warehouse` | `GET /reports/debt-by-warehouse?fmt=...` |
| `overdue-payments` | `GET /reports/overdue-payments?fmt=...` |
| `partially-paid-billing` | `GET /reports/partially-paid-billing?fmt=...` |

---

### 11.5 Механизм экспорта

**Функция**: `downloadReport(reportType, fmt)` (строки 2594–2638)

```js
const response = await fetch(`${API_BASE}${url}`, { headers });
const blob = await response.blob();
const objectUrl = URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = objectUrl;
a.download = `report_${reportType}.${fmt}`;
a.click();
URL.revokeObjectURL(objectUrl);
```

**Механизм**: через `fetch` → `response.blob()` → `URL.createObjectURL()` → программный клик по временному `<a>`. **Не использует** `window.location.href`. Не использует `apiFetch()` — напрямую через `fetch`.

**Передача роли**: заголовок `X-User-Role` (из `localStorage.getItem('user_role')`), **не** `X-Telegram-Id`. Это отличается от поведения остальных запросов.

**Форматы**: `csv` или `xlsx` (параметр `?fmt=`).

---

## 14. RENDERING ARCHITECTURE

### 14.1 Способ рендеринга DOM

**Полностью ручной рендеринг**: нет React, Vue, Angular или других фреймворков. Весь UI — vanilla JS.

**Три механизма рендеринга**:

1. **`innerHTML =`** — основной способ для динамических списков:
   - `createDealCard(deal)` → `card.innerHTML = \`...\`` (строки 730–753)
   - `renderDealDetail(deal)` → `body.innerHTML = renderDealDetail(deal)` (строки 938, 951–1034)
   - `buildTabs(role)` → `nav.innerHTML = ...` (строки 1722–1735)
   - `loadJournal()` → `listEl.innerHTML = data.map(...).join('')` (строки 2670–2685)
   - `loadExpenses()` → `listEl.innerHTML = data.map(...).join('')` (строки 2551–2573)
   - `loadOwnerDashboard()` → `kpisEl.innerHTML = ...`, `whEl.innerHTML = ...`, `clientsEl.innerHTML = ...` (строки 2752–2793)
   - `loadReceivables()` → множественные `innerHTML =` (строки 2844–2900)
   - `renderRefList()` → `listEl.innerHTML = ''` + appendChild (строки 1438–1471)
   - `_showMonthCloseResult()` → `resultEl.innerHTML = ...` (строки 2949–2988)

2. **DOM-метод `createElement` + `appendChild`** — для карточек сделок (`createDealCard`) и для `renderRefList` (кнопки удаления).

3. **`textContent` через `setEl(id, value)`** — для атомарных обновлений:
   ```js
   function setEl(id, value) {
     const el = document.getElementById(id);
     if (el) el.textContent = value;
   }
   ```

---

### 14.2 Безопасность innerHTML

**Функция `escHtml(str)`** (строки 1171–1179) применяется везде, где пользовательские данные вставляются через шаблонные строки в `innerHTML`:
```js
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
```

**Потенциально небезопасное место**: в `addBulkRow()` (строка 2346):
```js
row.innerHTML = `
  <button ... onclick="removeBulkRow(${idx})">✕</button>
```
Значение `idx` — это `_bulkRowIndex++` (числовой счётчик), так что инъекция невозможна. Но использование `onclick` в innerHTML является anti-pattern.

---

### 14.3 Шаблоны / компоненты

**Шаблонов нет**. Нет `<template>` HTML-элементов, нет системы компонентов. Все «компоненты» — это функции, возвращающие HTML-строку или создающие DOM-узлы.

**Функции, возвращающие HTML-строки** (квази-компоненты):
- `renderDealDetail(deal)` → строка HTML для модала
- `_showMonthCloseResult()` → строка HTML для результатов архивирования

---

### 14.4 Навешивание обработчиков событий

**Инициализация при загрузке**:
```js
document.addEventListener('DOMContentLoaded', init);
```

**Иерархия инициализации**:
1. `init()` → `initTelegram()`, `initTabs()`, `initDealForm()`, `initMyDeals()`, `initModal()`, `initMonthClose()`
2. `enterApp(role)` → `initBillingForm()`, `initExpensesForm()`, `initDealEdit()`, `initReportsHandlers()`, `initJournalHandlers()`, `initSubnav()`, `initSettingsManagement()`, `initDashboardHandlers()`, `initReceivablesHandlers()`

**Потенциальная проблема двойной инициализации**: `initAuthHandlers()` вызывается каждый раз при показе экрана авторизации. Обработчики на `.role-btn`, `#auth-back-btn`, `#auth-submit-btn`, `#auth-password` могут накапливаться при повторных вызовах `showAuthScreen()`. Однако на практике логин делается один раз.

**Делегирование событий**: используется только в `initReportsHandlers()` (общий обработчик на `[data-report]`). В остальных случаях — прямые обработчики на конкретных элементах.

**Обработчики внутри динамического контента**:
- `createDealCard(deal)` — навешивает обработчики непосредственно в функции (строки 756–764):
  ```js
  card.querySelectorAll('[data-action]').forEach(btn => {
    btn.addEventListener('click', ...);
  });
  card.addEventListener('click', () => openDealModal(deal.deal_id));
  ```
- `renderRefList()` — навешивает `deleteBtn.addEventListener('click', mapped.onDelete)` на каждую кнопку удаления
- `addBulkRow()` — навешивает `change` на cat1/cat2

---

### 14.5 Логика ре-рендеринга

**Нет реактивного ре-рендеринга**. Данные обновляются вручную:

| Ситуация | Метод |
|----------|-------|
| Обновление списка сделок | `clearDealsList()` (очищает `innerHTML`) → `renderDeals()` заново создаёт все карточки |
| Обновление справочника | `loadClientsSettings()` / `loadManagersSettings()` и т.д. — полная перезагрузка |
| Обновление KPI дашборда | `loadOwnerDashboard()` — перезаписывает `innerHTML` в `#dashboard-kpis` |
| Обновление billing-формы | `preloadBillingForm(data)` — устанавливает `.value` на каждое поле |
| Очистка формы | `clearForm()` → `form.reset()` / `clearBillingForm()` → ручная очистка полей |

**Инвалидация кэша**: при создании сделки — `state.deals = []` (строка 478).

---

### 14.6 Дублирующиеся функции

| Дублирование | Описание |
|--------------|----------|
| `collectFormData()` (строки 522–554) | Устаревшая версия, собирает текстовые значения. **Не вызывается** при submit. Мёртвый код. |
| `switchTab()` (строки 137–168) | Функция из старой версии приложения (frontend/), ищет `.tab-btn`. **Не используется** в miniapp (там `switchMainTab()`). В самом miniapp нет `.tab-btn` — они создаются динамически через `buildTabs()` |
| `_resolve_user()` | Дублируется в каждом backend-роутере (`deals_sql.py`, `billing_sql.py`, `expenses_sql.py`, `month_close.py`) — идентичный код |
| `initTabs()` (строки 127–135) | Ищет `.tab-btn` через `querySelectorAll` в `document` — на момент вызова при DOMContentLoaded таб-баров ещё нет (они создаются динамически). **Функция не даёт эффекта**. |

---

### 14.7 Фрагильные места

1. **`initTabs()` вызывается до `buildTabs()`**: при `DOMContentLoaded` нет ни одного `.tab-btn` в DOM (они создаются в `buildTabs(role)` после авторизации). `initTabs()` навешивает 0 обработчиков. Фактическая навигация работает через `switchMainTab()` в `buildTabs()`.

2. **Клиентская фильтрация по статусу/клиенту** в `renderDeals()` сравнивает числовые ID (из `<select>`) с текстовыми именами (из API) — потенциальный silent bug при enriched settings.

3. **`BILLING_VAT_RATE = 0.20`** жёстко задана в коде (строка 1842) — не берётся из справочника.

4. **Отправка категорий расходов по имени** (`category_level_1: "логистика"`), тогда как SQL-функция ожидает `category_level_1_id` — несоответствие фронта/бэка. Бэкенд-схема `ExpenseCreateRequest` содержит совместимые поля `category_level_1` (строка) и `category_level_1_id` (число), но SQL-функция `public.api_create_expense` вызывается с `params.category_level_1_id` — если он null, поведение SQL-функции неизвестно из кода.

5. **`loadDealsForEdit()`** загружает все сделки повторно (отдельный GET `/deals`) при переходе на суб-панель редактирования, не используя `state.deals`.

6. **`downloadReport()`** использует `X-User-Role` заголовок вместо `X-Telegram-Id`, что не соответствует паттерну остальных endpoints (нет защиты через app_users).

7. **`insertAdjacentHTML('afterbegin', roleRow)`** в `updateUserInfoWithRole()` (строка 1782) — добавляет строку роли при каждом входе, не очищая предыдущую. При перелогинизации без перезагрузки страницы строки ролей накапливались бы. На практике при смене роли делается `location.reload()`.

8. **`onclick` в innerHTML** в `addBulkRow()` (строка 2346): `onclick="removeBulkRow(${idx})"` — зависит от `removeBulkRow` как глобальной функции.

---

### 14.8 Существование двух UI-реализаций

В репозитории присутствуют два фронтенда:
- **`miniapp/`** — актуальная реализация (3092 строки JS)
- **`frontend/`** — параллельная или устаревшая реализация (572 строки JS), с другой архитектурой (есть `permissions.js` с `ROLE_PERMISSIONS`, `api.js` с `ApiClient` классом). Оба файла используют Telegram WebApp SDK. Нет признаков, что `frontend/` используется в production.

---

*Отчёт подготовлен на основе анализа реальных файлов: `miniapp/index.html`, `miniapp/app.js`, `miniapp/styles.css`, `backend/routers/deals_sql.py`, `backend/routers/billing_sql.py`, `backend/routers/expenses_sql.py`, `backend/routers/dashboard.py`, `backend/routers/reports.py`, `backend/routers/month_close.py`, `backend/schemas/deals.py`, `backend/schemas/billing.py`, `backend/schemas/expenses.py`.*
