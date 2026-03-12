'use strict';

const { v4: uuidv4 } = require('uuid');

/**
 * Хранилище данных в памяти.
 * В production заменяется реальной СУБД.
 */

// ── Сделки ─────────────────────────────────────────────────────────────────

/** @type {Map<string, object>} */
const deals = new Map();

/** Статусы сделок */
const DEAL_STATUSES = {
  NEW: 'new',
  IN_PROGRESS: 'in_progress',
  COMPLETED: 'completed',
  CANCELLED: 'cancelled',
};

/** Названия статусов на русском */
const DEAL_STATUS_LABELS = {
  new: 'Новая',
  in_progress: 'В работе',
  completed: 'Завершена',
  cancelled: 'Отменена',
};

// Начальные демо-данные
const seedDeals = [
  {
    id: uuidv4(),
    // Поля продаж
    name: 'Поставка оборудования ООО Альфа',
    client: 'ООО Альфа',
    status: DEAL_STATUSES.COMPLETED,
    amount: 350000,
    date: '2024-01-10',
    comment: 'Срочная поставка',
    // Бухгалтерские поля
    invoice: '2024-001',
    paid: true,
    paymentDate: '2024-01-15',
    accountingComment: 'Оплачено в полном объёме',
    // Системные поля
    createdBy: 'user_sales',
    createdAt: '2024-01-10T09:00:00Z',
    updatedAt: '2024-01-15T11:00:00Z',
  },
  {
    id: uuidv4(),
    name: 'Сервисный контракт ЗАО Бета',
    client: 'ЗАО Бета',
    status: DEAL_STATUSES.IN_PROGRESS,
    amount: 120000,
    date: '2024-02-01',
    comment: '',
    invoice: '2024-002',
    paid: false,
    paymentDate: null,
    accountingComment: 'Ожидаем оплату',
    createdBy: 'user_sales',
    createdAt: '2024-02-01T10:00:00Z',
    updatedAt: '2024-02-01T10:00:00Z',
  },
  {
    id: uuidv4(),
    name: 'Консалтинг ИП Гамма',
    client: 'ИП Гамма',
    status: DEAL_STATUSES.NEW,
    amount: 45000,
    date: '2024-03-05',
    comment: 'Первичная встреча запланирована',
    invoice: '',
    paid: false,
    paymentDate: null,
    accountingComment: '',
    createdBy: 'user_admin',
    createdAt: '2024-03-05T08:30:00Z',
    updatedAt: '2024-03-05T08:30:00Z',
  },
];

seedDeals.forEach((d) => deals.set(d.id, d));

// ── Журнал ──────────────────────────────────────────────────────────────────

/** @type {Map<string, object>} */
const journalEntries = new Map();

const JOURNAL_TYPES = { INCOME: 'income', EXPENSE: 'expense' };

const JOURNAL_TYPE_LABELS = {
  income: 'Приход',
  expense: 'Расход',
};

const seedJournal = [
  {
    id: uuidv4(),
    date: '2024-01-15',
    type: JOURNAL_TYPES.INCOME,
    amount: 350000,
    description: 'Оплата по сделке: Поставка оборудования ООО Альфа',
    dealId: null,
    createdBy: 'user_acc',
    createdAt: '2024-01-15T11:00:00Z',
  },
  {
    id: uuidv4(),
    date: '2024-01-20',
    type: JOURNAL_TYPES.EXPENSE,
    amount: 80000,
    description: 'Закупка комплектующих',
    dealId: null,
    createdBy: 'user_acc',
    createdAt: '2024-01-20T14:00:00Z',
  },
  {
    id: uuidv4(),
    date: '2024-02-10',
    type: JOURNAL_TYPES.EXPENSE,
    amount: 25000,
    description: 'Аренда офиса — февраль',
    dealId: null,
    createdBy: 'user_acc',
    createdAt: '2024-02-10T09:00:00Z',
  },
];

seedJournal.forEach((e) => journalEntries.set(e.id, e));

// ── Экспорт ─────────────────────────────────────────────────────────────────

module.exports = {
  deals,
  journalEntries,
  DEAL_STATUSES,
  DEAL_STATUS_LABELS,
  JOURNAL_TYPES,
  JOURNAL_TYPE_LABELS,
};
