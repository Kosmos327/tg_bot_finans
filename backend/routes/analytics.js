'use strict';

const express = require('express');
const { requirePermission } = require('../middleware/auth');
const { deals, journalEntries, DEAL_STATUSES, JOURNAL_TYPES } = require('../data/store');

const router = express.Router();

// Все эндпоинты аналитики требуют права canViewAnalytics
router.use(requirePermission('canViewAnalytics'));

// ── GET /api/analytics/summary — сводная аналитика ───────────────────────

router.get('/summary', (req, res) => {
  const allDeals = Array.from(deals.values());
  const allJournal = Array.from(journalEntries.values());

  // Статистика по сделкам
  const dealStats = {
    total: allDeals.length,
    byStatus: {},
    totalAmount: 0,
    paidAmount: 0,
    unpaidAmount: 0,
  };

  for (const deal of allDeals) {
    dealStats.byStatus[deal.status] = (dealStats.byStatus[deal.status] || 0) + 1;
    dealStats.totalAmount += deal.amount || 0;
    if (deal.paid) {
      dealStats.paidAmount += deal.amount || 0;
    } else {
      dealStats.unpaidAmount += deal.amount || 0;
    }
  }

  // Статистика по журналу
  const journalStats = {
    totalIncome: 0,
    totalExpense: 0,
    balance: 0,
  };

  for (const entry of allJournal) {
    if (entry.type === JOURNAL_TYPES.INCOME) {
      journalStats.totalIncome += entry.amount || 0;
    } else {
      journalStats.totalExpense += entry.amount || 0;
    }
  }
  journalStats.balance = journalStats.totalIncome - journalStats.totalExpense;

  res.json({ deals: dealStats, journal: journalStats });
});

// ── GET /api/analytics/deals-by-month — сделки по месяцам ────────────────

router.get('/deals-by-month', (req, res) => {
  const allDeals = Array.from(deals.values());
  const byMonth = {};

  for (const deal of allDeals) {
    const month = deal.date ? deal.date.slice(0, 7) : 'unknown';
    if (!byMonth[month]) byMonth[month] = { count: 0, amount: 0 };
    byMonth[month].count += 1;
    byMonth[month].amount += deal.amount || 0;
  }

  // Сортировка по месяцу
  const result = Object.entries(byMonth)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([month, data]) => ({ month, ...data }));

  res.json(result);
});

module.exports = router;
