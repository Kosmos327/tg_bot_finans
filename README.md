# tg_bot_finans

Production-ready **Telegram Mini App** integrated with **Google Sheets** for financial deal tracking.

## Architecture

```
User → Telegram Bot → Mini App → FastAPI Backend → Google Sheets
```

## Project Structure

```
project/
├── bot/
│   ├── bot.py          # aiogram 3.x entry point
│   ├── handlers.py     # /start command handler
│   └── keyboards.py    # WebApp keyboard button
├── backend/
│   ├── main.py         # FastAPI application
│   ├── routers/
│   │   ├── deals.py    # POST /deal/create, GET /deals/user
│   │   └── settings.py # GET /settings
│   └── services/
│       ├── sheets_service.py  # gspread Google Sheets integration
│       └── auth_service.py    # Telegram initData HMAC validation
├── miniapp/
│   ├── index.html      # Mini App shell
│   ├── app.js          # Vanilla JS logic
│   └── styles.css      # Telegram-themed styles
├── config/
│   └── config.py       # pydantic-settings configuration
├── .env.example        # Environment variables template
└── requirements.txt
```

## Quick Start

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram Bot API token from @BotFather |
| `MINI_APP_URL` | Public HTTPS URL of `miniapp/index.html` |
| `BACKEND_URL` | Public HTTPS URL of the FastAPI server |
| `GOOGLE_CREDENTIALS_FILE` | Path to your service account JSON key |
| `SPREADSHEET_NAME` | Google Sheets file name (default: `Финанс.xlsx`) |

### 3. Set up Google Sheets

1. Create a Google Cloud project and enable the **Google Sheets API** and **Google Drive API**.
2. Create a **Service Account** and download the JSON key as `credentials.json`.
3. Share your spreadsheet (`Финанс.xlsx`) with the service account email.
4. Ensure the spreadsheet has sheets named:
   - `Учёт сделок` — deals data (columns A–S)
   - `Настройки` — reference data with headers: `Статусы`, `Направления бизнеса`, `Клиенты`, `Менеджеры`, `Типы НДС`
   - `Журнал действий` — action log

### 4. Run the backend

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

The Mini App static files are served at `/miniapp/index.html`.

### 5. Run the bot

```bash
python -m bot.bot
```

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/deal/create` | Telegram initData | Create a new deal |
| GET | `/deals/user?manager=` | Telegram initData | Get deals by manager |
| GET | `/settings` | None | Load reference data |
| GET | `/health` | None | Health check |
| GET | `/miniapp/*` | None | Serve Mini App static files |

## Security

- All deal endpoints require a valid Telegram `initData` header (`X-Init-Data`).
- Validation uses **HMAC-SHA256** per the [Telegram Web Apps docs](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app).
- Invalid or missing signatures return `HTTP 401`.

## Google Sheets Column Mapping (`Учёт сделок`)

| Column | Field |
|---|---|
| A | ID сделки |
| B | Статус сделки |
| C | Направление бизнеса |
| D | Клиент |
| E | Менеджер |
| F | Начислено с НДС |
| G | Наличие НДС |
| H | Оплачено |
| I | Дата начала проекта |
| J | Дата окончания проекта |
| K | Дата выставления акта |
| L | Переменный расход 1 |
| M | Переменный расход 2 |
| N | Бонус менеджера % |
| O | Бонус менеджера выплачено |
| P | Общепроизводственный расход |
| Q | Источник |
| R | Документ/ссылка |
| S | Комментарий |

