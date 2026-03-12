/**
 * Telegram Mini App — Финансы
 * app.js — main application logic
 *
 * Architecture:
 *  - State stored in localStorage (key: "finans_deals")
 *  - Telegram WebApp API integration
 *  - Tab navigation with animation
 *  - CRUD for deals
 *  - Summary statistics
 *  - Filters
 *  - Modal bottom sheet
 */

'use strict';

/* ═══════════════════════════════════════════════════════════════
   CONSTANTS
═══════════════════════════════════════════════════════════════ */
const STORAGE_KEY = 'finans_deals';

const STATUS_LABELS = {
  new:         '🆕 Новая',
  in_progress: '⚡ В работе',
  done:        '✅ Завершено',
  canceled:    '❌ Отменено',
};

const TYPE_LABELS = {
  sale:     'Продажа',
  purchase: 'Закупка',
  service:  'Услуга',
  lease:    'Аренда',
  other:    'Другое',
};

/* ═══════════════════════════════════════════════════════════════
   STATE
═══════════════════════════════════════════════════════════════ */
const state = {
  deals:         [],
  activeFilter:  'all',
  activeDealId:  null,
  tg:            null,
  user:          null,
};

/* ═══════════════════════════════════════════════════════════════
   STORAGE HELPERS
═══════════════════════════════════════════════════════════════ */
function loadDeals() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (_) {
    return [];
  }
}

function saveDeals(deals) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(deals));
  } catch (_) {
    showToast('⚠️', 'Не удалось сохранить данные');
  }
}

/* ═══════════════════════════════════════════════════════════════
   DOM ELEMENTS (cached at startup)
═══════════════════════════════════════════════════════════════ */
let DOM = {};

function cacheDOM() {
  DOM = {
    // Header
    headerSubtitle:   document.getElementById('headerSubtitle'),
    headerAvatar:     document.getElementById('headerAvatar'),
    avatarInitial:    document.getElementById('avatarInitial'),

    // Loading
    loadingOverlay:   document.getElementById('loadingOverlay'),

    // Tabs
    tabItems:         document.querySelectorAll('.tab-item'),
    tabPanels:        document.querySelectorAll('.tab-panel'),

    // Deals tab
    summaryTotal:     document.getElementById('statTotal'),
    summaryActive:    document.getElementById('statActive'),
    summaryDone:      document.getElementById('statDone'),
    summaryMoney:     document.getElementById('statMoney'),
    filterBar:        document.getElementById('filterBar'),
    filterChips:      document.querySelectorAll('.filter-chip'),
    dealsList:        document.getElementById('dealsList'),
    emptyState:       document.getElementById('emptyState'),
    emptyAddBtn:      document.getElementById('emptyAddBtn'),

    // New deal form
    dealForm:         document.getElementById('dealForm'),
    clientName:       document.getElementById('clientName'),
    dealType:         document.getElementById('dealType'),
    dealAmount:       document.getElementById('dealAmount'),
    dealStatus:       document.getElementById('dealStatus'),
    dealComment:      document.getElementById('dealComment'),
    dealDate:         document.getElementById('dealDate'),
    commentCounter:   document.getElementById('commentCounter'),
    submitDealBtn:    document.getElementById('submitDealBtn'),

    // Profile
    profileAvatar:    document.getElementById('profileAvatar'),
    profileAvatarInitial: document.getElementById('profileAvatarInitial'),
    profileName:      document.getElementById('profileName'),
    profileUsername:  document.getElementById('profileUsername'),
    profileStatTotal:    document.getElementById('profileStatTotal'),
    profileStatDone:     document.getElementById('profileStatDone'),
    profileStatActive:   document.getElementById('profileStatActive'),
    profileStatCanceled: document.getElementById('profileStatCanceled'),
    profileStatMoney:    document.getElementById('profileStatMoney'),
    clearDataBtn:     document.getElementById('clearDataBtn'),
    exportDataBtn:    document.getElementById('exportDataBtn'),

    // Modal
    dealModal:        document.getElementById('dealModal'),
    modalTitle:       document.getElementById('modalTitle'),
    modalBody:        document.getElementById('modalBody'),
    modalClose:       document.getElementById('modalClose'),
    modalDeleteBtn:   document.getElementById('modalDeleteBtn'),

    // Toast
    toast:            document.getElementById('toast'),
    toastIcon:        document.getElementById('toastIcon'),
    toastText:        document.getElementById('toastText'),
  };
}

/* ═══════════════════════════════════════════════════════════════
   TELEGRAM WEB APP INIT
═══════════════════════════════════════════════════════════════ */
function initTelegram() {
  const tg = window.Telegram?.WebApp;
  if (!tg) return null;

  tg.ready();
  tg.expand();

  // Apply Telegram color theme
  document.body.classList.add('tg-theme');

  return tg;
}

function loadUser() {
  const tg = state.tg;
  const userData = tg?.initDataUnsafe?.user;

  if (userData) {
    return {
      id:         userData.id,
      first_name: userData.first_name || '',
      last_name:  userData.last_name  || '',
      username:   userData.username   || '',
    };
  }

  // Demo fallback
  return {
    id:         0,
    first_name: 'Демо',
    last_name:  'Пользователь',
    username:   'demo_user',
  };
}

/* ═══════════════════════════════════════════════════════════════
   TAB NAVIGATION
═══════════════════════════════════════════════════════════════ */
function switchTab(tabName) {
  DOM.tabItems.forEach(btn => {
    const isActive = btn.dataset.tab === tabName;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });

  DOM.tabPanels.forEach(panel => {
    const isActive = panel.id === tabNameToPanelId(tabName);
    // Remove then add class to re-trigger CSS animation
    panel.classList.remove('active');
    if (isActive) {
      // Micro delay so browser re-computes animation
      requestAnimationFrame(() => {
        panel.classList.add('active');
      });
    }
  });

  // When switching to profile, refresh stats
  if (tabName === 'profile') {
    renderProfileStats();
  }
}

function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/** Convert kebab-case tab name to panel element ID.
 *  'deals'    → 'tabDeals'
 *  'new-deal' → 'tabNewDeal'
 *  'profile'  → 'tabProfile'
 */
function tabNameToPanelId(tabName) {
  return 'tab' + tabName.split('-').map(capitalize).join('');
}

/* ═══════════════════════════════════════════════════════════════
   DEALS CRUD
═══════════════════════════════════════════════════════════════ */
function createDeal(data) {
  return {
    id:        `deal_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    client:    data.client.trim(),
    type:      data.type,
    amount:    parseFloat(data.amount) || 0,
    status:    data.status,
    comment:   data.comment ? data.comment.trim() : '',
    date:      data.date,
    createdAt: new Date().toISOString(),
  };
}

function addDeal(data) {
  const deal = createDeal(data);
  state.deals.unshift(deal);
  saveDeals(state.deals);
  return deal;
}

function deleteDeal(id) {
  state.deals = state.deals.filter(d => d.id !== id);
  saveDeals(state.deals);
}

/* ═══════════════════════════════════════════════════════════════
   FORMATTING HELPERS
═══════════════════════════════════════════════════════════════ */
function formatAmount(amount) {
  return new Intl.NumberFormat('ru-RU', {
    style:    'currency',
    currency: 'RUB',
    maximumFractionDigits: 2,
  }).format(amount);
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    const [y, m, d] = dateStr.split('-');
    return `${d}.${m}.${y}`;
  } catch (_) {
    return dateStr;
  }
}

function getStatusLabel(status) {
  return STATUS_LABELS[status] || status;
}

function getTypeLabel(type) {
  return TYPE_LABELS[type] || type;
}

/* ═══════════════════════════════════════════════════════════════
   STATISTICS
═══════════════════════════════════════════════════════════════ */
function calcStats(deals) {
  const total    = deals.length;
  const active   = deals.filter(d => d.status === 'new' || d.status === 'in_progress').length;
  const done     = deals.filter(d => d.status === 'done').length;
  const canceled = deals.filter(d => d.status === 'canceled').length;
  const money    = deals
    .filter(d => d.status === 'done')
    .reduce((acc, d) => acc + (d.amount || 0), 0);

  return { total, active, done, canceled, money };
}

/* ═══════════════════════════════════════════════════════════════
   RENDER — SUMMARY CARDS
═══════════════════════════════════════════════════════════════ */
function renderSummary() {
  const stats = calcStats(state.deals);
  DOM.summaryTotal.textContent  = stats.total;
  DOM.summaryActive.textContent = stats.active;
  DOM.summaryDone.textContent   = stats.done;
  DOM.summaryMoney.textContent  = formatAmount(stats.money);
}

/* ═══════════════════════════════════════════════════════════════
   RENDER — PROFILE STATS
═══════════════════════════════════════════════════════════════ */
function renderProfileStats() {
  const stats = calcStats(state.deals);
  DOM.profileStatTotal.textContent    = stats.total;
  DOM.profileStatDone.textContent     = stats.done;
  DOM.profileStatActive.textContent   = stats.active;
  DOM.profileStatCanceled.textContent = stats.canceled;
  DOM.profileStatMoney.textContent    = formatAmount(stats.money);
}

/* ═══════════════════════════════════════════════════════════════
   RENDER — DEAL CARDS
═══════════════════════════════════════════════════════════════ */
function buildDealCard(deal) {
  const card = document.createElement('div');
  card.className = `deal-card status--${deal.status}`;
  card.dataset.id = deal.id;
  card.setAttribute('role', 'button');
  card.setAttribute('tabindex', '0');
  card.setAttribute('aria-label', `Сделка с ${deal.client}`);

  const badgeClass = `status-badge--${deal.status}`;
  const commentHtml = deal.comment
    ? `<p class="deal-card__comment">${escapeHtml(deal.comment)}</p>`
    : '';

  card.innerHTML = `
    <div class="deal-card__inner">
      <div class="deal-card__accent"></div>
      <div class="deal-card__top">
        <span class="deal-card__client">${escapeHtml(deal.client)}</span>
        <span class="deal-card__amount">${formatAmount(deal.amount)}</span>
      </div>
      <div class="deal-card__meta">
        <span class="status-badge ${badgeClass}">${getStatusLabel(deal.status)}</span>
        <span class="deal-card__type">${escapeHtml(getTypeLabel(deal.type))}</span>
        <span class="deal-card__date">${formatDate(deal.date)}</span>
      </div>
      ${commentHtml}
    </div>
  `;

  card.addEventListener('click', () => openDealModal(deal.id));
  card.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      openDealModal(deal.id);
    }
  });

  return card;
}

function renderDeals() {
  const filter = state.activeFilter;
  const filtered = filter === 'all'
    ? state.deals
    : state.deals.filter(d => d.status === filter);

  DOM.dealsList.innerHTML = '';

  if (filtered.length === 0) {
    DOM.emptyState.classList.remove('hidden');
  } else {
    DOM.emptyState.classList.add('hidden');
    filtered.forEach((deal, i) => {
      const card = buildDealCard(deal);
      // Stagger animation
      card.style.animationDelay = `${i * 40}ms`;
      DOM.dealsList.appendChild(card);
    });
  }

  renderSummary();
}

/* ═══════════════════════════════════════════════════════════════
   DEAL MODAL
═══════════════════════════════════════════════════════════════ */
function openDealModal(id) {
  const deal = state.deals.find(d => d.id === id);
  if (!deal) return;

  state.activeDealId = id;
  DOM.modalTitle.textContent = deal.client;

  DOM.modalBody.innerHTML = `
    <div class="detail-row">
      <span class="detail-row__icon">💰</span>
      <div class="detail-row__content">
        <div class="detail-row__label">Сумма</div>
        <div class="detail-row__value detail-row__value--amount">${formatAmount(deal.amount)}</div>
      </div>
    </div>
    <div class="detail-row">
      <span class="detail-row__icon">🔖</span>
      <div class="detail-row__content">
        <div class="detail-row__label">Статус</div>
        <div class="detail-row__value">
          <span class="status-badge status-badge--${deal.status}">${getStatusLabel(deal.status)}</span>
        </div>
      </div>
    </div>
    <div class="detail-row">
      <span class="detail-row__icon">📌</span>
      <div class="detail-row__content">
        <div class="detail-row__label">Тип</div>
        <div class="detail-row__value">${escapeHtml(getTypeLabel(deal.type))}</div>
      </div>
    </div>
    <div class="detail-row">
      <span class="detail-row__icon">📅</span>
      <div class="detail-row__content">
        <div class="detail-row__label">Дата</div>
        <div class="detail-row__value">${formatDate(deal.date)}</div>
      </div>
    </div>
    ${deal.comment ? `
    <div class="detail-row">
      <span class="detail-row__icon">💬</span>
      <div class="detail-row__content">
        <div class="detail-row__label">Комментарий</div>
        <div class="detail-row__value">${escapeHtml(deal.comment)}</div>
      </div>
    </div>` : ''}
    <div class="detail-row">
      <span class="detail-row__icon">🕒</span>
      <div class="detail-row__content">
        <div class="detail-row__label">Создано</div>
        <div class="detail-row__value">${formatCreatedAt(deal.createdAt)}</div>
      </div>
    </div>
  `;

  DOM.dealModal.classList.remove('hidden', 'closing');
  document.body.style.overflow = 'hidden';
}

function closeDealModal() {
  DOM.dealModal.classList.add('closing');
  setTimeout(() => {
    DOM.dealModal.classList.add('hidden');
    DOM.dealModal.classList.remove('closing');
    document.body.style.overflow = '';
    state.activeDealId = null;
  }, 260);
}

function formatCreatedAt(isoStr) {
  if (!isoStr) return '—';
  try {
    return new Date(isoStr).toLocaleString('ru-RU', {
      day:    '2-digit',
      month:  '2-digit',
      year:   'numeric',
      hour:   '2-digit',
      minute: '2-digit',
    });
  } catch (_) {
    return isoStr;
  }
}

/* ═══════════════════════════════════════════════════════════════
   FORM — VALIDATION
═══════════════════════════════════════════════════════════════ */
function validateForm() {
  let valid = true;

  function setError(fieldId, errId, msg) {
    const field = document.getElementById(fieldId);
    const err   = document.getElementById(errId);
    if (msg) {
      field.classList.add('error');
      if (err) err.textContent = msg;
      valid = false;
    } else {
      field.classList.remove('error');
      if (err) err.textContent = '';
    }
  }

  const client = DOM.clientName.value.trim();
  setError('clientName', 'clientNameError',
    !client ? 'Введите имя клиента' : client.length < 2 ? 'Слишком короткое имя' : '');

  const type = DOM.dealType.value;
  setError('dealType', 'dealTypeError',
    !type ? 'Выберите тип сделки' : '');

  const amount = parseFloat(DOM.dealAmount.value);
  setError('dealAmount', 'dealAmountError',
    isNaN(amount) || DOM.dealAmount.value === '' ? 'Введите сумму'
    : amount < 0 ? 'Сумма не может быть отрицательной' : '');

  const status = DOM.dealStatus.value;
  setError('dealStatus', 'dealStatusError',
    !status ? 'Выберите статус' : '');

  const date = DOM.dealDate.value;
  setError('dealDate', 'dealDateError',
    !date ? 'Укажите дату' : '');

  return valid;
}

/* ═══════════════════════════════════════════════════════════════
   FORM — SUBMIT
═══════════════════════════════════════════════════════════════ */
function handleFormSubmit() {
  if (!validateForm()) {
    // Scroll to first error
    const firstError = DOM.dealForm.querySelector('.form-input.error, .form-select.error');
    if (firstError) firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return;
  }

  const btn = DOM.submitDealBtn;
  btn.classList.add('loading');
  btn.querySelector('.btn-text').textContent = 'Сохраняем...';

  // Simulate async save (backend call placeholder)
  setTimeout(() => {
    const deal = addDeal({
      client:  DOM.clientName.value,
      type:    DOM.dealType.value,
      amount:  DOM.dealAmount.value,
      status:  DOM.dealStatus.value,
      comment: DOM.dealComment.value,
      date:    DOM.dealDate.value,
    });

    // Haptic feedback
    state.tg?.HapticFeedback?.notificationOccurred('success');

    resetForm();
    renderDeals();

    btn.classList.remove('loading');
    btn.querySelector('.btn-text').textContent = 'Сохранить сделку';

    showToast('✅', 'Сделка добавлена!');
    switchTab('deals');
  }, 500);
}

function resetForm() {
  DOM.dealForm.reset();
  DOM.commentCounter.textContent = '0 / 500';
  DOM.dealForm.querySelectorAll('.error').forEach(el => el.classList.remove('error'));
  DOM.dealForm.querySelectorAll('.form-error').forEach(el => { el.textContent = ''; });
  // Set today's date as default
  DOM.dealDate.value = todayISO();
}

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/* ═══════════════════════════════════════════════════════════════
   TOAST
═══════════════════════════════════════════════════════════════ */
let toastTimer = null;

function showToast(icon, text, duration = 2500) {
  DOM.toastIcon.textContent = icon;
  DOM.toastText.textContent = text;
  DOM.toast.classList.remove('hidden');

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      DOM.toast.classList.add('show');
    });
  });

  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    DOM.toast.classList.remove('show');
    setTimeout(() => DOM.toast.classList.add('hidden'), 300);
  }, duration);
}

/* ═══════════════════════════════════════════════════════════════
   USER PROFILE UI
═══════════════════════════════════════════════════════════════ */
function renderUser() {
  const user = state.user;
  const fullName = [user.first_name, user.last_name].filter(Boolean).join(' ');
  const initial  = (fullName[0] || '?').toUpperCase();
  const username = user.username ? `@${user.username}` : '—';

  // Header
  DOM.headerSubtitle.textContent = `Привет, ${user.first_name || 'друг'}!`;
  DOM.avatarInitial.textContent  = initial;

  // Profile tab
  DOM.profileAvatarInitial.textContent = initial;
  DOM.profileName.textContent          = fullName || 'Пользователь';
  DOM.profileUsername.textContent      = username;
}

/* ═══════════════════════════════════════════════════════════════
   EXPORT DATA
═══════════════════════════════════════════════════════════════ */
function exportData() {
  if (state.deals.length === 0) {
    showToast('ℹ️', 'Нет данных для экспорта');
    return;
  }

  const rows = [
    ['ID', 'Клиент', 'Тип', 'Сумма', 'Статус', 'Дата', 'Комментарий'],
    ...state.deals.map(d => [
      d.id,
      d.client,
      getTypeLabel(d.type),
      d.amount,
      getStatusLabel(d.status).replace(/[^\w\s\u0410-\u042F\u0430-\u044F\u0401\u0451]/gu, '').trim(),
      formatDate(d.date),
      d.comment || '',
    ]),
  ];

  const csv = rows.map(r =>
    r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')
  ).join('\n');

  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `deals_${todayISO()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('📤', 'Файл скачивается...');
}

/* ═══════════════════════════════════════════════════════════════
   CLEAR DATA
═══════════════════════════════════════════════════════════════ */
function clearData() {
  const confirmed = window.confirm('Удалить все сделки? Это действие необратимо.');
  if (!confirmed) return;
  state.deals = [];
  saveDeals(state.deals);
  renderDeals();
  renderProfileStats();
  showToast('🗑️', 'Данные удалены');
  state.tg?.HapticFeedback?.notificationOccurred('warning');
}

/* ═══════════════════════════════════════════════════════════════
   ESCAPE HTML (XSS prevention)
═══════════════════════════════════════════════════════════════ */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/* ═══════════════════════════════════════════════════════════════
   EVENT LISTENERS
═══════════════════════════════════════════════════════════════ */
function bindEvents() {
  // Tab switching
  DOM.tabItems.forEach(btn => {
    btn.addEventListener('click', () => {
      switchTab(btn.dataset.tab);
      state.tg?.HapticFeedback?.selectionChanged();
    });
  });

  // Filters
  DOM.filterChips.forEach(chip => {
    chip.addEventListener('click', () => {
      DOM.filterChips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      state.activeFilter = chip.dataset.filter;
      renderDeals();
      state.tg?.HapticFeedback?.selectionChanged();
    });
  });

  // Empty state add button
  DOM.emptyAddBtn.addEventListener('click', () => {
    switchTab('new-deal');
  });

  // Header avatar → profile tab
  DOM.headerAvatar.addEventListener('click', () => switchTab('profile'));

  // Comment character counter
  DOM.dealComment.addEventListener('input', () => {
    const len = DOM.dealComment.value.length;
    DOM.commentCounter.textContent = `${len} / 500`;
  });

  // Clear inline errors on input change
  DOM.clientName.addEventListener('input',  () => clearFieldError('clientName', 'clientNameError'));
  DOM.dealType.addEventListener('change',   () => clearFieldError('dealType',   'dealTypeError'));
  DOM.dealAmount.addEventListener('input',  () => clearFieldError('dealAmount', 'dealAmountError'));
  DOM.dealStatus.addEventListener('change', () => clearFieldError('dealStatus', 'dealStatusError'));
  DOM.dealDate.addEventListener('change',   () => clearFieldError('dealDate',   'dealDateError'));

  // Submit button
  DOM.submitDealBtn.addEventListener('click', handleFormSubmit);

  // Modal close
  DOM.modalClose.addEventListener('click', closeDealModal);
  DOM.dealModal.addEventListener('click', e => {
    if (e.target === DOM.dealModal) closeDealModal();
  });

  // Modal delete
  DOM.modalDeleteBtn.addEventListener('click', () => {
    if (!state.activeDealId) return;
    const confirmed = window.confirm('Удалить эту сделку?');
    if (!confirmed) return;
    deleteDeal(state.activeDealId);
    closeDealModal();
    renderDeals();
    showToast('🗑️', 'Сделка удалена');
    state.tg?.HapticFeedback?.notificationOccurred('warning');
  });

  // Profile buttons
  DOM.clearDataBtn.addEventListener('click', clearData);
  DOM.exportDataBtn.addEventListener('click', exportData);

  // Keyboard: close modal on Escape
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !DOM.dealModal.classList.contains('hidden')) {
      closeDealModal();
    }
  });
}

function clearFieldError(fieldId, errId) {
  const field = document.getElementById(fieldId);
  const err   = document.getElementById(errId);
  field.classList.remove('error');
  if (err) err.textContent = '';
}

/* ═══════════════════════════════════════════════════════════════
   DEMO DATA (shown when no real data exists)
═══════════════════════════════════════════════════════════════ */
function insertDemoData() {
  const demo = [
    {
      id:        'demo_1',
      client:    'ООО «Альфа-Трейд»',
      type:      'sale',
      amount:    185000,
      status:    'done',
      comment:   'Поставка оборудования. Оплата получена.',
      date:      '2026-03-01',
      createdAt: '2026-03-01T10:00:00.000Z',
    },
    {
      id:        'demo_2',
      client:    'ИП Петров А.В.',
      type:      'service',
      amount:    42500,
      status:    'in_progress',
      comment:   'Монтажные работы. Сдача 15 марта.',
      date:      '2026-03-10',
      createdAt: '2026-03-05T14:30:00.000Z',
    },
    {
      id:        'demo_3',
      client:    'Строй-Группа Плюс',
      type:      'purchase',
      amount:    76000,
      status:    'new',
      comment:   '',
      date:      '2026-03-11',
      createdAt: '2026-03-11T08:15:00.000Z',
    },
    {
      id:        'demo_4',
      client:    'Частное лицо (Иванов)',
      type:      'lease',
      amount:    15000,
      status:    'canceled',
      comment:   'Клиент отказался от аренды.',
      date:      '2026-02-20',
      createdAt: '2026-02-20T09:00:00.000Z',
    },
  ];

  state.deals = demo;
  saveDeals(state.deals);
}

/* ═══════════════════════════════════════════════════════════════
   APP INIT
═══════════════════════════════════════════════════════════════ */
function init() {
  cacheDOM();

  // Telegram API
  state.tg   = initTelegram();
  state.user = loadUser();

  // Load persisted deals (or demo data on first visit)
  state.deals = loadDeals();
  if (state.deals.length === 0) {
    insertDemoData();
  }

  // Render UI
  renderUser();
  renderDeals();

  // Set default date on form
  DOM.dealDate.value = todayISO();

  // Bind interactions
  bindEvents();

  // Hide loading overlay
  setTimeout(() => {
    DOM.loadingOverlay.classList.add('fade-out');
    setTimeout(() => DOM.loadingOverlay.classList.add('hidden'), 400);
  }, 600);
}

// Start when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
