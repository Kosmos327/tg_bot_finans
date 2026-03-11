# 💼 Финансовая система — Telegram Mini App

Полноценная система учёта сделок на базе Telegram Mini App с интеграцией Google Sheets.

## 🏗️ Архитектура

```
project/
  bot/              — Telegram бот (aiogram 3.x)
  backend/          — FastAPI REST API
    routers/        — Эндпоинты (deals, settings, auth)
    services/       — Бизнес-логика (Google Sheets, auth)
    models/         — Pydantic схемы
  miniapp/          — Фронтенд Mini App (HTML/CSS/JS)
  config/           — Конфигурация приложения
```

## 🚀 Установка и запуск

### 1. Клонирование и зависимости

```bash
git clone <repo>
cd tg_bot_finans
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

```bash
cp .env.example .env
```

Заполните `.env`:

```env
BOT_TOKEN=ваш_токен_бота
WEBAPP_URL=https://ваш-домен.com/miniapp
GOOGLE_SERVICE_ACCOUNT_FILE=service_account.json
GOOGLE_SHEETS_SPREADSHEET_ID=id_вашей_таблицы
TELEGRAM_BOT_TOKEN=ваш_токен_бота
API_BASE_URL=http://localhost:8000
```

### 3. Подключение Google Sheets

#### Создание сервисного аккаунта

1. Откройте [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Включите **Google Sheets API** и **Google Drive API**
4. Создайте сервисный аккаунт: `IAM & Admin → Service Accounts → Create`
5. Скачайте ключ в формате JSON и сохраните как `service_account.json` в корень проекта
6. Скопируйте email сервисного аккаунта (вида `xxx@project.iam.gserviceaccount.com`)

#### Настройка таблицы Google Sheets

1. Создайте таблицу Google Sheets
2. Откройте доступ для сервисного аккаунта: `Поделиться → вставьте email → Редактор`
3. Скопируйте ID таблицы из URL: `https://docs.google.com/spreadsheets/d/**ВАШ_ID**/edit`
4. Создайте листы:
   - **"Учёт сделок"** — с заголовками в строке 1:
     `ID сделки | Статус сделки | Направление бизнеса | Клиент | Менеджер | Начислено с НДС | Наличие НДС | Оплачено | Дата начала проекта | Дата окончания проекта | Дата выставления акта | Переменный расход 1 | Переменный расход 2 | Бонус менеджера % | Бонус менеджера выплачено | Общепроизводственный расход | Источник | Документ/ссылка | Комментарий`
   - **"Настройки"** — справочники в формате:
     ```
     Статусы сделок | Новая | В работе | Завершена | Отменена
     Направления    | Разработка | Консалтинг | Дизайн
     Клиенты        | ООО Ромашка | ИП Иванов
     Менеджеры      | Иванов А. | Петров Б.
     Типы НДС       | С НДС | Без НДС
     Источники      | Рекомендация | Сайт | Реклама
     ```
   - **"Журнал действий"** — пустой лист (заполняется автоматически)

### 4. Запуск Backend API

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Документация API доступна по адресу: `http://localhost:8000/docs`

### 5. Запуск Telegram бота

```bash
python -m bot.bot
```

### 6. Настройка Telegram Mini App

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Выберите вашего бота → `Bot Settings → Menu Button → Configure menu button`
3. Установите URL: `https://ваш-домен.com/miniapp/index.html`
4. Либо установите через команду `/newapp`

> **Важно**: Mini App URL должен быть HTTPS. Для разработки используйте [ngrok](https://ngrok.com/) или аналоги.

#### Настройка для разработки с ngrok:

```bash
ngrok http 8000
# Скопируйте HTTPS URL и установите в WEBAPP_URL
```

## 🔌 API Эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/health` | Проверка состояния API |
| GET | `/settings` | Загрузка справочников |
| POST | `/deal/create` | Создание новой сделки |
| GET | `/deal/user` | Список сделок (с фильтром по менеджеру) |
| GET | `/deal/{deal_id}` | Получение сделки по ID |
| PUT | `/deal/{deal_id}` | Обновление сделки |
| POST | `/auth/validate` | Валидация Telegram initData |

## 📱 Возможности Mini App

- **🆕 Новая сделка** — форма создания сделки с 5 разделами
- **📂 Мои сделки** — список сделок с фильтрацией по статусу, клиенту, месяцу
- **⚙️ Настройки** — информация о справочниках и статусах подключений

## 🛡️ Безопасность

- Валидация Telegram WebApp `initData` согласно [официальной документации](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app)
- Передача `initData` через заголовок `X-Telegram-Init-Data`
- Все операции записываются в журнал действий

## 🧰 Технологии

- **Backend**: Python 3.11, FastAPI, gspread, aiogram 3.x, pydantic v2
- **Frontend**: Vanilla JS, Telegram WebApp SDK
- **Интеграция**: Google Sheets API с сервисным аккаунтом

