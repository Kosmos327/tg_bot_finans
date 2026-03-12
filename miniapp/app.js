/* ─────────────────────────────────────────────────────────
   Финансовый ERP — Telegram Mini App Logic
   ───────────────────────────────────────────────────────── */

/* =========================================================
   Configuration
   ========================================================= */
const API_BASE = (window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1'))
  ? 'http://localhost:8000'
  : window.location.origin;

// ── Mock Data ─────────────────────────────────────────────

const MOCK_DEALS = [
  {
    id: 1,
    title: 'Поставка IT-оборудования',
    client: 'ООО «Технолайн»',
    manager: 'Иванов И.И.',
    manager_id: 1,
    amount: 850000,
    status: 'active',
    stage: 'Переговоры',
    payment_status: 'partial',
    paid_amount: 425000,
    date: '2026-03-10',
    due_date: '2026-03-28',
  },
  {
    id: 2,
    title: 'Разработка корпоративного портала',
    client: 'ЗАО «МедиаГрупп»',
    manager: 'Петрова А.С.',
    manager_id: 2,
    amount: 1200000,
    status: 'active',
    stage: 'Коммерческое предложение',
    payment_status: 'pending',
    paid_amount: 0,
    date: '2026-03-08',
    due_date: '2026-04-15',
  },
  {
    id: 3,
    title: 'Аутсорсинг бухгалтерии',
    client: 'ИП Смирнов К.В.',
    manager: 'Иванов И.И.',
    manager_id: 1,
    amount: 240000,
    status: 'won',
    stage: 'Закрыто',
    payment_status: 'paid',
    paid_amount: 240000,
    date: '2026-02-20',
    due_date: '2026-03-01',
  },
  {
    id: 4,
    title: 'Лицензии ПО Microsoft 365',
    client: 'АО «Строй Инвест»',
    manager: 'Козлов М.Р.',
    manager_id: 3,
    amount: 390000,
    status: 'active',
    stage: 'Согласование договора',
    payment_status: 'overdue',
    paid_amount: 0,
    date: '2026-02-15',
    due_date: '2026-03-01',
  },
  {
    id: 5,
    title: 'Техобслуживание серверного зала',
    client: 'ООО «ЛогистикПро»',
    manager: 'Петрова А.С.',
    manager_id: 2,
    amount: 175000,
    status: 'active',
    stage: 'Первичный контакт',
    payment_status: 'pending',
    paid_amount: 0,
    date: '2026-03-12',
    due_date: '2026-04-10',
  },
  {
    id: 6,
    title: 'Внедрение CRM системы',
    client: 'ООО «РетейлМакс»',
    manager: 'Иванов И.И.',
    manager_id: 1,
    amount: 680000,
    status: 'on_hold',
    stage: 'Квалификация',
    payment_status: 'pending',
    paid_amount: 0,
    date: '2026-03-05',
    due_date: '2026-04-30',
  },
  {
    id: 7,
    title: 'Аудит информационной безопасности',
    client: 'ПАО «ФинансБанк»',
    manager: 'Козлов М.Р.',
    manager_id: 3,
    amount: 520000,
    status: 'active',
    stage: 'Презентация',
    payment_status: 'partial',
    paid_amount: 200000,
    date: '2026-03-01',
    due_date: '2026-03-20',
  },
  {
    id: 8,
    title: 'Облачная миграция данных',
    client: 'ООО «ДатаСервис»',
    manager: 'Сидорова Н.В.',
    manager_id: 4,
    amount: 950000,
    status: 'new',
    stage: 'Первичный контакт',
    payment_status: 'pending',
    paid_amount: 0,
    date: '2026-03-11',
    due_date: '2026-05-01',
  },
  {
    id: 9,
    title: 'Поддержка 1С:Предприятие',
    client: 'ИП Новикова О.Д.',
    manager: 'Сидорова Н.В.',
    manager_id: 4,
    amount: 96000,
    status: 'won',
    stage: 'Закрыто',
    payment_status: 'paid',
    paid_amount: 96000,
    date: '2026-02-28',
    due_date: '2026-03-05',
  },
  {
    id: 10,
    title: 'Разработка мобильного приложения',
    client: 'ООО «АгроТех»',
    manager: 'Петрова А.С.',
    manager_id: 2,
    amount: 1800000,
    status: 'lost',
    stage: 'Проигрыш',
    payment_status: 'pending',
    paid_amount: 0,
    date: '2026-02-10',
    due_date: '2026-03-10',
  },
];

const MOCK_TEAM = [
  { id: 1, name: 'Иванов И.И.',    initial: 'И', deals: 8,  won: 3, amount: 1770000, target: 2000000 },
  { id: 2, name: 'Петрова А.С.',   initial: 'П', deals: 7,  won: 2, amount: 3175000, target: 3500000 },
  { id: 3, name: 'Козлов М.Р.',    initial: 'К', deals: 6,  won: 4, amount: 910000,  target: 1500000 },
  { id: 4, name: 'Сидорова Н.В.',  initial: 'С', deals: 5,  won: 3, amount: 1046000, target: 1200000 },
  { id: 5, name: 'Фёдоров Д.А.',   initial: 'Ф', deals: 4,  won: 1, amount: 340000,  target: 800000 },
];

// ── Role Config ───────────────────────────────────────────

const ROLES = {
  manager: {
    id: 'manager',
    cssClass: 'role-manager',
    name: 'Менеджер',
    badgeLabel: 'Менеджер по продажам',
    icon: '👤',
    navItems: [
      { icon: '🏠', label: 'Главная',  tab: 'dashboard' },
      { icon: '💼', label: 'Сделки',   tab: 'deals' },
      { icon: '✅', label: 'Задачи',   tab: 'tasks' },
      { icon: '👤', label: 'Профиль',  tab: 'profile' },
    ],
    tabs: ['Мои сделки', 'Задачи'],
    filters: ['all', 'active', 'won', 'lost', 'on_hold'],
    filterLabels: { all: 'Все', active: 'В работе', won: 'Выиграно', lost: 'Проиграно', on_hold: 'На паузе' },
  },
  accountant: {
    id: 'accountant',
    cssClass: 'role-accountant',
    name: 'Бухгалтер',
    badgeLabel: 'Бухгалтер',
    icon: '📊',
    navItems: [
      { icon: '🏠', label: 'Главная',  tab: 'dashboard' },
      { icon: '💳', label: 'Платежи',  tab: 'payments' },
      { icon: '📋', label: 'Счета',    tab: 'invoices' },
      { icon: '📈', label: 'Отчёты',   tab: 'reports' },
    ],
    tabs: ['Платежи', 'Счета', 'Отчёты'],
    filters: ['all', 'pending', 'partial', 'overdue', 'paid'],
    filterLabels: { all: 'Все', pending: 'Ожидает', partial: 'Частично', overdue: 'Просрочено', paid: 'Оплачено' },
  },
  opdir: {
    id: 'opdir',
    cssClass: 'role-opdir',
    name: 'Оп. директор',
    badgeLabel: 'Операционный директор',
    icon: '🏢',
    navItems: [
      { icon: '🏠', label: 'Главная',  tab: 'dashboard' },
      { icon: '💼', label: 'Сделки',   tab: 'deals' },
      { icon: '👥', label: 'Команда',  tab: 'team' },
      { icon: '📈', label: 'Аналитика',tab: 'analytics' },
    ],
    tabs: ['Все сделки', 'Менеджеры', 'Аналитика'],
    filters: ['all', 'new', 'active', 'won', 'lost'],
    filterLabels: { all: 'Все', new: 'Новые', active: 'В работе', won: 'Закрыто', lost: 'Потеряно' },
  },
  rop: {
    id: 'rop',
    cssClass: 'role-rop',
    name: 'РОП',
    badgeLabel: 'Руководитель отдела продаж',
    icon: '🎯',
    navItems: [
      { icon: '🏠', label: 'Главная',  tab: 'dashboard' },
      { icon: '💼', label: 'Сделки',   tab: 'deals' },
      { icon: '👥', label: 'Команда',  tab: 'team' },
      { icon: '🎯', label: 'Планы',    tab: 'goals' },
    ],
    tabs: ['Все сделки', 'Команда', 'Планы'],
    filters: ['all', 'active', 'won', 'new', 'lost'],
    filterLabels: { all: 'Все', active: 'В работе', won: 'Выиграно', new: 'Новые', lost: 'Проиграно' },
  },
};

// ── Status / Payment helpers ──────────────────────────────

const STATUS_MAP = {
  new:      { label: 'Новая',       cls: 'deal-status-badge--new',    dot: '●' },
  active:   { label: 'В работе',    cls: 'deal-status-badge--active',  dot: '●' },
  won:      { label: 'Выиграно',    cls: 'deal-status-badge--won',     dot: '✔' },
  lost:     { label: 'Проиграно',   cls: 'deal-status-badge--lost',    dot: '✕' },
  on_hold:  { label: 'На паузе',    cls: 'deal-status-badge--hold',    dot: '⏸' },
};

const PAYMENT_MAP = {
  pending:  { label: 'Ожидает',       cls: 'deal-payment-badge--pending' },
  partial:  { label: 'Частично',      cls: 'deal-payment-badge--partial' },
  paid:     { label: 'Оплачено',      cls: 'deal-payment-badge--paid' },
  overdue:  { label: 'Просрочено',    cls: 'deal-payment-badge--overdue' },
};

// ── App State ─────────────────────────────────────────────

const State = {
  role: null,
  userName: 'Пользователь',
  userInitial: 'П',
  activeTab: 0,
  activeFilter: 'all',
  activeNav: 0,
  deals: MOCK_DEALS,
};

// ── Utilities ─────────────────────────────────────────────

function fmt(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace('.', ',') + ' млн ₽';
  if (n >= 1_000)     return (n / 1_000).toFixed(0) + ' тыс. ₽';
  return n.toLocaleString('ru-RU') + ' ₽';
}

function fmtShort(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace('.', ',') + 'M';
  if (n >= 1_000)     return Math.round(n / 1_000) + 'K';
  return String(n);
}

function fmtDate(dateStr) {
  const d = new Date(dateStr);
  const months = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек'];
  return d.getDate() + ' ' + months[d.getMonth()];
}

function pct(part, total) {
  if (!total) return 0;
  return Math.round((part / total) * 100);
}

function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
}

function svgIcon(path, size = 12) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
}

// ── Component Renderers ───────────────────────────────────

function renderKpiCard({ value, label, trend, trendDir }) {
  const trendClass = trendDir === 'up' ? 'kpi-card__trend--up' : trendDir === 'down' ? 'kpi-card__trend--down' : 'kpi-card__trend--warn';
  const trendArrow = trendDir === 'up' ? '↑' : trendDir === 'down' ? '↓' : '→';
  return `
    <div class="kpi-card">
      <div class="kpi-card__value">${value}</div>
      <div class="kpi-card__label">${label}</div>
      ${trend ? `<div class="kpi-card__trend ${trendClass}">${trendArrow} ${trend}</div>` : ''}
    </div>`;
}

function renderDealCard(deal, showManager = false) {
  const st = STATUS_MAP[deal.status] || STATUS_MAP.new;
  const pay = PAYMENT_MAP[deal.payment_status] || PAYMENT_MAP.pending;
  const payPct = pct(deal.paid_amount, deal.amount);
  const fillCls = deal.payment_status === 'paid' ? 'progress-bar__fill--paid'
                : deal.payment_status === 'overdue' ? 'progress-bar__fill--overdue'
                : 'progress-bar__fill--partial';

  const managerHtml = showManager
    ? `<span class="deal-meta__item">${svgIcon('<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>')} ${deal.manager}</span>`
    : '';

  return `
    <div class="deal-card" data-id="${deal.id}">
      <div class="deal-card__top">
        <div>
          <div class="deal-card__title">${deal.title}</div>
          <div class="deal-card__stage">${deal.stage}</div>
        </div>
        <span class="deal-status-badge ${st.cls}">${st.dot} ${st.label}</span>
      </div>
      <div class="deal-card__middle">
        <div class="deal-amount">
          <div class="deal-amount__value">${fmt(deal.amount)}</div>
          <div class="deal-amount__label">Сумма сделки</div>
        </div>
        <div class="deal-payment">
          <span class="deal-payment-badge ${pay.cls}">${pay.label}</span>
          <div class="deal-payment__progress">
            <div class="progress-bar" style="width:80px">
              <div class="progress-bar__fill ${fillCls}" style="width:${payPct}%"></div>
            </div>
            <span class="progress-pct">${payPct}%</span>
          </div>
        </div>
      </div>
      <div class="deal-card__bottom">
        <div class="deal-meta">
          <span class="deal-meta__item">${svgIcon('<path d="M20 7H4a2 2 0 0 0-2 2v6c0 1.1.9 2 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z"/><polyline points="16 3 12 7 8 3"/>')} ${deal.client}</span>
          ${managerHtml}
        </div>
        <span class="deal-date">${fmtDate(deal.date)}</span>
      </div>
    </div>`;
}

function renderEmptyState(icon, title, sub, btnLabel, btnAction) {
  return `
    <div class="empty-state">
      <div class="empty-state__icon">${icon}</div>
      <div class="empty-state__title">${title}</div>
      <div class="empty-state__sub">${sub}</div>
      ${btnLabel ? `<button class="empty-state__btn" onclick="${btnAction}">${btnLabel}</button>` : ''}
    </div>`;
}

function renderFilterRow(filters, filterLabels, active) {
  return filters.map(f =>
    `<button class="chip ${active === f ? 'active' : ''}" data-filter="${f}">${filterLabels[f]}</button>`
  ).join('');
}

// ── KPI Calculations ──────────────────────────────────────

function calcManagerKPIs(deals, managerId) {
  const my = deals.filter(d => d.manager_id === managerId);
  const won = my.filter(d => d.status === 'won');
  const total = my.reduce((s, d) => s + d.amount, 0);
  const conv = my.length ? Math.round((won.length / my.length) * 100) : 0;
  return [
    { value: String(my.length),       label: 'Мои сделки',    trend: '+2 за месяц', trendDir: 'up' },
    { value: fmtShort(total) + ' ₽',  label: 'В пайплайне',   trend: null },
    { value: String(won.length),       label: 'Закрыто',       trend: 'в этом месяце', trendDir: 'up' },
    { value: conv + '%',               label: 'Конверсия',     trend: conv > 35 ? 'хороший' : 'нужно выше', trendDir: conv > 35 ? 'up' : 'warn' },
  ];
}

function calcAccountantKPIs(deals) {
  const pending   = deals.filter(d => d.payment_status === 'pending').reduce((s, d) => s + d.amount, 0);
  const overdue   = deals.filter(d => d.payment_status === 'overdue').reduce((s, d) => s + d.amount, 0);
  const paid      = deals.filter(d => d.payment_status === 'paid').reduce((s, d) => s + d.amount, 0);
  const partial   = deals.filter(d => d.payment_status === 'partial').reduce((s, d) => s + (d.amount - d.paid_amount), 0);
  const debit     = pending + partial;
  return [
    { value: fmtShort(pending) + ' ₽',  label: 'К оплате',      trend: null },
    { value: fmtShort(overdue) + ' ₽',  label: 'Просрочено',     trend: overdue > 0 ? String(deals.filter(d => d.payment_status === 'overdue').length) + ' сделок' : 'Нет', trendDir: overdue > 0 ? 'down' : 'up' },
    { value: fmtShort(paid) + ' ₽',     label: 'Оплачено',       trend: 'за месяц', trendDir: 'up' },
    { value: fmtShort(debit) + ' ₽',    label: 'Дебиторка',      trend: null },
  ];
}

function calcOpDirKPIs(deals) {
  const total  = deals.length;
  const won    = deals.filter(d => d.status === 'won');
  const rev    = won.reduce((s, d) => s + d.amount, 0);
  const conv   = total ? Math.round((won.length / total) * 100) : 0;
  const newD   = deals.filter(d => d.status === 'new').length;
  return [
    { value: String(total),             label: 'Всего сделок',   trend: '+' + newD + ' новых', trendDir: 'up' },
    { value: fmtShort(rev) + ' ₽',     label: 'Выручка',        trend: 'за месяц', trendDir: 'up' },
    { value: conv + '%',                label: 'Конверсия',      trend: null },
    { value: String(newD),              label: 'Новых сделок',   trend: 'за 7 дней', trendDir: newD > 2 ? 'up' : 'warn' },
  ];
}

function calcRopKPIs() {
  const teamSize    = MOCK_TEAM.length;
  const totalRev    = MOCK_TEAM.reduce((s, t) => s + t.amount, 0);
  const totalTarget = MOCK_TEAM.reduce((s, t) => s + t.target, 0);
  const targetPct   = Math.round((totalRev / totalTarget) * 100);
  const totalWon    = MOCK_TEAM.reduce((s, t) => s + t.won, 0);
  const totalDeals  = MOCK_TEAM.reduce((s, t) => s + t.deals, 0);
  const winRate     = Math.round((totalWon / totalDeals) * 100);
  return [
    { value: String(teamSize),          label: 'Менеджеров',    trend: 'в команде', trendDir: 'up' },
    { value: fmtShort(totalRev) + ' ₽', label: 'Выручка',       trend: targetPct + '% от плана', trendDir: targetPct >= 70 ? 'up' : 'warn' },
    { value: String(totalWon),          label: 'Закрыто',       trend: 'сделок', trendDir: 'up' },
    { value: winRate + '%',             label: 'Win Rate',       trend: winRate > 35 ? 'выше нормы' : 'ниже цели', trendDir: winRate > 35 ? 'up' : 'warn' },
  ];
}

// ── Dashboard Renderers ───────────────────────────────────

function buildManagerDashboard() {
  const managerId = 1; // current user (Иванов)
  const myDeals = State.deals.filter(d => d.manager_id === managerId);
  const filtered = State.activeFilter === 'all' ? myDeals : myDeals.filter(d => d.status === State.activeFilter);
  const roleConf = ROLES.manager;
  const tab = State.activeTab;

  // KPI
  const kpis = calcManagerKPIs(State.deals, managerId);
  renderKpiSummary(kpis);

  // Tabs
  renderTabBar(roleConf.tabs);

  // Nav
  renderBottomNav(roleConf.navItems);

  // Sticky actions
  showStickyActions([
    { label: '+ Новая сделка', cls: 'action-btn--primary', action: 'App.noop()' },
  ]);

  const content = document.getElementById('app-content');

  if (tab === 0) {
    // Summary stats row
    const won   = myDeals.filter(d => d.status === 'won').length;
    const total = myDeals.reduce((s, d) => s + d.amount, 0);

    const statsHtml = `
      <div class="stats-row fade-in-up">
        <div class="stats-cell">
          <div class="stats-cell__value">${myDeals.length}</div>
          <div class="stats-cell__label">Мои сделки</div>
        </div>
        <div class="stats-cell">
          <div class="stats-cell__value">${won}</div>
          <div class="stats-cell__label">Закрыто</div>
        </div>
        <div class="stats-cell">
          <div class="stats-cell__value">${fmtShort(total)}₽</div>
          <div class="stats-cell__label">Пайплайн</div>
        </div>
      </div>`;

    const dealsHtml = filtered.length > 0
      ? filtered.map(d => renderDealCard(d, false)).join('')
      : renderEmptyState('💼', 'Нет сделок', 'Сделки с выбранным статусом не найдены.', 'Создать сделку', 'App.noop()');

    content.innerHTML = `
      ${statsHtml}
      <div class="section-card fade-in-up fade-in-up--1">
        <div class="section-header">
          <span class="section-title">Мои сделки</span>
          <span class="section-count">${filtered.length}</span>
        </div>
        <div class="filter-row">${renderFilterRow(roleConf.filters, roleConf.filterLabels, State.activeFilter)}</div>
        <div class="deal-list">${dealsHtml}</div>
      </div>`;

  } else if (tab === 1) {
    content.innerHTML = `
      <div class="section-card fade-in-up">
        <div class="section-header"><span class="section-title">Задачи на сегодня</span><span class="section-count">0</span></div>
        ${renderEmptyState('✅', 'Задач нет', 'Все задачи выполнены или ещё не назначены.', null, null)}
      </div>`;
  }

  bindFilters();
}

function buildAccountantDashboard() {
  const deals = State.deals;
  const filtered = State.activeFilter === 'all'
    ? deals
    : deals.filter(d => d.payment_status === State.activeFilter);
  const roleConf = ROLES.accountant;
  const tab = State.activeTab;

  const kpis = calcAccountantKPIs(deals);
  renderKpiSummary(kpis);
  renderTabBar(roleConf.tabs);
  renderBottomNav(roleConf.navItems);
  showStickyActions([
    { label: '+ Создать счёт', cls: 'action-btn--primary', action: 'App.noop()' },
    { label: 'Экспорт',        cls: 'action-btn--secondary', action: 'App.noop()' },
  ]);

  const content = document.getElementById('app-content');
  const overdueDeals = deals.filter(d => d.payment_status === 'overdue');
  const pendingDeals = deals.filter(d => d.payment_status === 'pending');

  const alertHtml = overdueDeals.length > 0
    ? `<div class="alert-banner fade-in-up">
        <div class="alert-banner__icon">⚠️</div>
        <div class="alert-banner__text">
          <div class="alert-banner__title">Просроченных платежей: ${overdueDeals.length}</div>
          Необходимо срочно связаться с клиентами или инициировать претензионную работу.
        </div>
      </div>` : '';

  if (tab === 0) {
    // Payment tab
    const pendingTotal  = pendingDeals.reduce((s, d) => s + d.amount, 0);
    const overdueTotal  = overdueDeals.reduce((s, d) => s + d.amount, 0);
    const paidTotal     = deals.filter(d => d.payment_status === 'paid').reduce((s, d) => s + d.amount, 0);
    const partialTotal  = deals.filter(d => d.payment_status === 'partial').reduce((s, d) => s + (d.amount - d.paid_amount), 0);

    const dealsHtml = filtered.length > 0
      ? filtered.map(d => renderDealCard(d, true)).join('')
      : renderEmptyState('💳', 'Нет платежей', 'Платежей с выбранным статусом не найдено.', null, null);

    content.innerHTML = `
      ${alertHtml}
      <div class="section-card fade-in-up fade-in-up--1">
        <div class="section-header"><span class="section-title">Сводка</span></div>
        <div class="info-row"><span class="info-row__label">Ожидает оплаты</span><span class="info-row__value">${fmt(pendingTotal)}</span></div>
        <div class="info-row"><span class="info-row__label">Просрочено</span><span class="info-row__value info-row__value--warn">${fmt(overdueTotal)}</span></div>
        <div class="info-row"><span class="info-row__label">Оплачено за месяц</span><span class="info-row__value info-row__value--ok">${fmt(paidTotal)}</span></div>
        <div class="info-row"><span class="info-row__label">Остаток дебиторки</span><span class="info-row__value info-row__value--accent">${fmt(partialTotal)}</span></div>
      </div>
      <div class="section-card fade-in-up fade-in-up--2">
        <div class="section-header">
          <span class="section-title">Платежи</span>
          <span class="section-count">${filtered.length}</span>
        </div>
        <div class="filter-row">${renderFilterRow(roleConf.filters, roleConf.filterLabels, State.activeFilter)}</div>
        <div class="deal-list">${dealsHtml}</div>
      </div>`;

  } else if (tab === 1) {
    content.innerHTML = `
      <div class="section-card fade-in-up">
        <div class="section-header"><span class="section-title">Счета</span><span class="section-count">0</span></div>
        ${renderEmptyState('📋', 'Нет счетов', 'Выставленных счетов пока нет. Создайте первый счёт.', '+ Создать счёт', 'App.noop()')}
      </div>`;
  } else if (tab === 2) {
    content.innerHTML = `
      <div class="section-card fade-in-up">
        <div class="section-header"><span class="section-title">Отчёты</span></div>
        ${renderEmptyState('📈', 'Нет данных', 'Аналитические отчёты появятся после накопления данных.', null, null)}
      </div>`;
  }

  bindFilters();
}

function buildOpDirDashboard() {
  const deals = State.deals;
  const filtered = State.activeFilter === 'all'
    ? deals
    : deals.filter(d => d.status === State.activeFilter);
  const roleConf = ROLES.opdir;
  const tab = State.activeTab;

  const kpis = calcOpDirKPIs(deals);
  renderKpiSummary(kpis);
  renderTabBar(roleConf.tabs);
  renderBottomNav(roleConf.navItems);
  hideStickyActions();

  const content = document.getElementById('app-content');

  if (tab === 0) {
    const activeDeals = deals.filter(d => d.status === 'active').length;
    const wonDeals    = deals.filter(d => d.status === 'won').length;
    const lostDeals   = deals.filter(d => d.status === 'lost').length;

    const statsHtml = `
      <div class="stats-row fade-in-up">
        <div class="stats-cell">
          <div class="stats-cell__value">${activeDeals}</div>
          <div class="stats-cell__label">В работе</div>
        </div>
        <div class="stats-cell">
          <div class="stats-cell__value">${wonDeals}</div>
          <div class="stats-cell__label">Закрыто</div>
        </div>
        <div class="stats-cell">
          <div class="stats-cell__value">${lostDeals}</div>
          <div class="stats-cell__label">Потеряно</div>
        </div>
      </div>`;

    const dealsHtml = filtered.length > 0
      ? filtered.map(d => renderDealCard(d, true)).join('')
      : renderEmptyState('💼', 'Нет сделок', 'Сделки с выбранным статусом не найдены.', null, null);

    content.innerHTML = `
      ${statsHtml}
      <div class="section-card fade-in-up fade-in-up--1">
        <div class="section-header">
          <span class="section-title">Все сделки</span>
          <span class="section-count">${filtered.length}</span>
        </div>
        <div class="filter-row">${renderFilterRow(roleConf.filters, roleConf.filterLabels, State.activeFilter)}</div>
        <div class="deal-list">${dealsHtml}</div>
      </div>`;

  } else if (tab === 1) {
    const teamHtml = MOCK_TEAM.map(member => `
      <div class="team-card">
        <div class="team-avatar">${member.initial}</div>
        <div class="team-info">
          <div class="team-name">${member.name}</div>
          <div class="team-stats">${member.deals} сделок · ${member.won} закрыто</div>
        </div>
        <div class="team-kpi">
          <div class="team-kpi__value">${fmtShort(member.amount)}₽</div>
          <div class="team-kpi__label">${pct(member.amount, member.target)}% плана</div>
        </div>
      </div>`).join('');

    content.innerHTML = `
      <div class="section-card fade-in-up">
        <div class="section-header"><span class="section-title">Менеджеры</span><span class="section-count">${MOCK_TEAM.length}</span></div>
        ${teamHtml}
      </div>`;

  } else if (tab === 2) {
    const totalPipeline = deals.filter(d => d.status === 'active' || d.status === 'new').reduce((s, d) => s + d.amount, 0);
    const totalWon      = deals.filter(d => d.status === 'won').reduce((s, d) => s + d.amount, 0);
    const avgDeal       = deals.length ? Math.round(deals.reduce((s, d) => s + d.amount, 0) / deals.length) : 0;

    content.innerHTML = `
      <div class="section-card fade-in-up">
        <div class="section-header"><span class="section-title">Аналитика</span></div>
        <div class="info-row"><span class="info-row__label">Пайплайн (активные)</span><span class="info-row__value info-row__value--accent">${fmt(totalPipeline)}</span></div>
        <div class="info-row"><span class="info-row__label">Выиграно за период</span><span class="info-row__value info-row__value--ok">${fmt(totalWon)}</span></div>
        <div class="info-row"><span class="info-row__label">Средняя сумма сделки</span><span class="info-row__value">${fmt(avgDeal)}</span></div>
        <div class="info-row"><span class="info-row__label">Всего сделок</span><span class="info-row__value">${deals.length}</span></div>
        <div class="info-row"><span class="info-row__label">Менеджеров в команде</span><span class="info-row__value">${MOCK_TEAM.length}</span></div>
      </div>`;
  }

  bindFilters();
}

function buildRopDashboard() {
  const deals = State.deals;
  const filtered = State.activeFilter === 'all'
    ? deals
    : deals.filter(d => d.status === State.activeFilter);
  const roleConf = ROLES.rop;
  const tab = State.activeTab;

  const kpis = calcRopKPIs();
  renderKpiSummary(kpis);
  renderTabBar(roleConf.tabs);
  renderBottomNav(roleConf.navItems);
  showStickyActions([
    { label: '+ Задача команде', cls: 'action-btn--primary', action: 'App.noop()' },
    { label: 'Отчёт',            cls: 'action-btn--secondary', action: 'App.noop()' },
  ]);

  const content = document.getElementById('app-content');

  if (tab === 0) {
    const won    = deals.filter(d => d.status === 'won').length;
    const active = deals.filter(d => d.status === 'active').length;
    const total  = deals.reduce((s, d) => s + d.amount, 0);

    const statsHtml = `
      <div class="stats-row fade-in-up">
        <div class="stats-cell">
          <div class="stats-cell__value">${deals.length}</div>
          <div class="stats-cell__label">Все сделки</div>
        </div>
        <div class="stats-cell">
          <div class="stats-cell__value">${active}</div>
          <div class="stats-cell__label">Активных</div>
        </div>
        <div class="stats-cell">
          <div class="stats-cell__value">${won}</div>
          <div class="stats-cell__label">Закрыто</div>
        </div>
      </div>`;

    const dealsHtml = filtered.length > 0
      ? filtered.map(d => renderDealCard(d, true)).join('')
      : renderEmptyState('🎯', 'Нет сделок', 'Сделки с выбранным статусом не найдены.', null, null);

    content.innerHTML = `
      ${statsHtml}
      <div class="section-card fade-in-up fade-in-up--1">
        <div class="section-header">
          <span class="section-title">Сделки команды</span>
          <span class="section-count">${filtered.length}</span>
        </div>
        <div class="filter-row">${renderFilterRow(roleConf.filters, roleConf.filterLabels, State.activeFilter)}</div>
        <div class="deal-list">${dealsHtml}</div>
      </div>`;

  } else if (tab === 1) {
    const teamHtml = MOCK_TEAM.map(member => {
      const tPct = pct(member.amount, member.target);
      const fillCls = tPct >= 80 ? 'goal-bar__fill--ok' : tPct >= 50 ? '' : 'goal-bar__fill--warn';
      return `
        <div class="team-card">
          <div class="team-avatar">${member.initial}</div>
          <div class="team-info">
            <div class="team-name">${member.name}</div>
            <div class="team-stats">${member.deals} сделок · Win Rate ${pct(member.won, member.deals)}%</div>
            <div class="goal-bar" style="margin-top:6px">
              <div class="goal-bar__fill ${fillCls}" style="width:${tPct}%"></div>
            </div>
          </div>
          <div class="team-kpi">
            <div class="team-kpi__value">${tPct}%</div>
            <div class="team-kpi__label">плана</div>
          </div>
        </div>`;
    }).join('');

    content.innerHTML = `
      <div class="section-card fade-in-up">
        <div class="section-header"><span class="section-title">Команда</span><span class="section-count">${MOCK_TEAM.length}</span></div>
        ${teamHtml}
      </div>`;

  } else if (tab === 2) {
    const goalsHtml = MOCK_TEAM.map(member => {
      const tPct = pct(member.amount, member.target);
      const fillCls = tPct >= 80 ? 'goal-bar__fill--ok' : tPct >= 50 ? '' : 'goal-bar__fill--warn';
      return `
        <div class="goal-bar-wrap">
          <div class="goal-bar-header">
            <span class="goal-bar-title">${member.name}</span>
            <span class="goal-bar-pct">${tPct}%</span>
          </div>
          <div class="goal-bar">
            <div class="goal-bar__fill ${fillCls}" style="width:${tPct}%"></div>
          </div>
          <div class="goal-bar-sub">${fmt(member.amount)} из ${fmt(member.target)}</div>
        </div>`;
    }).join('');

    const totalRev = MOCK_TEAM.reduce((s, t) => s + t.amount, 0);
    const totalTgt = MOCK_TEAM.reduce((s, t) => s + t.target, 0);
    const overallPct = pct(totalRev, totalTgt);

    content.innerHTML = `
      <div class="section-card fade-in-up">
        <div class="section-header">
          <span class="section-title">Выполнение плана</span>
          <span class="section-count">${overallPct}%</span>
        </div>
        ${goalsHtml}
      </div>`;
  }

  bindFilters();
}

// ── UI Helpers ────────────────────────────────────────────

function renderKpiSummary(kpis) {
  const el = document.getElementById('kpi-summary');
  el.innerHTML = kpis.map(k => renderKpiCard(k)).join('');
}

function renderTabBar(tabs) {
  const bar = document.getElementById('tab-bar');
  bar.innerHTML = tabs.map((t, i) =>
    `<button class="tab-item ${i === State.activeTab ? 'active' : ''}" data-tab="${i}">${t}</button>`
  ).join('');
  bar.querySelectorAll('.tab-item').forEach(btn => {
    btn.addEventListener('click', () => {
      State.activeTab = parseInt(btn.dataset.tab);
      State.activeFilter = 'all';
      renderDashboard();
    });
  });
}

function renderBottomNav(items) {
  const nav = document.getElementById('bottom-nav');
  nav.innerHTML = items.map((item, i) =>
    `<button class="nav-item ${i === State.activeNav ? 'active' : ''}" data-nav="${i}">
      <span class="nav-item__icon">${item.icon}</span>
      <span class="nav-item__label">${item.label}</span>
    </button>`
  ).join('');
  nav.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      State.activeNav = parseInt(btn.dataset.nav);
      State.activeTab = State.activeNav;
      State.activeFilter = 'all';
      renderDashboard();
    });
    filterRow.appendChild(chip);
  });
}

function showStickyActions(actions) {
  const bar = document.getElementById('sticky-actions');
  bar.innerHTML = actions.map(a =>
    `<button class="action-btn ${a.cls}" onclick="${a.action}">${a.label}</button>`
  ).join('');
  bar.classList.remove('hidden');
}

function hideStickyActions() {
  document.getElementById('sticky-actions').classList.add('hidden');
}

function bindFilters() {
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      State.activeFilter = chip.dataset.filter;
      renderDashboard();
    });
  });
}

// ── Dashboard Router ──────────────────────────────────────

function renderDashboard() {
  switch (State.role) {
    case 'manager':    buildManagerDashboard();    break;
    case 'accountant': buildAccountantDashboard(); break;
    case 'opdir':      buildOpDirDashboard();      break;
    case 'rop':        buildRopDashboard();         break;
  }
}

// ── App Boot ──────────────────────────────────────────────

const App = {
  selectRole(roleId) {
    State.role = roleId;
    State.activeTab = 0;
    State.activeFilter = 'all';
    State.activeNav = 0;

    const roleConf = ROLES[roleId];
    const mainApp  = document.getElementById('main-app');
    const selector = document.getElementById('role-selector');

    // Apply role class to main app wrapper
    mainApp.className = 'main-app ' + roleConf.cssClass;

    // Update header
    document.getElementById('header-name').textContent = State.userName;
    document.getElementById('header-role-badge').textContent = roleConf.badgeLabel;
    document.getElementById('header-avatar').textContent = State.userInitial;

    selector.classList.add('hidden');
    mainApp.classList.remove('hidden');

    renderDashboard();
  },

  noop() {
    // placeholder for action buttons
    if (window.Telegram && window.Telegram.WebApp) {
      window.Telegram.WebApp.showAlert('Функция будет доступна в полной версии.');
    }
  },

  init() {
    const tg = window.Telegram && window.Telegram.WebApp;

    if (tg) {
      tg.ready();
      tg.expand();
      document.body.classList.add('tg-theme');

      // Try to get user info from Telegram
      const user = tg.initDataUnsafe && tg.initDataUnsafe.user;
      if (user) {
        const firstName = user.first_name || '';
        const lastName  = user.last_name  || '';
        State.userName  = [firstName, lastName].filter(Boolean).join(' ') || 'Пользователь';
        State.userInitial = State.userName[0].toUpperCase();
      }

      // Handle back button
      tg.BackButton.onClick(() => {
        const selector = document.getElementById('role-selector');
        if (!selector.classList.contains('hidden')) return;
        document.getElementById('main-app').classList.add('hidden');
        document.getElementById('role-selector').classList.remove('hidden');
        tg.BackButton.hide();
      });
    }

    // Check URL param for role (demo mode)
    const urlParams = new URLSearchParams(window.location.search);
    const urlRole = urlParams.get('role');

    // Dismiss splash
    const splash = document.getElementById('splash');
    setTimeout(() => {
      splash.classList.add('fade-out');
      setTimeout(() => {
        splash.classList.add('hidden');

        if (urlRole && ROLES[urlRole]) {
          App.selectRole(urlRole);
        } else {
          document.getElementById('role-selector').classList.remove('hidden');
        }

        // Switch role button
        document.getElementById('switch-role-btn').addEventListener('click', () => {
          State.activeTab = 0;
          State.activeFilter = 'all';
          State.activeNav = 0;
          document.getElementById('main-app').classList.add('hidden');
          document.getElementById('role-selector').classList.remove('hidden');
        });

        // Notification button
        document.getElementById('notif-btn').addEventListener('click', () => {
          App.noop();
        });

      }, 400);
    }, 1200);
  },
};

// ── Start ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => App.init());
