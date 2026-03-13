# Анализ Mini App — Финансовая система

> Анализ выполнен на основе исходного кода проекта без изменений.  
> Senior full-stack developer review.

---

## 1. Mini App структура

В проекте присутствуют **две** директории с фронтендом:

### `miniapp/` — основной Telegram Mini App

```
miniapp/
├── index.html      # Единственный HTML-файл (SPA), все экраны в нём
├── app.js          # Вся бизнес-логика (~1 400 строк)
└── styles.css      # Стили (~900+ строк, mobile-first)
```

### `frontend/` — альтернативный фронтенд (отдельная архитектура)

```
frontend/
├── index.html          # SPA с шапкой, экранами сделок, журнала, аналитики
├── js/
│   ├── api.js          # Класс ApiClient — обёртка над fetch
│   ├── app.js          # Инициализация, навигация, обработчики
│   └── permissions.js  # Клиентская матрица разрешений (PERMISSION_MATRIX)
└── css/
    └── styles.css      # Стили
```

> **Дальнейший анализ сосредоточен на `miniapp/`** — основном Mini App, интегрированном с Telegram WebApp SDK, системой авторизации по ролям и всеми API-эндпоинтами.

---

## 2. Экраны интерфейса

### Первый экран: **Экран авторизации** (`#auth-screen`)

При первом открытии (нет `user_role` в `localStorage`) отображается карточка входа:

| Элемент | Описание |
|---------|----------|
| `💼` + заголовок | Логотип и название «Финансовая система» |
| **Шаг 1 — Выбор роли** | 4 кнопки выбора роли (Менеджер / Операц. директор / Бухгалтерия / Администратор) |
| **Шаг 2 — Пароль** | Поле ввода пароля, кнопки «Войти» и «Назад», блок ошибки |

### Основное приложение (`#app-main`) — после авторизации

| Зона | Описание |
|------|----------|
| **Шапка** (`app-header`) | Иконка, название, подзаголовок с ролью, аватар пользователя (инициалы из Telegram) |
| **Навигация** (`#main-tab-nav`) | Горизонтальные вкладки — набор зависит от роли |
| **Основной контент** (`main.main-content`) | Содержимое активной вкладки |
| **Модальное окно** (`#deal-modal`) | Детали сделки (нижний слой, sheet-стиль) |
| **Toast-уведомления** (`#toast-container`) | Всплывающие сообщения об успехе/ошибке |

### Вкладки и их содержимое

| Вкладка | ID панели | Содержимое |
|---------|-----------|------------|
| 💰 Финансы | `tab-finances` | Подвкладки: «🆕 Новая сделка» (форма) и «📂 Мои сделки» (список с фильтрами) |
| 🏭 Billing | `tab-billing` | Форма billing по складам (2 периода) + форма отметки оплаты |
| 📉 Расходы | `tab-expenses` | Форма добавления расхода + список расходов |
| 📥 Отчёты | `tab-reports` | 4 типа отчётов, скачивание в CSV/XLSX |
| 📜 Журнал | `tab-journal` | Список записей журнала действий |
| ⚙️ Настройки | `settings-tab` | Статистика справочников, статус подключений, информация о пользователе |

---

## 3. Все кнопки Mini App

### Экран авторизации

| Кнопка | Действие | Функция |
|--------|----------|---------|
| `👤 Менеджер` | Выбор роли `manager`, показ шага ввода пароля | `initAuthHandlers()` (обработчик `.role-btn`) |
| `📊 Операционный директор` | Выбор роли `operations_director` | то же |
| `🧾 Бухгалтерия` | Выбор роли `accounting` | то же |
| `🔐 Администратор` | Выбор роли `admin` | то же |
| `Войти` (`#auth-submit-btn`) | Отправка пароля на сервер | `doLogin()` (внутри `initAuthHandlers`) |
| `Назад` (`#auth-back-btn`) | Возврат к выбору роли | обработчик в `initAuthHandlers()` |

### Вкладка «Финансы» — форма сделки

| Кнопка | Действие | Функция |
|--------|----------|---------|
| `🆕 Новая сделка` (subnav) | Показывает под-панель `#new-deal-sub` | `initSubnav()` |
| `📂 Мои сделки` (subnav) | Показывает под-панель `#my-deals-sub`, загружает сделки | `initSubnav()` → `loadDeals()` |
| `💾 Сохранить сделку` (`#submit-btn`) | Валидация формы и отправка на сервер | `handleFormSubmit()` |
| `Очистить форму` (`#clear-btn`) | Сброс всех полей формы | `clearForm()` |
| `🆕 Создать ещё сделку` (`#new-deal-btn`) | Показывает форму снова (после успеха) | `showForm()` |
| `📂 Мои сделки` (`#view-deals-btn`) | Переход к списку сделок (после успеха) | `initSubnav()` обработчик |

### Вкладка «Финансы» — список сделок

| Кнопка | Действие | Функция |
|--------|----------|---------|
| `🔄 Обновить` (`#refresh-deals-btn`) | Перезагрузка списка сделок | `loadDeals()` |
| `👁 Открыть` (на карточке сделки) | Открывает модальное окно с деталями | `openDealModal(dealId)` |
| `📌` (на карточке сделки) | Копирует ID сделки в буфер обмена | `copyToClipboard(id)` |

### Модальное окно сделки

| Кнопка | Действие | Функция |
|--------|----------|---------|
| `✕` (`#modal-close-btn`) | Закрывает модальное окно | `closeDealModal()` |
| Клик по оверлею | Закрывает модальное окно | `closeDealModal()` |

### Вкладка «Billing»

| Кнопка | Действие | Функция |
|--------|----------|---------|
| `💾 Сохранить billing` (`#billing-save-btn`) | Отправка данных billing на сервер | `saveBilling()` |
| `✅ Отметить оплату` (`#payment-mark-btn`) | Отметка оплаты по ID сделки | `markPayment()` |

### Вкладка «Расходы»

| Кнопка | Действие | Функция |
|--------|----------|---------|
| `💾 Добавить расход` (`#expense-save-btn`) | Сохранение расхода на сервер | `saveExpense()` |
| `🔄 Загрузить` (`#load-expenses-btn`) | Загрузка списка расходов | `loadExpenses()` |

### Вкладка «Отчёты»

| Кнопка | Действие | Функция |
|--------|----------|---------|
| `CSV` (Отчёт по складу) | Скачивание отчёта по складу в CSV | `downloadReport('warehouse', 'csv')` |
| `XLSX` (Отчёт по складу) | Скачивание отчёта по складу в XLSX | `downloadReport('warehouse', 'xlsx')` |
| `CSV` (Отчёт по клиентам) | Скачивание отчёта по клиентам в CSV | `downloadReport('clients', 'csv')` |
| `XLSX` (Отчёт по клиентам) | Скачивание отчёта по клиентам в XLSX | `downloadReport('clients', 'xlsx')` |
| `CSV` (Отчёт по расходам) | Скачивание отчёта по расходам в CSV | `downloadReport('expenses', 'csv')` |
| `XLSX` (Отчёт по расходам) | Скачивание отчёта по расходам в XLSX | `downloadReport('expenses', 'xlsx')` |
| `CSV` (Отчёт по прибыли) | Скачивание отчёта по прибыли в CSV | `downloadReport('profit', 'csv')` |
| `XLSX` (Отчёт по прибыли) | Скачивание отчёта по прибыли в XLSX | `downloadReport('profit', 'xlsx')` |

### Вкладка «Журнал»

| Кнопка | Действие | Функция |
|--------|----------|---------|
| `🔄 Загрузить` (`#load-journal-btn`) | Загрузка последних 50 записей журнала | `loadJournal()` |

### Вкладка «Настройки»

| Кнопка | Действие | Функция |
|--------|----------|---------|
| `🚪 Сменить роль` (`#logout-btn`) | Очищает `localStorage`, перезагружает страницу (выход) | обработчик в `enterApp()` |

---

## 4. Все JS-функции

### Инициализация и Telegram

| Функция | Описание | API-вызов |
|---------|----------|-----------|
| `init()` | Точка входа: инициализирует Telegram, вкладки, форму, модалку; проверяет сохранённую роль | — |
| `initTelegram()` | Инициализирует `Telegram.WebApp`, устанавливает тему, получает данные пользователя | — |
| `renderUserAvatar(user)` | Отображает инициалы пользователя в шапке | — |
| `getInitials(first, last)` | Возвращает первые буквы имени и фамилии | — |
| `getTelegramInitData()` | Возвращает `tg.initData` для передачи в заголовок запроса | — |

### Сеть / API

| Функция | Описание | API-вызов |
|---------|----------|-----------|
| `apiFetch(path, options)` | Обёртка над `fetch`: добавляет заголовки `Content-Type`, `X-Telegram-Init-Data`, `X-User-Role`; обрабатывает ошибки | Используется во всех API-запросах |

### Авторизация

| Функция | Описание | API-вызов |
|---------|----------|-----------|
| `showAuthScreen()` | Показывает экран авторизации, скрывает основное приложение | — |
| `initAuthHandlers()` | Привязывает обработчики ко всем кнопкам авторизации | — |
| `doLogin()` | Считывает роль и пароль, отправляет POST-запрос, сохраняет роль в `localStorage` | `POST /auth/role-login` |
| `enterApp(role)` | Скрывает auth-экран, строит навигацию, загружает справочники, показывает первую вкладку | — |

### Навигация и вкладки

| Функция | Описание | API-вызов |
|---------|----------|-----------|
| `buildTabs(role)` | Строит HTML навигации на основе `ROLE_TABS[role]` | — |
| `switchMainTab(tabId)` | Переключает активную вкладку; при `settings-tab` вызывает `checkConnections()` | — |
| `initTabs()` | Привязывает обработчики к `.tab-btn` (старый вариант, дополняется `switchMainTab`) | — |
| `switchTab(tabId)` | Переключение вкладок с ленивой загрузкой сделок | — |
| `initSubnav()` | Привязывает обработчики к кнопкам подвкладок Финансы | — |

### Справочники

| Функция | Описание | API-вызов |
|---------|----------|-----------|
| `loadSettings()` | Загружает справочники (статусы, клиенты, менеджеры и др.), заполняет все `<select>` | `GET /settings` |
| `populateSelects(data)` | Заполняет селекты в форме и фильтрах | — |
| `fillSelect(id, options, hasAll)` | Заполняет конкретный `<select>` списком опций | — |
| `updateSettingsStats(data)` | Обновляет счётчики на вкладке «Настройки» | — |

### Форма создания сделки

| Функция | Описание | API-вызов |
|---------|----------|-----------|
| `initDealForm()` | Привязывает обработчик `submit`, кнопок «Очистить», «Создать ещё», «Мои сделки»; live-обновление итога | — |
| `updateSummary()` | Обновляет карточку «Итог сделки» при изменении ключевых полей | — |
| `handleFormSubmit(e)` | Обрабатывает отправку формы: валидация → сбор данных → POST → экран успеха | `POST /deal/create` |
| `validateForm()` | Проверяет обязательные поля, показывает ошибки под полями | — |
| `collectFormData()` | Считывает значения всех полей формы в объект | — |
| `setSubmitting(isLoading)` | Управляет состоянием кнопки «Сохранить» (спиннер / текст) | — |
| `clearForm()` | Сбрасывает форму и все ошибки валидации | — |
| `showSuccessScreen(dealId)` | Скрывает форму, показывает экран успеха с ID сделки | — |
| `showForm()` | Показывает форму, скрывает экран успеха | — |

### Список сделок

| Функция | Описание | API-вызов |
|---------|----------|-----------|
| `initMyDeals()` | Привязывает обработчик кнопки «Обновить» и фильтры | — |
| `loadDeals()` | Загружает сделки пользователя с сервера | `GET /deal/user` |
| `renderDeals()` | Фильтрует `state.deals` по статусу, клиенту, месяцу и рендерит карточки | — |
| `createDealCard(deal)` | Создаёт DOM-элемент карточки сделки с кнопками «Открыть» и «Копировать» | — |
| `showDealsLoading(show)` | Показывает/скрывает спиннер загрузки | — |
| `showDealsEmpty(show)` | Показывает/скрывает пустое состояние | — |
| `clearDealsList()` | Очищает список сделок | — |

### Модальное окно сделки

| Функция | Описание | API-вызов |
|---------|----------|-----------|
| `openDealModal(dealId)` | Открывает модальное окно: берёт сделку из `state.deals` или загружает с сервера | `GET /deal/{dealId}` |
| `closeDealModal()` | Закрывает модальное окно, восстанавливает скролл | — |
| `renderDealDetail(deal)` | Строит HTML с детальной информацией по сделке (5 разделов) | — |
| `initModal()` | Привязывает кнопку закрытия, клик по оверлею, Escape | — |

### Billing

| Функция | Описание | API-вызов |
|---------|----------|-----------|
| `initBillingForm()` | Привязывает live-расчёт итогов, кнопки «Сохранить billing» и «Отметить оплату» | — |
| `calcBillingTotals(prefix)` | Вычисляет «Итого без штрафов» и «Итого со штрафами» для периода | — |
| `saveBilling()` | Считывает поля двух периодов, отправляет данные на сервер | `POST /billing/{warehouse}` |
| `markPayment()` | Отправляет отметку оплаты по ID сделки | `POST /billing/payment/mark` |

### Расходы

| Функция | Описание | API-вызов |
|---------|----------|-----------|
| `initExpensesForm()` | Привязывает live-расчёт суммы без НДС, кнопки «Добавить расход» и «Загрузить» | — |
| `saveExpense()` | Собирает данные расхода и отправляет на сервер | `POST /expenses` |
| `loadExpenses()` | Загружает список расходов с сервера и рендерит их | `GET /expenses` |

### Отчёты

| Функция | Описание | API-вызов |
|---------|----------|-----------|
| `initReportsHandlers()` | Привязывает кнопки `[data-report]` к функции `downloadReport` | — |
| `downloadReport(reportType, fmt)` | Скачивает отчёт через `fetch` (не `apiFetch`) в виде blob-файла | `GET /reports/{type}?fmt=csv|xlsx` или `GET /reports/warehouse/{wh}?fmt=...` |

### Журнал

| Функция | Описание | API-вызов |
|---------|----------|-----------|
| `initJournalHandlers()` | Привязывает кнопку «Загрузить» к `loadJournal` | — |
| `loadJournal()` | Загружает последние 50 записей журнала и рендерит их | `GET /journal?limit=50` |

### Настройки

| Функция | Описание | API-вызов |
|---------|----------|-----------|
| `checkConnections()` | Проверяет статус Telegram, API-сервера и Google Sheets | `GET /health`, `GET /settings` |
| `setConnectionStatus(key, ok, text)` | Обновляет индикаторы подключения (зелёный/красный) | — |
| `renderUserInfoCard()` | Отображает данные Telegram-пользователя на вкладке «Настройки» | — |
| `updateUserInfoWithRole(role, roleLabel)` | Добавляет строку «Роль» в карточку пользователя | — |

### Утилиты

| Функция | Описание |
|---------|----------|
| `showToast(message, type, duration)` | Показывает всплывающее уведомление (success / error / warning / default) |
| `getFieldValue(id)` | Считывает и триммирует значение поля по ID |
| `setEl(id, value)` | Устанавливает `textContent` элемента по ID |
| `escHtml(str)` | Экранирует HTML-специальные символы |
| `formatCurrency(value)` | Форматирует число как валюту RUB через `Intl.NumberFormat` |
| `formatDate(dateStr)` | Форматирует дату в формат `дд.мм.гггг` через `Intl.DateTimeFormat` |
| `copyToClipboard(text)` | Копирует текст в буфер (Clipboard API или fallback через `execCommand`) |

---

## 5. API endpoints

Все запросы выполняются через `apiFetch(path, options)`, которая:
- Устанавливает заголовок `Content-Type: application/json`
- Добавляет `X-Telegram-Init-Data` (если есть `tg.initData`)
- Добавляет `X-User-Role` из `localStorage`

### Авторизация

```
POST /auth/role-login
Body: { role: string, password: string }
Ответ: { success: bool, role: string, role_label: string }
```

### Справочники

```
GET /settings
Ответ: { statuses, business_directions, clients, managers, vat_types, sources }
```

### Healthcheck

```
GET /health
Ответ: статус 200 = сервер доступен
```

### Сделки

```
POST /deal/create
Body:
{
  status, business_direction, client, manager,
  charged_with_vat, vat_type, paid,
  project_start_date, project_end_date, act_date,
  variable_expense_1, variable_expense_2,
  manager_bonus_percent, manager_bonus_paid,
  general_production_expense,
  source, document_link, comment
}
Ответ: { deal_id: string }

GET /deal/user
Query (опционально): ?manager=<имя>
Ответ: массив объектов сделки

GET /deal/{deal_id}
Ответ: объект сделки
```

### Billing

```
POST /billing/{warehouse}      (warehouse: msk | nsk | ekb)
Headers: X-User-Role
Body:
{
  client_name: string,
  p1: {
    shipments_amount, units, storage_amount, pallets,
    returns_amount, returns_trips, extra_services, penalties
  },
  p2: { ... те же поля ... }
}

POST /billing/payment/mark
Headers: X-User-Role
Body: { deal_id: string, payment_amount: number }
Ответ: { remaining_amount: number }
```

### Расходы

```
POST /expenses
Headers: X-User-Role
Body:
{
  deal_id: string | null,
  expense_type: "variable" | "production" | "logistics" | "returns" | "extra",
  amount: number,
  vat: number,
  amount_without_vat: number
}

GET /expenses
Headers: X-User-Role
Ответ: массив объектов расхода
```

### Отчёты

```
GET /reports/{type}?fmt=csv|xlsx
GET /reports/warehouse/{warehouse}?fmt=csv|xlsx
Headers: X-User-Role
Типы: clients | expenses | profit
Ответ: blob-файл (CSV или XLSX)
```

### Журнал

```
GET /journal?limit=50
Headers: X-User-Role
Ответ: массив записей журнала
```

---

## 6. Формы

### Форма создания сделки (`#deal-form`)

#### Раздел «Основное»

| Поле | Тип | ID | Обязательное |
|------|-----|----|:---:|
| Статус сделки | `<select>` | `status` | ✅ |
| Направление | `<select>` | `business_direction` | ✅ |
| Клиент | `<select>` | `client` | ✅ |
| Менеджер | `<select>` | `manager` | ✅ |

#### Раздел «Финансы»

| Поле | Тип | ID | Обязательное |
|------|-----|----|:---:|
| Начислено с НДС, ₽ | `number` | `charged_with_vat` | ✅ |
| Наличие НДС | `<select>` | `vat_type` | ✅ |
| Оплачено, ₽ | `number` | `paid` | — |

#### Раздел «Сроки»

| Поле | Тип | ID | Обязательное |
|------|-----|----|:---:|
| Дата начала | `date` | `project_start_date` | ✅ |
| Дата окончания | `date` | `project_end_date` | ✅ |
| Дата акта | `date` | `act_date` | — |

#### Раздел «Расходы и бонусы»

| Поле | Тип | ID | Обязательное |
|------|-----|----|:---:|
| Перем. расход 1, ₽ | `number` | `variable_expense_1` | — |
| Перем. расход 2, ₽ | `number` | `variable_expense_2` | — |
| Бонус мен., % | `number` | `manager_bonus_percent` | — |
| Бонус выпл., ₽ | `number` | `manager_bonus_paid` | — |
| Общепроизв. расход, ₽ | `number` | `general_production_expense` | — |

#### Раздел «Дополнительно»

| Поле | Тип | ID | Обязательное |
|------|-----|----|:---:|
| Источник | `<select>` | `source` | — |
| Документ / Ссылка | `url` | `document_link` | — |
| Комментарий | `<textarea>` | `comment` | — |

---

### Форма фильтрации сделок

| Поле | Тип | ID |
|------|-----|----|
| Статус | `<select>` | `filter-status` |
| Клиент | `<select>` | `filter-client` |
| Месяц | `month` | `filter-month` |

---

### Форма billing (`#tab-billing`)

#### Выбор склада и клиента

| Поле | Тип | ID |
|------|-----|----|
| Склад | `<select>` | `billing-warehouse` (msk / nsk / ekb) |
| Клиент | `text` | `billing-client` |

#### Период 1

| Поле | Тип | ID |
|------|-----|----|
| Сумма отгрузок, ₽ | `number` | `p1-shipments` |
| Кол-во единиц | `number` | `p1-units` |
| Сумма хранения, ₽ | `number` | `p1-storage` |
| Паллет | `number` | `p1-pallets` |
| Сумма возвратов, ₽ | `number` | `p1-returns` |
| Рейсы возвратов | `number` | `p1-returns-trips` |
| Доп. услуги, ₽ | `number` | `p1-extra` |
| Штрафы, ₽ | `number` | `p1-penalties` |

#### Период 2

Аналогичные поля с префиксом `p2-`.

#### Форма отметки оплаты

| Поле | Тип | ID |
|------|-----|----|
| ID сделки | `text` | `payment-deal-id` |
| Сумма оплаты, ₽ | `number` | `payment-amount` |

---

### Форма добавления расхода (`#tab-expenses`)

| Поле | Тип | ID |
|------|-----|----|
| ID сделки (необязательно) | `text` | `expense-deal-id` |
| Тип расхода | `<select>` | `expense-type` (variable / production / logistics / returns / extra) |
| Сумма, ₽ | `number` | `expense-amount` |
| НДС, ₽ | `number` | `expense-vat` |

> Поле «Сумма без НДС» — расчётное, отображается автоматически.

---

## 7. Загрузка данных

### `loadSettings()` — загрузка справочников

- **Endpoint:** `GET /settings`
- **Когда вызывается:** при каждом входе в приложение (в `enterApp(role)`)
- **Что делает:** заполняет все `<select>` в форме (статусы, направления, клиенты, менеджеры, тип НДС, источники), а также фильтры в «Мои сделки»
- **Fallback:** при ошибке использует захардкоженный набор значений по умолчанию

### `loadDeals()` — загрузка сделок

- **Endpoint:** `GET /deal/user`
- **Когда вызывается:**
  - При переходе на подвкладку «Мои сделки» (если `state.deals` пуст)
  - При нажатии кнопки «🔄 Обновить»
- **Как отображаются:** через `renderDeals()` → `createDealCard(deal)` — карточки в `#deals-list`
- **Фильтрация:** клиентская — по полям `filter-status`, `filter-client`, `filter-month`

### `openDealModal(dealId)` — детали сделки

- **Endpoint:** `GET /deal/{dealId}` (только если сделки нет в `state.deals`)
- **Как отображаются:** через `renderDealDetail(deal)` — 5 разделов в модальном окне

### `loadExpenses()` — список расходов

- **Endpoint:** `GET /expenses`
- **Когда вызывается:** при нажатии «🔄 Загрузить» на вкладке «Расходы»
- **Как отображаются:** карточки `.expense-row` в `#expenses-list`

### `loadJournal()` — журнал действий

- **Endpoint:** `GET /journal?limit=50`
- **Когда вызывается:** при нажатии «🔄 Загрузить» на вкладке «Журнал»
- **Как отображаются:** карточки `.journal-row` в `#journal-list` (действие, временная метка, пользователь, объект, детали)

### `checkConnections()` — статус подключений

- **Endpoints:** `GET /health`, `GET /settings`
- **Когда вызывается:** при переходе на вкладку «Настройки»
- **Как отображается:** цветные индикаторы (зелёный/красный) для Telegram, API, Google Sheets

---

## 8. Авторизация

### Telegram WebApp initData

```javascript
// miniapp/app.js
const tg = window.Telegram?.WebApp;

function initTelegram() {
  tg.ready();
  tg.expand();
  telegramUser = tg.initDataUnsafe?.user || null;
}

function getTelegramInitData() {
  return tg?.initData || '';
}
```

- `tg.initData` — строка с подписанными данными от Telegram (HMAC-SHA256)
- `tg.initDataUnsafe.user` — объект с `id`, `first_name`, `last_name`, `username`, `language_code`

### Передача на бэкенд

В каждом запросе через `apiFetch`:

```javascript
headers['X-Telegram-Init-Data'] = tg.initData;   // подпись Telegram
headers['X-User-Role'] = localStorage.getItem('user_role');  // роль из пароля
```

### Авторизация по паролю (основной метод)

1. Пользователь выбирает **роль** из 4 кнопок
2. Вводит **пароль** в текстовое поле
3. Нажимает «Войти» → `POST /auth/role-login` с `{ role, password }`
4. При успехе сервер возвращает `{ success: true, role, role_label }`
5. Роль сохраняется в `localStorage('user_role')` и `localStorage('user_role_label')`
6. Вызывается `enterApp(role)` — приложение открывается

### Проверка при повторном открытии

```javascript
// При DOMContentLoaded:
const savedRole = localStorage.getItem('user_role');
if (savedRole) {
  await enterApp(savedRole);  // пропускает экран авторизации
} else {
  showAuthScreen();
}
```

### Выход из системы

- Кнопка «🚪 Сменить роль» — очищает `localStorage`, вызывает `location.reload()`

---

## 9. Роли

Ролевая система **реализована** на уровне Mini App.

### Список ролей

| Роль | Ключ | Метка |
|------|------|-------|
| Менеджер | `manager` | Менеджер |
| Операционный директор | `operations_director` | Операционный директор |
| Бухгалтерия | `accounting` | Бухгалтерия |
| Администратор | `admin` | Администратор |
| Бухгалтер (legacy) | `accountant` | Бухгалтер |
| Руководитель отдела продаж (legacy) | `head_of_sales` | Руководитель отдела продаж |

### Доступ к вкладкам по ролям (`ROLE_TABS`)

| Вкладка | manager | operations_director | accounting | admin |
|---------|:-------:|:-------------------:|:----------:|:-----:|
| 💰 Финансы | ✅ | ✅ | ✅ | ✅ |
| 🏭 Billing | ✅ | ✅ | — | ✅ |
| 📉 Расходы | ✅ | ✅ | ✅ | ✅ |
| 📥 Отчёты | — | ✅ | ✅ | ✅ |
| 📜 Журнал | — | ✅ | ✅ | ✅ |
| ⚙️ Настройки | ✅ | ✅ | ✅ | ✅ |

### Механизм применения ролей

- Вкладки строятся динамически в `buildTabs(role)` — пользователь физически не видит недоступные вкладки
- Роль передаётся в каждый API-запрос через заголовок `X-User-Role`
- Бэкенд несёт ответственность за серверную авторизацию по этому заголовку

### Матрица разрешений (`frontend/js/permissions.js`)

В директории `frontend/` также присутствует более детальная клиентская матрица разрешений (`PERMISSION_MATRIX`):

| Разрешение | admin | sales | accounting | viewer |
|-----------|:-----:|:-----:|:----------:|:------:|
| canViewAllDeals | ✅ | — | ✅ | ✅ |
| canCreateDeals | ✅ | ✅ | — | — |
| canDeleteDeals | ✅ | — | — | — |
| canEditSalesFields | ✅ | ✅ | — | — |
| canEditAccountingFields | ✅ | — | ✅ | — |
| canViewJournal | ✅ | — | ✅ | ✅ |
| canViewAnalytics | ✅ | — | ✅ | ✅ |
| canViewSettings | ✅ | — | — | — |
| canManageUsers | ✅ | — | — | — |

---

## 10. Работа с Google Sheets

Mini App взаимодействует с Google Sheets **косвенно** — через API-эндпоинты бэкенда. Прямых вызовов Google Sheets API из JS нет.

### Эндпоинты, запись в Google Sheets

| Endpoint | Действие | Лист Google Sheets |
|----------|----------|--------------------|
| `POST /deal/create` | Создание новой строки сделки | «Учёт сделок» |
| `POST /billing/{warehouse}` | Запись billing-данных по складу | «Warehouse_MSK» / «Warehouse_NSK» / «Warehouse_EKB» |
| `POST /billing/payment/mark` | Обновление поля «Оплачено» в строке сделки | «Учёт сделок» |
| `POST /expenses` | Добавление строки расхода | отдельный лист расходов |

### Эндпоинты, чтение из Google Sheets

| Endpoint | Действие | Лист Google Sheets |
|----------|----------|--------------------|
| `GET /settings` | Загрузка справочников (статусы, клиенты, менеджеры и др.) | лист справочников |
| `GET /deal/user` | Список сделок пользователя | «Учёт сделок» |
| `GET /deal/{id}` | Детали одной сделки | «Учёт сделок» |
| `GET /expenses` | Список расходов | лист расходов |
| `GET /journal?limit=50` | Последние 50 записей журнала | «Журнал» |

### Эндпоинты, генерация отчётов

| Endpoint | Описание |
|----------|----------|
| `GET /reports/warehouse/{wh}?fmt=csv|xlsx` | Выгрузка billing-данных склада |
| `GET /reports/clients?fmt=csv|xlsx` | Выгрузка данных по клиентам |
| `GET /reports/expenses?fmt=csv|xlsx` | Выгрузка расходов |
| `GET /reports/profit?fmt=csv|xlsx` | Выгрузка данных по прибыли |

> Данные для отчётов читаются из Google Sheets бэкендом и конвертируются в CSV/XLSX перед отдачей клиенту.
