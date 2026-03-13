# Google Sheets Structure — Telegram Mini App + FastAPI Backend

Полный анализ проекта для проектирования структуры Google Sheets.

---

## 1. Pydantic Models

### DealCreate (`backend/models/deal.py`)

Используется для создания сделки (`POST /deal/create`).

| Поле | Тип | Optional |
|------|-----|----------|
| `status` | `str` | нет |
| `business_direction` | `str` | нет |
| `client` | `str` | нет |
| `manager` | `str` | нет |
| `charged_with_vat` | `float` | нет |
| `vat_type` | `str` | нет |
| `paid` | `float` | да (`= None`) |
| `project_start_date` | `str` | нет |
| `project_end_date` | `str` | нет |
| `act_date` | `str` | да (`= None`) |
| `variable_expense_1` | `float` | да (`= None`) |
| `variable_expense_2` | `float` | да (`= None`) |
| `manager_bonus_percent` | `float` | да (`= None`) |
| `manager_bonus_paid` | `float` | да (`= None`) |
| `general_production_expense` | `float` | да (`= None`) |
| `source` | `str` | да (`= None`) |
| `document_link` | `str` | да (`= None`) |
| `comment` | `str` | да (`= None`) |

---

### DealUpdate (`backend/models/deal.py`)

Используется для обновления сделки (`PUT /deal/{deal_id}`).
Все поля `Optional` (передаются только изменяемые).

| Поле | Тип | Optional |
|------|-----|----------|
| `status` | `str` | да |
| `business_direction` | `str` | да |
| `client` | `str` | да |
| `manager` | `str` | да |
| `charged_with_vat` | `float` | да |
| `vat_type` | `str` | да |
| `paid` | `float` | да |
| `project_start_date` | `str` | да |
| `project_end_date` | `str` | да |
| `act_date` | `str` | да |
| `variable_expense_1` | `float` | да |
| `variable_expense_2` | `float` | да |
| `manager_bonus_percent` | `float` | да |
| `manager_bonus_paid` | `float` | да |
| `general_production_expense` | `float` | да |
| `source` | `str` | да |
| `document_link` | `str` | да |
| `comment` | `str` | да |

---

### DealResponse (`backend/models/deal.py`)

Используется как схема ответа при получении сделки.

| Поле | Тип | Optional |
|------|-----|----------|
| `deal_id` | `str` | нет |
| `status` | `str` | нет |
| `business_direction` | `str` | нет |
| `client` | `str` | нет |
| `manager` | `str` | нет |
| `charged_with_vat` | `float` | да |
| `vat_type` | `str` | да |
| `paid` | `float` | да |
| `project_start_date` | `str` | да |
| `project_end_date` | `str` | да |
| `act_date` | `str` | да |
| `variable_expense_1` | `float` | да |
| `variable_expense_2` | `float` | да |
| `manager_bonus_percent` | `float` | да |
| `manager_bonus_paid` | `float` | да |
| `general_production_expense` | `float` | да |
| `source` | `str` | да |
| `document_link` | `str` | да |
| `comment` | `str` | да |

---

## 2. API Endpoints

Все endpoints связанные со сделками (`backend/routers/deals.py`):

| HTTP Method | Path | Request Model | Response Model | Описание |
|-------------|------|---------------|----------------|----------|
| `POST` | `/deal/create` | `DealCreate` | `{"success": bool, "deal_id": str}` | Создание новой сделки |
| `GET` | `/deal/all` | — | `list` | Все сделки (только accountant/director/head_of_sales) |
| `GET` | `/deal/user` | query: `?manager=` | `list` | Сделки текущего пользователя / фильтр по менеджеру |
| `GET` | `/deal/filter` | query: `?manager=&client=&status=&business_direction=&month=&paid=` | `list` | Фильтрованный список сделок |
| `GET` | `/deal/{deal_id}` | — | `dict` | Одна сделка по ID |
| `PUT` | `/deal/{deal_id}` | `DealUpdate` | `{"success": bool, "deal_id": str}` | Обновление сделки |

Прочие полезные endpoints:

| HTTP Method | Path | Описание |
|-------------|------|----------|
| `GET` | `/dashboard` | Сводная статистика, зависит от роли пользователя |
| `GET` | `/journal/recent` | Последние записи журнала действий (не доступно для manager) |
| `GET` | `/settings` | Справочные данные (статусы, направления, клиенты и т.д.) |
| `POST` | `/auth/validate` | Валидация Telegram initData и получение роли |
| `GET` | `/auth/role` | Роль и права редактирования для аутентифицированного пользователя |
| `GET` | `/health` | Health check |

---

## 3. Google Sheets Integration

Весь код работы с Google Sheets сосредоточен в:

### `backend/services/sheets_service.py`

| Функция | Назначение |
|---------|------------|
| `get_spreadsheet()` | Возвращает объект `gspread.Spreadsheet` по `GOOGLE_SHEETS_SPREADSHEET_ID` |
| `get_worksheet(name)` | Возвращает лист по имени, поднимает `SheetNotFoundError` если не найден |
| `get_header_map(sheet)` | Читает первую строку листа, возвращает `{имя_колонки: 0-based_индекс}` |
| `get_required_column(hmap, name)` | Возвращает индекс обязательной колонки или поднимает `MissingHeaderError` |
| `row_to_dict(hmap, row)` | Конвертирует строку (list) в dict по заголовкам |
| `dict_to_row(hmap, payload, headers)` | Конвертирует dict в list для записи в строку |

### `backend/services/deals_service.py`

| Функция | Действие в Sheets | Колонки |
|---------|-------------------|---------|
| `create_deal(...)` | `ws.append_row(new_row)` | Все 19 колонок (A–S) |
| `update_deal(...)` | `ws.update(f"A{n}:{col}{n}", [new_row])` | Все 19 колонок (A–S) |
| `get_deal_by_id(deal_id)` | `ws.get_all_values()` + поиск по "ID сделки" | Все колонки |
| `get_all_deals()` | `ws.get_all_values()` | Все колонки |
| `get_deals_by_user(manager)` | `ws.get_all_values()` + фильтр по "Менеджер" | Все колонки |
| `get_deals_filtered(filters)` | `ws.get_all_values()` + Python-фильтрация | Все колонки |

### `backend/services/journal_service.py`

| Функция | Действие в Sheets | Колонки |
|---------|-------------------|---------|
| `append_journal_entry(...)` | `ws.append_row(row)` | timestamp, telegram_user_id, full_name, user_role, action, deal_id, changed_fields, payload_summary |

### `backend/services/settings_service.py`

| Функция | Действие в Sheets |
|---------|-------------------|
| `_load_section(key)` | `ws.get_all_values()` из листа "Настройки" |
| `load_all_settings()` | `ws.get_all_values()` из листа "Настройки" (один запрос) |

---

## 4. Google Sheets Columns

### Лист "Учёт сделок"

Порядок колонок при `append_row` (из `DEALS_COLUMN_MAP` в `deals_service.py`):

| Колонка | Заголовок (RU) | Внутреннее поле | Тип данных |
|---------|---------------|-----------------|------------|
| A | ID сделки | `deal_id` | string (`DEAL-000001`) |
| B | Статус сделки | `status` | string |
| C | Направление бизнеса | `business_direction` | string |
| D | Клиент | `client` | string |
| E | Менеджер | `manager` | string |
| F | Начислено с НДС | `charged_with_vat` | float |
| G | Наличие НДС | `vat_type` | string |
| H | Оплачено | `paid` | float |
| I | Дата начала проекта | `project_start_date` | string (`YYYY-MM-DD`) |
| J | Дата окончания проекта | `project_end_date` | string (`YYYY-MM-DD`) |
| K | Дата выставления акта | `act_date` | string (`YYYY-MM-DD`) |
| L | Переменный расход 1 | `variable_expense_1` | float |
| M | Переменный расход 2 | `variable_expense_2` | float |
| N | Бонус менеджера % | `manager_bonus_percent` | float |
| O | Бонус менеджера выплачено | `manager_bonus_paid` | float |
| P | Общепроизводственный расход | `general_production_expense` | float |
| Q | Источник | `source` | string |
| R | Документ/ссылка | `document_link` | string |
| S | Комментарий | `comment` | string |

Пример `append_row`:

```python
ws.append_row([
    "DEAL-000001",   # A: ID сделки
    "В работе",      # B: Статус сделки
    "Разработка",    # C: Направление бизнеса
    "ООО Ромашка",   # D: Клиент
    "Иван Петров",   # E: Менеджер
    150000.0,        # F: Начислено с НДС
    "С НДС",         # G: Наличие НДС
    0.0,             # H: Оплачено
    "2025-01-15",    # I: Дата начала проекта
    "2025-03-31",    # J: Дата окончания проекта
    "",              # K: Дата выставления акта
    0.0,             # L: Переменный расход 1
    0.0,             # M: Переменный расход 2
    0.0,             # N: Бонус менеджера %
    0.0,             # O: Бонус менеджера выплачено
    0.0,             # P: Общепроизводственный расход
    "Рекомендация",  # Q: Источник
    "",              # R: Документ/ссылка
    "",              # S: Комментарий
], value_input_option="USER_ENTERED")
```

### Лист "Настройки"

Формат блоков: каждый раздел начинается с заголовка в квадратных скобках.

```
[Статусы сделок]
Новая
В работе
Завершена
Отменена
Приостановлена

[Направления бизнеса]
Разработка
Консалтинг
...

[Клиенты]
ООО Ромашка
...

[Менеджеры]
Иван Петров
...

[Наличие НДС]
С НДС
Без НДС

[Источники]
Рекомендация
Сайт
...

[Роли пользователей]
telegram_user_id | full_name | role | active
123456789 | Иван Петров | manager | TRUE
987654321 | Анна Смирнова | accountant | TRUE
```

| Колонка | Поле |
|---------|------|
| A (0) | `telegram_user_id` |
| B (1) | `full_name` |
| C (2) | `role` |
| D (3) | `active` |

### Лист "Журнал действий"

| Колонка | Заголовок | Описание |
|---------|-----------|----------|
| A (0) | `timestamp` | `YYYY-MM-DD HH:MM:SS` (UTC) |
| B (1) | `telegram_user_id` | Telegram ID пользователя |
| C (2) | `full_name` | Имя пользователя |
| D (3) | `user_role` | Роль пользователя |
| E (4) | `action` | Действие (`create_deal`, `update_deal`, `forbidden_edit_attempt`, …) |
| F (5) | `deal_id` | ID затронутой сделки |
| G (6) | `changed_fields` | JSON-список изменённых полей |
| H (7) | `payload_summary` | Краткое описание изменений |

---

## 5. Worksheets

Названия листов (`backend/services/sheets_service.py`, `backend/config.py`):

| Константа | Название листа | Назначение |
|-----------|---------------|------------|
| `SHEET_DEALS` | `"Учёт сделок"` | Основная база сделок |
| `SHEET_SETTINGS` | `"Настройки"` | Справочники и роли пользователей |
| `SHEET_JOURNAL` | `"Журнал действий"` | Аудит всех действий пользователей |

---

## 6. Deal ID Logic

Файл: `backend/services/deals_service.py`

```python
_DEAL_ID_PATTERN = re.compile(r"^DEAL-(\d+)$")
_deal_id_lock = threading.Lock()

def parse_deal_id_number(deal_id: str) -> Optional[int]:
    m = _DEAL_ID_PATTERN.match(deal_id.strip())
    if m:
        return int(m.group(1))
    return None

def format_deal_id(number: int) -> str:
    return f"DEAL-{number:06d}"

def generate_next_deal_id(existing_ids: List[str]) -> str:
    max_num = 0
    for raw_id in existing_ids:
        num = parse_deal_id_number(raw_id)
        if num is not None and num > max_num:
            max_num = num
    return format_deal_id(max_num + 1)
```

| Аспект | Описание |
|--------|----------|
| Формат | `DEAL-000001` (6 цифр, zero-padded) |
| Определение последнего ID | Читает все строки листа "Учёт сделок", извлекает числовой суффикс из колонки "ID сделки" |
| Инкремент | `max(existing_numeric_ids) + 1` |
| Thread safety | `threading.Lock()` (`_deal_id_lock`) оборачивает весь блок чтения + генерации + записи |

---

## 7. Columns Read From Sheets

### Лист "Учёт сделок"

Все поля, которые читает backend (из `DEALS_COLUMN_MAP`):

```python
row["ID сделки"]                   → deal_id           (str)
row["Статус сделки"]               → status            (str)
row["Направление бизнеса"]         → business_direction (str)
row["Клиент"]                      → client            (str)
row["Менеджер"]                    → manager           (str)
row["Начислено с НДС"]             → charged_with_vat  (float | None)
row["Наличие НДС"]                 → vat_type          (str)
row["Оплачено"]                    → paid              (float | None)
row["Дата начала проекта"]         → project_start_date (str | None)
row["Дата окончания проекта"]      → project_end_date  (str | None)
row["Дата выставления акта"]       → act_date          (str | None)
row["Переменный расход 1"]         → variable_expense_1  (float | None)
row["Переменный расход 2"]         → variable_expense_2  (float | None)
row["Бонус менеджера %"]           → manager_bonus_percent (float | None)
row["Бонус менеджера выплачено"]   → manager_bonus_paid  (float | None)
row["Общепроизводственный расход"] → general_production_expense (float | None)
row["Источник"]                    → source            (str)
row["Документ/ссылка"]             → document_link     (str)
row["Комментарий"]                 → comment           (str)
```

### Лист "Настройки" (роли)

```python
row["telegram_user_id"]  → str
row["full_name"]         → str
row["role"]              → str (manager | accountant | operations_director | head_of_sales)
row["active"]            → str (TRUE | FALSE)
```

### Лист "Журнал действий"

```python
row["timestamp"]          → str
row["telegram_user_id"]   → str
row["full_name"]          → str
row["user_role"]          → str
row["action"]             → str
row["deal_id"]            → str
row["changed_fields"]     → str (JSON)
row["payload_summary"]    → str
```

---

## 8. Example Request JSON

### POST /deal/create

Заголовок: `X-Telegram-Init-Data: <Telegram initData>`

```json
{
  "status": "В работе",
  "business_direction": "Разработка",
  "client": "ООО Ромашка",
  "manager": "Иван Петров",
  "charged_with_vat": 150000.0,
  "vat_type": "С НДС",
  "paid": null,
  "project_start_date": "2025-01-15",
  "project_end_date": "2025-03-31",
  "act_date": null,
  "variable_expense_1": null,
  "variable_expense_2": null,
  "manager_bonus_percent": null,
  "manager_bonus_paid": null,
  "general_production_expense": null,
  "source": "Рекомендация",
  "document_link": null,
  "comment": null
}
```

### PUT /deal/{deal_id}

Частичное обновление (только изменяемые поля):

```json
{
  "paid": 75000.0,
  "act_date": "2025-03-20"
}
```

---

## 9. Example Response JSON

### GET /deal/{deal_id}

```json
{
  "deal_id": "DEAL-000001",
  "status": "В работе",
  "business_direction": "Разработка",
  "client": "ООО Ромашка",
  "manager": "Иван Петров",
  "charged_with_vat": 150000.0,
  "vat_type": "С НДС",
  "paid": 75000.0,
  "project_start_date": "2025-01-15",
  "project_end_date": "2025-03-31",
  "act_date": "2025-03-20",
  "variable_expense_1": null,
  "variable_expense_2": null,
  "manager_bonus_percent": null,
  "manager_bonus_paid": null,
  "general_production_expense": null,
  "source": "Рекомендация",
  "document_link": null,
  "comment": null
}
```

### POST /deal/create

```json
{
  "success": true,
  "deal_id": "DEAL-000001"
}
```

### PUT /deal/{deal_id}

```json
{
  "success": true,
  "deal_id": "DEAL-000001"
}
```

### GET /dashboard (роль: manager)

```json
{
  "role": "manager",
  "full_name": "Иван Петров",
  "data": {
    "total_my_deals": 10,
    "in_progress": 7,
    "completed": 3,
    "total_amount": 1500000.0
  }
}
```

### GET /settings

```json
{
  "statuses": ["Новая", "В работе", "Завершена", "Отменена", "Приостановлена"],
  "business_directions": ["Разработка", "Консалтинг", "Дизайн", "Маркетинг", "Другое"],
  "clients": ["ООО Ромашка", "ИП Сидоров"],
  "managers": ["Иван Петров", "Анна Смирнова"],
  "vat_types": ["С НДС", "Без НДС"],
  "sources": ["Рекомендация", "Сайт", "Реклама", "Холодный звонок", "Другое"]
}
```

---

## 10. Environment Variables

Из `.env.example` и `config/config.py`:

### Обязательные

| Переменная | Назначение | Где используется |
|------------|------------|------------------|
| `TELEGRAM_BOT_TOKEN` | Токен бота от @BotFather | `config/config.py` → `Settings.telegram_bot_token`; Telegram bot polling; `/auth/validate` |
| `WEBAPP_URL` | Публичный HTTPS URL Mini App | `config/config.py` → `Settings.webapp_url`; бот передаёт ссылку на Mini App |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Полный JSON service account key | `backend/services/sheets_service.py` → `_get_client()` |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | ID Google Spreadsheet | `backend/services/sheets_service.py` → `get_spreadsheet()` |

### Опциональные

| Переменная | Назначение | Где используется |
|------------|------------|------------------|
| `API_BASE_URL` | Публичный URL backend API | `miniapp/app.js` → `API_BASE` (fallback: same-origin) |

### Пример `.env` файла

> **Важно:** Никогда не коммитьте реальные credentials в систему контроля версий.
> Добавьте `.env` в `.gitignore`. Используйте только placeholder-значения в документации и примерах.

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
WEBAPP_URL=https://your-domain.com/miniapp
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"...","private_key_id":"...","private_key":"-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n","client_email":"...@....iam.gserviceaccount.com","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token"}
GOOGLE_SHEETS_SPREADSHEET_ID=your_google_spreadsheet_id_here
API_BASE_URL=https://your-backend-domain.com
```

---

## Summary: Google Sheets Structure

### Spreadsheet layout

```
┌─────────────────────────────────────────────────────────────┐
│  Sheet 1: "Учёт сделок"                                     │
│  Sheet 2: "Настройки"                                       │
│  Sheet 3: "Журнал действий"                                 │
└─────────────────────────────────────────────────────────────┘
```

### "Учёт сделок" — row 1 (headers)

```
A             B               C                    D        E          F                G            H         I                      J                       K                     L                    M                    N                  O                          P                         Q         R              S
ID сделки | Статус сделки | Направление бизнеса | Клиент | Менеджер | Начислено с НДС | Наличие НДС | Оплачено | Дата начала проекта | Дата окончания проекта | Дата выставления акта | Переменный расход 1 | Переменный расход 2 | Бонус менеджера % | Бонус менеджера выплачено | Общепроизводственный расход | Источник | Документ/ссылка | Комментарий
```

### "Настройки" — block layout

```
[Статусы сделок]       ← section header (col A)
Новая                  ← values (one per row, col A)
В работе
...

[Роли пользователей]
telegram_user_id | full_name | role | active   ← pipe-delimited table header
123456789 | Иван Петров | manager | TRUE        ← data rows
```

### "Журнал действий" — row 1 (headers)

```
A          B                  C           D           E       F        G                H
timestamp | telegram_user_id | full_name | user_role | action | deal_id | changed_fields | payload_summary
```
