'use strict';

const express = require('express');
const { v4: uuidv4 } = require('uuid');
const { requirePermission } = require('../middleware/auth');
const { journalEntries, JOURNAL_TYPES } = require('../data/store');

const router = express.Router();

// Все эндпоинты журнала требуют права canViewJournal
router.use(requirePermission('canViewJournal'));

// ── GET /api/journal — список записей ────────────────────────────────────

router.get('/', (req, res) => {
  const entries = Array.from(journalEntries.values()).sort(
    (a, b) => new Date(b.date) - new Date(a.date)
  );
  res.json(entries);
});

// ── GET /api/journal/:id — одна запись ───────────────────────────────────

router.get('/:id', (req, res) => {
  const entry = journalEntries.get(req.params.id);
  if (!entry) return res.status(404).json({ error: 'Запись не найдена' });
  res.json(entry);
});

// ── POST /api/journal — добавить запись (только бухгалтер/admin) ─────────

router.post('/', requirePermission('canEditAccountingFields'), (req, res) => {
  const { date, type, amount, description, dealId } = req.body;

  if (!date || !type || !amount || !description) {
    return res.status(400).json({ error: 'Поля date, type, amount, description обязательны' });
  }

  if (!Object.values(JOURNAL_TYPES).includes(type)) {
    return res.status(400).json({ error: 'Недопустимый тип записи' });
  }

  const entry = {
    id: uuidv4(),
    date,
    type,
    amount: Number(amount),
    description,
    dealId: dealId || null,
    createdBy: req.user.id,
    createdAt: new Date().toISOString(),
  };

  journalEntries.set(entry.id, entry);
  res.status(201).json(entry);
});

// ── DELETE /api/journal/:id — удалить запись (только admin) ──────────────

router.delete('/:id', requirePermission('canDeleteDeals'), (req, res) => {
  if (!journalEntries.has(req.params.id)) {
    return res.status(404).json({ error: 'Запись не найдена' });
  }
  journalEntries.delete(req.params.id);
  res.json({ success: true });
});

module.exports = router;
