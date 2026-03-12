/* ==========================================
   ФИНАНСОВАЯ СИСТЕМА — Mini App
   ========================================== */

'use strict';

// ==========================================
// CONFIG
// ==========================================
const API_BASE = (function () {
  // Check meta tag first (set this in index.html for production deployment)
  const meta = document.querySelector('meta[name="api-base"]');
  if (meta && meta.content) return meta.content.replace(/\/$/, '');
  // Check global config override
  if (window.APP_CONFIG && window.APP_CONFIG.apiBase) return window.APP_CONFIG.apiBase;
  // Default: same origin (works when backend serves the frontend)
  return window.location.origin;
})();

// ==========================================
// TELEGRAM WEB APP INIT
// ==========================================
const tg = window.Telegram?.WebApp;
let telegramUser = null;

function initTelegram() {
  if (!tg) {
    console.warn('Telegram WebApp SDK not available');
    return;
  }
  tg.ready();
  tg.expand();

  // Apply Telegram color scheme
  if (tg.colorScheme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  }

  telegramUser = tg.initDataUnsafe?.user || null;

  if (telegramUser) {
    renderUserAvatar(telegramUser);
  }
}

function renderUserAvatar(user) {
  const avatar = document.getElementById('user-avatar');
  if (!avatar) return;
  const initials = getInitials(user.first_name, user.last_name);
  avatar.textContent = initials;
  avatar.title = `${user.first_name} ${user.last_name || ''}`.trim();
}

function getInitials(first, last) {
  const f = (first || '').charAt(0).toUpperCase();
  const l = (last || '').charAt(0).toUpperCase();
  return f + (l || '');
}

function getTelegramInitData() {
  return tg?.initData || '';
}

// ==========================================
// API HELPERS
// ==========================================
async function apiFetch(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };
  const initData = getTelegramInitData();
  if (initData) {
    headers['X-Telegram-Init-Data'] = initData;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}`;
    try {
      const err = await response.json();
      errorDetail = err.detail || err.error || errorDetail;
    } catch (_) {}
    throw new Error(errorDetail);
  }

  return response.json();
}

// ==========================================
// APP STATE
// ==========================================
const state = {
  settings: null,
  deals: [],
  currentTab: 'new-deal',
  isSubmitting: false,
  isLoadingDeals: false,
};

// ==========================================
// TAB NAVIGATION
// ==========================================
function initTabs() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const tabId = btn.dataset.tab;
      switchTab(tabId);
    });
  });
}

function switchTab(tabId) {
  // Update buttons
  document.querySelectorAll('.tab-btn').forEach(btn => {
    const isActive = btn.dataset.tab === tabId;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-selected', isActive);
  });

  // Update panels
  document.querySelectorAll('.tab-panel').forEach(panel => {
    const isActive = panel.id === tabId;
    panel.style.display = isActive ? 'block' : 'none';
    if (isActive) {
      panel.classList.add('active');
    } else {
      panel.classList.remove('active');
    }
  });

  state.currentTab = tabId;

  // Lazy load deals when switching to that tab
  if (tabId === 'my-deals' && state.deals.length === 0) {
    loadDeals();
  }

  // Check connections when switching to settings
  if (tabId === 'settings-tab') {
    checkConnections();
    renderUserInfoCard();
  }
}

// ==========================================
// SETTINGS LOADER
// ==========================================
async function loadSettings() {
  try {
    const data = await apiFetch('/settings');
    state.settings = data;
    populateSelects(data);
    updateSettingsStats(data);
    return data;
  } catch (err) {
    console.error('Failed to load settings:', err);
    showToast('Ошибка загрузки справочников. Используются значения по умолчанию.', 'warning');
    // Use fallback data
    const fallback = {
      statuses: ['Новая', 'В работе', 'Завершена', 'Отменена', 'Приостановлена'],
      business_directions: ['Разработка', 'Консалтинг', 'Дизайн', 'Маркетинг', 'Другое'],
      clients: [],
      managers: [],
      vat_types: ['С НДС', 'Без НДС'],
      sources: ['Рекомендация', 'Сайт', 'Реклама', 'Холодный звонок', 'Другое'],
    };
    state.settings = fallback;
    populateSelects(fallback);
    updateSettingsStats(fallback);
    return fallback;
  }
}

function populateSelects(data) {
  fillSelect('status', data.statuses || []);
  fillSelect('business_direction', data.business_directions || []);
  fillSelect('client', data.clients || []);
  fillSelect('manager', data.managers || []);
  fillSelect('vat_type', data.vat_types || []);
  fillSelect('source', data.sources || []);

  // Filters
  fillSelect('filter-status', data.statuses || [], true);
  fillSelect('filter-client', data.clients || [], true);
}

function fillSelect(id, options, hasAll = false) {
  const select = document.getElementById(id);
  if (!select) return;

  const currentValue = select.value;

  // Keep first placeholder option
  const firstOption = select.options[0];
  select.innerHTML = '';
  if (firstOption) select.appendChild(firstOption);

  options.forEach(opt => {
    const option = document.createElement('option');
    option.value = opt;
    option.textContent = opt;
    select.appendChild(option);
  });

  // Restore previous value if exists
  if (currentValue) select.value = currentValue;
}

function updateSettingsStats(data) {
  setEl('cnt-statuses', (data.statuses || []).length);
  setEl('cnt-clients', (data.clients || []).length);
  setEl('cnt-managers', (data.managers || []).length);
  setEl('cnt-directions', (data.business_directions || []).length);
}

// ==========================================
// DEAL FORM
// ==========================================
function initDealForm() {
  const form = document.getElementById('deal-form');
  const clearBtn = document.getElementById('clear-btn');
  const newDealBtn = document.getElementById('new-deal-btn');
  const viewDealsBtn = document.getElementById('view-deals-btn');

  if (form) form.addEventListener('submit', handleFormSubmit);
  if (clearBtn) clearBtn.addEventListener('click', clearForm);
  if (newDealBtn) newDealBtn.addEventListener('click', showForm);
  if (viewDealsBtn) viewDealsBtn.addEventListener('click', () => switchTab('my-deals'));

  // Live summary update
  ['client', 'charged_with_vat', 'status', 'manager'].forEach(fieldId => {
    const el = document.getElementById(fieldId);
    if (el) el.addEventListener('change', updateSummary);
  });
}

function updateSummary() {
  const client = getFieldValue('client');
  const amount = getFieldValue('charged_with_vat');
  const status = getFieldValue('status');
  const manager = getFieldValue('manager');

  const summaryCard = document.getElementById('deal-summary');
  if (!summaryCard) return;

  const hasData = client || amount || status || manager;
  summaryCard.style.display = hasData ? 'block' : 'none';

  setEl('sum-client', client || '—');
  setEl('sum-amount', amount ? formatCurrency(parseFloat(amount)) : '—');
  setEl('sum-status', status || '—');
  setEl('sum-manager', manager || '—');
}

async function handleFormSubmit(e) {
  e.preventDefault();

  if (state.isSubmitting) return;

  const errors = validateForm();
  if (errors.length > 0) {
    showToast('Пожалуйста, заполните обязательные поля', 'error');
    return;
  }

  const dealData = collectFormData();

  setSubmitting(true);

  try {
    const result = await apiFetch('/deal/create', {
      method: 'POST',
      body: JSON.stringify(dealData),
    });

    showSuccessScreen(result.deal_id);
    showToast(`Сделка ${result.deal_id} успешно создана!`, 'success');

    // Invalidate deals cache
    state.deals = [];

  } catch (err) {
    showToast(`Ошибка при сохранении: ${err.message}`, 'error');
  } finally {
    setSubmitting(false);
  }
}

function validateForm() {
  const required = [
    { id: 'status', label: 'Статус сделки' },
    { id: 'business_direction', label: 'Направление бизнеса' },
    { id: 'client', label: 'Клиент' },
    { id: 'manager', label: 'Менеджер' },
    { id: 'charged_with_vat', label: 'Начислено с НДС' },
    { id: 'vat_type', label: 'Наличие НДС' },
    { id: 'project_start_date', label: 'Дата начала проекта' },
    { id: 'project_end_date', label: 'Дата окончания проекта' },
  ];

  const errors = [];

  // Clear previous errors
  document.querySelectorAll('.field-error').forEach(el => {
    el.textContent = '';
  });
  document.querySelectorAll('.field--error').forEach(el => {
    el.classList.remove('field--error');
  });

  required.forEach(({ id, label }) => {
    const el = document.getElementById(id);
    if (!el || !el.value.trim()) {
      errors.push(label);
      const errorEl = document.getElementById(`${id}-error`);
      if (errorEl) errorEl.textContent = 'Обязательное поле';
      if (el) el.closest('.field')?.classList.add('field--error');
    }
  });

  return errors;
}

function collectFormData() {
  const floatVal = (id) => {
    const v = getFieldValue(id);
    return v !== '' ? parseFloat(v) : null;
  };

  return {
    status: getFieldValue('status'),
    business_direction: getFieldValue('business_direction'),
    client: getFieldValue('client'),
    manager: getFieldValue('manager'),
    charged_with_vat: floatVal('charged_with_vat'),
    vat_type: getFieldValue('vat_type'),
    paid: floatVal('paid'),
    project_start_date: getFieldValue('project_start_date'),
    project_end_date: getFieldValue('project_end_date'),
    act_date: getFieldValue('act_date') || null,
    variable_expense_1: floatVal('variable_expense_1'),
    variable_expense_2: floatVal('variable_expense_2'),
    manager_bonus_percent: floatVal('manager_bonus_percent'),
    manager_bonus_paid: floatVal('manager_bonus_paid'),
    general_production_expense: floatVal('general_production_expense'),
    source: getFieldValue('source') || null,
    document_link: getFieldValue('document_link') || null,
    comment: getFieldValue('comment') || null,
  };
}

function setSubmitting(isLoading) {
  state.isSubmitting = isLoading;
  const btn = document.getElementById('submit-btn');
  if (!btn) return;

  const text = btn.querySelector('.btn-text');
  const loader = btn.querySelector('.btn-loader');

  btn.disabled = isLoading;
  if (text) text.style.display = isLoading ? 'none' : '';
  if (loader) loader.style.display = isLoading ? 'inline-flex' : 'none';
}

function clearForm() {
  const form = document.getElementById('deal-form');
  if (!form) return;
  form.reset();

  // Clear error states
  document.querySelectorAll('.field-error').forEach(el => (el.textContent = ''));
  document.querySelectorAll('.field--error').forEach(el =>
    el.classList.remove('field--error')
  );

  // Hide summary
  const summaryCard = document.getElementById('deal-summary');
  if (summaryCard) summaryCard.style.display = 'none';

  showToast('Форма очищена', 'success');
}

function showSuccessScreen(dealId) {
  const form = document.getElementById('deal-form');
  const successScreen = document.getElementById('success-screen');

  if (form) form.style.display = 'none';
  if (successScreen) {
    successScreen.style.display = 'flex';
    setEl('success-deal-id', dealId);
  }
}

function showForm() {
  const form = document.getElementById('deal-form');
  const successScreen = document.getElementById('success-screen');

  if (form) form.style.display = 'block';
  if (successScreen) successScreen.style.display = 'none';

  clearForm();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ==========================================
// MY DEALS
// ==========================================
function initMyDeals() {
  const refreshBtn = document.getElementById('refresh-deals-btn');
  const gotoNewDeal = document.getElementById('goto-new-deal-btn');

  if (refreshBtn) refreshBtn.addEventListener('click', () => loadDeals());
  if (gotoNewDeal) gotoNewDeal.addEventListener('click', () => switchTab('new-deal'));

  // Filters
  ['filter-status', 'filter-client', 'filter-month'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', renderDeals);
  });
}

async function loadDeals() {
  if (state.isLoadingDeals) return;
  state.isLoadingDeals = true;

  showDealsLoading(true);
  clearDealsList();

  try {
    const manager = telegramUser
      ? (document.getElementById('filter-manager')?.value || '')
      : '';

    const params = new URLSearchParams();
    if (manager) params.set('manager', manager);

    const deals = await apiFetch(`/deal/user${params.toString() ? '?' + params : ''}`);
    state.deals = deals;
    renderDeals();
  } catch (err) {
    showToast(`Ошибка загрузки сделок: ${err.message}`, 'error');
    showDealsEmpty(true);
  } finally {
    state.isLoadingDeals = false;
    showDealsLoading(false);
  }
}

function renderDeals() {
  const statusFilter = document.getElementById('filter-status')?.value || '';
  const clientFilter = document.getElementById('filter-client')?.value || '';
  const monthFilter = document.getElementById('filter-month')?.value || '';

  let filtered = state.deals.filter(deal => {
    if (statusFilter && deal.status !== statusFilter) return false;
    if (clientFilter && deal.client !== clientFilter) return false;
    if (monthFilter) {
      const startDate = deal.project_start_date || '';
      if (!startDate.startsWith(monthFilter)) return false;
    }
    return true;
  });

  clearDealsList();

  if (filtered.length === 0) {
    showDealsEmpty(true);
    return;
  }

  showDealsEmpty(false);
  const listEl = document.getElementById('deals-list');
  filtered.forEach(deal => {
    const card = createDealCard(deal);
    listEl.appendChild(card);
  });
}

function createDealCard(deal) {
  const card = document.createElement('div');
  card.className = 'deal-card';
  card.setAttribute('role', 'article');

  const amount = deal.charged_with_vat
    ? formatCurrency(deal.charged_with_vat)
    : '—';

  const dateRange = [deal.project_start_date, deal.project_end_date]
    .filter(Boolean)
    .map(d => formatDate(d))
    .join(' — ');

  card.innerHTML = `
    <div class="deal-card-header">
      <span class="deal-id">${escHtml(deal.deal_id)}</span>
      <span class="deal-status-badge" data-status="${escHtml(deal.status)}">${escHtml(deal.status)}</span>
    </div>
    <div class="deal-card-title">${escHtml(deal.client || 'Клиент не указан')}</div>
    <div class="deal-card-meta">
      <span class="deal-meta-item">🏢 ${escHtml(deal.business_direction || '—')}</span>
      <span class="deal-meta-item">👤 ${escHtml(deal.manager || '—')}</span>
      ${dateRange ? `<span class="deal-meta-item">📅 ${escHtml(dateRange)}</span>` : ''}
    </div>
    <div class="deal-card-footer">
      <span class="deal-amount">${amount}</span>
      <div class="deal-card-actions">
        <button class="deal-action-btn deal-action-btn--primary" data-id="${escHtml(deal.deal_id)}" data-action="view">
          👁 Открыть
        </button>
        <button class="deal-action-btn" data-id="${escHtml(deal.deal_id)}" data-action="copy">
          📌
        </button>
      </div>
    </div>
    ${deal.comment ? `<div class="deal-comment" title="${escHtml(deal.comment)}">💬 ${escHtml(deal.comment)}</div>` : ''}
  `;

  // Bind actions
  card.querySelectorAll('[data-action]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const action = btn.dataset.action;
      const id = btn.dataset.id;
      if (action === 'view') openDealModal(id);
      if (action === 'copy') copyToClipboard(id);
    });
  });

  card.addEventListener('click', () => openDealModal(deal.deal_id));

  return card;
}

function showDealsLoading(show) {
  const el = document.getElementById('deals-loading');
  if (el) el.style.display = show ? 'flex' : 'none';
}

function showDealsEmpty(show) {
  const el = document.getElementById('deals-empty');
  if (el) el.style.display = show ? 'flex' : 'none';
}

function clearDealsList() {
  const listEl = document.getElementById('deals-list');
  if (listEl) listEl.innerHTML = '';
  showDealsEmpty(false);
}

// ==========================================
// DEAL DETAIL MODAL
// ==========================================
async function openDealModal(dealId) {
  const modal = document.getElementById('deal-modal');
  const body = document.getElementById('modal-body');
  const title = document.getElementById('modal-title');

  if (!modal || !body) return;

  // Try to find in state first
  let deal = state.deals.find(d => d.deal_id === dealId);

  if (!deal) {
    try {
      deal = await apiFetch(`/deal/${dealId}`);
    } catch (err) {
      showToast(`Ошибка загрузки сделки: ${err.message}`, 'error');
      return;
    }
  }

  if (title) title.textContent = dealId;
  body.innerHTML = renderDealDetail(deal);
  modal.style.display = 'flex';

  // Prevent body scroll
  document.body.style.overflow = 'hidden';
}

function closeDealModal() {
  const modal = document.getElementById('deal-modal');
  if (modal) modal.style.display = 'none';
  document.body.style.overflow = '';
}

function renderDealDetail(deal) {
  const sections = [
    {
      title: '📋 Основное',
      fields: [
        ['Статус', deal.status],
        ['Направление', deal.business_direction],
        ['Клиент', deal.client],
        ['Менеджер', deal.manager],
      ],
    },
    {
      title: '💰 Финансы',
      fields: [
        ['Начислено с НДС', deal.charged_with_vat != null ? formatCurrency(deal.charged_with_vat) : null],
        ['Тип НДС', deal.vat_type],
        ['Оплачено', deal.paid != null ? formatCurrency(deal.paid) : null],
      ],
    },
    {
      title: '📅 Сроки',
      fields: [
        ['Начало проекта', formatDate(deal.project_start_date)],
        ['Окончание проекта', formatDate(deal.project_end_date)],
        ['Дата акта', formatDate(deal.act_date)],
      ],
    },
    {
      title: '📊 Расходы и бонусы',
      fields: [
        ['Переменный расход 1', deal.variable_expense_1 != null ? formatCurrency(deal.variable_expense_1) : null],
        ['Переменный расход 2', deal.variable_expense_2 != null ? formatCurrency(deal.variable_expense_2) : null],
        ['Бонус менеджера %', deal.manager_bonus_percent != null ? `${deal.manager_bonus_percent}%` : null],
        ['Бонус выплачено', deal.manager_bonus_paid != null ? formatCurrency(deal.manager_bonus_paid) : null],
        ['Общепроизв. расход', deal.general_production_expense != null ? formatCurrency(deal.general_production_expense) : null],
      ],
    },
    {
      title: '📎 Дополнительно',
      fields: [
        ['Источник', deal.source],
        ['Документ/ссылка', deal.document_link],
        ['Комментарий', deal.comment],
      ],
    },
  ];

  return sections.map(section => {
    const visibleFields = section.fields.filter(([, v]) => v != null && v !== '');
    if (visibleFields.length === 0) return '';

    const fieldsHtml = visibleFields.map(([label, value]) => `
      <div class="modal-field">
        <span class="modal-field-label">${escHtml(label)}</span>
        <span class="modal-field-value">${escHtml(String(value))}</span>
      </div>
    `).join('');

    return `
      <div class="modal-section">
        <div class="modal-section-title">${escHtml(section.title)}</div>
        ${fieldsHtml}
      </div>
    `;
  }).join('');
}

function initModal() {
  const closeBtn = document.getElementById('modal-close-btn');
  const overlay = document.getElementById('deal-modal');

  if (closeBtn) closeBtn.addEventListener('click', closeDealModal);
  if (overlay) {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeDealModal();
    });
  }

  // Close on back button / escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDealModal();
  });
}

// ==========================================
// SETTINGS TAB
// ==========================================
async function checkConnections() {
  // Telegram
  const hasTg = !!tg && !!tg.initData;
  setConnectionStatus('telegram', hasTg, hasTg ? 'Подключено' : 'Нет данных');

  // API
  try {
    await apiFetch('/health');
    setConnectionStatus('api', true, 'Онлайн');
  } catch (_) {
    setConnectionStatus('api', false, 'Недоступен');
  }

  // Google Sheets (check settings endpoint)
  try {
    await apiFetch('/settings');
    setConnectionStatus('sheets', true, 'Подключено');
  } catch (_) {
    setConnectionStatus('sheets', false, 'Ошибка');
  }
}

function setConnectionStatus(key, ok, text) {
  const dot = document.getElementById(`dot-${key}`);
  const statusEl = document.getElementById(`status-${key}`);

  if (dot) {
    dot.classList.toggle('ok', ok);
    dot.classList.toggle('error', !ok);
  }
  if (statusEl) {
    statusEl.textContent = text;
    statusEl.classList.toggle('ok', ok);
    statusEl.classList.toggle('error', !ok);
  }
}

function renderUserInfoCard() {
  if (!telegramUser) return;

  const card = document.getElementById('user-info-card');
  const content = document.getElementById('user-info-content');
  if (!card || !content) return;

  card.style.display = 'block';

  const fields = [
    ['ID', telegramUser.id],
    ['Имя', `${telegramUser.first_name} ${telegramUser.last_name || ''}`.trim()],
    ['Username', telegramUser.username ? `@${telegramUser.username}` : '—'],
    ['Язык', telegramUser.language_code || '—'],
  ];

  content.innerHTML = fields.map(([label, value]) => `
    <div class="user-info-row">
      <span>${escHtml(label)}</span>
      <span>${escHtml(String(value))}</span>
    </div>
  `).join('');
}

// ==========================================
// TOAST NOTIFICATIONS
// ==========================================
function showToast(message, type = 'default', duration = 3500) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const icons = {
    success: '✅',
    error: '❌',
    warning: '⚠️',
    default: 'ℹ️',
  };

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || icons.default}</span>
    <span>${escHtml(message)}</span>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('exiting');
    setTimeout(() => toast.remove(), 200);
  }, duration);
}

// ==========================================
// UTILITIES
// ==========================================
function getFieldValue(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : '';
}

function setEl(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function escHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatCurrency(value) {
  if (value == null) return '—';
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatDate(dateStr) {
  if (!dateStr) return null;
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    }).format(date);
  } catch (_) {
    return dateStr;
  }
}

async function copyToClipboard(text) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      // Fallback
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
    showToast(`ID скопирован: ${text}`, 'success');
  } catch (_) {
    showToast('Не удалось скопировать ID', 'error');
  }
}

// ==========================================
// APP INIT
// ==========================================
async function init() {
  initTelegram();
  initTabs();
  initDealForm();
  initMyDeals();
  initModal();

  // Load settings on startup
  await loadSettings();

  // Show first tab
  switchTab('new-deal');
}

document.addEventListener('DOMContentLoaded', init);
