'use strict';

const express = require('express');
const cors = require('cors');
const { authenticate } = require('./middleware/auth');
const { getPermissionsForRole, ROLES } = require('./permissions');
const { DEMO_USERS } = require('./middleware/auth');

const dealsRouter = require('./routes/deals');
const journalRouter = require('./routes/journal');
const analyticsRouter = require('./routes/analytics');

const app = express();

// ── Middleware ────────────────────────────────────────────────────────────

app.use(cors());
app.use(express.json());

// ── Публичные эндпоинты ───────────────────────────────────────────────────

/** Возвращает список демо-пользователей (для UI-переключателя роли) */
app.get('/api/demo-users', (req, res) => {
  const users = Object.values(DEMO_USERS).map((u) => ({
    id: u.id,
    name: u.name,
    role: u.role,
    permissions: getPermissionsForRole(u.role),
  }));
  res.json(users);
});

// ── Аутентификация для всех /api маршрутов ────────────────────────────────
app.use('/api', authenticate);

// ── Профиль текущего пользователя ─────────────────────────────────────────

app.get('/api/me', (req, res) => {
  res.json({
    id: req.user.id,
    name: req.user.name,
    role: req.user.role,
    permissions: req.userPermissions,
  });
});

// ── Защищённые роуты ──────────────────────────────────────────────────────

app.use('/api/deals', dealsRouter);
app.use('/api/journal', journalRouter);
app.use('/api/analytics', analyticsRouter);

// ── Обработка ошибок ──────────────────────────────────────────────────────

app.use((req, res) => res.status(404).json({ error: 'Маршрут не найден' }));

// eslint-disable-next-line no-unused-vars
app.use((err, req, res, next) => {
  console.error(err);
  res.status(500).json({ error: 'Внутренняя ошибка сервера' });
});

// ── Запуск ────────────────────────────────────────────────────────────────

const PORT = process.env.PORT || 3000;

/* istanbul ignore next */
if (require.main === module) {
  app.listen(PORT, () => console.log(`Сервер запущен на порту ${PORT}`));
}

module.exports = app;
