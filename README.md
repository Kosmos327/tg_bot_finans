# tg_bot_finans — Финансовый менеджер (Telegram Mini App)

Telegram Mini App для управления финансовыми сделками с **ролевой системой доступа**.

## Роли и права доступа

| Право | admin | sales | accounting | viewer |
|-------|:-----:|:-----:|:----------:|:------:|
| Видеть все сделки | ✅ | ❌ (только свои) | ✅ | ✅ |
| Создавать сделки | ✅ | ✅ | ❌ | ❌ |
| Удалять сделки | ✅ | ❌ | ❌ | ❌ |
| Редактировать поля продаж | ✅ | ✅ | ❌ | ❌ |
| Редактировать бухгалтерские поля | ✅ | ❌ | ✅ | ❌ |
| Просматривать журнал | ✅ | ❌ | ✅ | ✅ |
| Просматривать аналитику | ✅ | ❌ | ✅ | ✅ |
| Настройки / пользователи | ✅ | ❌ | ❌ | ❌ |

## Структура проекта

```
tg_bot_finans/
├── backend/                   # Node.js + Express API
│   ├── server.js              # Точка входа
│   ├── permissions/index.js   # Централизованная матрица прав + хелперы
│   ├── middleware/auth.js     # Аутентификация и проверка прав
│   ├── data/store.js          # Хранилище данных (in-memory)
│   ├── routes/
│   │   ├── deals.js           # CRUD сделок с проверкой прав
│   │   ├── journal.js         # Журнал операций
│   │   └── analytics.js       # Аналитика
│   └── tests/
│       ├── permissions.test.js
│       └── deals.test.js
└── frontend/                  # Telegram Mini App (HTML/CSS/JS)
    ├── index.html
    ├── css/styles.css
    └── js/
        ├── permissions.js     # Матрица прав на фронте (зеркало backend)
        ├── api.js             # API-клиент
        └── app.js             # Главная логика + UI-компоненты
```

## Запуск

### Backend

```bash
cd backend
npm install
npm start          # http://localhost:3000
npm test           # запуск тестов
```

### Frontend

Откройте `frontend/index.html` в браузере или разместите на статическом хостинге.
Убедитесь, что backend запущен на `http://localhost:3000`.

## API эндпоинты

| Метод | URL | Описание | Права |
|-------|-----|----------|-------|
| GET | `/api/demo-users` | Список демо-пользователей | публичный |
| GET | `/api/me` | Текущий пользователь + права | любой |
| GET | `/api/deals` | Список сделок | любой |
| POST | `/api/deals` | Создать сделку | canCreateDeals |
| PATCH | `/api/deals/:id` | Обновить сделку | canEditSalesFields / canEditAccountingFields |
| DELETE | `/api/deals/:id` | Удалить сделку | canDeleteDeals |
| GET | `/api/journal` | Журнал | canViewJournal |
| POST | `/api/journal` | Добавить запись | canEditAccountingFields |
| GET | `/api/analytics/summary` | Сводка | canViewAnalytics |
| GET | `/api/analytics/deals-by-month` | Сделки по месяцам | canViewAnalytics |

## Заголовок аутентификации

Все защищённые запросы требуют заголовок:
```
X-User-Id: user_admin | user_sales | user_acc | user_view
```

