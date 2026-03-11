/**
 * tg_bot_finans Mini App — app.js
 * Role-based interface for Telegram Mini App
 */

/* =========================================================
   Configuration
   ========================================================= */
const API_BASE = (window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1'))
  ? 'http://localhost:8000'
  : window.location.origin;

/* =========================================================
   State
   ========================================================= */
const state = {
  me: null,         // MeResponse from /me
  deals: [],        // cached deals
  dashboard: null,  // cached dashboard data
  journal: [],      // cached journal
  activeTab: 0,
  currentFilter: 'all',
  editDealId: null,
};

/* =========================================================
   Telegram Web App init
   ========================================================= */
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

function getInitData() {
  return tg?.initData || '';
}

/* =========================================================
   API helpers
   ========================================================= */
async function apiFetch(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    'X-Init-Data': getInitData(),
    ...(options.headers || {}),
  };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Ошибка запроса');
  }
  return res.json();
}

/* =========================================================
   Toast
   ========================================================= */
function showToast(msg, duration = 2500) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.classList.remove('hidden');
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.add('hidden'), duration);
}

/* =========================================================
   Number formatting
   ========================================================= */
function fmtAmount(val) {
  const n = parseFloat(String(val).replace(',', '.').replace(/\s/g, ''));
  if (isNaN(n)) return val || '—';
  return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(n);
}

function fmtNum(n) {
  if (n === null || n === undefined) return '—';
  return new Intl.NumberFormat('ru-RU').format(n);
}

/* =========================================================
   Status helpers
   ========================================================= */
function statusClass(status) {
  if (!status) return 'status-other';
  const s = status.toLowerCase();
  if (s.includes('новая') || s.includes('новый')) return 'status-new';
  if (s.includes('завершен') || s.includes('закрыт')) return 'status-completed';
  if (s.includes('работ') || s.includes('актив')) return 'status-inprogress';
  return 'status-other';
}

function paymentStatus(deal) {
  const amount = parseFloat(String(deal.amount_with_vat || 0).replace(',', '.'));
  const paid   = parseFloat(String(deal.paid || 0).replace(',', '.'));
  if (paid <= 0)       return { label: 'Не оплачено',      cls: 'pay-unpaid' };
  if (paid < amount)   return { label: 'Частично оплачено', cls: 'pay-partial' };
  return               { label: 'Оплачено',               cls: 'pay-paid' };
}

/* =========================================================
   Role config
   ========================================================= */
const ROLE_CONFIG = {
  manager: {
    label: 'Менеджер',
    accent: 'role-manager',
    tabs: ['Мои сделки', 'Новая сделка', 'Мои показатели'],
    actions: [
      { icon: '➕', label: 'Новая сделка',   tab: 1 },
      { icon: '📂', label: 'Мои сделки',    tab: 0 },
      { icon: '🔍', label: 'Поиск сделки',  tab: 0 },
      { icon: '📊', label: 'Мои показатели', tab: 2 },
    ],
  },
  accountant: {
    label: 'Бухгалтер',
    accent: 'role-accountant',
    tabs: ['Сделки', 'Оплаты', 'Расходы', 'Журнал'],
    actions: [
      { icon: '💳', label: 'Оплаты',            tab: 1 },
      { icon: '🧾', label: 'Закрытие сделки',   tab: 0 },
      { icon: '📂', label: 'Все сделки',         tab: 0 },
      { icon: '📜', label: 'Журнал действий',    tab: 3 },
    ],
  },
  operations_director: {
    label: 'Операционный директор',
    accent: 'role-operations_director',
    tabs: ['Дашборд', 'Сделки', 'Аналитика', 'Команда', 'Журнал'],
    actions: [
      { icon: '📊', label: 'Общий дашборд',     tab: 0 },
      { icon: '📂', label: 'Все сделки',         tab: 1 },
      { icon: '🧾', label: 'Финансы',            tab: 2 },
      { icon: '📜', label: 'Журнал действий',    tab: 4 },
      { icon: '👥', label: 'По менеджерам',      tab: 3 },
    ],
  },
  head_of_sales: {
    label: 'РОП',
    accent: 'role-head_of_sales',
    tabs: ['Команда', 'Сделки', 'Воронка', 'KPI', 'Аналитика'],
    actions: [
      { icon: '👥', label: 'Команда',            tab: 0 },
      { icon: '📂', label: 'Все сделки',         tab: 1 },
      { icon: '📈', label: 'Воронка',            tab: 2 },
      { icon: '🔎', label: 'Контроль менеджеров', tab: 0 },
    ],
  },
};

/* =========================================================
   Field labels
   ========================================================= */
const FIELD_LABELS = {
  status:         'Статус',
  direction:      'Направление бизнеса',
  client:         'Клиент',
  manager:        'Менеджер',
  amount_with_vat:'Начислено с НДС',
  has_vat:        'Наличие НДС',
  paid:           'Оплачено',
  date_start:     'Дата начала',
  date_end:       'Дата окончания',
  act_date:       'Дата выставления акта',
  var_exp1:       'Переменный расход 1',
  var_exp2:       'Переменный расход 2',
  bonus_pct:      'Бонус менеджера %',
  bonus_paid:     'Бонус менеджера выплачено',
  prod_exp:       'Общепроизводственный расход',
  source:         'Источник',
  document:       'Документ/ссылка',
  comment:        'Комментарий',
  creator_tg_id:  'ID создателя',
};

const ALL_DEAL_FIELDS = Object.keys(FIELD_LABELS).filter(f => f !== 'creator_tg_id');

/* =========================================================
   App bootstrap
   ========================================================= */
async function init() {
  try {
    state.me = await apiFetch('/me');
    setupApp();
    await loadDashboard();
  } catch (e) {
    showNoAccess();
  }
}

function showNoAccess() {
  document.getElementById('loading-screen').classList.add('hidden');
  document.getElementById('no-access-screen').classList.remove('hidden');
}

function setupApp() {
  const me = state.me;
  document.getElementById('loading-screen').classList.add('hidden');

  if (!me.active || me.role === 'no_access') {
    showNoAccess();
    return;
  }

  const app = document.getElementById('app');
  const cfg = ROLE_CONFIG[me.role] || {};

  // Apply role accent class
  app.className = cfg.accent || '';
  app.classList.remove('hidden');

  // Header
  const initials = (me.full_name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  document.getElementById('user-avatar').textContent = initials;
  document.getElementById('user-name').textContent = me.full_name || 'Пользователь';
  document.getElementById('role-badge').textContent = me.role_label_ru || me.role;

  // Tabs
  renderTabs(cfg.tabs || []);

  // Actions
  renderActions(cfg.actions || []);

  // Refresh button
  document.getElementById('refresh-btn').addEventListener('click', async () => {
    showToast('Обновление…');
    await loadDashboard();
  });
}

/* =========================================================
   Tabs
   ========================================================= */
function renderTabs(tabs) {
  const bar = document.getElementById('tab-bar');
  bar.innerHTML = '';
  tabs.forEach((label, i) => {
    const btn = document.createElement('button');
    btn.className = 'tab-item' + (i === 0 ? ' active' : '');
    btn.textContent = label;
    btn.addEventListener('click', () => switchTab(i));
    bar.appendChild(btn);
  });
}

function switchTab(index) {
  state.activeTab = index;
  document.querySelectorAll('.tab-item').forEach((t, i) => {
    t.classList.toggle('active', i === index);
  });
  renderTabContent();
}

/* =========================================================
   Actions
   ========================================================= */
function renderActions(actions) {
  const section = document.getElementById('actions-section');
  section.innerHTML = '';
  actions.forEach(a => {
    const btn = document.createElement('button');
    btn.className = 'action-tile';
    btn.innerHTML = `<span class="tile-icon">${a.icon}</span><span class="tile-label">${a.label}</span>`;
    btn.addEventListener('click', () => switchTab(a.tab));
    section.appendChild(btn);
  });
}

/* =========================================================
   Dashboard load
   ========================================================= */
async function loadDashboard() {
  renderKPISkeletons();
  renderTabSkeletons();
  try {
    const res = await apiFetch('/dashboard');
    state.dashboard = res.data;
    state.deals = res.data.deals || [];

    renderKPIs(res.role, res.data);
    renderTabContent();
  } catch (e) {
    showToast('Ошибка загрузки: ' + e.message);
  }
}

/* =========================================================
   KPI Cards
   ========================================================= */
function renderKPISkeletons() {
  const section = document.getElementById('kpi-section');
  section.innerHTML = Array(4).fill('<div class="skeleton skeleton-card"></div>').join('');
}

function renderKPIs(role, data) {
  const section = document.getElementById('kpi-section');
  section.innerHTML = '';

  const cards = buildKPICards(role, data);
  cards.forEach((card, i) => {
    const el = document.createElement('div');
    el.className = 'kpi-card' + (i === 0 ? ' accent' : '');
    el.innerHTML = `
      <div class="kpi-icon">${card.icon}</div>
      <div class="kpi-value">${card.value}</div>
      <div class="kpi-label">${card.label}</div>
    `;
    section.appendChild(el);
  });
}

function buildKPICards(role, d) {
  switch (role) {
    case 'manager':
      return [
        { icon: '📁', label: 'Мои сделки',           value: fmtNum(d.total_my_deals) },
        { icon: '🔄', label: 'В работе',              value: fmtNum(d.in_progress) },
        { icon: '✅', label: 'Завершено',             value: fmtNum(d.completed) },
        { icon: '💰', label: 'Сумма начислений',      value: fmtAmount(d.total_amount) },
      ];
    case 'accountant':
      return [
        { icon: '⏳', label: 'Ожидают оплаты',       value: fmtNum(d.awaiting_payment) },
        { icon: '🔶', label: 'Частично оплачено',     value: fmtNum(d.partially_paid) },
        { icon: '✅', label: 'Полностью оплачено',    value: fmtNum(d.fully_paid) },
        { icon: '💸', label: 'Сумма к получению',     value: fmtAmount(d.total_receivable) },
        { icon: '💰', label: 'Сумма оплачено',        value: fmtAmount(d.total_paid) },
      ];
    case 'operations_director':
      return [
        { icon: '📁', label: 'Все сделки',            value: fmtNum(d.total_deals) },
        { icon: '🔄', label: 'Активные',              value: fmtNum(d.active_deals) },
        { icon: '💰', label: 'Общая сумма начислений',value: fmtAmount(d.total_amount) },
        { icon: '💳', label: 'Оплачено',              value: fmtAmount(d.total_paid) },
        { icon: '📊', label: 'Дебиторка',             value: fmtAmount(d.receivable) },
        { icon: '💼', label: 'Общие расходы',         value: fmtAmount(d.total_expenses) },
        { icon: '📈', label: 'Валовая прибыль',       value: fmtAmount(d.gross_profit) },
      ];
    case 'head_of_sales':
      return [
        { icon: '🔄', label: 'Сделки в работе',       value: fmtNum(d.deals_in_progress) },
        { icon: '🆕', label: 'Новые сделки',          value: fmtNum(d.new_deals) },
        { icon: '✅', label: 'Завершённые',           value: fmtNum(d.completed_deals) },
        { icon: '💰', label: 'Сумма начислений',      value: fmtAmount(d.total_amount) },
        { icon: '📊', label: 'Средний чек',           value: fmtAmount(d.avg_deal_amount) },
      ];
    default:
      return [];
  }
}

/* =========================================================
   Tab content router
   ========================================================= */
function renderTabSkeletons() {
  const content = document.getElementById('tab-content');
  content.innerHTML = Array(3).fill('<div class="skeleton skeleton-card"></div>').join('');
}

function renderTabContent() {
  const role = state.me?.role;
  const idx  = state.activeTab;
  const content = document.getElementById('tab-content');
  content.innerHTML = '';

  const renderers = {
    manager:              [renderManagerDeals, renderNewDealForm, renderManagerStats],
    accountant:           [renderAccountantDeals, renderPaymentsTab, renderExpensesTab, renderJournalTab],
    operations_director:  [renderOpsDashboard, renderAllDealsTab, renderAnalyticsTab, renderTeamTab, renderJournalTab],
    head_of_sales:        [renderTeamTab, renderAllDealsTab, renderFunnelTab, renderKPITab, renderAnalyticsTab],
  };

  const fns = renderers[role] || [];
  const fn  = fns[idx];
  if (fn) fn(content);
  else content.innerHTML = '<div class="empty-state"><div class="empty-icon">📭</div><h3>Раздел в разработке</h3></div>';
}

/* =========================================================
   ── MANAGER tabs ─────────────────────────────────────────
   ========================================================= */
function renderManagerDeals(container) {
  const deals = state.deals;
  if (!deals.length) { renderEmpty(container, '📭', 'Нет сделок', 'Создайте первую сделку.'); return; }
  renderDealFilter(container, deals, 'manager');
}

function renderManagerStats(container) {
  const d = state.dashboard;
  if (!d) return;
  const w = document.createElement('div');
  w.className = 'summary-widget';
  w.innerHTML = `
    <div class="summary-title">📊 Мои показатели</div>
    ${summaryRow('Всего сделок', fmtNum(d.total_my_deals))}
    ${summaryRow('В работе', fmtNum(d.in_progress))}
    ${summaryRow('Завершено', fmtNum(d.completed))}
    ${summaryRow('Сумма начислений', fmtAmount(d.total_amount))}
  `;
  container.appendChild(w);
}

function renderNewDealForm(container) {
  const editable = state.me?.editable_fields || [];
  container.appendChild(buildDealForm(null, editable, async (data) => {
    try {
      await apiFetch('/deals/create', { method: 'POST', body: JSON.stringify(data) });
      showToast('✅ Сделка создана');
      switchTab(0);
      await loadDashboard();
    } catch (e) {
      showToast('❌ ' + e.message);
    }
  }, 'Создать сделку'));
}

/* =========================================================
   ── ACCOUNTANT tabs ───────────────────────────────────────
   ========================================================= */
function renderAccountantDeals(container) {
  const deals = state.deals;
  if (!deals.length) { renderEmpty(container, '📭', 'Нет сделок', ''); return; }
  renderDealFilter(container, deals, 'accountant');
}

function renderPaymentsTab(container) {
  const deals = state.deals;
  const title = document.createElement('div');
  title.className = 'summary-title';
  title.textContent = '💳 Реестр оплат';
  container.appendChild(title);

  const list = document.createElement('div');
  list.className = 'deal-list';

  deals.forEach(deal => {
    const ps = paymentStatus(deal);
    const card = document.createElement('div');
    card.className = 'deal-card';
    card.innerHTML = `
      <div class="deal-card-header">
        <span class="deal-id">Сделка #${deal.id}</span>
        <span class="deal-status-badge ${ps.cls}">${ps.label}</span>
      </div>
      <div class="deal-client">${deal.client || '—'}</div>
      <div class="deal-row"><span class="label">Начислено</span><span class="value">${fmtAmount(deal.amount_with_vat)}</span></div>
      <div class="deal-row"><span class="label">Оплачено</span><span class="value">${fmtAmount(deal.paid)}</span></div>
      <div class="deal-row"><span class="label">Остаток</span><span class="value">${fmtAmount((parseFloat(deal.amount_with_vat||0)-parseFloat(deal.paid||0)).toString())}</span></div>
      <div class="deal-row"><span class="label">Дата акта</span><span class="value">${deal.act_date || '—'}</span></div>
    `;
    card.addEventListener('click', () => openDealModal(deal));
    list.appendChild(card);
  });
  container.appendChild(list);
}

function renderExpensesTab(container) {
  const deals = state.deals;
  let totalVar1 = 0, totalVar2 = 0, totalProd = 0;
  deals.forEach(d => {
    totalVar1 += parseFloat(d.var_exp1 || 0);
    totalVar2 += parseFloat(d.var_exp2 || 0);
    totalProd += parseFloat(d.prod_exp || 0);
  });
  const w = document.createElement('div');
  w.className = 'summary-widget';
  w.innerHTML = `
    <div class="summary-title">🧾 Сводка расходов</div>
    ${summaryRow('Переменный расход 1', fmtAmount(totalVar1.toString()))}
    ${summaryRow('Переменный расход 2', fmtAmount(totalVar2.toString()))}
    ${summaryRow('Общепроизводственный', fmtAmount(totalProd.toString()))}
    ${summaryRow('Итого расходы', fmtAmount((totalVar1+totalVar2+totalProd).toString()))}
  `;
  container.appendChild(w);
}

/* =========================================================
   ── OPERATIONS DIRECTOR tabs ─────────────────────────────
   ========================================================= */
function renderOpsDashboard(container) {
  const d = state.dashboard;
  if (!d) return;

  // Financial summary
  const fin = document.createElement('div');
  fin.className = 'summary-widget';
  fin.innerHTML = `
    <div class="summary-title">💼 Финансовая сводка</div>
    ${summaryRow('Всего сделок', fmtNum(d.total_deals))}
    ${summaryRow('Активные сделки', fmtNum(d.active_deals))}
    ${summaryRow('Начислено', fmtAmount(d.total_amount))}
    ${summaryRow('Оплачено', fmtAmount(d.total_paid))}
    ${summaryRow('Дебиторка', fmtAmount(d.receivable))}
    ${summaryRow('Расходы', fmtAmount(d.total_expenses))}
    ${summaryRow('Валовая прибыль *', fmtAmount(d.gross_profit))}
  `;
  container.appendChild(fin);

  const hint = document.createElement('p');
  hint.style.cssText = 'font-size:11px;color:var(--tg-hint);padding:0 4px 12px';
  hint.textContent = '* Рассчитано как: Оплачено − Расходы (оценочный показатель)';
  container.appendChild(hint);

  // Top managers
  if (d.by_manager?.length) {
    const mgr = document.createElement('div');
    mgr.className = 'summary-widget';
    mgr.innerHTML = `<div class="summary-title">👥 Лидеры по начислениям</div>`;
    const sorted = [...d.by_manager].sort((a, b) => b.amount - a.amount).slice(0, 5);
    sorted.forEach((m, i) => {
      mgr.innerHTML += summaryRow(`${i+1}. ${m.manager}`, fmtAmount(m.amount));
    });
    container.appendChild(mgr);
  }

  // Recent deals
  const recent = [...(d.deals||[])].slice(-5).reverse();
  if (recent.length) {
    const rw = document.createElement('div');
    rw.className = 'summary-widget';
    rw.innerHTML = `<div class="summary-title">🕒 Последние сделки</div>`;
    const list = document.createElement('div');
    list.className = 'deal-list';
    recent.forEach(deal => list.appendChild(buildDealCard(deal, 'ops')));
    rw.appendChild(list);
    container.appendChild(rw);
  }
}

function renderAllDealsTab(container) {
  const deals = state.deals;
  if (!deals.length) { renderEmpty(container, '📭', 'Нет сделок', ''); return; }
  renderDealFilter(container, deals, state.me.role);
}

function renderAnalyticsTab(container) {
  const d = state.dashboard;
  if (!d) return;

  if (d.by_manager?.length) {
    const title = document.createElement('div');
    title.className = 'summary-title';
    title.style.marginBottom = '12px';
    title.textContent = '📊 Аналитика по менеджерам';
    container.appendChild(title);

    d.by_manager.forEach(m => {
      const card = document.createElement('div');
      card.className = 'manager-card';
      card.innerHTML = `
        <div class="manager-card-header">
          <span class="manager-name">👤 ${m.manager}</span>
          <span class="deal-status-badge status-inprogress">${m.deals} сделок</span>
        </div>
        <div class="manager-stats">
          <div class="manager-stat">
            <div class="stat-val">${fmtNum(m.deals)}</div>
            <div class="stat-lbl">Сделок</div>
          </div>
          <div class="manager-stat">
            <div class="stat-val">${fmtAmount(m.amount)}</div>
            <div class="stat-lbl">Начислено</div>
          </div>
          <div class="manager-stat">
            <div class="stat-val">${fmtAmount(m.avg || 0)}</div>
            <div class="stat-lbl">Средний чек</div>
          </div>
        </div>
      `;
      container.appendChild(card);
    });
  } else {
    renderEmpty(container, '📊', 'Нет данных', 'Аналитика появится после добавления сделок.');
  }
}

function renderTeamTab(container) {
  renderAnalyticsTab(container);
}

/* =========================================================
   ── HEAD OF SALES tabs ────────────────────────────────────
   ========================================================= */
function renderFunnelTab(container) {
  const deals = state.deals;
  // Group by status
  const byStatus = {};
  deals.forEach(d => {
    const s = d.status || 'Неизвестно';
    if (!byStatus[s]) byStatus[s] = { count: 0, amount: 0 };
    byStatus[s].count++;
    byStatus[s].amount += parseFloat(d.amount_with_vat || 0);
  });

  const title = document.createElement('div');
  title.className = 'summary-title';
  title.style.marginBottom = '12px';
  title.textContent = '📈 Воронка по статусам';
  container.appendChild(title);

  if (!Object.keys(byStatus).length) {
    renderEmpty(container, '📭', 'Нет данных', '');
    return;
  }

  Object.entries(byStatus).forEach(([status, info]) => {
    const card = document.createElement('div');
    card.className = 'summary-widget';
    card.innerHTML = `
      <div class="summary-title">
        <span class="deal-status-badge ${statusClass(status)}" style="margin-right:8px">${status}</span>
      </div>
      ${summaryRow('Количество сделок', fmtNum(info.count))}
      ${summaryRow('Сумма начислений', fmtAmount(info.amount.toString()))}
    `;
    container.appendChild(card);
  });
}

function renderKPITab(container) {
  const d = state.dashboard;
  if (!d) return;
  const w = document.createElement('div');
  w.className = 'summary-widget';
  w.innerHTML = `
    <div class="summary-title">📊 KPI команды</div>
    ${summaryRow('Сделок в работе', fmtNum(d.deals_in_progress))}
    ${summaryRow('Новых сделок', fmtNum(d.new_deals))}
    ${summaryRow('Завершённых', fmtNum(d.completed_deals))}
    ${summaryRow('Сумма начислений', fmtAmount(d.total_amount))}
    ${summaryRow('Средний чек', fmtAmount(d.avg_deal_amount))}
  `;
  container.appendChild(w);

  renderAnalyticsTab(container);
}

/* =========================================================
   ── JOURNAL tab ───────────────────────────────────────────
   ========================================================= */
async function renderJournalTab(container) {
  container.innerHTML = '<div class="skeleton skeleton-card"></div>'.repeat(3);
  try {
    const entries = await apiFetch('/journal/recent?limit=30');
    container.innerHTML = '';
    if (!entries.length) { renderEmpty(container, '📜', 'Журнал пуст', ''); return; }
    const title = document.createElement('div');
    title.className = 'summary-title';
    title.style.marginBottom = '12px';
    title.textContent = '📜 Журнал действий';
    container.appendChild(title);
    entries.forEach(e => {
      const el = document.createElement('div');
      el.className = 'journal-entry';
      el.innerHTML = `
        <div class="journal-meta">
          <span>${e.timestamp}</span>
          <span>${e.role || '—'}</span>
        </div>
        <div class="journal-action">${actionLabel(e.action)} ${e.deal_id ? `#${e.deal_id}` : ''}</div>
        <div class="journal-summary">${e.summary || ''}</div>
      `;
      container.appendChild(el);
    });
  } catch (err) {
    container.innerHTML = '';
    showToast('Ошибка загрузки журнала');
  }
}

function actionLabel(action) {
  const map = {
    create_deal: '📝 Создание сделки',
    update_deal: '✏️ Обновление сделки',
  };
  return map[action] || action || '—';
}

/* =========================================================
   Deal filter / list helpers
   ========================================================= */
function renderDealFilter(container, deals, role) {
  // Filter chips
  const statuses = ['all', ...new Set(deals.map(d => d.status).filter(Boolean))];
  const filterRow = document.createElement('div');
  filterRow.className = 'filter-row';

  statuses.forEach(s => {
    const chip = document.createElement('button');
    chip.className = 'chip' + (state.currentFilter === s ? ' active' : '');
    chip.textContent = s === 'all' ? 'Все' : s;
    chip.addEventListener('click', () => {
      state.currentFilter = s;
      container.innerHTML = '';
      renderDealFilter(container, deals, role);
    });
    filterRow.appendChild(chip);
  });
  container.appendChild(filterRow);

  const filtered = state.currentFilter === 'all'
    ? deals
    : deals.filter(d => d.status === state.currentFilter);

  if (!filtered.length) {
    renderEmpty(container, '🔍', 'Ничего не найдено', 'Попробуйте другой фильтр.');
    return;
  }

  const list = document.createElement('div');
  list.className = 'deal-list';
  filtered.forEach(deal => {
    list.appendChild(buildDealCard(deal, role));
  });
  container.appendChild(list);
}

function buildDealCard(deal, role) {
  const card = document.createElement('div');
  card.className = 'deal-card';

  const sClass = statusClass(deal.status);

  if (role === 'accountant') {
    const ps = paymentStatus(deal);
    card.innerHTML = `
      <div class="deal-card-header">
        <span class="deal-id">Сделка #${deal.id}</span>
        <span class="deal-status-badge ${ps.cls}">${ps.label}</span>
      </div>
      <div class="deal-client">${deal.client || '—'}</div>
      <div class="deal-row"><span class="label">Начислено</span><span class="value">${fmtAmount(deal.amount_with_vat)}</span></div>
      <div class="deal-row"><span class="label">Оплачено</span><span class="value">${fmtAmount(deal.paid)}</span></div>
      <div class="deal-row"><span class="label">Дата акта</span><span class="value">${deal.act_date || '—'}</span></div>
    `;
  } else {
    card.innerHTML = `
      <div class="deal-card-header">
        <span class="deal-id">Сделка #${deal.id}</span>
        <span class="deal-status-badge ${sClass}">${deal.status || '—'}</span>
      </div>
      <div class="deal-client">${deal.client || '—'}</div>
      <div class="deal-direction">${deal.direction || ''}</div>
      <div class="deal-row"><span class="label">Начислено</span><span class="value">${fmtAmount(deal.amount_with_vat)}</span></div>
      <div class="deal-row"><span class="label">Менеджер</span><span class="value">${deal.manager || '—'}</span></div>
      ${deal.comment ? `<div class="deal-row"><span class="label">Комментарий</span><span class="value">${deal.comment}</span></div>` : ''}
    `;
  }

  card.addEventListener('click', () => openDealModal(deal));
  return card;
}

/* =========================================================
   Deal modal
   ========================================================= */
function openDealModal(deal) {
  const modal = document.getElementById('deal-modal');
  const title = document.getElementById('modal-title');
  const body  = document.getElementById('modal-body');
  const footer = document.getElementById('modal-footer');

  title.textContent = `Сделка #${deal.id}`;
  body.innerHTML = '';
  footer.innerHTML = '';

  const editable = new Set(state.me?.editable_fields || []);

  // Build read-only view
  const viewSection = document.createElement('div');
  ALL_DEAL_FIELDS.forEach(field => {
    const val = deal[field];
    const row = document.createElement('div');
    row.className = 'deal-row';
    row.innerHTML = `<span class="label">${FIELD_LABELS[field]}</span><span class="value">${val || '—'}</span>`;
    viewSection.appendChild(row);
  });
  body.appendChild(viewSection);

  // Edit button (if user has editable fields for this deal)
  if (editable.size > 0) {
    const editBtn = document.createElement('button');
    editBtn.className = 'btn btn-primary';
    editBtn.textContent = '✏️ Редактировать';
    editBtn.addEventListener('click', () => openEditDealModal(deal));
    footer.appendChild(editBtn);
  }

  // Close
  document.getElementById('modal-close').onclick = closeModal;
  document.getElementById('modal-backdrop').onclick = closeModal;
  modal.classList.remove('hidden');
}

function openEditDealModal(deal) {
  const modal = document.getElementById('deal-modal');
  const title = document.getElementById('modal-title');
  const body  = document.getElementById('modal-body');
  const footer = document.getElementById('modal-footer');

  title.textContent = `Редактировать #${deal.id}`;
  body.innerHTML = '';
  footer.innerHTML = '';

  const editable = state.me?.editable_fields || [];
  const form = buildDealForm(deal, editable, async (data) => {
    try {
      await apiFetch(`/deals/${deal.id}`, { method: 'PUT', body: JSON.stringify(data) });
      showToast('✅ Сделка обновлена');
      closeModal();
      await loadDashboard();
    } catch (e) {
      showToast('❌ ' + e.message);
    }
  }, 'Сохранить изменения');
  body.appendChild(form);
}

function closeModal() {
  document.getElementById('deal-modal').classList.add('hidden');
}

/* =========================================================
   Deal form builder
   ========================================================= */
function buildDealForm(existingDeal, editableFields, onSubmit, submitLabel) {
  const editableSet = new Set(editableFields);
  const wrapper = document.createElement('div');

  // Editable fields section
  const editSection = document.createElement('div');
  editSection.className = 'form-section';
  const editTitle = document.createElement('div');
  editTitle.className = 'form-section-title';
  editTitle.textContent = 'Редактируемые поля';
  editSection.appendChild(editTitle);

  // Read-only section
  const readSection = document.createElement('div');
  readSection.className = 'form-section';
  const readTitle = document.createElement('div');
  readTitle.className = 'form-section-title';
  readTitle.textContent = 'Только чтение';
  readSection.appendChild(readTitle);

  let hasReadOnly = false;

  ALL_DEAL_FIELDS.forEach(field => {
    const isEditable = editableSet.has(field);
    const val = existingDeal ? (existingDeal[field] || '') : '';
    const label = FIELD_LABELS[field];

    const group = document.createElement('div');
    group.className = 'form-group';

    if (isEditable) {
      group.innerHTML = `
        <label class="form-label">${label}</label>
        <input class="form-input" type="text" name="${field}" value="${escHtml(val)}" placeholder="${label}">
      `;
      editSection.appendChild(group);
    } else if (existingDeal) {
      group.innerHTML = `
        <label class="form-label">${label}</label>
        <input class="form-input" type="text" name="${field}" value="${escHtml(val)}" readonly>
        <p class="form-hint">Только чтение</p>
      `;
      readSection.appendChild(group);
      hasReadOnly = true;
    }
  });

  wrapper.appendChild(editSection);
  if (hasReadOnly) wrapper.appendChild(readSection);

  const submitBtn = document.createElement('button');
  submitBtn.className = 'btn btn-primary';
  submitBtn.textContent = submitLabel || 'Сохранить';
  submitBtn.type = 'button';
  submitBtn.addEventListener('click', () => {
    const data = {};
    wrapper.querySelectorAll('input:not([readonly]), select, textarea').forEach(el => {
      if (el.name) data[el.name] = el.value;
    });
    onSubmit(data);
  });
  wrapper.appendChild(submitBtn);

  return wrapper;
}

/* =========================================================
   Helpers
   ========================================================= */
function summaryRow(label, value) {
  return `<div class="summary-row"><span class="s-label">${label}</span><span class="s-value">${value}</span></div>`;
}

function renderEmpty(container, icon, title, subtitle) {
  const el = document.createElement('div');
  el.className = 'empty-state';
  el.innerHTML = `<div class="empty-icon">${icon}</div><h3>${title}</h3><p>${subtitle}</p>`;
  container.appendChild(el);
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* =========================================================
   Bootstrap
   ========================================================= */
document.addEventListener('DOMContentLoaded', init);
