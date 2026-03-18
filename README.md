# tg_bot_finans

Telegram Mini App — финансовая система учёта сделок на базе FastAPI + Google Sheets.

---

## Архитектура

```
tg_bot_finans/
├── backend/              # FastAPI backend
│   ├── main.py           # Entry point, CORS, static serving
│   ├── models/           # Pydantic request/response models
│   ├── routers/          # API route handlers
│   └── services/         # Business logic & Google Sheets layer
│       ├── sheets_service.py     # Low-level gspread client + header helpers
│       ├── settings_service.py   # "Настройки" sheet parser + role mapping
│       ├── deals_service.py      # Deal CRUD, filtering, ID generation
│       ├── journal_service.py    # Audit log writer
│       ├── permissions.py        # Role-based field permission matrix
│       └── telegram_auth.py      # Telegram initData validation
├── bot/                  # Telegram bot (aiogram 3)
├── config/               # App configuration (pydantic-settings)
├── miniapp/              # Frontend: HTML/CSS/JS
├── tests/                # Pytest unit tests for pure helpers
├── requirements.txt
└── .env.example
```

---

## Переменные окружения

| Переменная                      | Описание                                                         |
|---------------------------------|------------------------------------------------------------------|
| `TELEGRAM_BOT_TOKEN`            | Токен бота от @BotFather                                         |
| `WEBAPP_URL`                    | Публичный HTTPS URL Mini App (например `https://app.example.com`) |
| `GOOGLE_SERVICE_ACCOUNT_JSON`   | **Полное содержимое** JSON-ключа сервисного аккаунта Google      |
| `GOOGLE_SHEETS_SPREADSHEET_ID`  | ID Google Spreadsheet                                            |
| `API_BASE_URL`                  | Публичный URL backend API (например `https://api.example.com`)   |

> **Важно:** Файл `credentials.json` или `service_account.json` **не требуется**.
> Весь JSON ключа сервисного аккаунта передаётся через переменную
> `GOOGLE_SERVICE_ACCOUNT_JSON`.

---

## Архитектура запуска (один процесс)

FastAPI и Telegram бот работают **в одном процессе**. Бот запускается
автоматически вместе с FastAPI через механизм `lifespan`. Опрос Telegram API
(polling) выполняется в фоне через `asyncio.create_task`, не блокируя FastAPI.

Единственная команда запуска:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Эта команда запускает **одновременно**:
- FastAPI (REST API + Mini App)
- Telegram бот (polling, ответ на `/start`, кнопка «🚀 Открыть Mini App»)

Кнопка «🚀 Открыть Mini App» открывает Telegram Mini App по URL из
переменной окружения `WEBAPP_URL`.

---

## Быстрый старт (локальная разработка)

1. Скопируйте `.env.example` в `.env` и заполните все переменные:
   ```bash
   cp .env.example .env
   ```
2. В `GOOGLE_SERVICE_ACCOUNT_JSON` вставьте полное содержимое JSON-ключа
   сервисного аккаунта (в одну строку или как многострочный JSON).
3. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
4. Запустите приложение (FastAPI + бот в одном процессе):
   ```bash
   uvicorn backend.main:app --reload
   ```

---

## Деплой на Timeweb

1. В панели Timeweb App добавьте переменные окружения:
   - `TELEGRAM_BOT_TOKEN` — токен бота
   - `WEBAPP_URL` — URL Mini App (должен быть HTTPS), используется для кнопки бота
   - `GOOGLE_SERVICE_ACCOUNT_JSON` — полный JSON ключа сервисного аккаунта
   - `GOOGLE_SHEETS_SPREADSHEET_ID` — ID таблицы Google Sheets
   - `API_BASE_URL` — публичный URL вашего backend
2. Команда запуска (запускает FastAPI **и** Telegram бота):
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```
3. Файл `.env` и файлы ключей (`credentials.json`, `service_account.json`)
   **не нужны** на сервере — все значения берутся из переменных окружения.
4. Убедитесь, что `WEBAPP_URL` указывает на реальный HTTPS URL Mini App, а
   `API_BASE_URL` — на реальный URL backend.

> **Безопасность:** Никогда не коммитьте реальные токены и ключи в репозиторий.
> `.env` и файлы ключей добавлены в `.gitignore`.

---

## Настройка GOOGLE_SERVICE_ACCOUNT_JSON

1. Создайте проект в [Google Cloud Console](https://console.cloud.google.com/).
2. Включите **Google Sheets API** и **Google Drive API**.
3. Создайте **Service Account** и скачайте JSON-ключ.
4. Поделитесь таблицей с email сервисного аккаунта (роль «Редактор»).
5. Скопируйте **всё содержимое** JSON-файла в переменную окружения
   `GOOGLE_SERVICE_ACCOUNT_JSON`.

---

## Структура Google Spreadsheet

Книга должна содержать **три листа** с точными именами:

| Лист                | Назначение                        |
|---------------------|-----------------------------------|
| `Настройки`         | Справочники и роли пользователей  |
| `Учёт сделок`       | Основная таблица сделок           |
| `Журнал действий`   | Неизменяемый журнал аудита        |

---

## Лист «Настройки»

### Формат

Лист организован в **блоки**. Каждый блок начинается со строки-заголовка
вида `[Название секции]`, затем следуют значения (по одному в строке, в
колонке A). Пустая строка или новый заголовок завершают блок.

### Обязательные секции

```
[Статусы сделок]
Новая
В работе
Завершена
Отменена
Приостановлена

[Направления бизнеса]
Фулфилмент
Логистика
Хранение

[Клиенты]
ООО Альфа
ИП Петров

[Менеджеры]
Иван Петров
Мария Смирнова

[Наличие НДС]
с НДС
без НДС

[Источники]
Входящий
Рекомендация
Повторный клиент

[Роли пользователей]
telegram_user_id | full_name | role | active
123456789 | Иван Петров | manager | TRUE
987654321 | Анна Смирнова | accountant | TRUE
111222333 | Дмитрий Козлов | operations_director | TRUE
444555666 | Елена Новикова | head_of_sales | TRUE
```

### Роли пользователей

Секция `[Роли пользователей]` содержит таблицу с pipe-разделителем.
Первая строка после заголовка — названия колонок.

| Колонка            | Описание                                         |
|--------------------|--------------------------------------------------|
| `telegram_user_id` | Числовой Telegram ID пользователя                |
| `full_name`        | Полное имя (должно совпадать с полем «Менеджер») |
| `role`             | Одна из допустимых ролей (см. ниже)              |
| `active`           | `TRUE` — активен; любое другое значение — нет    |

**Допустимые роли:**

| Роль                  | Описание                                         |
|-----------------------|--------------------------------------------------|
| `manager`             | Только свои сделки; редактирует бизнес-поля      |
| `accountant`          | Все сделки; редактирует бухгалтерские поля       |
| `operations_director` | Все сделки + аналитика; редактирует все поля     |
| `head_of_sales`       | Все сделки + продажи; редактирует все поля       |

Если пользователь не найден или `active != TRUE` — доступ запрещён
(`no_access`).

---

## Лист «Учёт сделок»

Первая строка — заголовки колонок. Сервис использует **header-based mapping**:
при каждом запросе читается заголовочная строка и столбцы определяются по
названию, а не по позиции.

### Ожидаемые заголовки (порядок рекомендован, но не обязателен)

| Колонка | Заголовок                       | Тип          |
|---------|---------------------------------|--------------|
| A       | `ID сделки`                     | строка       |
| B       | `Статус сделки`                 | строка       |
| C       | `Направление бизнеса`           | строка       |
| D       | `Клиент`                        | строка       |
| E       | `Менеджер`                      | строка       |
| F       | `Начислено с НДС`               | число        |
| G       | `Наличие НДС`                   | строка       |
| H       | `Оплачено`                      | число        |
| I       | `Дата начала проекта`           | YYYY-MM-DD   |
| J       | `Дата окончания проекта`        | YYYY-MM-DD   |
| K       | `Дата выставления акта`         | YYYY-MM-DD   |
| L       | `Переменный расход 1`           | число        |
| M       | `Переменный расход 2`           | число        |
| N       | `Бонус менеджера %`             | число        |
| O       | `Бонус менеджера выплачено`     | число        |
| P       | `Общепроизводственный расход`   | число        |
| Q       | `Источник`                      | строка       |
| R       | `Документ/ссылка`               | строка       |
| S       | `Комментарий`                   | строка       |

### Генерация ID сделок

Формат: `DEAL-000001`

Алгоритм:
1. Считываются все значения колонки `ID сделки`.
2. Из строк вида `DEAL-XXXXXX` извлекается числовой суффикс.
3. Находится максимальное число; следующий ID = max + 1, отформатированный как
   6-значное число с ведущими нулями.
4. Некорректные строки (не соответствующие паттерну) игнорируются.

Генерация выполняется под `threading.Lock` для безопасности при
конкурентных запросах.

---

## Лист «Журнал действий»

Используется как **неизменяемый журнал аудита**. Записи только добавляются,
никогда не удаляются.

### Заголовки (создаются автоматически, если лист пуст)

| Колонка            | Описание                                |
|--------------------|-----------------------------------------|
| `timestamp`        | UTC время события `YYYY-MM-DD HH:MM:SS` |
| `telegram_user_id` | Telegram ID пользователя               |
| `full_name`        | Полное имя пользователя                |
| `user_role`        | Роль в момент действия                 |
| `action`           | Тип действия (см. ниже)                |
| `deal_id`          | ID затронутой сделки                   |
| `changed_fields`   | JSON-список изменённых полей           |
| `payload_summary`  | Краткое описание изменений             |

### Типы действий

| Действие                   | Когда записывается                         |
|----------------------------|--------------------------------------------|
| `create_deal`              | Создание новой сделки                      |
| `update_deal`              | Успешное обновление сделки                 |
| `forbidden_edit_attempt`   | Попытка изменить поле, недоступное роли    |
| `forbidden_update_attempt` | Попытка изменить чужую сделку (менеджер)   |

---

## API endpoints

| Метод  | Путь                  | Описание                                    |
|--------|-----------------------|---------------------------------------------|
| POST   | `/deal/create`        | Создать сделку                              |
| GET    | `/deal/all`           | Все сделки (accountant+)                    |
| GET    | `/deal/user`          | Сделки текущего пользователя                |
| GET    | `/deal/filter`        | Фильтрация сделок по параметрам             |
| GET    | `/deal/{deal_id}`     | Одна сделка по ID                           |
| PUT    | `/deal/{deal_id}`     | Обновить сделку (с проверкой прав)          |
| GET    | `/settings`           | Справочные данные из «Настройки»            |
| POST   | `/auth/validate`      | Валидация Telegram initData + роль          |
| GET    | `/auth/role`          | Роль и права текущего пользователя          |
| GET    | `/health`             | Проверка работоспособности                  |

Аутентификация: заголовок `x-telegram-init-data` (Telegram WebApp `initData`).

### Параметры фильтрации `/deal/filter`

| Параметр             | Тип     | Описание                           |
|----------------------|---------|------------------------------------|
| `manager`            | string  | Точное имя менеджера               |
| `client`             | string  | Точное название клиента            |
| `status`             | string  | Статус сделки                      |
| `business_direction` | string  | Направление бизнеса                |
| `month`              | string  | Месяц в формате `YYYY-MM`          |
| `paid`               | boolean | `true` — оплаченные, `false` — нет |

---

## Матрица прав по ролям

### Видимые данные

| Роль                  | Видит сделки           |
|-----------------------|------------------------|
| `manager`             | Только свои            |
| `accountant`          | Все                    |
| `operations_director` | Все                    |
| `head_of_sales`       | Все                    |

### Редактируемые поля

| Поле                        | manager | accountant | director | head |
|-----------------------------|:-------:|:----------:|:--------:|:----:|
| status                      | ✅      |            | ✅       | ✅   |
| business_direction          | ✅      |            | ✅       | ✅   |
| client                      | ✅      |            | ✅       | ✅   |
| manager                     | ✅      |            | ✅       | ✅   |
| charged_with_vat            | ✅      |            | ✅       | ✅   |
| vat_type                    | ✅      |            | ✅       | ✅   |
| project_start_date          | ✅      |            | ✅       | ✅   |
| project_end_date            | ✅      |            | ✅       | ✅   |
| source                      | ✅      |            | ✅       | ✅   |
| document_link               | ✅      |            | ✅       | ✅   |
| comment                     | ✅      |            | ✅       | ✅   |
| paid                        |         | ✅         | ✅       | ✅   |
| act_date                    |         | ✅         | ✅       | ✅   |
| variable_expense_1          |         | ✅         | ✅       | ✅   |
| variable_expense_2          |         | ✅         | ✅       | ✅   |
| manager_bonus_percent       |         | ✅         | ✅       | ✅   |
| manager_bonus_paid          |         | ✅         | ✅       | ✅   |
| general_production_expense  |         | ✅         | ✅       | ✅   |

---

## Тесты

```bash
pytest tests/ -v
```

Тесты покрывают чистые вспомогательные функции без обращения к Google Sheets:

- Генерация и разбор ID сделок
- Нормализация дат и чисел
- Header-mapping хелперы (`row_to_dict`, `dict_to_row`)
- Парсер секций листа «Настройки»
- Матрица прав по ролям
- Фильтрация сделок

---

## 21. FULL FUNCTION INDEX

Полный список значимых функций фронтенда с описанием назначения, места вызова и
зависимостей.

### `frontend/js/api.js` — HTTP-клиент

| Функция | Назначение | Вызывается из | Вызывает |
|---------|-----------|---------------|---------|
| `ApiClient.constructor(baseUrl)` | Создаёт экземпляр клиента | `App.constructor()` | — |
| `ApiClient.setUser(userId)` | Устанавливает `X-User-Id` | `App._setActiveUser()` | — |
| `ApiClient._headers()` | Формирует заголовки запроса | `ApiClient._request()` | — |
| `ApiClient._request(method, path, body)` | Обёртка над `fetch` с обработкой ошибок | Все публичные методы `ApiClient` | `fetch` |
| `ApiClient.getMe()` | `GET /api/me` | `App._setActiveUser()` | `_request()` |
| `ApiClient.getDemoUsers()` | `GET /api/demo-users` | `App._setupUser()`, `SettingsScreen.load()` | `_request()` |
| `ApiClient.getDeals()` | `GET /api/deals` | `DealsScreen.load()` | `_request()` |
| `ApiClient.getDeal(id)` | `GET /api/deals/{id}` | — | `_request()` |
| `ApiClient.createDeal(data)` | `POST /api/deals` | `initAddDealModal()` handler | `_request()` |
| `ApiClient.updateDeal(id, data)` | `PATCH /api/deals/{id}` | `DealsScreen._saveDeal()` | `_request()` |
| `ApiClient.deleteDeal(id)` | `DELETE /api/deals/{id}` | `DealsScreen._deleteDeal()` | `_request()` |
| `ApiClient.getJournal()` | `GET /api/journal` | `JournalScreen.load()` | `_request()` |
| `ApiClient.createJournalEntry(data)` | `POST /api/journal` | — | `_request()` |
| `ApiClient.getAnalyticsSummary()` | `GET /api/analytics/summary` | `AnalyticsScreen.load()` | `_request()` |
| `ApiClient.getAnalyticsByMonth()` | `GET /api/analytics/deals-by-month` | `AnalyticsScreen.load()` | `_request()` |

---

### `frontend/js/permissions.js` — Матрица прав

| Функция | Назначение | Вызывается из | Вызывает |
|---------|-----------|---------------|---------|
| `Permissions.constructor(role)` | Загружает матрицу прав для роли | `App._setActiveUser()` | — |
| `Permissions.role` (getter) | Возвращает строку роли | Различные места | — |
| `Permissions.roleLabel` (getter) | Возвращает локализованное название роли | `App._setActiveUser()` | — |
| `Permissions.has(permission)` | Проверяет одно право | Все методы `can*()` | — |
| `Permissions.canViewAllDeals()` | Видит ли все сделки или только свои | `DealsScreen._render()` | `has()` |
| `Permissions.canEditSalesFields()` | Может ли редактировать поля продаж | `DealsScreen._renderModal()`, `applyFormRestrictions()` | `has()` |
| `Permissions.canEditAccountingFields()` | Может ли редактировать бухгалтерские поля | `DealsScreen._renderModal()`, `JournalScreen._render()` | `has()` |
| `Permissions.canViewJournal()` | Видит ли вкладку «Журнал» | `App._buildTabs()`, `App._isTabAllowed()` | `has()` |
| `Permissions.canViewAnalytics()` | Видит ли вкладку «Аналитика» | `App._buildTabs()`, `App._isTabAllowed()` | `has()` |
| `Permissions.canCreateDeals()` | Может ли создавать сделки | `DealsScreen._render()` | `has()` |
| `Permissions.canDeleteDeals()` | Может ли удалять сделки | `DealsScreen._renderModal()` | `has()` |
| `Permissions.canViewSettings()` | Видит ли вкладку «Настройки» | `App._buildTabs()`, `App._isTabAllowed()` | `has()` |
| `Permissions.applyFormRestrictions(formEl)` | Отключает поля формы согласно правам | `DealsScreen._renderModal()` | `_setFieldAccess()` |
| `Permissions._setFieldAccess(el, editable)` | Устанавливает `disabled`/`readOnly` для поля | `applyFormRestrictions()` | — |

---

### `frontend/js/app.js` — Главный модуль (простой Mini App)

| Функция | Назначение | Вызывается из | Вызывает |
|---------|-----------|---------------|---------|
| `formatMoney(n)` | Форматирует число как рубли `₽` | `DealsScreen._dealCard()`, `AnalyticsScreen._render()`, `JournalScreen._render()` | `Number.toLocaleString()` |
| `formatDate(s)` | Форматирует ISO-дату для отображения | `DealsScreen._dealCard()`, `DealsScreen._renderModal()`, `JournalScreen._render()` | `Date.toLocaleDateString()` |
| `showToast(msg, type)` | Показывает всплывающее уведомление | Все экраны | DOM API |
| `showLoading(show)` | Показывает/скрывает оверлей загрузки | `App.init()`, `App._navigate()`, `DealsScreen._saveDeal()`, `DealsScreen._deleteDeal()`, `initAddDealModal()` | DOM API |
| `App.constructor()` | Инициализирует состояние приложения | `DOMContentLoaded` handler | `ApiClient`, `Permissions` |
| `App.init()` | Запускает инициализацию, настраивает пользователя и вкладки | `DOMContentLoaded` | `_setupUser()`, `_buildTabs()`, `_initScreens()`, `_navigate()` |
| `App._setupUser()` | Загружает демо-пользователей и устанавливает активного | `App.init()` | `api.getDemoUsers()`, `_renderDemoSelector()`, `_setActiveUser()` |
| `App._setActiveUser(userId)` | Переключает роль/пользователя | `_setupUser()`, `_renderDemoSelector()` change handler | `api.setUser()`, `api.getMe()`, `_buildTabs()` |
| `App._renderDemoSelector(users)` | Рендерит выпадающий список ролей для демо | `_setupUser()` | DOM API, `_setActiveUser()` |
| `App._buildTabs()` | Строит нижнюю навигацию согласно правам | `App.init()`, `App._setActiveUser()`, `App._navigate()` | `Permissions` методы, DOM API |
| `App._isTabAllowed(tabId)` | Проверяет, доступна ли вкладка текущей роли | `_renderDemoSelector()` change handler | `Permissions` методы |
| `App._initScreens()` | Создаёт экземпляры экранов | `App.init()` | `new DealsScreen()`, `JournalScreen()`, `AnalyticsScreen()`, `SettingsScreen()` |
| `App._navigate(tabId)` | Переключает видимый экран и загружает данные | `_buildTabs()` tab click, `App.init()` | DOM API, `showLoading()`, `screen.load()` |
| `DealsScreen.constructor(app)` | Создаёт экран сделок | `App._initScreens()` | — |
| `DealsScreen.load()` | Загружает список сделок из API | `App._navigate()`, `DealsScreen._saveDeal()`, `DealsScreen._deleteDeal()`, `initAddDealModal()` | `api.getDeals()`, `_render()` |
| `DealsScreen._render()` | Рендерит карточки сделок | `DealsScreen.load()` | `_dealCard()`, DOM API, `_openDeal()` |
| `DealsScreen._dealCard(deal)` | Генерирует HTML карточки сделки | `DealsScreen._render()` | `formatMoney()`, `formatDate()` |
| `DealsScreen._openDeal(id)` | Открывает модальное окно редактирования | `.deal-card` click | `_renderModal()` |
| `DealsScreen._renderModal(deal)` | Рендерит форму редактирования сделки | `_openDeal()` | `perms.applyFormRestrictions()`, `_saveDeal()`, `_deleteDeal()` |
| `DealsScreen._saveDeal(id, formEl)` | Сохраняет изменения через `PATCH /api/deals/{id}` | `#btn-save-deal` click | `api.updateDeal()`, `showToast()`, `showLoading()`, `load()` |
| `DealsScreen._deleteDeal(id)` | Удаляет сделку через `DELETE /api/deals/{id}` | `#btn-delete-deal` click | `api.deleteDeal()`, `showToast()`, `showLoading()`, `load()` |
| `JournalScreen.constructor(app)` | Создаёт экран журнала | `App._initScreens()` | — |
| `JournalScreen.load()` | Загружает записи журнала | `App._navigate()` | `api.getJournal()`, `_render()` |
| `JournalScreen._render(entries)` | Рендерит записи журнала | `load()` | `formatDate()`, `formatMoney()` |
| `AnalyticsScreen.constructor(app)` | Создаёт экран аналитики | `App._initScreens()` | — |
| `AnalyticsScreen.load()` | Загружает данные аналитики | `App._navigate()` | `api.getAnalyticsSummary()`, `api.getAnalyticsByMonth()`, `_render()` |
| `AnalyticsScreen._render(summary, byMonth)` | Рендерит KPI и таблицу по месяцам | `load()` | `formatMoney()` |
| `SettingsScreen.constructor(app)` | Создаёт экран настроек | `App._initScreens()` | — |
| `SettingsScreen.load()` | Загружает и отображает список пользователей | `App._navigate()` | `api.getDemoUsers()`, `_formatPerms()` |
| `SettingsScreen._formatPerms(perms)` | Форматирует права пользователя в HTML-теги | `load()` | — |
| `initAddDealModal(app)` | Привязывает обработчики модального окна «Новая сделка» | `DOMContentLoaded` | DOM API, `api.createDeal()`, `showToast()`, `showLoading()`, `app.screens.deals.load()` |

---

### `miniapp/app.js` — Расширенный Mini App

| Функция | Назначение | Вызывается из | Вызывает |
|---------|-----------|---------------|---------|
| `initTelegram()` | Инициализирует Telegram WebApp SDK, применяет тему | `init()` | `tg.ready()`, `tg.expand()`, `renderUserAvatar()` |
| `renderUserAvatar(user)` | Отрисовывает инициалы пользователя в аватаре | `initTelegram()` | `getInitials()` |
| `getInitials(first, last)` | Извлекает инициалы из имени | `renderUserAvatar()` | — |
| `getTelegramInitData()` | Возвращает `tg.initData` для авторизации | `apiFetch()` | — |
| `apiFetch(path, options)` | Обёртка над `fetch` с Telegram-заголовками (`X-Telegram-Init-Data`, `X-Telegram-Id`, `X-User-Role`) | Все функции, вызывающие API | `fetch`, `getTelegramInitData()` |
| `initTabs()` | Привязывает клики на `.tab-btn` к `switchTab()` | `init()` | `switchTab()` |
| `switchTab(tabId)` | Переключает `.tab-panel` и навигационные кнопки | `.tab-btn` click (простые вкладки), `initSubnav()` | `loadDeals()`, `checkConnections()`, `renderUserInfoCard()` |
| `loadSettings()` | Загружает справочники с `/settings/enriched`, кэширует в `state.settings` | `enterApp()` | `apiFetch()`, `populateSelects()`, `updateSettingsStats()` |
| `populateSelects(data)` | Заполняет все выпадающие списки данными из справочников | `loadSettings()` | `fillSelect()`, `initDependentDealDropdowns()` |
| `fillSelect(id, options, hasAll)` | Заполняет `<select>` по ID: строки или `{id,name}` | `populateSelects()`, `loadClientsSettings()`, `loadManagersSettings()`, `loadDirectionsSettings()`, `loadStatusesSettings()` | DOM API |
| `populateSelectFromObjects(selectEl, items)` | Заполняет `<select>` объектами `{id, name}` | `loadDealsFiltered()` | DOM API |
| `loadDealsFiltered(dealSelectId, directionId, clientId)` | Загружает сделки с фильтрами direction/client в `<select>` | `initDependentDealDropdowns()` | `apiFetch('/deals')`, `populateSelectFromObjects()` |
| `initDependentDealDropdowns(dirSelectId, clientSelectId, dealSelectId)` | Инициализирует связанные выпадающие direction→client→deal | `populateSelects()`, `initBillingForm()`, `initExpensesForm()` | `loadDealsFiltered()` |
| `updateSettingsStats(data)` | Обновляет счётчики на вкладке «Настройки» | `loadSettings()` | `setEl()` |
| `initDealForm()` | Привязывает обработчики формы создания сделки | `init()` | DOM API, `handleFormSubmit()`, `clearForm()`, `showForm()`, `updateSummary()`, `updateChargedLabel()`, `updateDealVat()` |
| `updateSummary()` | Обновляет блок предпросмотра в форме сделки | change events полей `client`, `charged_with_vat`, `status`, `manager` | `getFieldValue()`, `setEl()`, `formatCurrency()` |
| `handleFormSubmit(e)` | Обрабатывает submit формы сделки | `#deal-form` submit | `validateForm()`, `collectFormDataSql()`, `apiFetch('/deals/create')`, `showSuccessScreen()`, `showToast()` |
| `validateForm()` | Проверяет заполнение обязательных полей | `handleFormSubmit()` | `getFieldValue()` |
| `collectFormData()` | Собирает данные формы как строки (устаревший путь) | — (не используется в основном потоке) | `getFieldValue()` |
| `collectFormDataSql()` | Собирает данные формы как числовые ID для SQL-эндпоинтов | `handleFormSubmit()` | `getFieldValue()` |
| `setSubmitting(isLoading)` | Блокирует/разблокирует кнопку отправки | `handleFormSubmit()` | DOM API |
| `clearForm()` | Сбрасывает форму и состояния ошибок | `#clear-btn` click, `showForm()` | DOM API, `showToast()` |
| `showSuccessScreen(dealId)` | Отображает экран успеха с ID сделки | `handleFormSubmit()` | `setEl()` |
| `showForm()` | Возвращает форму из экрана успеха | `#new-deal-btn` click, `initSubnav()` `view-deals-btn` | `clearForm()` |
| `initMyDeals()` | Привязывает фильтры и кнопку обновления списка сделок | `init()` | DOM API, `loadDeals()`, `renderDeals()` |
| `loadDeals()` | Загружает сделки с `GET /deals` | Tab switch к `my-deals`, `#refresh-deals-btn` click | `apiFetch()`, `renderDeals()` |
| `renderDeals()` | Фильтрует и рендерит карточки сделок | `loadDeals()`, filter change events | `createDealCard()`, `showDealsEmpty()` |
| `createDealCard(deal)` | Создаёт DOM-элемент карточки сделки | `renderDeals()` | `formatCurrency()`, `formatDate()`, `escHtml()`, `openDealModal()`, `copyToClipboard()` |
| `showDealsLoading(show)` | Показывает/скрывает индикатор загрузки сделок | `loadDeals()` | DOM API |
| `showDealsEmpty(show)` | Показывает/скрывает заглушку «нет сделок» | `renderDeals()`, `loadDeals()` | DOM API |
| `clearDealsList()` | Очищает контейнер списка сделок | `loadDeals()`, `renderDeals()` | DOM API |
| `initDealEdit()` | Инициализирует форму редактирования сделки | `enterApp()` | DOM API, `onEditDealSelected()`, `saveEditedDeal()`, `switchSubnav()` |
| `loadDealsForEdit()` | Загружает сделки в `<select>` раздела «Редактировать» | `initSubnav()` subnav switch | `apiFetch('/deals')` |
| `onEditDealSelected(dealId)` | Загружает выбранную сделку и заполняет поля редактирования | `#edit-deal-select` change | `apiFetch('/deals/{id}')`, `showToast()` |
| `saveEditedDeal()` | Сохраняет изменения через `PATCH /deals/update/{id}` | `#edit-deal-save-btn` click | `apiFetch()`, `showToast()` |
| `switchSubnav(subId)` | Переключает под-панели внутри вкладки «Финансы» | `#edit-deal-back-btn` click, `initSubnav()` | DOM API |
| `openDealModal(dealId)` | Открывает модальное окно с деталями сделки | `.deal-card` click, `[data-action=view]` click | `apiFetch('/deals/{id}')`, `renderDealDetail()` |
| `closeDealModal()` | Закрывает модальное окно | `#modal-close-btn` click, overlay click, Escape | DOM API |
| `renderDealDetail(deal)` | Формирует HTML секций с полями сделки | `openDealModal()` | `formatCurrency()`, `formatDate()`, `escHtml()` |
| `initModal()` | Привязывает закрытие модального окна | `init()` | `closeDealModal()` |
| `checkConnections()` | Проверяет доступность Telegram, API и Google Sheets | `switchMainTab('settings-tab')` | `apiFetch('/health')`, `apiFetch('/settings')`, `setConnectionStatus()` |
| `setConnectionStatus(key, ok, text)` | Обновляет индикатор подключения | `checkConnections()` | DOM API |
| `renderUserInfoCard()` | Отображает данные Telegram-пользователя | `switchMainTab('settings-tab')`, `enterApp()` | `setEl()`, `escHtml()` |
| `showToast(message, type, duration)` | Создаёт и показывает всплывающее уведомление | Весь файл | DOM API |
| `getFieldValue(id)` | Возвращает обрезанное значение поля по ID | Формы, валидация | DOM API |
| `setEl(id, value)` | Устанавливает `textContent` элемента | Повсеместно | DOM API |
| `escHtml(str)` | Экранирует HTML-спецсимволы | Все функции рендеринга | — |
| `formatCurrency(value)` | Форматирует число как рубли через `Intl.NumberFormat` | Карточки, модальные окна, аналитика | — |
| `formatDate(dateStr)` | Форматирует строку даты через `Intl.DateTimeFormat` | Карточки, модальные окна | — |
| `copyToClipboard(text)` | Копирует текст через `navigator.clipboard` или fallback | `[data-action=copy]` click | `showToast()` |
| `initSettingsManagement()` | Инициализирует CRUD для клиентов/менеджеров/направлений/статусов | `enterApp()` | `loadClientsSettings()`, `loadManagersSettings()`, `loadDirectionsSettings()`, `loadStatusesSettings()` |
| `loadClientsSettings()` | Загружает клиентов с `GET /settings/clients` | `initSettingsManagement()`, `#refresh-clients-btn`, `switchMainTab('settings-tab')` | `apiFetch()`, `renderRefList()`, `fillSelect()` |
| `addClient()` | Создаёт клиента через `POST /settings/clients` | `#add-client-btn` click | `apiFetch()`, `showToast()`, `loadClientsSettings()` |
| `deleteClient(clientId, clientName)` | Удаляет клиента через `DELETE /settings/clients/{id}` | `.ref-delete-btn` click | `apiFetch()`, `showToast()`, `loadClientsSettings()` |
| `loadManagersSettings()` | Загружает менеджеров с `GET /settings/managers` | `initSettingsManagement()`, `#refresh-managers-btn`, `switchMainTab('settings-tab')` | `apiFetch()`, `renderRefList()`, `fillSelect()` |
| `addManager()` | Создаёт менеджера через `POST /settings/managers` | `#add-manager-btn` click | `apiFetch()`, `showToast()`, `loadManagersSettings()` |
| `deleteManager(managerId, managerName)` | Удаляет менеджера через `DELETE /settings/managers/{id}` | `.ref-delete-btn` click | `apiFetch()`, `showToast()`, `loadManagersSettings()` |
| `loadDirectionsSettings()` | Загружает направления с `GET /settings/directions` | `initSettingsManagement()`, `#refresh-directions-btn`, `switchMainTab('settings-tab')` | `apiFetch()`, `renderRefList()`, `fillSelect()` |
| `addDirection()` | Добавляет направление через `POST /settings/directions` | `#add-direction-btn` click | `apiFetch()`, `showToast()`, `loadDirectionsSettings()` |
| `deleteDirection(direction)` | Удаляет направление через `DELETE /settings/directions/{name}` | `.ref-delete-btn` click | `apiFetch()`, `showToast()`, `loadDirectionsSettings()` |
| `loadStatusesSettings()` | Загружает статусы с `GET /settings/statuses` | `initSettingsManagement()`, `#refresh-statuses-btn`, `switchMainTab('settings-tab')` | `apiFetch()`, `renderRefList()`, `fillSelect()` |
| `addStatus()` | Добавляет статус через `POST /settings/statuses` | `#add-status-btn` click | `apiFetch()`, `showToast()`, `loadStatusesSettings()` |
| `deleteStatus(status)` | Удаляет статус через `DELETE /settings/statuses/{name}` | `.ref-delete-btn` click | `apiFetch()`, `showToast()`, `loadStatusesSettings()` |
| `renderRefList(listId, emptyId, items, itemMapper)` | Универсальный рендер списка справочника с кнопками удаления | `load*Settings()` | DOM API |
| `init()` | Главная точка входа mini app: Telegram, вкладки, формы, авторизация | `DOMContentLoaded` | `initTelegram()`, `initTabs()`, `initDealForm()`, `initMyDeals()`, `initModal()`, `initMonthClose()`, `enterApp()` или `showAuthScreen()` |
| `showAuthScreen()` | Показывает экран ввода роли и пароля | `init()` | `initAuthHandlers()` |
| `initAuthHandlers()` | Привязывает выбор роли, ввод пароля и submit авторизации | `showAuthScreen()` | `apiFetch('/auth/miniapp-login')` или `/auth/role-login`, `enterApp()` |
| `enterApp(role)` | Открывает основной интерфейс, строит вкладки, загружает справочники | `init()`, `initAuthHandlers()` | `buildTabs()`, `loadSettings()`, `switchMainTab()`, `initBillingForm()`, `initExpensesForm()`, `initDealEdit()`, `initReportsHandlers()`, `initJournalHandlers()`, `initSubnav()`, `initSettingsManagement()`, `initDashboardHandlers()`, `initReceivablesHandlers()` |
| `buildTabs(role)` | Строит главную навигацию согласно `ROLE_TABS[role]` | `enterApp()` | DOM API, `switchMainTab()` |
| `switchMainTab(tabId)` | Переключает главные `.tab-panel` | `buildTabs()` click, `enterApp()`, `initSubnav()` | `checkConnections()`, `renderUserInfoCard()`, `loadOwnerDashboard()`, `loadReceivables()`, `load*Settings()` |
| `updateUserInfoWithRole(role, roleLabel)` | Добавляет строку роли в карточку пользователя | `enterApp()` | DOM API |
| `initSubnav()` | Привязывает кнопки под-навигации вкладки «Финансы» | `enterApp()` | `loadDeals()`, `loadDealsForEdit()`, `switchMainTab()` |
| `calcBillingTotals(prefix)` | Пересчитывает итоги billing (старый формат p1/p2) | input events полей billing | `setEl()` |
| `calcBillingTotalsV2()` | Пересчитывает итоги billing v2 с НДС/без НДС | input events полей billing, `switchBillingFormat()`, `preloadBillingForm()` | `setEl()` |
| `updateBillingInputLabels()` | Обновляет подписи полей billing согласно формату | `switchBillingFormat()` | DOM API |
| `switchBillingFormat(fmt)` | Переключает между новым и старым форматом billing | `#billing-format` change | `updateBillingInputLabels()`, `calcBillingTotalsV2()` |
| `initBillingForm()` | Инициализирует форму billing: расчёт, загрузка, сохранение, оплата | `enterApp()` | DOM API, `calcBillingTotals()`, `calcBillingTotalsV2()`, `loadBillingEntry()`, `saveBilling()`, `markPayment()`, `initDependentDealDropdowns()` |
| `loadBillingEntry()` | Загружает запись billing через `/billing/v2/search` или `/billing/search` | `#billing-load-btn` click | `apiFetch()`, `preloadBillingForm()`, `clearBillingForm()`, `showToast()` |
| `preloadBillingForm(data)` | Заполняет форму billing загруженными данными | `loadBillingEntry()` | `calcBillingTotalsV2()`, `calcBillingTotals()` |
| `clearBillingForm()` | Очищает все поля формы billing | `loadBillingEntry()` (не найдено) | `calcBillingTotalsV2()`, `calcBillingTotals()` |
| `saveBilling()` | Сохраняет запись billing через `/billing/v2/upsert` или `/billing/upsert` | `#billing-save-btn` click | `apiFetch()`, `showToast()` |
| `markPayment()` | Отмечает оплату сделки через `POST /billing/v2/payment/mark` | `#payment-mark-btn` click | `apiFetch()`, `showToast()`, `formatCurrency()` |
| `updateExpenseCat2(cat1Val, cat2SelectId, cat2FieldId)` | Обновляет `<select>` второго уровня категорий расходов | `#expense-cat1` change, bulk row cat1 change | DOM API, `EXPENSE_CATS_L2` |
| `updateExpenseCommentVisibility(cat1Val, cat2Val, commentFieldId, requiredMarkId)` | Управляет видимостью поля комментария | `#expense-cat1` change, `#expense-cat2` change | `COMMENT_REQUIRED_L2` |
| `initExpensesForm()` | Инициализирует форму расходов: категории, расчёт НДС, сохранение | `enterApp()` | DOM API, `updateExpenseCat2()`, `updateExpenseCommentVisibility()`, `saveExpense()`, `loadExpenses()`, `initDependentDealDropdowns()` |
| `saveExpense()` | Создаёт расход через `POST /expenses/v2/create` | `#expense-save-btn` click | `apiFetch()`, `showToast()` |
| `saveBulkExpenses()` | Сохраняет несколько расходов через `POST /expenses/v2/create` | `#bulk-save-btn` click | `apiFetch()`, `showToast()` |
| `loadExpenses()` | Загружает расходы с `GET /expenses/v2` | `#expenses-load-btn` click | `apiFetch()`, `formatCurrency()`, `escHtml()`, `showToast()` |
| `initReportsHandlers()` | Привязывает `[data-report]` кнопки к `downloadReport()` | `enterApp()` | `downloadReport()` |
| `downloadReport(reportType, fmt)` | Скачивает отчёт через `/reports/{type}` | `[data-report]` click | `fetch`, `showToast()` |
| `initJournalHandlers()` | Инициализирует кнопку загрузки журнала | `enterApp()` | `loadJournal()` |
| `loadJournal()` | Загружает записи журнала с `GET /journal?limit=50` | `#load-journal-btn` click | `apiFetch()`, `escHtml()`, `showToast()` |
| `initDashboardHandlers()` | Инициализирует кнопки загрузки дашборда | `enterApp()` | `loadOwnerDashboard()` |
| `loadOwnerDashboard()` | Загружает KPI и сводку с `GET /dashboard/summary` | `#load-dashboard-btn` click, `#apply-dashboard-filter-btn` click, `switchMainTab('tab-dashboard')` | `apiFetch()`, `formatCurrency()`, `escHtml()`, `showToast()` |
| `initReceivablesHandlers()` | Инициализирует раздел задолженностей | `enterApp()` | `loadReceivables()`, `downloadReport()` |
| `loadReceivables()` | Загружает данные по задолженностям с `GET /receivables` | `#load-receivables-btn`, `#apply-receivables-filter-btn`, `switchMainTab('tab-receivables')` | `apiFetch()`, `formatCurrency()`, `escHtml()`, `showToast()` |
| `initMonthClose()` | Инициализирует кнопки раздела закрытия месяца | `init()` | `runMonthArchive()`, `runMonthCleanup()`, `runMonthClose()`, `loadArchiveBatches()` |
| `_getMonthCloseParams()` | Читает год и месяц из полей формы | `runMonthArchive()`, `runMonthCleanup()`, `runMonthClose()`, `loadArchiveBatches()` | DOM API |
| `_showMonthCloseResult(resultEl, data, error)` | Отображает результат операции закрытия месяца | `runMonthArchive()`, `runMonthCleanup()`, `runMonthClose()` | `escHtml()` |
| `runMonthArchive(dryRun)` | Запускает архивацию месяца (`POST /month/archive`) | `#month-close-dry-run-btn` / `#month-close-archive-btn` click | `_getMonthCloseParams()`, `apiFetch()`, `_showMonthCloseResult()`, `showToast()`, `loadArchiveBatches()` |
| `runMonthCleanup()` | Запускает очистку месяца (`POST /month/cleanup`) | `#month-close-cleanup-btn` click | `_getMonthCloseParams()`, `apiFetch()`, `_showMonthCloseResult()`, `showToast()`, `loadArchiveBatches()` |
| `runMonthClose()` | Закрывает месяц (`POST /month/close`) | `#month-close-close-btn` click | `_getMonthCloseParams()`, `apiFetch()`, `_showMonthCloseResult()`, `showToast()`, `loadArchiveBatches()` |
| `loadArchiveBatches()` | Загружает список архивных батчей (`GET /month/archive-batches`) | `#month-close-load-batches-btn`, после `runMonth*()` | `_getMonthCloseParams()`, `apiFetch()`, `escHtml()` |

---

## 22. FULL EVENT MAP

Все события UI с указанием селектора/элемента, обработчика и результата.

### Стартовые события

| Событие | Элемент | Обработчик | Результат |
|---------|---------|-----------|----------|
| `DOMContentLoaded` | `document` | `async () => { new App(); app.init(); initAddDealModal(app); }` (frontend/js/app.js) | Инициализация приложения, загрузка демо-пользователей, создание вкладок и экранов |
| `DOMContentLoaded` | `document` | `init()` (miniapp/app.js) | Инициализация Telegram SDK, авторизация или вход в приложение, загрузка справочников |

---

### Авторизация (miniapp/app.js)

| Событие | Элемент / Селектор | Обработчик | Результат |
|---------|--------------------|-----------|----------|
| `click` | `.role-btn` | анонимный → показывает шаг ввода пароля, сохраняет `selectedRole` | Скрывает шаг выбора роли, показывает поле пароля |
| `click` | `#auth-back-btn` | анонимный | Возврат к шагу выбора роли |
| `click` | `#auth-submit-btn` | `doLogin()` | Вызов `/auth/miniapp-login` (с Telegram) или `/auth/role-login` (без), переход в `enterApp()` |
| `keydown` (Enter) | `#auth-password` | `doLogin()` | То же, что клик по `#auth-submit-btn` |
| `click` | `#logout-btn` | анонимный | Очищает `localStorage` (`user_role`, `user_role_label`, `telegram_id`), перезагружает страницу |

---

### Навигация по вкладкам (miniapp/app.js)

| Событие | Элемент / Селектор | Обработчик | Результат |
|---------|--------------------|-----------|----------|
| `click` | `.tab-btn` (простые вкладки, `initTabs()`) | `switchTab(tabId)` | Переключает `.tab-panel`, запускает ленивую загрузку сделок или проверку подключений |
| `click` | `#main-tab-nav .tab-btn` | `switchMainTab(tabId)` | Переключает главные `.tab-panel`, запускает `loadOwnerDashboard()`, `loadReceivables()` или обновляет настройки при переходе на `settings-tab` |
| `click` | `.subnav-btn` (вкладка «Финансы») | `initSubnav()` handler | Переключает под-панели (`new-deal-sub`, `my-deals-sub`, `edit-deal-sub`), запускает `loadDeals()` или `loadDealsForEdit()` |

---

### Навигация по вкладкам (frontend/js/app.js)

| Событие | Элемент / Селектор | Обработчик | Результат |
|---------|--------------------|-----------|----------|
| `click` | `.tab-btn` (нижняя навигация) | `App._navigate(id)` | Переключает `.screen`, вызывает `screen.load()` |
| `change` | `#demo-user-select` | `App._setActiveUser(sel.value)` | Переключает роль, перестраивает вкладки, перезагружает экран |

---

### Форма создания сделки — frontend/js/app.js

| Событие | Элемент / Селектор | Обработчик | Результат |
|---------|--------------------|-----------|----------|
| `click` | `#btn-add-deal` | анонимный | Показывает `#add-deal-modal` |
| `click` | `#btn-cancel-add-deal` | анонимный | Скрывает `#add-deal-modal` |
| `submit` | `#form-add-deal` | анонимный | Собирает `FormData`, вызывает `POST /api/deals`, показывает тост, перезагружает список |

---

### Просмотр и редактирование сделки — frontend/js/app.js

| Событие | Элемент / Селектор | Обработчик | Результат |
|---------|--------------------|-----------|----------|
| `click` | `.deal-card` | `DealsScreen._openDeal(id)` | Загружает данные сделки, рендерит модальное окно |
| `click` | `#btn-save-deal` | `DealsScreen._saveDeal(id, formEl)` | Собирает `[data-field]`, вызывает `PATCH /api/deals/{id}`, закрывает модал, перезагружает список |
| `click` | `#btn-delete-deal` | `DealsScreen._deleteDeal(id)` | Подтверждение `confirm()`, вызывает `DELETE /api/deals/{id}`, закрывает модал, перезагружает список |
| `click` | `#btn-close-modal` | анонимный | Скрывает `#deal-modal` |

---

### Форма создания сделки — miniapp/app.js

| Событие | Элемент / Селектор | Обработчик | Результат |
|---------|--------------------|-----------|----------|
| `submit` | `#deal-form` | `handleFormSubmit(e)` | Валидация → `collectFormDataSql()` → `POST /deals/create` → `showSuccessScreen()` |
| `click` | `#clear-btn` | `clearForm()` | Сбрасывает форму и ошибки |
| `click` | `#new-deal-btn` | `showForm()` | Возвращает форму из экрана успеха |
| `click` | `#view-deals-btn` | `switchTab('my-deals')` | Переходит к списку сделок |
| `change` | `#client`, `#charged_with_vat`, `#status`, `#manager` | `updateSummary()` | Обновляет блок предпросмотра |
| `change` | `#vat_type` | `updateChargedLabel()` | Меняет подпись поля «Начислено» |
| `input` | `#charged_with_vat`, `#vat_rate` | `updateDealVat()` | Пересчитывает сумму и НДС в форме |

---

### Список сделок — miniapp/app.js

| Событие | Элемент / Селектор | Обработчик | Результат |
|---------|--------------------|-----------|----------|
| `click` | `#refresh-deals-btn` | `loadDeals()` | Перезагружает список сделок |
| `change` | `#filter-status`, `#filter-client`, `#filter-month` | `renderDeals()` | Фильтрует список сделок на клиенте |
| `click` | `.deal-card` | `openDealModal(deal.deal_id)` | Открывает модальное окно с деталями |
| `click` | `[data-action="view"]` в карточке | `openDealModal(id)` | То же (кнопка «Открыть») |
| `click` | `[data-action="copy"]` в карточке | `copyToClipboard(id)` | Копирует ID сделки в буфер обмена |

---

### Модальное окно сделки — miniapp/app.js

| Событие | Элемент / Селектор | Обработчик | Результат |
|---------|--------------------|-----------|----------|
| `click` | `#modal-close-btn` | `closeDealModal()` | Закрывает модал |
| `click` | `#deal-modal` (overlay) | `closeDealModal()` (если клик вне контента) | Закрывает модал |
| `keydown` (Escape) | `document` | `closeDealModal()` | Закрывает модал |

---

### Редактирование сделки — miniapp/app.js

| Событие | Элемент / Селектор | Обработчик | Результат |
|---------|--------------------|-----------|----------|
| `change` | `#edit-deal-select` | `onEditDealSelected(value)` | Загружает `GET /deals/{id}`, заполняет поля формы |
| `click` | `#edit-deal-save-btn` | `saveEditedDeal()` | Собирает изменённые поля, вызывает `PATCH /deals/update/{id}` |
| `click` | `#edit-deal-back-btn` | `switchSubnav('my-deals-sub')` | Возвращает в список сделок |

---

### Billing — miniapp/app.js

| Событие | Элемент / Селектор | Обработчик | Результат |
|---------|--------------------|-----------|----------|
| `change` | `#billing-format` | `switchBillingFormat(fmt)` | Переключает между новым/старым форматом, обновляет подписи и пересчитывает итоги |
| `input` | Поля `p1-*`, `p2-*` billing (старый формат) | `calcBillingTotals('p1')` / `calcBillingTotals('p2')` | Пересчитывает итоги по периодам |
| `input` | Поля `bv2-*` billing (новый формат) | `calcBillingTotalsV2()` | Пересчитывает итоги с НДС/без НДС |
| `click` | `#billing-load-btn` | `loadBillingEntry()` | Поиск записи billing через `/billing/v2/search`, предзаполнение формы |
| `click` | `#billing-save-btn` | `saveBilling()` | Сохранение записи billing через `/billing/v2/upsert` |
| `change` | `#payment-direction-select`, `#payment-client-select` | `loadDealsFiltered()` | Перезагружает `#payment-deal-select` |
| `click` | `#payment-mark-btn` | `markPayment()` | Отмечает оплату через `POST /billing/v2/payment/mark` |

---

### Расходы — miniapp/app.js

| Событие | Элемент / Селектор | Обработчик | Результат |
|---------|--------------------|-----------|----------|
| `change` | `#expense-cat1` | `updateExpenseCat2()` + `updateExpenseCommentVisibility()` | Обновляет `#expense-cat2`, показывает/скрывает поле комментария |
| `change` | `#expense-cat2` | `updateExpenseCommentVisibility()` | Показывает/скрывает обязательный комментарий |
| `change` | `#expense-direction-select`, `#expense-client-select` | `loadDealsFiltered()` | Перезагружает `#expense-deal-select` |
| `click` | `#expense-save-btn` | `saveExpense()` | Создаёт расход через `POST /expenses/v2/create` |
| `click` | `#expenses-load-btn` | `loadExpenses()` | Загружает расходы с `GET /expenses/v2` |
| `click` | `#add-bulk-row-btn` | `addBulkRow()` | Добавляет строку в таблицу массового ввода расходов |
| `click` | `.bulk-remove-btn` | `removeBulkRow(idx)` | Удаляет строку из таблицы массового ввода |
| `click` | `#bulk-save-btn` | `saveBulkExpenses()` | Сохраняет все строки через `POST /expenses/v2/create` |

---

### Отчёты — miniapp/app.js

| Событие | Элемент / Селектор | Обработчик | Результат |
|---------|--------------------|-----------|----------|
| `click` | `[data-report]` | `downloadReport(reportType, fmt)` | Скачивает отчёт через `GET /reports/{type}?fmt={fmt}` как blob-файл |

---

### Журнал — miniapp/app.js

| Событие | Элемент / Селектор | Обработчик | Результат |
|---------|--------------------|-----------|----------|
| `click` | `#load-journal-btn` | `loadJournal()` | Загружает записи с `GET /journal?limit=50`, рендерит список |

---

### Дашборд — miniapp/app.js

| Событие | Элемент / Селектор | Обработчик | Результат |
|---------|--------------------|-----------|----------|
| `click` | `#load-dashboard-btn` | `loadOwnerDashboard()` | Загружает KPI с `GET /dashboard/summary` |
| `click` | `#apply-dashboard-filter-btn` | `loadOwnerDashboard()` | То же, с фильтром по месяцу |
| Tab switch к `tab-dashboard` | — | `switchMainTab()` side-effect | Автоматически вызывает `loadOwnerDashboard()` |

---

### Задолженности — miniapp/app.js

| Событие | Элемент / Селектор | Обработчик | Результат |
|---------|--------------------|-----------|----------|
| `click` | `#load-receivables-btn` | `loadReceivables()` | Загружает данные с `GET /receivables`, рендерит KPI и таблицы |
| `click` | `#apply-receivables-filter-btn` | `loadReceivables()` | То же, с фильтром по месяцу |
| `click` | `#tab-receivables [data-report]` | `downloadReport(type, fmt)` | Скачивает отчёт по дебиторке |
| Tab switch к `tab-receivables` | — | `switchMainTab()` side-effect | Автоматически вызывает `loadReceivables()` |

---

### Закрытие месяца — miniapp/app.js

| Событие | Элемент / Селектор | Обработчик | Результат |
|---------|--------------------|-----------|----------|
| `click` | `#month-close-dry-run-btn` | `runMonthArchive(true)` | Dry-run архивации (`POST /month/archive` с `dry_run: true`) |
| `click` | `#month-close-archive-btn` | `runMonthArchive(false)` | Реальная архивация с подтверждением `confirm()` |
| `click` | `#month-close-cleanup-btn` | `runMonthCleanup()` | Очистка месяца (`POST /month/cleanup`) с подтверждением |
| `click` | `#month-close-close-btn` | `runMonthClose()` | Закрытие месяца (`POST /month/close`) с подтверждением |
| `click` | `#month-close-load-batches-btn` | `loadArchiveBatches()` | Загружает список батчей (`GET /month/archive-batches`) |

---

### Управление справочниками — miniapp/app.js

| Событие | Элемент / Селектор | Обработчик | Результат |
|---------|--------------------|-----------|----------|
| `click` | `#add-client-btn` | `addClient()` | `POST /settings/clients`, обновляет список и селекты |
| `click` | `#refresh-clients-btn` | `loadClientsSettings()` | Перезагружает клиентов |
| `click` | `.ref-delete-btn` (в списке клиентов) | `deleteClient(id, name)` | `DELETE /settings/clients/{id}`, обновляет список |
| `click` | `#add-manager-btn` | `addManager()` | `POST /settings/managers`, обновляет список и селект |
| `click` | `#refresh-managers-btn` | `loadManagersSettings()` | Перезагружает менеджеров |
| `click` | `.ref-delete-btn` (в списке менеджеров) | `deleteManager(id, name)` | `DELETE /settings/managers/{id}`, обновляет список |
| `click` | `#add-direction-btn` | `addDirection()` | `POST /settings/directions`, обновляет список и селект |
| `click` | `#refresh-directions-btn` | `loadDirectionsSettings()` | Перезагружает направления |
| `click` | `.ref-delete-btn` (в списке направлений) | `deleteDirection(name)` | `DELETE /settings/directions/{name}`, обновляет список |
| `click` | `#add-status-btn` | `addStatus()` | `POST /settings/statuses`, обновляет список и селекты |
| `click` | `#refresh-statuses-btn` | `loadStatusesSettings()` | Перезагружает статусы |
| `click` | `.ref-delete-btn` (в списке статусов) | `deleteStatus(name)` | `DELETE /settings/statuses/{name}`, обновляет список |
| Tab switch к `settings-tab` | — | `switchMainTab()` side-effect | Вызывает `checkConnections()`, `renderUserInfoCard()`, все `load*Settings()` |

---

## 23. SETTINGS CONTRACT AUDIT

Строгий аудит контракта между ожиданиями фронтенда и данными, предоставляемыми
бэкендом.

> **Примечание:** номера строк в колонке «Место в коде» являются приближёнными
> ориентирами и могут меняться по мере развития кодовой базы.

### Источник данных

Основной эндпоинт: **`GET /settings/enriched`** (`backend/routers/settings.py`)  
Реализация: `settings_service.load_enriched_settings_pg(db)` (`backend/services/settings_service.py:526`)

---

### Поля, ожидаемые фронтендом

#### Клиенты (`clients`)

| Аспект | Описание |
|--------|---------|
| Ожидаемый формат (основной) | `Array<{ id: number, name: string }>` — из `/settings/enriched` |
| Ожидаемый формат (после CRUD) | `Array<string>` — из `GET /settings/clients` (возвращает `{ client_id, client_name }`, `fillSelect` вызывается со строками `client_name`) |
| Используется в селектах | `#client`, `#billing-client-select`, `#filter-client`, `#payment-client-select`, `#expense-client-select`, `#report-client-select` |
| Используется в запросах | `client_id: intVal('client')` в `collectFormDataSql()` → `POST /deals/create` |
| Место в коде | `populateSelects()` → `fillSelect('client', data.clients)` (miniapp/app.js:211); `loadClientsSettings()` → `fillSelect('client', clientNames)` (miniapp/app.js:1225) |
| **⚠️ Риск** | `loadClientsSettings()` перезаписывает `#client` строками (`client_name`), а не числовыми ID. Если CRUD-функции настроек отработали после `loadSettings()`, `collectFormDataSql()` получит `client_id: null` (строка не парсится как целое). Форма создания сделки отправит пустой `client_id`. |

#### Менеджеры (`managers`)

| Аспект | Описание |
|--------|---------|
| Ожидаемый формат (основной) | `Array<{ id: number, name: string }>` — из `/settings/enriched` |
| Ожидаемый формат (после CRUD) | `Array<string>` — из `GET /settings/managers` (строки `manager_name`) |
| Используется в селектах | `#manager` |
| Используется в запросах | `manager_id: intVal('manager')` в `collectFormDataSql()` → `POST /deals/create` |
| Место в коде | `populateSelects()` → `fillSelect('manager', data.managers)` (miniapp/app.js:213); `loadManagersSettings()` → `fillSelect('manager', managerNames)` (miniapp/app.js:1246) |
| **⚠️ Риск** | Аналогично `clients`: после вызова `loadManagersSettings()` `#manager` содержит строки, что делает `manager_id` в `collectFormDataSql()` равным `null`. |

#### Направления бизнеса (`business_directions`)

| Аспект | Описание |
|--------|---------|
| Ожидаемый формат (основной) | `Array<{ id: number, name: string }>` — из `/settings/enriched` |
| Ожидаемый формат (после CRUD) | `Array<string>` — из `GET /settings/directions` (возвращает чистые строки) |
| Используется в селектах | `#business_direction`, `#payment-direction-select`, `#expense-direction-select` |
| Используется в запросах | `business_direction_id: intVal('business_direction')` в `collectFormDataSql()` |
| Место в коде | `populateSelects()` → `fillSelect('business_direction', data.business_directions)` (miniapp/app.js:210); `loadDirectionsSettings()` → `fillSelect('business_direction', directions)` (miniapp/app.js:1265) |
| **⚠️ Риск** | Аналогично `clients`: после CRUD `#business_direction` содержит строки, `business_direction_id` становится `null`. |

#### Статусы (`statuses`)

| Аспект | Описание |
|--------|---------|
| Ожидаемый формат (основной) | `Array<{ id: number, name: string }>` — из `/settings/enriched` |
| Ожидаемый формат (после CRUD) | `Array<string>` — из `GET /settings/statuses` |
| Используется в селектах | `#status`, `#edit-status`, `#filter-status` |
| Используется в запросах | `status_id: intVal('status')` в `collectFormDataSql()` |
| Место в коде | `populateSelects()` → `fillSelect('status', data.statuses)` (miniapp/app.js:209); `loadStatusesSettings()` → `fillSelect('status', statuses)` (miniapp/app.js:1295) |
| **⚠️ Риск** | Аналогично выше. При редактировании статусов фронтенд теряет числовые ID в `#status`. `saveEditedDeal()` отправляет `status` как строку, что соответствует ожиданиям `PATCH /deals/update/{id}` — здесь риска нет. Но `collectFormDataSql()` (создание сделки) будет отправлять `status_id: null`. |

#### Типы НДС (`vat_types`)

| Аспект | Описание |
|--------|---------|
| Ожидаемый формат | `Array<{ id: number, name: string }>` — из `/settings/enriched` |
| Резервное значение | `[{ id: 1, name: "С НДС" }, { id: 2, name: "Без НДС" }]` (хардкод в `loadSettings()`) |
| Используется в селектах | `#vat_type` |
| Используется в запросах | `vat_type_id: intVal('vat_type')` в `collectFormDataSql()` |
| Место в коде | `populateSelects()` → `fillSelect('vat_type', data.vat_types)` (miniapp/app.js:214) |
| **⚠️ Риск** | Хардкодированный fallback `id: 1/2` может не совпадать с реальными PK в базе данных. |

#### Источники (`sources`)

| Аспект | Описание |
|--------|---------|
| Ожидаемый формат | `Array<{ id: number, name: string }>` — из `/settings/enriched` |
| Используется в селектах | `#source` |
| Используется в запросах | `source_id: intVal('source')` в `collectFormDataSql()` |
| Место в коде | `populateSelects()` → `fillSelect('source', data.sources)` (miniapp/app.js:215) |
| Риск | Нет особых рисков при работе через `/settings/enriched` |

#### Склады (`warehouses`)

| Аспект | Описание |
|--------|---------|
| Ожидаемый формат | `Array<{ id: number, name: string, code: string }>` — из `/settings/enriched` |
| Преобразование в UI | `{ id: w.id, name: "${w.code.toUpperCase()} — ${w.name}" }` (miniapp/app.js:222) |
| Используется в селектах | `#billing-warehouse` |
| Используется в запросах | `warehouse_id: parseInt(warehouseVal)` в `loadBillingEntry()` и `saveBilling()` |
| Место в коде | `populateSelects()` (miniapp/app.js:219–225) |
| **⚠️ Риск** | Если поле `code` отсутствует (null) в БД, метка склада будет ` — Имя` (пустой код). Проверка `w.code || ''` защищает от ошибки, но отображение будет некорректным. |

#### Категории расходов (`expense_categories`)

| Аспект | Описание |
|--------|---------|
| Ожидаемый формат | `Array<{ id: number, name: string, sub_categories: Array<{ id: number, name: string }> }>` |
| Резервные данные | `EXPENSE_CATS_L2` — статический объект в коде (miniapp/app.js:2223), переопределяется данными из БД |
| Используется в селектах | `#expense-cat1`, `#expense-cat2`, bulk-row cat1/cat2 |
| Используется в запросах | `category_level_1`, `category_level_2` в `POST /expenses/v2/create` |
| Место в коде | `populateSelects()` (miniapp/app.js:243–254) |
| **⚠️ Риск** | Статическая карта `EXPENSE_CATS_L2` задаёт значения `option.value` в нижнем регистре (`opt.toLowerCase()`), а данные из БД — как есть. Это приводит к несоответствию регистра между уровнем 1 (строка из БД) и ключами `EXPENSE_CATS_L2` при сравнении `EXPENSE_CATS_L2[cat1Val]` (miniapp/app.js:2237 использует `cat1Val` напрямую, а объект инициализирован строчными ключами). |

---

### Сводная таблица рисков

| Поле | Риск | Уровень | Место в коде |
|------|------|---------|-------------|
| `clients` | `loadClientsSettings()` перезаписывает `#client` строками — `client_id` в `collectFormDataSql()` становится `null` | 🔴 Высокий | miniapp/app.js:1225, 810 |
| `managers` | `loadManagersSettings()` перезаписывает `#manager` строками — `manager_id` в `collectFormDataSql()` становится `null` | 🔴 Высокий | miniapp/app.js:1246, 813 |
| `business_directions` | `loadDirectionsSettings()` перезаписывает `#business_direction` строками — `business_direction_id` становится `null` | 🔴 Высокий | miniapp/app.js:1265, 810 |
| `statuses` | `loadStatusesSettings()` перезаписывает `#status` строками — `status_id` в форме создания становится `null` | 🟡 Средний | miniapp/app.js:1295, 802 |
| `vat_types` | Хардкодированный fallback `id: 1/2` может не совпасть с реальными PK в БД | 🟡 Средний | miniapp/app.js:175–177 |
| `warehouses` | Отсутствующий `code` даёт некорректный текст в `<option>`, но не ломает запросы | 🟢 Низкий | miniapp/app.js:219–225 |
| `expense_categories` | Несоответствие регистра между ключами `EXPENSE_CATS_L2` и именами из БД при построении L2-dropdown | 🟡 Средний | miniapp/app.js:2223, 2237, 247–252 |
