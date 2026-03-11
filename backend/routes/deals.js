'use strict';

const express = require('express');
const { v4: uuidv4 } = require('uuid');
const { requirePermission } = require('../middleware/auth');
const { deals, DEAL_STATUSES } = require('../data/store');
const {
  canViewAllDeals,
  canEditSalesFields,
  canEditAccountingFields,
} = require('../permissions');

const router = express.Router();

// ── Поля, доступные для редактирования по роли ────────────────────────────

/** Поля продаж — редактирует менеджер по продажам */
const SALES_FIELDS = ['name', 'client', 'status', 'amount', 'date', 'comment'];

/** Бухгалтерские поля — редактирует бухгалтер */
const ACCOUNTING_FIELDS = ['invoice', 'paid', 'paymentDate', 'accountingComment'];

// ── GET /api/deals — список сделок ───────────────────────────────────────

router.get('/', (req, res) => {
  let allDeals = Array.from(deals.values());

  // Менеджер видит только свои сделки
  if (!canViewAllDeals(req.user.role)) {
    allDeals = allDeals.filter((d) => d.createdBy === req.user.id);
  }

  // Скрываем бухгалтерские поля для тех, кто не может их редактировать/видеть
  const result = allDeals.map((d) => sanitizeDeal(d, req.user.role));

  res.json(result);
});

// ── GET /api/deals/:id — одна сделка ─────────────────────────────────────

router.get('/:id', (req, res) => {
  const deal = deals.get(req.params.id);
  if (!deal) return res.status(404).json({ error: 'Сделка не найдена' });

  // Менеджер может открыть только свою сделку
  if (!canViewAllDeals(req.user.role) && deal.createdBy !== req.user.id) {
    return res.status(403).json({ error: 'Доступ запрещён' });
  }

  res.json(sanitizeDeal(deal, req.user.role));
});

// ── POST /api/deals — создание сделки ────────────────────────────────────

router.post('/', requirePermission('canCreateDeals'), (req, res) => {
  const { name, client, status, amount, date, comment } = req.body;

  if (!name || !client) {
    return res.status(400).json({ error: 'Поля «Название» и «Клиент» обязательны' });
  }

  if (status && !Object.values(DEAL_STATUSES).includes(status)) {
    return res.status(400).json({ error: 'Недопустимый статус сделки' });
  }

  const deal = {
    id: uuidv4(),
    name,
    client,
    status: status || DEAL_STATUSES.NEW,
    amount: Number(amount) || 0,
    date: date || new Date().toISOString().slice(0, 10),
    comment: comment || '',
    invoice: '',
    paid: false,
    paymentDate: null,
    accountingComment: '',
    createdBy: req.user.id,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };

  deals.set(deal.id, deal);
  res.status(201).json(sanitizeDeal(deal, req.user.role));
});

// ── PATCH /api/deals/:id — обновление сделки ─────────────────────────────

router.patch('/:id', (req, res) => {
  const deal = deals.get(req.params.id);
  if (!deal) return res.status(404).json({ error: 'Сделка не найдена' });

  // Менеджер может обновлять только свою сделку
  if (!canViewAllDeals(req.user.role) && deal.createdBy !== req.user.id) {
    return res.status(403).json({ error: 'Доступ запрещён' });
  }

  const { role } = req.user;
  const updates = req.body;
  const updated = { ...deal };
  const rejectedFields = [];

  for (const field of Object.keys(updates)) {
    if (SALES_FIELDS.includes(field)) {
      // Поле продаж — нужно право canEditSalesFields
      if (canEditSalesFields(role)) {
        if (field === 'status' && !Object.values(DEAL_STATUSES).includes(updates[field])) {
          return res.status(400).json({ error: 'Недопустимый статус сделки' });
        }
        if (field === 'amount') {
          updated[field] = Number(updates[field]);
        } else {
          updated[field] = updates[field];
        }
      } else {
        rejectedFields.push(field);
      }
    } else if (ACCOUNTING_FIELDS.includes(field)) {
      // Бухгалтерское поле — нужно право canEditAccountingFields
      if (canEditAccountingFields(role)) {
        updated[field] = updates[field];
      } else {
        rejectedFields.push(field);
      }
    }
    // Системные поля (id, createdBy, createdAt) игнорируются
  }

  if (rejectedFields.length > 0 && Object.keys(updates).every((f) => rejectedFields.includes(f))) {
    // Все переданные поля отклонены — нет ни одного права
    return res.status(403).json({
      error: 'Доступ запрещён: нет прав на редактирование переданных полей',
      rejectedFields,
    });
  }

  updated.updatedAt = new Date().toISOString();
  deals.set(deal.id, updated);

  const response = sanitizeDeal(updated, role);
  if (rejectedFields.length > 0) {
    response._rejectedFields = rejectedFields;
  }
  res.json(response);
});

// ── DELETE /api/deals/:id — удаление сделки ──────────────────────────────

router.delete('/:id', requirePermission('canDeleteDeals'), (req, res) => {
  if (!deals.has(req.params.id)) {
    return res.status(404).json({ error: 'Сделка не найдена' });
  }
  deals.delete(req.params.id);
  res.json({ success: true });
});

// ── Утилиты ──────────────────────────────────────────────────────────────

/**
 * Скрывает бухгалтерские поля для ролей, которым они недоступны.
 * Менеджер по продажам не видит бухгалтерские данные; все остальные роли видят их.
 * @param {object} deal
 * @param {string} role
 * @returns {object}
 */
function sanitizeDeal(deal, role) {
  const result = { ...deal };

  // Бухгалтерские поля скрываем только для менеджера по продажам
  if (role === 'sales') {
    ACCOUNTING_FIELDS.forEach((f) => delete result[f]);
  }

  return result;
}

module.exports = router;
