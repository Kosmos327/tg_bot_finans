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

// Billing input mode constants (must match backend INPUT_MODE_* values)
const BILLING_INPUT_MODE_WITH_VAT    = 'Новый (с НДС)';
const BILLING_INPUT_MODE_WITHOUT_VAT = 'Новый (без НДС)';
const BILLING_INPUT_MODE_OLD         = 'Старый (p1/p2)';

// ==========================================
// TELEGRAM WEB APP INIT
// ==========================================
// tg is intentionally null at module level and assigned inside initTelegram()
// (called on DOMContentLoaded) to avoid capturing the SDK reference before the
// Telegram client has fully injected initData/initDataUnsafe into the webview.
let tg = null;
let telegramUser = null;

function initTelegram() {
  tg = window.Telegram?.WebApp;

  console.log('[tg-init] window.Telegram exists:', !!window.Telegram);
  console.log('[tg-init] Telegram.WebApp exists:', !!tg);

  if (!tg) {
    console.warn('[tg-init] Telegram WebApp SDK not available – running outside Telegram');
    return;
  }

  tg.ready();
  tg.expand();

  console.log('[tg-init] initData length:', tg.initData ? tg.initData.length : 0);
  console.log('[tg-init] initDataUnsafe.user exists:', !!tg.initDataUnsafe?.user);

  // Apply Telegram color scheme
  if (tg.colorScheme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  }

  telegramUser = tg.initDataUnsafe?.user || null;

  console.log('[tg-init] telegramUser id:', telegramUser ? telegramUser.id : null);

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

/**
 * Build auth headers shared by apiFetch and downloadReport.
 * Attaches X-Telegram-Init-Data, X-Telegram-Id, and X-User-Role when available.
 */
function getAuthHeaders() {
  const h = {};
  const initData = getTelegramInitData();
  if (initData) h['X-Telegram-Init-Data'] = initData;
  const telegramId = telegramUser?.id || localStorage.getItem('telegram_id');
  if (telegramId) h['X-Telegram-Id'] = String(telegramId);
  const savedRole = localStorage.getItem('user_role');
  if (savedRole) h['X-User-Role'] = savedRole;
  console.log('[auth-headers] initData present:', !!initData, '| telegramId:', telegramId || null, '| role:', savedRole || null);
  return h;
}

async function apiFetch(path, options = {}) {
  const authHeaders = getAuthHeaders();
  const headers = {
    'Content-Type': 'application/json',
    ...authHeaders,
    ...options.headers,  // allow callers to override specific headers
  };

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}`;
    try {
      const err = await response.json();
      const rawDetail = err.detail || err.error;
      if (rawDetail !== undefined && rawDetail !== null) {
        errorDetail = typeof rawDetail === 'string' ? rawDetail : JSON.stringify(rawDetail);
      }
    } catch (_) {}

    throw new Error(errorDetail);
  }

  return response.json();
}

/**
 * Extract a human-readable error message from any error value.
 * Handles strings, Error objects, FastAPI detail responses, and plain objects.
 */
function getErrorMessage(error) {
  if (!error) return 'Unknown error';
  if (typeof error === 'string') return error;
  if (error.detail) {
    if (typeof error.detail === 'string') return error.detail;
    if (Array.isArray(error.detail))
      return error.detail.map(e => e.msg || JSON.stringify(e)).join(', ');
  }
  if (error.message) return error.message;
  if (error.response?.detail) {
    if (typeof error.response.detail === 'string') return error.response.detail;
    return JSON.stringify(error.response.detail);
  }
  return JSON.stringify(error);
}

// ==========================================
// APP STATE
// ==========================================
const state = {
  settings: null,
  enrichedSettings: null,
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

/**
 * Normalize raw enriched-settings response into a unified {id, name} format.
 * Handles backend field-name variants (e.g. client_name vs name).
 */
function normalizeSettings(data) {
  return {
    statuses: (data.statuses || []).map(s =>
      (s && typeof s === 'object' && 'id' in s)
        ? { id: s.id, name: s.name }
        : { id: s, name: s }
    ),
    clients: (data.clients || []).map(c => ({
      id: c.id,
      name: c.name || c.client_name,
    })),
    managers: (data.managers || []).map(m => ({
      id: m.id,
      name: m.name || m.manager_name,
    })),
    directions: (data.business_directions || data.directions || []).map(d => ({
      id: d.id,
      name: d.name,
    })),
    warehouses: (data.warehouses || []).map(w => ({
      id: w.id,
      name: w.name,
      code: w.code,
    })),
    expense_categories: data.expense_categories || [],
    vat_types: data.vat_types || [],
  };
}

async function loadSettings() {
  // Prevent duplicate requests — return cached settings if already loaded.
  if (state.settings) return state.settings;
  // /settings/enriched is the single source of truth for all reference data.
  // It returns {id, name} objects used by SQL-function endpoints.
  try {
    const enriched = await apiFetch('/settings/enriched');
    console.log("Loaded settings:", enriched);
    state.enrichedSettings = normalizeSettings(enriched);
    state.settings = enriched;
    populateSelects(enriched);
    updateSettingsStats(enriched);
    return enriched;
  } catch (err) {
    console.error('Failed to load enriched settings:', err);
    showToast('Ошибка загрузки справочников. Используются значения по умолчанию.', 'warning');
    // Fallback: plain-string lists so the UI stays usable when DB is unreachable.
    const fallback = {
      statuses: ['Новая', 'В работе', 'Завершена', 'Отменена', 'Приостановлена'],
      business_directions: ['ФФ МСК', 'ФФ НСК', 'ФФ ЕКБ', 'ТЛК', 'УТЛ'],
      clients: [],
      managers: [],
      vat_types: ['С НДС', 'Без НДС'],
      sources: ['Рекомендация', 'Сайт', 'Реклама', 'Холодный звонок', 'Другое'],
      warehouses: [],
      expense_categories: [],
    };
    state.settings = fallback;
    state.enrichedSettings = null;
    console.warn("Settings not loaded, using fallback lists");
    populateSelects(fallback);
    updateSettingsStats(fallback);
    return fallback;
  }
}

function populateSelects(data) {
  // data is the enriched settings object ({id,name} items when available)
  fillSelect('status', data.statuses || []);
  fillSelect('business_direction', data.business_directions || []);
  fillSelect('client', data.clients || []);
  fillSelect('manager', data.managers || []);
  fillSelect('vat_type', data.vat_types || []);
  fillSelect('source', data.sources || []);

  // ALL client dropdowns — use the same normalized source
  const clients = data.clients || [];
  console.log('[populateSelects] populating client dropdowns with', clients.length, 'clients');
  fillSelect('billing-client-select', clients);
  fillSelect('payment-client-select', clients);
  fillSelect('expense-client-select', clients);
  fillSelect('report-client-select', clients);
  fillSelect('filter-client', clients, true);

  // Direction dropdowns
  const dirs = data.business_directions || [];
  fillSelect('payment-direction-select', dirs);
  fillSelect('expense-direction-select', dirs);

  // Billing warehouse dropdown – populate from enriched warehouses when available
  if (data.warehouses && data.warehouses.length > 0) {
    fillSelect('billing-warehouse', data.warehouses.map(w => ({
      id: w.id,
      name: `${(w.code || '').toUpperCase()} — ${w.name}`,
    })));
  }

  // Edit deal status dropdown
  fillSelect('edit-status', data.statuses || []);

  // Filters
  fillSelect('filter-status', data.statuses || [], true);

  // Expense category level 1 — populate from DB categories if available
  if (data.expense_categories && data.expense_categories.length > 0) {
    // Rebuild EXPENSE_CATS_L2 map and ID lookup maps from loaded data
    const cat1Items = [];
    data.expense_categories.forEach(cat => {
      const key = cat.name.toLowerCase();
      const catIdStr = String(cat.id);
      // Store sub-category objects {id, name} indexed by L1 numeric ID (for ID-based lookup)
      EXPENSE_CATS_L2_BY_ID[catIdStr] = (cat.sub_categories || []).map(sc => ({ id: sc.id, name: sc.name }));
      // Also keep name-based fallback for static EXPENSE_CATS_L2 (used when settings fail)
      EXPENSE_CATS_L2[key] = (cat.sub_categories || []).map(sc => sc.name);
      // Build name→id and id→name lookups for category submission
      EXPENSE_CAT_L1_NAME_TO_ID[key] = cat.id;
      EXPENSE_CAT_L1_ID_TO_NAME[catIdStr] = key;
      (cat.sub_categories || []).forEach(sc => {
        const scKey = sc.name.toLowerCase();
        EXPENSE_CAT_L2_NAME_TO_ID[scKey] = sc.id;
        EXPENSE_CAT_L2_ID_TO_NAME[String(sc.id)] = scKey;
      });
      // Use numeric ID as dropdown value
      cat1Items.push({ id: cat.id, name: cat.name });
    });
    fillSelect('expense-cat1', cat1Items);
  }
}

/**
 * Fill a <select> element with options.
 * Each option can be:
 *   - a plain string  →  value=string, label=string
 *   - an object {id, name}  →  value=id, label=name (for SQL function endpoints)
 */
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
    if (opt && typeof opt === 'object' && 'id' in opt) {
      // Enriched format: store ID as value, show name as label
      option.value = String(opt.id);
      option.textContent = opt.name;
      option.dataset.name = opt.name;
    } else {
      option.value = opt;
      option.textContent = opt;
    }
    select.appendChild(option);
  });

  // Restore previous value if exists
  if (currentValue) select.value = currentValue;
}

/**
 * Populate a <select> element with {id, name} objects.
 * Keeps the first placeholder <option>.
 */
function populateSelectFromObjects(selectEl, items) {
  if (!selectEl) return;
  const first = selectEl.options[0];
  selectEl.innerHTML = '';
  if (first) selectEl.appendChild(first);
  (items || []).forEach(item => {
    const o = document.createElement('option');
    o.value = String(item.id);
    o.textContent = item.name || item.deal_name || String(item.id);
    o.dataset.name = item.name || item.deal_name || String(item.id);
    selectEl.appendChild(o);
  });
}

/**
 * Load deals from /deals filtered by optional direction_id and client_id,
 * then populate the given <select> element.
 */
async function loadDealsFiltered(dealSelectId, directionId, clientId) {
  const select = document.getElementById(dealSelectId);
  if (!select) return;

  const params = new URLSearchParams();
  if (directionId) params.set('business_direction_id', directionId);
  if (clientId)    params.set('client_id', clientId);

  try {
    const qs = params.toString();
    const deals = await apiFetch(`/deals${qs ? '?' + qs : ''}`);
    const items = (deals || []).map(d => ({
      id: d.id,
      name: d.deal_name || d.client || `Сделка #${d.id}`,
    }));
    populateSelectFromObjects(select, items);
  } catch (err) {
    console.warn('loadDealsFiltered error:', err);
    populateSelectFromObjects(select, []);
  }
}

/**
 * Init dependent direction→client→deal dropdowns.
 * @param {string} dirSelectId   ID of direction <select>
 * @param {string} clientSelectId ID of client <select>
 * @param {string} dealSelectId  ID of deal <select>
 */
function initDependentDealDropdowns(dirSelectId, clientSelectId, dealSelectId) {
  const dirEl    = document.getElementById(dirSelectId);
  const clientEl = document.getElementById(clientSelectId);
  const dealEl   = document.getElementById(dealSelectId);
  if (!dirEl || !clientEl || !dealEl) return;

  // Direction change: clear deal dropdown since client context may be irrelevant
  dirEl.addEventListener('change', () => {
    console.log('[dropdown] direction changed:', dirEl.value);
    populateSelectFromObjects(dealEl, []);
  });

  // Client change: reload deals only when a client is actually selected
  clientEl.addEventListener('change', () => {
    const dirId    = dirEl.value    || null;
    const clientId = clientEl.value || null;
    console.log('[dropdown] client changed:', clientId, 'dir:', dirId);
    if (clientId) {
      loadDealsFiltered(dealSelectId, dirId, clientId);
    } else {
      populateSelectFromObjects(dealEl, []);
    }
  });
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

  // Update "Начислено" label based on VAT type
  const vatTypeEl = document.getElementById('vat_type');
  const chargedLabelEl = document.getElementById('charged-label');
  const updateChargedLabel = () => {
    if (!chargedLabelEl) return;
    const vatType = vatTypeEl ? vatTypeEl.value : '';
    if (vatType === 'С НДС') {
      chargedLabelEl.innerHTML = 'Начислено с НДС, ₽ <span class="required">*</span>';
    } else if (vatType === 'Без НДС') {
      chargedLabelEl.innerHTML = 'Начислено без НДС, ₽ <span class="required">*</span>';
    } else {
      chargedLabelEl.innerHTML = 'Начислено, ₽ <span class="required">*</span>';
    }
  };
  if (vatTypeEl) vatTypeEl.addEventListener('change', updateChargedLabel);

  // Live VAT calculation in deal form
  const chargedEl = document.getElementById('charged_with_vat');
  const vatRateEl = document.getElementById('vat_rate');
  const updateDealVat = () => {
    const charged = parseFloat(chargedEl?.value || 0) || 0;
    const vatRate = parseFloat(vatRateEl?.value || 0) || 0;
    const calcRow = document.getElementById('deal-vat-calc');
    if (!calcRow) return;

    if (charged && vatRate) {
      const amountNoVat = charged / (1 + vatRate);
      const vatAmount = charged - amountNoVat;
      calcRow.style.display = 'flex';
      setEl('deal-calc-vat-amount', `${vatAmount.toFixed(2)} ₽`);
      setEl('deal-calc-amount-no-vat', `${amountNoVat.toFixed(2)} ₽`);
    } else {
      calcRow.style.display = 'none';
    }
  };
  if (chargedEl) chargedEl.addEventListener('input', updateDealVat);
  if (vatRateEl) vatRateEl.addEventListener('input', updateDealVat);
}

function updateSummary() {
  const clientId = getFieldValue('client');
  const amount = getFieldValue('charged_with_vat');
  const statusId = getFieldValue('status');
  const managerId = getFieldValue('manager');

  const summaryCard = document.getElementById('deal-summary');
  if (!summaryCard) return;

  const hasData = clientId || amount || statusId || managerId;
  summaryCard.style.display = hasData ? 'block' : 'none';

  // Resolve human-readable labels from normalized settings when IDs are stored in selects.
  const ns = state.enrichedSettings;
  const labelById = (items, id) => {
    if (!id) return '—';
    if (ns) {
      const found = (items || []).find(x => String(x.id) === String(id));
      if (found) return found.name;
    }
    // Fallback: try to read the option text directly from the select element
    const el = document.querySelector(`select option[value="${id}"]`);
    return (el && el.textContent) ? el.textContent : String(id);
  };

  setEl('sum-client', labelById(ns?.clients, clientId));
  setEl('sum-amount', amount ? formatCurrency(parseFloat(amount)) : '—');
  setEl('sum-status', labelById(ns?.statuses, statusId));
  setEl('sum-manager', labelById(ns?.managers, managerId));
}

async function handleFormSubmit(e) {
  e.preventDefault();

  if (state.isSubmitting) return;

  const errors = validateForm();
  if (errors.length > 0) {
    showToast('Пожалуйста, заполните обязательные поля', 'error');
    return;
  }

  const dealData = collectFormDataSql();
  console.log('[deal save] payload:', dealData);

  setSubmitting(true);

  try {
    // Always use the SQL-function endpoint /deals/create.
    // Requires enriched settings to be loaded (IDs, not text values).
    if (!state.enrichedSettings) {
      throw new Error('Справочники не загружены. Перезагрузите страницу и попробуйте снова.');
    }
    const result = await apiFetch('/deals/create', {
      method: 'POST',
      body: JSON.stringify(dealData),
    });

    const dealId = result.deal_id || result.id || result.deal?.id || '—';
    showSuccessScreen(dealId);
    showToast(`Сделка ${dealId} успешно создана!`, 'success');

    // Invalidate deals cache
    state.deals = [];

  } catch (err) {
    showToast(`Ошибка при сохранении: ${getErrorMessage(err)}`, 'error');
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

  // Validate that critical select fields contain valid numeric IDs (required for SQL endpoint)
  [
    { id: 'status',  label: 'Статус сделки' },
    { id: 'client',  label: 'Клиент' },
    { id: 'manager', label: 'Менеджер' },
  ].forEach(({ id, label }) => {
    const el = document.getElementById(id);
    const val = el ? el.value.trim() : '';
    if (val && isNaN(parseInt(val, 10))) {
      errors.push(label);
      const errorEl = document.getElementById(`${id}-error`);
      if (errorEl) errorEl.textContent = 'Справочник не загружен — перезагрузите страницу';
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
    vat_rate: floatVal('vat_rate'),
    paid: floatVal('paid'),
    project_start_date: getFieldValue('project_start_date'),
    project_end_date: getFieldValue('project_end_date'),
    act_date: getFieldValue('act_date') || null,
    // Legacy expense fields
    variable_expense_1: floatVal('variable_expense_1'),
    variable_expense_2: floatVal('variable_expense_2'),
    // New expense VAT fields
    variable_expense_1_with_vat: floatVal('variable_expense_1_with_vat'),
    variable_expense_2_with_vat: floatVal('variable_expense_2_with_vat'),
    production_expense_with_vat: floatVal('production_expense_with_vat'),
    manager_bonus_percent: floatVal('manager_bonus_percent'),
    manager_bonus_paid: floatVal('manager_bonus_paid'),
    general_production_expense: floatVal('general_production_expense'),
    source: getFieldValue('source') || null,
    document_link: getFieldValue('document_link') || null,
    comment: getFieldValue('comment') || null,
  };
}

/**
 * Collect deal form data using IDs from enriched settings.
 * Used when submitting to the SQL-function endpoint /deals/create.
 */
function collectFormDataSql() {
  const intVal = (id) => {
    const v = getFieldValue(id);
    if (!v) return null;
    const n = parseInt(v, 10);
    return Number.isFinite(n) ? n : null;
  };
  const floatVal = (id) => {
    const v = getFieldValue(id);
    return v !== '' ? parseFloat(v) : null;
  };

  return {
    status_id: intVal('status'),
    business_direction_id: intVal('business_direction'),
    client_id: intVal('client'),
    manager_id: intVal('manager'),
    charged_with_vat: floatVal('charged_with_vat'),
    vat_type_id: intVal('vat_type'),
    vat_rate: floatVal('vat_rate'),
    paid: floatVal('paid') || 0,
    project_start_date: getFieldValue('project_start_date') || null,
    project_end_date: getFieldValue('project_end_date') || null,
    act_date: getFieldValue('act_date') || null,
    variable_expense_1_without_vat: floatVal('variable_expense_1'),
    variable_expense_2_without_vat: floatVal('variable_expense_2'),
    // Prefer the general_production_expense field; fall back to production_expense_with_vat
    // for backward compatibility when the form only has the legacy VAT-inclusive field.
    production_expense_without_vat: floatVal('general_production_expense') || floatVal('production_expense_with_vat'),
    manager_bonus_percent: floatVal('manager_bonus_percent'),
    source_id: intVal('source'),
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

  if (refreshBtn) refreshBtn.addEventListener('click', () => loadDeals());

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
    const params = new URLSearchParams();
    // The /deals endpoint filters by the authenticated user's role automatically.
    // Optional client/status filters can be passed as query params.

    const deals = await apiFetch(`/deals${params.toString() ? '?' + params : ''}`);
    state.deals = deals;
    renderDeals();
  } catch (err) {
    showToast(`Ошибка загрузки сделок: ${getErrorMessage(err)}`, 'error');
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

  // Build ID→name map for client lookup (filter-client dropdown uses numeric IDs)
  const clientMap = Object.fromEntries(
    (state.enrichedSettings?.clients || []).map(c => [String(c.id), c.name])
  );

  let filtered = state.deals.filter(deal => {
    if (statusFilter && deal.status !== statusFilter) return false;
    if (clientFilter) {
      // clientFilter is a numeric ID; deal.client is a name, deal.client_id is a numeric ID
      const dealClientName = deal.client || clientMap[String(deal.client_id)];
      const filterClientName = clientMap[clientFilter] || clientFilter;
      if (dealClientName !== filterClientName) return false;
    }
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
// DEAL EDITING
// ==========================================
function initDealEdit() {
  const dealSelect = document.getElementById('edit-deal-select');
  if (dealSelect) {
    dealSelect.addEventListener('change', () => onEditDealSelected(dealSelect.value));
  }

  const saveBtn = document.getElementById('edit-deal-save-btn');
  if (saveBtn) saveBtn.addEventListener('click', saveEditedDeal);

  const backBtn = document.getElementById('edit-deal-back-btn');
  if (backBtn) {
    backBtn.addEventListener('click', () => {
      switchSubnav('my-deals-sub');
    });
  }
}

async function loadDealsForEdit() {
  const dealSelect = document.getElementById('edit-deal-select');
  if (!dealSelect) return;

  try {
    const deals = await apiFetch('/deals');
    dealSelect.innerHTML = '<option value="">Выберите сделку...</option>';
    deals.forEach(d => {
      const opt = document.createElement('option');
      opt.value = d.deal_id;
      opt.textContent = `${d.deal_id} — ${d.client || ''}${d.status ? ' [' + d.status + ']' : ''}`;
      dealSelect.appendChild(opt);
    });
  } catch (err) {
    showToast(`Ошибка загрузки сделок: ${getErrorMessage(err)}`, 'error');
  }
}

async function onEditDealSelected(dealId) {
  const formBody = document.getElementById('edit-deal-form-body');
  const saveActions = document.getElementById('edit-deal-save-actions');
  if (!dealId) {
    if (formBody) formBody.style.display = 'none';
    if (saveActions) saveActions.style.display = 'none';
    return;
  }

  try {
    const deal = await apiFetch(`/deals/${dealId}`);

    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el && val !== null && val !== undefined && val !== '') el.value = val;
    };

    setVal('edit-status', deal.status);
    setVal('edit-variable-expense-1-with-vat', deal.variable_expense_1_with_vat);
    setVal('edit-variable-expense-2-with-vat', deal.variable_expense_2_with_vat);
    setVal('edit-production-expense-with-vat', deal.production_expense_with_vat);
    setVal('edit-general-production-expense', deal.general_production_expense);
    setVal('edit-manager-bonus-pct', deal.manager_bonus_pct);
    setVal('edit-comment', deal.comment);

    if (formBody) formBody.style.display = 'block';
    if (saveActions) saveActions.style.display = 'block';
  } catch (err) {
    showToast(`Ошибка загрузки сделки: ${getErrorMessage(err)}`, 'error');
  }
}

async function saveEditedDeal() {
  const dealId = document.getElementById('edit-deal-select')?.value;
  if (!dealId) { showToast('Выберите сделку', 'error'); return; }

  const pFloat = (id) => {
    const v = document.getElementById(id)?.value;
    return v ? parseFloat(v) : null;
  };

  const payload = {};
  const statusEl = document.getElementById('edit-status');
  if (statusEl?.value) payload.status = statusEl.value;

  const v1 = pFloat('edit-variable-expense-1-with-vat');
  if (v1 != null) payload.variable_expense_1_with_vat = v1;

  const v2 = pFloat('edit-variable-expense-2-with-vat');
  if (v2 != null) payload.variable_expense_2_with_vat = v2;

  const pe = pFloat('edit-production-expense-with-vat');
  if (pe != null) payload.production_expense_with_vat = pe;

  const gpe = pFloat('edit-general-production-expense');
  if (gpe != null) payload.general_production_expense = gpe;

  const bonusPct = pFloat('edit-manager-bonus-pct');
  if (bonusPct != null) payload.manager_bonus_pct = bonusPct;

  const commentEl = document.getElementById('edit-comment');
  if (commentEl?.value?.trim()) payload.comment = commentEl.value.trim();

  if (Object.keys(payload).length === 0) {
    showToast('Нет изменений для сохранения', 'warning');
    return;
  }

  try {
    await apiFetch(`/deals/update/${dealId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
    showToast(`Сделка ${dealId} обновлена!`, 'success');
  } catch (err) {
    showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
  }
}

function switchSubnav(subId) {
  const parent = document.getElementById('tab-finances');
  if (!parent) return;
  parent.querySelectorAll('.subnav-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.sub === subId);
  });
  parent.querySelectorAll('[id$="-sub"]').forEach(panel => {
    panel.style.display = panel.id === subId ? 'block' : 'none';
  });
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
      deal = await apiFetch(`/deals/${dealId}`);
    } catch (err) {
      showToast(`Ошибка загрузки сделки: ${getErrorMessage(err)}`, 'error');
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
        ['Ставка НДС', deal.vat_rate != null ? `${(deal.vat_rate * 100).toFixed(0)}%` : null],
        ['Сумма НДС', deal.vat_amount != null ? formatCurrency(deal.vat_amount) : null],
        ['Без НДС', deal.amount_without_vat != null ? formatCurrency(deal.amount_without_vat) : null],
        ['Тип НДС', deal.vat_type],
        ['Оплачено', deal.paid != null ? formatCurrency(deal.paid) : null],
      ],
    },
    {
      title: '📊 Маржинальность',
      fields: [
        ['Маржинальный доход', deal.marginal_income != null ? formatCurrency(deal.marginal_income) : null],
        ['Валовая прибыль', deal.gross_profit != null ? formatCurrency(deal.gross_profit) : null],
        ['Бонус менеджера', deal.manager_bonus_amount != null ? formatCurrency(deal.manager_bonus_amount) : null],
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
        ['Переменный расход 1 с НДС', deal.variable_expense_1_with_vat != null ? formatCurrency(deal.variable_expense_1_with_vat) : null],
        ['Переменный расход 1 без НДС', deal.variable_expense_1_without_vat != null ? formatCurrency(deal.variable_expense_1_without_vat) : null],
        ['Переменный расход 2', deal.variable_expense_2 != null ? formatCurrency(deal.variable_expense_2) : null],
        ['Переменный расход 2 с НДС', deal.variable_expense_2_with_vat != null ? formatCurrency(deal.variable_expense_2_with_vat) : null],
        ['Переменный расход 2 без НДС', deal.variable_expense_2_without_vat != null ? formatCurrency(deal.variable_expense_2_without_vat) : null],
        ['Произв. расход с НДС', deal.production_expense_with_vat != null ? formatCurrency(deal.production_expense_with_vat) : null],
        ['Произв. расход без НДС', deal.production_expense_without_vat != null ? formatCurrency(deal.production_expense_without_vat) : null],
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
        ['Дата создания', deal.created_at],
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
  // Telegram: consider WebApp present AND (initData non-empty OR user object available).
  // initData can be an empty string in certain Telegram contexts even when opened from
  // within Telegram, so we also check initDataUnsafe.user / telegramUser as fallback.
  const tgSdkAvailable = !!tg;
  const hasInitData = !!(tg?.initData);
  const hasUser = !!(telegramUser || tg?.initDataUnsafe?.user);
  const isInTelegram    = tgSdkAvailable && (hasInitData || hasUser);

  console.log('[tg-check] SDK available:', tgSdkAvailable, '| initData present:', hasInitData,
              '| user present:', hasUser, '| isInTelegram:', isInTelegram);

  let tgStatus, tgOk;
  if (isInTelegram) {
    tgOk = true;
    tgStatus = 'Подключено';
  } else if (tgSdkAvailable) {
    tgOk = false;
    tgStatus = 'Открыто вне Telegram';
  } else {
    tgOk = false;
    tgStatus = 'Открыто вне Telegram';
  }
  setConnectionStatus('telegram', tgOk, tgStatus);

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
// SETTINGS MANAGEMENT (Clients, Managers, Directions, Statuses)
// ==========================================

function initSettingsManagement() {
  // Clients
  const addClientBtn = document.getElementById('add-client-btn');
  const refreshClientsBtn = document.getElementById('refresh-clients-btn');
  if (addClientBtn) addClientBtn.addEventListener('click', addClient);
  if (refreshClientsBtn) refreshClientsBtn.addEventListener('click', loadClientsSettings);

  // Managers
  const addManagerBtn = document.getElementById('add-manager-btn');
  const refreshManagersBtn = document.getElementById('refresh-managers-btn');
  if (addManagerBtn) addManagerBtn.addEventListener('click', addManager);
  if (refreshManagersBtn) refreshManagersBtn.addEventListener('click', loadManagersSettings);

  // Directions
  const addDirectionBtn = document.getElementById('add-direction-btn');
  const refreshDirectionsBtn = document.getElementById('refresh-directions-btn');
  if (addDirectionBtn) addDirectionBtn.addEventListener('click', addDirection);
  if (refreshDirectionsBtn) refreshDirectionsBtn.addEventListener('click', loadDirectionsSettings);

  // Statuses
  const addStatusBtn = document.getElementById('add-status-btn');
  const refreshStatusesBtn = document.getElementById('refresh-statuses-btn');
  if (addStatusBtn) addStatusBtn.addEventListener('click', addStatus);
  if (refreshStatusesBtn) refreshStatusesBtn.addEventListener('click', loadStatusesSettings);

  // Load all reference data
  loadClientsSettings();
  loadManagersSettings();
  loadDirectionsSettings();
  loadStatusesSettings();
}

// --- Clients ---
async function loadClientsSettings() {
  try {
    const clients = await apiFetch('/settings/clients');
    renderRefList('clients-list-settings', 'clients-empty-settings', clients, (item) => ({
      id: item.client_id,
      label: item.client_name,
      onDelete: () => deleteClient(item.client_id, item.client_name),
    }));
    setEl('cnt-clients', clients.length);
    // Use {id, name} objects so ALL client dropdowns carry numeric IDs
    const clientItems = clients.map(c => ({ id: c.client_id, name: c.client_name }));
    console.log('[clients] loaded', clientItems.length, 'clients from settings');
    fillSelect('client', clientItems);
    fillSelect('filter-client', clientItems, true);
    fillSelect('billing-client-select', clientItems);
    fillSelect('payment-client-select', clientItems);
    fillSelect('expense-client-select', clientItems);
    fillSelect('report-client-select', clientItems);
    if (state.settings) state.settings.clients = clientItems;
    if (state.enrichedSettings) state.enrichedSettings.clients = clientItems;
  } catch (err) {
    console.warn('Could not load clients from settings API:', err);
  }
}

async function addClient() {
  const input = document.getElementById('new-client-name');
  const name = input ? input.value.trim() : '';
  if (!name) { showToast('Введите название клиента', 'error'); return; }
  try {
    await apiFetch('/settings/clients', { method: 'POST', body: JSON.stringify({ client_name: name }) });
    if (input) input.value = '';
    showToast('Клиент добавлен', 'success');
    await loadClientsSettings();
  } catch (err) {
    showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
  }
}

async function deleteClient(clientId, clientName) {
  if (!confirm(`Удалить клиента "${clientName}"?`)) return;
  try {
    await apiFetch(`/settings/clients/${encodeURIComponent(clientId)}`, { method: 'DELETE' });
    showToast('Клиент удалён', 'success');
    await loadClientsSettings();
  } catch (err) {
    showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
  }
}

// --- Managers ---
async function loadManagersSettings() {
  try {
    const managers = await apiFetch('/settings/managers');
    renderRefList('managers-list-settings', 'managers-empty-settings', managers, (item) => ({
      id: item.manager_id,
      label: `${item.manager_name} (${item.role || 'manager'})`,
      onDelete: () => deleteManager(item.manager_id, item.manager_name),
    }));
    setEl('cnt-managers', managers.length);
    const managerItems = managers.map(m => ({ id: m.manager_id, name: m.manager_name }));
    console.log('[managers] loaded', managerItems.length, 'managers from settings');
    fillSelect('manager', managerItems);
    if (state.settings) state.settings.managers = managerItems;
    if (state.enrichedSettings) state.enrichedSettings.managers = managerItems;
  } catch (err) {
    console.warn('Could not load managers from settings API:', err);
  }
}

async function addManager() {
  const nameInput = document.getElementById('new-manager-name');
  const roleInput = document.getElementById('new-manager-role');
  const name = nameInput ? nameInput.value.trim() : '';
  const role = roleInput ? roleInput.value : 'manager';
  if (!name) { showToast('Введите имя менеджера', 'error'); return; }
  try {
    await apiFetch('/settings/managers', { method: 'POST', body: JSON.stringify({ manager_name: name, role }) });
    if (nameInput) nameInput.value = '';
    showToast('Менеджер добавлен', 'success');
    await loadManagersSettings();
  } catch (err) {
    showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
  }
}

async function deleteManager(managerId, managerName) {
  if (!confirm(`Удалить менеджера "${managerName}"?`)) return;
  try {
    await apiFetch(`/settings/managers/${encodeURIComponent(managerId)}`, { method: 'DELETE' });
    showToast('Менеджер удалён', 'success');
    await loadManagersSettings();
  } catch (err) {
    showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
  }
}

// --- Directions ---
async function loadDirectionsSettings() {
  try {
    const directions = await apiFetch('/settings/directions');
    renderRefList('directions-list-settings', 'directions-empty-settings', directions.map(d => ({ value: d })), (item) => ({
      id: item.value,
      label: item.value,
      onDelete: () => deleteDirection(item.value),
    }));
    setEl('cnt-directions', directions.length);
    // Prefer enriched settings with IDs; if unavailable, leave form selects empty
    // so the form fails validation rather than sending string values as direction IDs
    const dirItems = (state.enrichedSettings && state.enrichedSettings.business_directions && state.enrichedSettings.business_directions.length > 0)
      ? state.enrichedSettings.business_directions
      : [];
    fillSelect('business_direction', dirItems);
    fillSelect('payment-direction-select', dirItems);
    fillSelect('expense-direction-select', dirItems);
    if (state.settings) state.settings.business_directions = dirItems;
  } catch (err) {
    console.warn('Could not load directions from settings API:', err);
  }
}

async function addDirection() {
  const input = document.getElementById('new-direction-name');
  const name = input ? input.value.trim() : '';
  if (!name) { showToast('Введите название направления', 'error'); return; }
  try {
    await apiFetch('/settings/directions', { method: 'POST', body: JSON.stringify({ value: name }) });
    if (input) input.value = '';
    showToast('Направление добавлено', 'success');
    await loadDirectionsSettings();
  } catch (err) {
    showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
  }
}

async function deleteDirection(direction) {
  if (!confirm(`Удалить направление "${direction}"?`)) return;
  try {
    await apiFetch(`/settings/directions/${encodeURIComponent(direction)}`, { method: 'DELETE' });
    showToast('Направление удалено', 'success');
    await loadDirectionsSettings();
  } catch (err) {
    showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
  }
}

// --- Statuses ---
async function loadStatusesSettings() {
  try {
    const statuses = await apiFetch('/settings/statuses');
    renderRefList('statuses-list-settings', 'statuses-empty-settings', statuses.map(s => ({ value: s })), (item) => ({
      id: item.value,
      label: item.value,
      onDelete: () => deleteStatus(item.value),
    }));
    setEl('cnt-statuses', statuses.length);
    // Prefer enriched settings with IDs; if unavailable, leave form selects empty
    // so validateForm catches the missing data (string IDs would fail backend validation)
    const statusItems = (state.enrichedSettings && state.enrichedSettings.statuses && state.enrichedSettings.statuses.length > 0)
      ? state.enrichedSettings.statuses
      : [];
    fillSelect('status', statusItems);
    fillSelect('edit-status', statusItems);
    fillSelect('filter-status', statusItems, true);
    if (state.settings) state.settings.statuses = statusItems;
  } catch (err) {
    console.warn('Could not load statuses from settings API:', err);
  }
}

async function addStatus() {
  const input = document.getElementById('new-status-name');
  const name = input ? input.value.trim() : '';
  if (!name) { showToast('Введите название статуса', 'error'); return; }
  try {
    await apiFetch('/settings/statuses', { method: 'POST', body: JSON.stringify({ value: name }) });
    if (input) input.value = '';
    showToast('Статус добавлен', 'success');
    await loadStatusesSettings();
  } catch (err) {
    showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
  }
}

async function deleteStatus(status) {
  if (!confirm(`Удалить статус "${status}"?`)) return;
  try {
    await apiFetch(`/settings/statuses/${encodeURIComponent(status)}`, { method: 'DELETE' });
    showToast('Статус удалён', 'success');
    await loadStatusesSettings();
  } catch (err) {
    showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
  }
}

// --- Generic ref-list renderer ---
function renderRefList(listId, emptyId, items, itemMapper) {
  const listEl = document.getElementById(listId);
  const emptyEl = document.getElementById(emptyId);

  if (!listEl) return;
  listEl.innerHTML = '';

  if (!items || items.length === 0) {
    if (emptyEl) emptyEl.style.display = 'flex';
    return;
  }
  if (emptyEl) emptyEl.style.display = 'none';

  items.forEach(item => {
    const mapped = itemMapper(item);
    const row = document.createElement('div');
    row.className = 'ref-list-item';

    const labelSpan = document.createElement('span');
    labelSpan.className = 'ref-list-label';
    labelSpan.textContent = mapped.label;

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'btn btn-sm btn-danger ref-delete-btn';
    deleteBtn.title = 'Удалить';
    deleteBtn.textContent = '🗑';
    deleteBtn.addEventListener('click', mapped.onDelete);

    row.appendChild(labelSpan);
    row.appendChild(deleteBtn);
    listEl.appendChild(row);
  });
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
  initMonthClose();

  // Check auth before showing any content
  const savedRole = localStorage.getItem('user_role');

  // If running inside Telegram and user has a saved role but no telegram_id stored,
  // the app_users record may not exist yet (old login flow). Force re-authentication
  // so that /auth/miniapp-login is called and the record is created.
  if (savedRole && telegramUser && !localStorage.getItem('telegram_id')) {
    localStorage.removeItem('user_role');
    localStorage.removeItem('user_role_label');
    showAuthScreen();
    return;
  }

  if (savedRole) {
    await enterApp(savedRole);
  } else {
    showAuthScreen();
  }
}

document.addEventListener('DOMContentLoaded', init);

// ==========================================
// AUTH SYSTEM
// ==========================================

const ROLE_LABELS = {
  manager: 'Менеджер',
  operations_director: 'Операционный директор',
  accounting: 'Бухгалтерия',
  admin: 'Администратор',
  accountant: 'Бухгалтер',
  head_of_sales: 'Руководитель отдела продаж',
};

// Tabs available per role
const ROLE_TABS = {
  manager: [
    { id: 'tab-finances', icon: '💰', label: 'Финансы' },
    { id: 'tab-billing',  icon: '🏭', label: 'Billing' },
    { id: 'tab-expenses', icon: '📉', label: 'Расходы' },
    { id: 'settings-tab', icon: '⚙️', label: 'Настройки' },
  ],
  operations_director: [
    { id: 'tab-finances',    icon: '💰', label: 'Финансы' },
    { id: 'tab-dashboard',   icon: '🏠', label: 'Дашборд' },
    { id: 'tab-receivables', icon: '💳', label: 'Долги' },
    { id: 'tab-billing',     icon: '🏭', label: 'Billing' },
    { id: 'tab-expenses',    icon: '📉', label: 'Расходы' },
    { id: 'tab-reports',     icon: '📥', label: 'Отчёты' },
    { id: 'tab-journal',     icon: '📜', label: 'Журнал' },
    { id: 'tab-month-close', icon: '📅', label: 'Закрытие месяца' },
    { id: 'settings-tab',    icon: '⚙️', label: 'Настройки' },
  ],
  accounting: [
    { id: 'tab-finances',    icon: '💰', label: 'Финансы' },
    { id: 'tab-dashboard',   icon: '🏠', label: 'Дашборд' },
    { id: 'tab-receivables', icon: '💳', label: 'Долги' },
    { id: 'tab-expenses',    icon: '📉', label: 'Расходы' },
    { id: 'tab-reports',     icon: '📥', label: 'Отчёты' },
    { id: 'tab-journal',     icon: '📜', label: 'Журнал' },
    { id: 'settings-tab',    icon: '⚙️', label: 'Настройки' },
  ],
  admin: [
    { id: 'tab-finances',    icon: '💰', label: 'Финансы' },
    { id: 'tab-dashboard',   icon: '🏠', label: 'Дашборд' },
    { id: 'tab-receivables', icon: '💳', label: 'Долги' },
    { id: 'tab-billing',     icon: '🏭', label: 'Billing' },
    { id: 'tab-expenses',    icon: '📉', label: 'Расходы' },
    { id: 'tab-reports',     icon: '📥', label: 'Отчёты' },
    { id: 'tab-journal',     icon: '📜', label: 'Журнал' },
    { id: 'tab-month-close', icon: '📅', label: 'Закрытие месяца' },
    { id: 'settings-tab',    icon: '⚙️', label: 'Настройки' },
  ],
  // Legacy roles
  accountant: [
    { id: 'tab-finances',    icon: '💰', label: 'Финансы' },
    { id: 'tab-dashboard',   icon: '🏠', label: 'Дашборд' },
    { id: 'tab-receivables', icon: '💳', label: 'Долги' },
    { id: 'tab-expenses',    icon: '📉', label: 'Расходы' },
    { id: 'tab-reports',     icon: '📥', label: 'Отчёты' },
    { id: 'settings-tab',    icon: '⚙️', label: 'Настройки' },
  ],
  head_of_sales: [
    { id: 'tab-finances', icon: '💰', label: 'Финансы' },
    { id: 'tab-reports',  icon: '📥', label: 'Отчёты' },
    { id: 'settings-tab', icon: '⚙️', label: 'Настройки' },
  ],
};

function showAuthScreen() {
  const authScreen = document.getElementById('auth-screen');
  const appMain = document.getElementById('app-main');
  if (authScreen) authScreen.style.display = 'flex';
  if (appMain) appMain.style.display = 'none';

  initAuthHandlers();
}

function initAuthHandlers() {
  let selectedRole = null;

  // Role buttons
  document.querySelectorAll('.role-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      selectedRole = btn.dataset.role;
      const label = ROLE_LABELS[selectedRole] || selectedRole;
      setEl('auth-role-label', label);

      document.getElementById('auth-step-role').style.display = 'none';
      document.getElementById('auth-step-password').style.display = 'block';

      const pwInput = document.getElementById('auth-password');
      if (pwInput) {
        pwInput.value = '';
        pwInput.focus();
      }

      const errEl = document.getElementById('auth-error');
      if (errEl) errEl.style.display = 'none';
    });
  });

  // Back button
  const backBtn = document.getElementById('auth-back-btn');
  if (backBtn) backBtn.addEventListener('click', () => {
    document.getElementById('auth-step-role').style.display = 'block';
    document.getElementById('auth-step-password').style.display = 'none';
    selectedRole = null;
  });

  // Submit button
  const submitBtn = document.getElementById('auth-submit-btn');
  const pwInput = document.getElementById('auth-password');

  const doLogin = async () => {
    const password = pwInput ? pwInput.value : '';
    if (!selectedRole || !password) return;

    submitBtn.disabled = true;
    const errEl = document.getElementById('auth-error');
    if (errEl) errEl.style.display = 'none';

    try {
      let role, roleLabel;

      console.log('[auth] doLogin – selectedRole:', selectedRole, '| authMode:', telegramUser ? 'telegram' : 'role-login');

      if (telegramUser) {
        // Primary path: call /auth/miniapp-login to create/update app_users record
        const fullName = [telegramUser.first_name, telegramUser.last_name]
          .filter(Boolean).join(' ');
        const result = await apiFetch('/auth/miniapp-login', {
          method: 'POST',
          body: JSON.stringify({
            telegram_id: telegramUser.id,
            full_name: fullName,
            username: telegramUser.username || null,
            selected_role: selectedRole,
            password,
          }),
        });
        role = result.role;
        roleLabel = ROLE_LABELS[role] || role;
        localStorage.setItem('telegram_id', String(telegramUser.id));
      } else {
        // Fallback path: no Telegram context (e.g. dev/testing environment)
        const result = await apiFetch('/auth/role-login', {
          method: 'POST',
          body: JSON.stringify({ role: selectedRole, password }),
        });
        if (!result.success) throw new Error(result.error || result.message || 'Login failed');
        role = result.role;
        roleLabel = result.role_label;
      }

      localStorage.setItem('user_role', role);
      localStorage.setItem('user_role_label', roleLabel);
      await enterApp(role);
    } catch (err) {
      if (errEl) {
        errEl.textContent = 'Неверный пароль. Попробуйте ещё раз.';
        errEl.style.display = 'block';
      }
    } finally {
      submitBtn.disabled = false;
    }
  };

  if (submitBtn) submitBtn.addEventListener('click', doLogin);
  if (pwInput) pwInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') doLogin();
  });
}

async function enterApp(role) {
  console.log('[auth] enterApp – role:', role, '| telegram_id:', localStorage.getItem('telegram_id'), '| hasTelegramUser:', !!telegramUser);
  const authScreen = document.getElementById('auth-screen');
  const appMain = document.getElementById('app-main');
  if (authScreen) authScreen.style.display = 'none';
  if (appMain) appMain.style.display = 'block';

  // Update role label in header
  const roleLabel = localStorage.getItem('user_role_label') || ROLE_LABELS[role] || role;
  setEl('header-role-label', roleLabel);

  // Build role-specific tabs
  buildTabs(role);

  // Load settings
  await loadSettings();

  // Show first tab
  const firstTab = (ROLE_TABS[role] || ROLE_TABS.manager)[0];
  switchMainTab(firstTab.id);

  // Setup logout
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) logoutBtn.addEventListener('click', () => {
    localStorage.removeItem('user_role');
    localStorage.removeItem('user_role_label');
    localStorage.removeItem('telegram_id');
    location.reload();
  });

  // Show user info
  renderUserInfoCard();
  updateUserInfoWithRole(role, roleLabel);

  // Init new feature handlers
  initBillingForm();
  initExpensesForm();
  initDealEdit();
  initReportsHandlers();
  initJournalHandlers();
  initSubnav();
  initSettingsManagement();
  initDashboardHandlers();
  initReceivablesHandlers();
}

function buildTabs(role) {
  const nav = document.getElementById('main-tab-nav');
  if (!nav) return;

  const tabs = ROLE_TABS[role] || ROLE_TABS.manager;
  nav.innerHTML = tabs.map((tab, i) => `
    <button class="tab-btn${i === 0 ? ' active' : ''}"
      data-tab="${tab.id}" role="tab"
      aria-selected="${i === 0}">
      <span class="tab-icon">${tab.icon}</span>
      <span class="tab-label">${tab.label}</span>
    </button>
  `).join('');

  nav.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchMainTab(btn.dataset.tab));
  });
}

function switchMainTab(tabId) {
  // Update nav buttons
  document.querySelectorAll('#main-tab-nav .tab-btn').forEach(btn => {
    const active = btn.dataset.tab === tabId;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', active);
  });

  // Show/hide panels
  document.querySelectorAll('.tab-panel').forEach(panel => {
    const active = panel.id === tabId;
    panel.style.display = active ? 'block' : 'none';
    panel.classList.toggle('active', active);
  });

  // Side effects
  if (tabId === 'settings-tab') {
    checkConnections();
    renderUserInfoCard();
    // Refresh settings reference lists when switching to settings
    if (typeof loadClientsSettings === 'function') loadClientsSettings();
    if (typeof loadManagersSettings === 'function') loadManagersSettings();
    if (typeof loadDirectionsSettings === 'function') loadDirectionsSettings();
    if (typeof loadStatusesSettings === 'function') loadStatusesSettings();
  }
  if (tabId === 'tab-dashboard') {
    loadOwnerDashboard();
  }
  if (tabId === 'tab-receivables') {
    loadReceivables();
  }
  if (tabId === 'tab-finances' && !document.getElementById('my-deals-sub').style.display) {
    // show new deal sub by default
  }
}

function updateUserInfoWithRole(role, roleLabel) {
  const content = document.getElementById('user-info-content');
  if (!content) return;

  const roleRow = `<div class="user-info-row"><span>Роль</span><span><strong>${escHtml(roleLabel)}</strong></span></div>`;
  content.insertAdjacentHTML('afterbegin', roleRow);
}

// ==========================================
// SUB-NAV (Finances tab)
// ==========================================
function initSubnav() {
  document.querySelectorAll('.subnav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const subId = btn.dataset.sub;
      document.querySelectorAll('.subnav-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      // Show/hide sub-panels
      ['new-deal-sub', 'my-deals-sub', 'edit-deal-sub'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = id === subId ? 'block' : 'none';
      });

      if (subId === 'my-deals-sub' && state.deals.length === 0) {
        loadDeals();
      }
      if (subId === 'edit-deal-sub') {
        loadDealsForEdit();
      }
    });
  });

  // Override view-deals-btn to switch sub
  const viewDealsBtn = document.getElementById('view-deals-btn');
  if (viewDealsBtn) {
    viewDealsBtn.addEventListener('click', () => {
      switchMainTab('tab-finances');
      const myDealsBtn = document.querySelector('.subnav-btn[data-sub="my-deals-sub"]');
      if (myDealsBtn) myDealsBtn.click();
    });
  }
}

// ==========================================
// BILLING FORM
// ==========================================
function calcBillingTotals(prefix) {
  const val = (id) => parseFloat(document.getElementById(id)?.value || 0) || 0;
  const shipments = val(`${prefix}-shipments`);
  const storage   = val(`${prefix}-storage`);
  const returns   = val(`${prefix}-returns`);
  const extra     = val(`${prefix}-extra`);
  const penalties = val(`${prefix}-penalties`);
  const totalNoPen = shipments + storage + returns + extra;
  const totalWithPen = totalNoPen - penalties;

  setEl(`${prefix}-total-no-pen`,   `${totalNoPen.toFixed(2)} ₽`);
  setEl(`${prefix}-total-with-pen`, `${totalWithPen.toFixed(2)} ₽`);
}

function calcBillingTotalsV2() {
  const pVal = (id) => parseFloat(document.getElementById(id)?.value || 0) || 0;
  const fmt = document.getElementById('billing-format')?.value || 'new';
  const noVatMode = (fmt === 'new-no-vat');
  const BILLING_VAT_RATE = 0.20;

  const services = [
    { id: 'bv2-shipments-with-vat',      calcId: 'bv2-shipments-no-vat-calc' },
    { id: 'bv2-storage-with-vat',        calcId: 'bv2-storage-no-vat-calc' },
    { id: 'bv2-returns-pickup-with-vat', calcId: 'bv2-returns-pickup-no-vat-calc' },
    { id: 'bv2-additional-with-vat',     calcId: 'bv2-additional-no-vat-calc' },
  ];

  let totalNoVat = 0;
  let totalVat = 0;

  for (const svc of services) {
    const entered = pVal(svc.id);
    let noVat, vatA;
    if (noVatMode) {
      noVat = entered;
      vatA = 0;
    } else {
      noVat = entered / (1 + BILLING_VAT_RATE);
      vatA = entered - noVat;
    }
    totalNoVat += noVat;
    totalVat += vatA;
    setEl(svc.calcId, `${noVat.toFixed(2)} ₽`);
  }

  const penalties = pVal('bv2-penalties');
  totalNoVat = totalNoVat - penalties;
  const totalWithVat = noVatMode ? totalNoVat : totalNoVat + totalVat;

  setEl('bv2-total-no-vat', `${totalNoVat.toFixed(2)} ₽`);
  setEl('bv2-total-vat', `${totalVat.toFixed(2)} ₽`);
  setEl('bv2-total-with-vat', `${totalWithVat.toFixed(2)} ₽`);
}

function updateBillingInputLabels() {
  const fmt = document.getElementById('billing-format')?.value || 'new';
  const noVatMode = (fmt === 'new-no-vat');
  const vatRow = document.getElementById('bv2-vat-row');

  const labelMap = {
    'bv2-shipments-label': noVatMode ? 'Отгрузки (без НДС), ₽' : 'Отгрузки с НДС, ₽',
    'bv2-storage-label':   noVatMode ? 'Хранение (без НДС), ₽' : 'Хранение с НДС, ₽',
    'bv2-returns-label':   noVatMode ? 'Забор возвратов (без НДС), ₽' : 'Забор возвратов с НДС, ₽',
    'bv2-additional-label': noVatMode ? 'Доп. услуги (без НДС), ₽' : 'Доп. услуги с НДС, ₽',
  };
  for (const [id, text] of Object.entries(labelMap)) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }
  const calcLabelText = noVatMode ? '(итого без НДС)' : 'Без НДС:';
  ['bv2-shipments-calc-label','bv2-storage-calc-label','bv2-returns-calc-label','bv2-additional-calc-label'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = calcLabelText;
  });
  if (vatRow) vatRow.style.display = noVatMode ? 'none' : '';
}

function switchBillingFormat(fmt) {
  const newSection = document.getElementById('billing-section-new');
  const oldSection = document.getElementById('billing-section-old');
  if (!newSection || !oldSection) return;

  const showNew = (fmt === 'new' || fmt === 'new-no-vat');
  newSection.style.display = showNew ? 'block' : 'none';
  oldSection.style.display = showNew ? 'none' : 'block';

  updateBillingInputLabels();
  calcBillingTotalsV2();
}

function initBillingForm() {
  // Format switcher
  const fmtSelect = document.getElementById('billing-format');
  if (fmtSelect) {
    fmtSelect.addEventListener('change', () => switchBillingFormat(fmtSelect.value));
    switchBillingFormat(fmtSelect.value || 'new');
  }

  // Live total calculation – old format
  ['p1-shipments','p1-storage','p1-returns','p1-extra','p1-penalties'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', () => calcBillingTotals('p1'));
  });
  ['p2-shipments','p2-storage','p2-returns','p2-extra','p2-penalties'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', () => calcBillingTotals('p2'));
  });

  // Live total calculation – new format
  [
    'bv2-shipments-with-vat', 'bv2-storage-with-vat',
    'bv2-returns-pickup-with-vat', 'bv2-additional-with-vat', 'bv2-penalties',
  ].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', calcBillingTotalsV2);
  });

  // Load existing billing when filters are all set
  const loadBtn = document.getElementById('billing-load-btn');
  if (loadBtn) loadBtn.addEventListener('click', loadBillingEntry);

  // Save billing
  const saveBtn = document.getElementById('billing-save-btn');
  if (saveBtn) saveBtn.addEventListener('click', saveBilling);

  // Mark payment – dependent dropdowns: direction → client → deal
  initDependentDealDropdowns('payment-direction-select', 'payment-client-select', 'payment-deal-select');

  // Mark payment
  const markBtn = document.getElementById('payment-mark-btn');
  if (markBtn) markBtn.addEventListener('click', markPayment);
}

async function loadBillingEntry() {
  const warehouse = document.getElementById('billing-warehouse')?.value;
  const client = document.getElementById('billing-client-select')?.value?.trim();
  const month = document.getElementById('billing-month')?.value || '';
  const period = document.getElementById('billing-half')?.value || '';
  const statusEl = document.getElementById('billing-search-status');

  if (!warehouse || !client) {
    showToast('Выберите склад и клиента', 'error');
    return;
  }

  if (statusEl) { statusEl.style.display = 'block'; statusEl.textContent = 'Поиск...'; }

  try {
    // Use SQL-first /billing/v2/search when enriched settings provide numeric IDs
    const warehouseId = parseInt(warehouse, 10);
    const clientId = parseInt(client, 10);
    const useV2 = state.enrichedSettings && Number.isFinite(warehouseId) && warehouseId > 0
                  && Number.isFinite(clientId) && clientId > 0;

    let url;
    if (useV2) {
      url = `/billing/v2/search?warehouse_id=${warehouseId}&client_id=${clientId}`;
      if (month) url += `&month=${encodeURIComponent(month)}`;
      if (period) url += `&period=${encodeURIComponent(period)}`;
    } else {
      // Legacy fallback for text-based warehouse/client values
      const role = localStorage.getItem('user_role') || '';
      url = `/billing/search?warehouse=${encodeURIComponent(warehouse)}&client=${encodeURIComponent(client)}`;
      if (month) url += `&month=${encodeURIComponent(month)}`;
      if (period) url += `&period=${encodeURIComponent(period)}`;
      const result = await apiFetch(url, { headers: { 'X-User-Role': role } });
      if (result.found) {
        preloadBillingForm(result);
        if (statusEl) { statusEl.textContent = '✅ Запись найдена и загружена.'; }
        showToast('Данные billing загружены', 'success');
      } else {
        if (statusEl) { statusEl.textContent = 'ℹ️ Запись не найдена. Форма очищена для новой записи.'; }
        clearBillingForm();
        showToast('Новая запись — введите данные', 'default');
      }
      return;
    }

    const result = await apiFetch(url);

    if (result.found) {
      preloadBillingForm(result);
      if (statusEl) { statusEl.textContent = '✅ Запись найдена и загружена.'; }
      showToast('Данные billing загружены', 'success');
    } else {
      if (statusEl) { statusEl.textContent = 'ℹ️ Запись не найдена. Форма очищена для новой записи.'; }
      clearBillingForm();
      showToast('Новая запись — введите данные', 'default');
    }
  } catch (err) {
    if (statusEl) { statusEl.textContent = `Ошибка: ${getErrorMessage(err)}`; }
    showToast(`Ошибка поиска: ${getErrorMessage(err)}`, 'error');
  }
}

function preloadBillingForm(data) {
  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el && val !== undefined && val !== null && val !== '') el.value = val;
  };
  const fmt = document.getElementById('billing-format')?.value || 'new';
  if (fmt === 'new' || fmt === 'new-no-vat') {
    setVal('bv2-shipments-with-vat', data.shipments_with_vat);
    setVal('bv2-units', data.units_count);
    setVal('bv2-storage-with-vat', data.storage_with_vat);
    setVal('bv2-pallets', data.pallets_count);
    setVal('bv2-returns-pickup-with-vat', data.returns_pickup_with_vat);
    setVal('bv2-returns-trips', data.returns_trips_count);
    setVal('bv2-additional-with-vat', data.additional_services_with_vat);
    setVal('bv2-penalties', data.penalties);
    setVal('bv2-payment-status', data.payment_status);
    setVal('bv2-payment-amount', data.payment_amount);
    setVal('bv2-payment-date', data.payment_date);
    calcBillingTotalsV2();
  } else {
    setVal('p1-shipments', data.p1_shipments_amount);
    setVal('p1-units', data.p1_units);
    setVal('p1-storage', data.p1_storage_amount);
    setVal('p1-pallets', data.p1_pallets);
    setVal('p1-returns', data.p1_returns_amount);
    setVal('p1-returns-trips', data.p1_returns_trips);
    setVal('p1-extra', data.p1_extra_services);
    setVal('p1-penalties', data.p1_penalties);
    setVal('p2-shipments', data.p2_shipments_amount);
    setVal('p2-units', data.p2_units);
    setVal('p2-storage', data.p2_storage_amount);
    setVal('p2-pallets', data.p2_pallets);
    setVal('p2-returns', data.p2_returns_amount);
    setVal('p2-returns-trips', data.p2_returns_trips);
    setVal('p2-extra', data.p2_extra_services);
    setVal('p2-penalties', data.p2_penalties);
    calcBillingTotals('p1');
    calcBillingTotals('p2');
  }
}

function clearBillingForm() {
  const ids = [
    'bv2-shipments-with-vat','bv2-units','bv2-storage-with-vat','bv2-pallets',
    'bv2-returns-pickup-with-vat','bv2-returns-trips','bv2-additional-with-vat',
    'bv2-penalties','bv2-payment-amount','bv2-payment-date',
    'p1-shipments','p1-units','p1-storage','p1-pallets','p1-returns','p1-returns-trips','p1-extra','p1-penalties',
    'p2-shipments','p2-units','p2-storage','p2-pallets','p2-returns','p2-returns-trips','p2-extra','p2-penalties',
  ];
  ids.forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  const statusEl = document.getElementById('bv2-payment-status');
  if (statusEl) statusEl.value = '';
  calcBillingTotalsV2();
  calcBillingTotals('p1');
  calcBillingTotals('p2');
}

async function saveBilling() {
  const warehouseVal = document.getElementById('billing-warehouse')?.value;
  const clientVal = document.getElementById('billing-client-select')?.value?.trim();
  const fmt = document.getElementById('billing-format')?.value || 'new';

  if (!warehouseVal || !clientVal) {
    showToast('Укажите склад и клиента', 'error');
    return;
  }

  const month = document.getElementById('billing-month')?.value || null;
  const half = document.getElementById('billing-half')?.value || null;

  if (!month) {
    showToast('Укажите месяц', 'error');
    return;
  }
  // Send month and period as separate fields.
  // month is validated non-empty above; period (half) is optional.

  const pVal = (id) => {
    const v = document.getElementById(id)?.value;
    return v ? parseFloat(v) : null;
  };

  // Use /billing/v2/upsert when enriched settings provide warehouse and client IDs.
  const warehouseId = parseInt(warehouseVal, 10);
  const clientId = parseInt(clientVal, 10);
  const useV2 = state.enrichedSettings && !isNaN(warehouseId) && !isNaN(clientId);

  if (useV2 && (fmt === 'new' || fmt === 'new-no-vat')) {
    // SQL-function path: /billing/v2/upsert
    // For 'new' format: entered values are with-VAT → send to *_with_vat fields.
    // For 'new-no-vat' format: entered values are without-VAT → send to *_without_vat fields.
    // Note: the HTML input IDs use the "-with-vat" suffix as a legacy naming convention;
    // updateBillingInputLabels() changes the visible labels dynamically based on the format.
    const isNoVat = (fmt === 'new-no-vat');
    const amtVal = (id) => pVal(id); // amount entered by user; VAT direction depends on isNoVat
    const body = {
      client_id: clientId,
      warehouse_id: warehouseId,
      month,
      period: half || undefined,
      shipments_with_vat:              isNoVat ? null : amtVal('bv2-shipments-with-vat'),
      shipments_without_vat:           isNoVat ? amtVal('bv2-shipments-with-vat') : null,
      units_count:                     pVal('bv2-units') != null ? (parseInt(pVal('bv2-units')) || null) : null,
      storage_with_vat:                isNoVat ? null : amtVal('bv2-storage-with-vat'),
      storage_without_vat:             isNoVat ? amtVal('bv2-storage-with-vat') : null,
      pallets_count:                   pVal('bv2-pallets') != null ? (parseInt(pVal('bv2-pallets')) || null) : null,
      returns_pickup_with_vat:         isNoVat ? null : amtVal('bv2-returns-pickup-with-vat'),
      returns_pickup_without_vat:      isNoVat ? amtVal('bv2-returns-pickup-with-vat') : null,
      returns_trips_count:             pVal('bv2-returns-trips') != null ? (parseInt(pVal('bv2-returns-trips')) || null) : null,
      additional_services_with_vat:    isNoVat ? null : amtVal('bv2-additional-with-vat'),
      additional_services_without_vat: isNoVat ? amtVal('bv2-additional-with-vat') : null,
      penalties:                       pVal('bv2-penalties'),
    };
    Object.keys(body).forEach(k => body[k] == null && delete body[k]);
    console.log('[billing] v2/upsert payload:', JSON.stringify(body));
    try {
      await apiFetch('/billing/v2/upsert', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      showToast('Billing сохранён!', 'success');
    } catch (err) {
      showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
    }
    return;
  }

  // Legacy path: /billing/{warehouse} (used when warehouse/client have text values
  // or when the old p1/p2 format is selected)
  const warehouse = warehouseVal;
  const clientName = clientVal;
  let body;

  if (fmt === 'new' || fmt === 'new-no-vat') {
    body = {
      client: clientName,
      month: month || undefined,
      period: half || undefined,
      input_mode: fmt === 'new-no-vat' ? BILLING_INPUT_MODE_WITHOUT_VAT : BILLING_INPUT_MODE_WITH_VAT,
      shipments_with_vat:           pVal('bv2-shipments-with-vat'),
      units_count:                  pVal('bv2-units') != null ? parseInt(pVal('bv2-units')) : null,
      storage_with_vat:             pVal('bv2-storage-with-vat'),
      pallets_count:                pVal('bv2-pallets') != null ? parseInt(pVal('bv2-pallets')) : null,
      returns_pickup_with_vat:      pVal('bv2-returns-pickup-with-vat'),
      returns_trips_count:          pVal('bv2-returns-trips') != null ? parseInt(pVal('bv2-returns-trips')) : null,
      additional_services_with_vat: pVal('bv2-additional-with-vat'),
      penalties:                    pVal('bv2-penalties'),
      payment_status:               document.getElementById('bv2-payment-status')?.value || null,
      payment_amount:               pVal('bv2-payment-amount'),
      payment_date:                 document.getElementById('bv2-payment-date')?.value || null,
    };
    Object.keys(body).forEach(k => body[k] == null && delete body[k]);
  } else {
    body = {
      client_name: clientName,
      p1: {
        shipments_amount:  pVal('p1-shipments'),
        units:             pVal('p1-units'),
        storage_amount:    pVal('p1-storage'),
        pallets:           pVal('p1-pallets'),
        returns_amount:    pVal('p1-returns'),
        returns_trips:     pVal('p1-returns-trips'),
        extra_services:    pVal('p1-extra'),
        penalties:         pVal('p1-penalties'),
      },
      p2: {
        shipments_amount:  pVal('p2-shipments'),
        units:             pVal('p2-units'),
        storage_amount:    pVal('p2-storage'),
        pallets:           pVal('p2-pallets'),
        returns_amount:    pVal('p2-returns'),
        returns_trips:     pVal('p2-returns-trips'),
        extra_services:    pVal('p2-extra'),
        penalties:         pVal('p2-penalties'),
      },
    };
  }

  try {
    // DEPRECATED: legacy billing endpoint. Use /billing/v2/upsert when possible.
    const role = localStorage.getItem('user_role') || '';
    await apiFetch(`/billing/${warehouse}`, {
      method: 'POST',
      headers: { 'X-User-Role': role },
      body: JSON.stringify(body),
    });
    showToast('Billing сохранён!', 'success');
  } catch (err) {
    showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
  }
}

async function markPayment() {
  // Read deal_id from dropdown (preferred) or fall back to the legacy text input
  const dealId = document.getElementById('payment-deal-select')?.value?.trim()
              || document.getElementById('payment-deal-id')?.value?.trim();
  const amount = parseFloat(document.getElementById('payment-amount')?.value || 0);

  if (!dealId) { showToast('Выберите сделку', 'error'); return; }
  if (!amount || amount <= 0) { showToast('Укажите сумму оплаты', 'error'); return; }

  try {
    const result = await apiFetch('/billing/v2/payment/mark', {
      method: 'POST',
      body: JSON.stringify({ deal_id: dealId, payment_amount: amount }),
    });
    showToast(`Оплата ${formatCurrency(amount)} отмечена. Остаток: ${formatCurrency(result.remaining_amount)}`, 'success');
    const dealSelectEl = document.getElementById('payment-deal-select');
    if (dealSelectEl) dealSelectEl.value = '';
    const dealIdEl = document.getElementById('payment-deal-id');
    if (dealIdEl) dealIdEl.value = '';
    document.getElementById('payment-amount').value = '';
  } catch (err) {
    showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
  }
}

// ==========================================
// EXPENSES FORM
// ==========================================
const EXPENSE_CATS_L2 = {
  'логистика': ['Забор возвратов', 'Отвоз FBO', 'Отвоз FBS', 'Другое'],
  'наёмный персонал': ['Погрузочно-разгрузочные работы', 'Упаковка товара', 'Другое'],
  'расходники': ['Упаковочный материал', 'Паллеты', 'Короба', 'Пломбы'],
  'другое': [],
};

// Maps populated from enriched settings: L1 numeric ID → [{id, name}] sub-categories
const EXPENSE_CATS_L2_BY_ID = {};
// Name→ID lookup maps for payload construction
const EXPENSE_CAT_L1_NAME_TO_ID = {};
const EXPENSE_CAT_L2_NAME_TO_ID = {};
// Reverse ID→name maps for O(1) name resolution (populated alongside NAME_TO_ID maps)
const EXPENSE_CAT_L1_ID_TO_NAME = {};
const EXPENSE_CAT_L2_ID_TO_NAME = {};

const COMMENT_REQUIRED_L2 = new Set(['другое', 'упаковочный материал']);

/**
 * Resolve L1 category name from its dropdown value (may be numeric ID or name string).
 */
function _getCat1Name(cat1Val) {
  if (EXPENSE_CAT_L1_ID_TO_NAME[cat1Val] !== undefined) {
    return EXPENSE_CAT_L1_ID_TO_NAME[cat1Val];
  }
  return (cat1Val || '').toLowerCase();
}

/**
 * Resolve L2 category name from its dropdown value (may be numeric ID or name string).
 */
function _getCat2Name(cat2Val) {
  if (!cat2Val) return '';
  if (EXPENSE_CAT_L2_ID_TO_NAME[cat2Val] !== undefined) {
    return EXPENSE_CAT_L2_ID_TO_NAME[cat2Val];
  }
  return cat2Val.toLowerCase();
}

/**
 * Resolve category level IDs for expense payload.
 * Returns {cat1Id, cat2Id} where values may be undefined if no ID is available.
 */
function _resolveCatIds(cat1Val, cat2Val) {
  // If enriched settings are loaded, cat values are numeric IDs
  const hasEnrichedCats = Object.keys(EXPENSE_CATS_L2_BY_ID).length > 0;
  let cat1Id, cat2Id;
  if (hasEnrichedCats) {
    cat1Id = Number(cat1Val) || undefined;
    cat2Id = cat2Val ? (Number(cat2Val) || undefined) : undefined;
  } else {
    // Fallback: look up IDs from names
    const cat1Name = _getCat1Name(cat1Val);
    const cat2Name = _getCat2Name(cat2Val);
    cat1Id = EXPENSE_CAT_L1_NAME_TO_ID[cat1Name] || undefined;
    cat2Id = cat2Val ? (EXPENSE_CAT_L2_NAME_TO_ID[cat2Name] || undefined) : undefined;
  }
  return { cat1Id, cat2Id };
}

function updateExpenseCat2(cat1Val, cat2SelectId, cat2FieldId) {
  const cat2Select = document.getElementById(cat2SelectId);
  const cat2Field = document.getElementById(cat2FieldId);
  if (!cat2Select || !cat2Field) return;

  // Prefer ID-keyed lookup (from enriched settings); fall back to name-based static map
  const subCats = EXPENSE_CATS_L2_BY_ID[cat1Val];
  if (subCats !== undefined) {
    // enriched path: sub-categories are {id, name} objects
    cat2Select.innerHTML = '<option value="">Выберите...</option>';
    subCats.forEach(sc => {
      const o = document.createElement('option');
      o.value = String(sc.id);
      o.textContent = sc.name;
      cat2Select.appendChild(o);
    });
    cat2Field.style.display = (subCats.length > 0) ? 'block' : 'none';
  } else {
    // fallback path: use name-based static EXPENSE_CATS_L2
    const cat1Name = _getCat1Name(cat1Val);
    const options = EXPENSE_CATS_L2[cat1Name] || [];
    cat2Select.innerHTML = '<option value="">Выберите...</option>';
    options.forEach(opt => {
      const o = document.createElement('option');
      o.value = opt.toLowerCase();
      o.textContent = opt;
      cat2Select.appendChild(o);
    });
    cat2Field.style.display = (options.length > 0) ? 'block' : 'none';
  }
}

function updateExpenseCommentVisibility(cat1Val, cat2Val, commentFieldId, requiredMarkId) {
  const commentField = document.getElementById(commentFieldId);
  const requiredMark = document.getElementById(requiredMarkId);
  if (!commentField) return;

  const cat1Name = _getCat1Name(cat1Val);
  const cat2Name = _getCat2Name(cat2Val);
  const cat1Required = (cat1Name === 'другое');
  const cat2Required = cat2Val && COMMENT_REQUIRED_L2.has(cat2Name);
  const needsComment = cat1Required || cat2Required;

  commentField.style.display = (needsComment || cat1Name === 'другое') ? 'block' : 'none';
  if (requiredMark) requiredMark.style.display = needsComment ? 'inline' : 'none';
}

function initExpensesForm() {
  // Category level 1 change → populate level 2
  const cat1El = document.getElementById('expense-cat1');
  const cat2El = document.getElementById('expense-cat2');
  const commentInput = document.getElementById('expense-comment');

  if (cat1El) {
    cat1El.addEventListener('change', () => {
      const cat1Val = cat1El.value;
      updateExpenseCat2(cat1Val, 'expense-cat2', 'expense-cat2-field');
      updateExpenseCommentVisibility(cat1Val, '', 'expense-comment-field', 'expense-comment-required');
      if (cat2El) cat2El.value = '';
      if (commentInput) commentInput.value = '';
    });
  }
  if (cat2El) {
    cat2El.addEventListener('change', () => {
      const cat1Val = cat1El?.value || '';
      const cat2Val = cat2El.value;
      updateExpenseCommentVisibility(cat1Val, cat2Val, 'expense-comment-field', 'expense-comment-required');
    });
  }

  // Live VAT calc (supports both VAT rate and explicit VAT amount)
  const amountEl = document.getElementById('expense-amount');
  const vatRateEl = document.getElementById('expense-vat-rate');
  const vatEl = document.getElementById('expense-vat');
  const calcNoVatEl = document.getElementById('expense-calc-no-vat');
  const calcVatAmountEl = document.getElementById('expense-calc-vat-amount');

  const updateCalc = () => {
    const amount = parseFloat(amountEl?.value || 0) || 0;
    const vatRate = parseFloat(vatRateEl?.value || 0) || 0;

    let vatAmount;
    let amountNoVat;

    if (vatRate) {
      amountNoVat = amount / (1 + vatRate);
      vatAmount = amount - amountNoVat;
    } else {
      vatAmount = parseFloat(vatEl?.value || 0) || 0;
      amountNoVat = amount - vatAmount;
    }

    if (calcVatAmountEl) calcVatAmountEl.textContent = `${vatAmount.toFixed(2)} ₽`;
    if (calcNoVatEl) calcNoVatEl.textContent = `${amountNoVat.toFixed(2)} ₽`;
  };

  if (amountEl) amountEl.addEventListener('input', updateCalc);
  if (vatRateEl) vatRateEl.addEventListener('input', updateCalc);
  if (vatEl) vatEl.addEventListener('input', updateCalc);

  // Dependent deal dropdowns: direction → client → deal
  initDependentDealDropdowns('expense-direction-select', 'expense-client-select', 'expense-deal-select');

  // Save single expense
  const saveBtn = document.getElementById('expense-save-btn');
  if (saveBtn) saveBtn.addEventListener('click', saveExpense);

  // Load expenses list
  const loadBtn = document.getElementById('load-expenses-btn');
  if (loadBtn) loadBtn.addEventListener('click', loadExpenses);

  // Bulk entry
  const bulkAddBtn = document.getElementById('bulk-add-row-btn');
  if (bulkAddBtn) bulkAddBtn.addEventListener('click', addBulkRow);

  const bulkSaveBtn = document.getElementById('bulk-save-btn');
  if (bulkSaveBtn) bulkSaveBtn.addEventListener('click', saveBulkExpenses);
}

let _bulkRowIndex = 0;

function addBulkRow() {
  const container = document.getElementById('bulk-rows-container');
  const saveActionsEl = document.getElementById('bulk-save-row');
  if (!container) return;

  const idx = _bulkRowIndex++;
  const row = document.createElement('div');
  row.className = 'bulk-expense-row card';
  row.id = `bulk-row-${idx}`;
  row.style.cssText = 'position:relative;padding:12px;margin-bottom:8px;';
  row.innerHTML = `
    <button class="btn btn-sm" style="position:absolute;top:8px;right:8px;color:var(--color-danger);" onclick="removeBulkRow(${idx})">✕</button>
    <div class="field-group">
      <div class="field-row">
        <div class="field"><label>Категория 1 *</label>
          <div class="select-wrapper"><select id="bulk-cat1-${idx}" class="bulk-cat1">
            <option value="">Выбрать...</option>
            <option value="логистика">Логистика</option>
            <option value="наёмный персонал">Наёмный персонал</option>
            <option value="расходники">Расходники</option>
            <option value="другое">Другое</option>
          </select></div>
        </div>
        <div class="field" id="bulk-cat2-field-${idx}" style="display:none;"><label>Категория 2</label>
          <div class="select-wrapper"><select id="bulk-cat2-${idx}"></select></div>
        </div>
      </div>
      <div class="field" id="bulk-comment-field-${idx}" style="display:none;"><label>Комментарий <span id="bulk-comment-req-${idx}" style="display:none;color:var(--color-danger);">*</span></label>
        <input type="text" id="bulk-comment-${idx}" placeholder="Комментарий..." />
      </div>
      <div class="field-row">
        <div class="field"><label>Сумма с НДС, ₽ *</label><input type="number" id="bulk-amount-${idx}" placeholder="0.00" min="0" step="0.01" /></div>
        <div class="field"><label>Ставка НДС</label><input type="number" id="bulk-vat-rate-${idx}" placeholder="0.20" min="0" max="1" step="0.01" /></div>
      </div>
      <div class="field"><label>ID сделки</label><input type="text" id="bulk-deal-id-${idx}" placeholder="(необязательно)" /></div>
    </div>
  `;
  container.appendChild(row);

  // Populate bulk-cat1 from loaded settings categories if available
  const bulkCat1El = document.getElementById(`bulk-cat1-${idx}`);
  const loadedCats = state.settings && state.settings.expense_categories;
  if (bulkCat1El && loadedCats && loadedCats.length > 0) {
    bulkCat1El.innerHTML = '<option value="">Выбрать...</option>';
    loadedCats.forEach(cat => {
      const o = document.createElement('option');
      // Use numeric ID as value when available (matches enriched settings); fall back to name
      o.value = (cat.id != null) ? String(cat.id) : cat.name;
      o.textContent = cat.name;
      bulkCat1El.appendChild(o);
    });
  }

  // Hook category change
  const cat1El = document.getElementById(`bulk-cat1-${idx}`);
  if (cat1El) {
    cat1El.addEventListener('change', () => {
      const cat1Val = cat1El.value;
      updateExpenseCat2(cat1Val, `bulk-cat2-${idx}`, `bulk-cat2-field-${idx}`);
      updateExpenseCommentVisibility(cat1Val, '', `bulk-comment-field-${idx}`, `bulk-comment-req-${idx}`);
    });
  }
  const cat2El = document.getElementById(`bulk-cat2-${idx}`);
  if (cat2El) {
    cat2El.addEventListener('change', () => {
      const cat1Val = cat1El?.value || '';
      updateExpenseCommentVisibility(cat1Val, cat2El.value, `bulk-comment-field-${idx}`, `bulk-comment-req-${idx}`);
    });
  }

  if (saveActionsEl) saveActionsEl.style.display = 'block';
}

function removeBulkRow(idx) {
  const row = document.getElementById(`bulk-row-${idx}`);
  if (row) row.remove();
  const container = document.getElementById('bulk-rows-container');
  const saveActionsEl = document.getElementById('bulk-save-row');
  if (container && saveActionsEl) {
    saveActionsEl.style.display = container.children.length > 0 ? 'block' : 'none';
  }
}

async function saveBulkExpenses() {
  const container = document.getElementById('bulk-rows-container');
  if (!container || container.children.length === 0) {
    showToast('Нет строк для сохранения', 'error');
    return;
  }

  const rows = [];
  for (const child of container.children) {
    const idxMatch = child.id.match(/bulk-row-(\d+)/);
    if (!idxMatch) continue;
    const idx = idxMatch[1];

    const cat1 = document.getElementById(`bulk-cat1-${idx}`)?.value?.trim() || '';
    const cat2 = document.getElementById(`bulk-cat2-${idx}`)?.value?.trim() || '';
    const comment = document.getElementById(`bulk-comment-${idx}`)?.value?.trim() || '';
    const amount = parseFloat(document.getElementById(`bulk-amount-${idx}`)?.value || 0) || 0;
    const vatRate = parseFloat(document.getElementById(`bulk-vat-rate-${idx}`)?.value || 0) || 0;
    const dealId = document.getElementById(`bulk-deal-id-${idx}`)?.value?.trim() || '';

    if (!cat1) { showToast(`Строка ${parseInt(idx)+1}: выберите категорию 1`, 'error'); return; }
    if (!amount) { showToast(`Строка ${parseInt(idx)+1}: укажите сумму`, 'error'); return; }

    const { cat1Id, cat2Id } = _resolveCatIds(cat1, cat2);
    rows.push({
      category_level_1_id: cat1Id || undefined,
      category_level_2_id: cat2Id || undefined,
      category_level_1: _getCat1Name(cat1) || undefined,
      category_level_2: cat2 ? (_getCat2Name(cat2) || undefined) : undefined,
      comment: comment || undefined,
      amount_without_vat: vatRate ? amount / (1 + vatRate) : amount,
      vat_rate: vatRate || undefined,
      deal_id: dealId ? (Number.isFinite(parseInt(dealId, 10)) ? parseInt(dealId, 10) : undefined) : undefined,
    });
  }

  if (rows.length === 0) { showToast('Нет строк для сохранения', 'error'); return; }

  try {
    // Send each expense row individually to /expenses/v2/create.
    let saved = 0;
    for (const row of rows) {
      await apiFetch('/expenses/v2/create', {
        method: 'POST',
        body: JSON.stringify(row),
      });
      saved++;
    }
    showToast(`Сохранено ${saved} расходов!`, 'success');
    container.innerHTML = '';
    const saveActionsEl = document.getElementById('bulk-save-row');
    if (saveActionsEl) saveActionsEl.style.display = 'none';
    _bulkRowIndex = 0;
  } catch (err) {
    showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
  }
}

async function saveExpense() {
  const cat1 = document.getElementById('expense-cat1')?.value?.trim() || '';
  const cat2 = document.getElementById('expense-cat2')?.value?.trim() || '';
  const comment = document.getElementById('expense-comment')?.value?.trim() || '';
  const amount = parseFloat(document.getElementById('expense-amount')?.value || 0);

  if (!cat1) { showToast('Выберите категорию', 'error'); return; }
  if (!amount || amount <= 0) { showToast('Укажите сумму расхода', 'error'); return; }

  // Validate comment requirement (resolve names for ID-based values)
  const cat1Name = _getCat1Name(cat1);
  const cat2Name = _getCat2Name(cat2);
  const cat1Required = (cat1Name === 'другое');
  const cat2Required = cat2 && COMMENT_REQUIRED_L2.has(cat2Name);
  if ((cat1Required || cat2Required) && !comment) {
    showToast('Комментарий обязателен для выбранной категории', 'error');
    return;
  }

  // Read deal_id from dropdown (preferred) or fall back to legacy text input
  const dealId = document.getElementById('expense-deal-select')?.value?.trim()
              || document.getElementById('expense-deal-id')?.value?.trim()
              || null;
  const vatRate = parseFloat(document.getElementById('expense-vat-rate')?.value || 0) || 0;
  const vat = parseFloat(document.getElementById('expense-vat')?.value || 0) || 0;

  // Resolve category IDs: prefer numeric ID from enriched settings lookup
  const { cat1Id, cat2Id } = _resolveCatIds(cat1, cat2);

  const payload = {
    category_level_1_id: cat1Id || undefined,
    category_level_2_id: cat2Id || undefined,
    category_level_1: cat1Name || undefined,
    category_level_2: cat2Name || undefined,
    comment: comment || undefined,
    deal_id: dealId ? (Number.isFinite(parseInt(dealId, 10)) ? parseInt(dealId, 10) : undefined) : undefined,
    amount_without_vat: vatRate ? amount / (1 + vatRate) : amount - vat,
    vat_rate: vatRate || undefined,
  };

  try {
    console.log('[expenses] saving single expense to /expenses/v2/create');
    await apiFetch('/expenses/v2/create', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    showToast('Расход добавлен!', 'success');
    // Clear form
    ['expense-deal-id', 'expense-amount', 'expense-vat-rate', 'expense-vat', 'expense-comment'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    const cat1El = document.getElementById('expense-cat1');
    if (cat1El) cat1El.value = '';
    const cat2El = document.getElementById('expense-cat2');
    if (cat2El) cat2El.value = '';
    document.getElementById('expense-cat2-field')?.style && (document.getElementById('expense-cat2-field').style.display = 'none');
    document.getElementById('expense-comment-field')?.style && (document.getElementById('expense-comment-field').style.display = 'none');
    const calcNoVatEl = document.getElementById('expense-calc-no-vat');
    const calcVatAmountEl = document.getElementById('expense-calc-vat-amount');
    if (calcNoVatEl) calcNoVatEl.textContent = '0.00 ₽';
    if (calcVatAmountEl) calcVatAmountEl.textContent = '0.00 ₽';
  } catch (err) {
    showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
  }
}

async function loadExpenses() {
  const loadingEl = document.getElementById('expenses-loading');
  const listEl = document.getElementById('expenses-list');
  const emptyEl = document.getElementById('expenses-empty');

  if (loadingEl) loadingEl.style.display = 'flex';
  if (listEl) listEl.innerHTML = '';
  if (emptyEl) emptyEl.style.display = 'none';

  try {
    console.log('[expenses] loading /expenses/v2');
    const data = await apiFetch('/expenses/v2');

    if (loadingEl) loadingEl.style.display = 'none';

    if (!data || data.length === 0) {
      if (emptyEl) emptyEl.style.display = 'flex';
      return;
    }

    if (listEl) {
      listEl.innerHTML = data.map(e => {
        const cat1 = e.category_level_1 || '';
        const cat2 = e.category_level_2 || '';
        const category = cat1 ? (cat2 ? `${cat1} / ${cat2}` : cat1) : (e.category || e.expense_type || '—');
        const comment = e.comment || '';
        const amountWithVat = parseFloat(e.amount_with_vat || e.amount) || 0;
        const amountNoVat = parseFloat(e.amount_without_vat) || 0;
        const vatAmount = parseFloat(e.vat_amount || e.vat) || 0;
        const date = e.date || e.created_at || '';
        return `
        <div class="expense-row">
          <div class="expense-row-header">
            <span class="expense-type-badge">${escHtml(category)}</span>
            <span class="expense-amount">${formatCurrency(amountWithVat)}</span>
          </div>
          ${comment ? `<div class="expense-row-comment" style="font-size:12px;color:var(--color-text-secondary);margin-top:2px;">${escHtml(comment)}</div>` : ''}
          ${amountNoVat ? `<div class="expense-row-vat"><span>Без НДС: ${formatCurrency(amountNoVat)}</span><span>НДС: ${formatCurrency(vatAmount)}</span></div>` : ''}
          <div class="expense-row-meta">
            ${e.deal_id ? `<span>Сделка: ${escHtml(e.deal_id)}</span>` : ''}
            ${date ? `<span>${escHtml(date)}</span>` : ''}
          </div>
        </div>
      `}).join('');
    }
  } catch (err) {
    if (loadingEl) loadingEl.style.display = 'none';
    showToast(`Ошибка загрузки расходов: ${getErrorMessage(err)}`, 'error');
  }
}

// ==========================================
// REPORTS
// ==========================================
function initReportsHandlers() {
  document.querySelectorAll('[data-report]').forEach(btn => {
    btn.addEventListener('click', () => {
      const reportType = btn.dataset.report;
      const fmt = btn.dataset.fmt;
      downloadReport(reportType, fmt);
    });
  });
}

async function downloadReport(reportType, fmt) {
  let url;

  if (reportType === 'warehouse') {
    const warehouse = document.getElementById('report-warehouse')?.value || 'msk';
    url = `/reports/warehouse/${warehouse}?fmt=${fmt}`;
  } else if (reportType === 'billing-by-month') {
    const month = document.getElementById('report-month')?.value || '';
    if (!month) { showToast('Выберите месяц для отчёта', 'error'); return; }
    url = `/reports/billing-by-month?month=${encodeURIComponent(month)}&fmt=${fmt}`;
  } else if (reportType === 'billing-by-client') {
    // Prefer select dropdown (report-client-select), fall back to legacy text input
    const clientSelectEl = document.getElementById('report-client-select');
    const clientTextEl = document.getElementById('report-client-filter');
    const clientName = (clientSelectEl?.options[clientSelectEl.selectedIndex]?.dataset?.name)
                    || clientSelectEl?.options[clientSelectEl?.selectedIndex]?.textContent?.trim()
                    || clientTextEl?.value?.trim()
                    || '';
    if (!clientName) { showToast('Выберите клиента', 'error'); return; }
    url = `/reports/billing-by-client?client=${encodeURIComponent(clientName)}&fmt=${fmt}`;
  } else {
    url = `/reports/${reportType}?fmt=${fmt}`;
  }

  try {
    const headers = getAuthHeaders();
    const response = await fetch(`${API_BASE}${url}`, { headers });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = objectUrl;
    a.download = `report_${reportType}.${fmt}`;
    a.click();
    URL.revokeObjectURL(objectUrl);
    showToast(`Отчёт скачан (${fmt.toUpperCase()})`, 'success');
  } catch (err) {
    showToast(`Ошибка скачивания: ${getErrorMessage(err)}`, 'error');
  }
}

// ==========================================
// JOURNAL
// ==========================================
function initJournalHandlers() {
  const loadBtn = document.getElementById('load-journal-btn');
  if (loadBtn) loadBtn.addEventListener('click', loadJournal);
}

async function loadJournal() {
  // Guard against concurrent calls (e.g. double-click or duplicate listeners)
  if (state._loadingJournal) return;
  state._loadingJournal = true;

  const loadingEl = document.getElementById('journal-loading');
  const listEl = document.getElementById('journal-list');
  const emptyEl = document.getElementById('journal-empty');

  if (loadingEl) loadingEl.style.display = 'flex';
  if (listEl) listEl.innerHTML = '';
  if (emptyEl) emptyEl.style.display = 'none';

  try {
    console.log('[journal] loading /journal?limit=50');
    const data = await apiFetch('/journal?limit=50');

    if (loadingEl) loadingEl.style.display = 'none';

    if (!data || data.length === 0) {
      if (emptyEl) emptyEl.style.display = 'flex';
      state._loadingJournal = false;
      return;
    }

    if (listEl) {
      listEl.innerHTML = data.map(entry => `
        <div class="journal-row">
          <div class="journal-row-header">
            <span class="journal-action">${escHtml(entry.action || '')}</span>
            <span class="journal-timestamp">${escHtml(entry.timestamp || '')}</span>
          </div>
          <div class="journal-row-meta">
            <span>Пользователь: ${escHtml(entry.user || entry.full_name || entry.telegram_user_id || '—')}</span>
            ${entry.entity ? `<span>Объект: ${escHtml(entry.entity)}</span>` : ''}
            ${entry.entity_id ? `<span>ID: ${escHtml(entry.entity_id)}</span>` : ''}
            ${entry.deal_id ? `<span>Сделка: ${escHtml(entry.deal_id)}</span>` : ''}
          </div>
          ${(entry.details || entry.payload_summary) ? `<div class="journal-details">${escHtml(entry.details || entry.payload_summary)}</div>` : ''}
        </div>
      `).join('');
    }
  } catch (err) {
    if (loadingEl) loadingEl.style.display = 'none';
    showToast(`Ошибка загрузки журнала: ${getErrorMessage(err)}`, 'error');
  } finally {
    state._loadingJournal = false;
  }
}

// ==========================================
// OWNER DASHBOARD
// ==========================================
function initDashboardHandlers() {
  const loadBtn = document.getElementById('load-dashboard-btn');
  if (loadBtn) loadBtn.addEventListener('click', loadOwnerDashboard);

  const applyBtn = document.getElementById('apply-dashboard-filter-btn');
  if (applyBtn) applyBtn.addEventListener('click', loadOwnerDashboard);
}

async function loadOwnerDashboard() {
  // Guard: only load dashboard when authenticated
  if (!localStorage.getItem('user_role')) {
    console.warn('[dashboard] not authenticated, skipping load');
    return;
  }

  const loadingEl = document.getElementById('dashboard-loading');
  const contentEl = document.getElementById('dashboard-content');
  const emptyEl   = document.getElementById('dashboard-empty');

  if (loadingEl) loadingEl.style.display = 'flex';
  if (contentEl) contentEl.style.display = 'none';
  if (emptyEl)   emptyEl.style.display   = 'none';

  try {
    const month = document.getElementById('dashboard-month-filter')?.value || '';
    const qs = month ? `?month=${encodeURIComponent(month)}` : '';

    let totalRevWithVat = 0, totalRevNoVat = 0, totalExpenses = 0, totalGross = 0, totalDebt = 0;
    let paidBilling = 0, unpaidBilling = 0;
    const whMap = {};
    const clientMap = {};

    console.log('[dashboard] /dashboard/summary', qs || '(no filter)');
    const rows = await apiFetch(`/dashboard/summary${qs}`);

    if (loadingEl) loadingEl.style.display = 'none';
    if (!rows || rows.length === 0) { if (emptyEl) emptyEl.style.display = 'flex'; return; }

    rows.forEach(r => {
      totalRevWithVat  += parseFloat(r.total_revenue_with_vat  || r.charged_with_vat  || 0);
      totalRevNoVat    += parseFloat(r.total_revenue_without_vat || r.amount_without_vat || 0);
      totalExpenses    += parseFloat(r.total_expenses   || 0);
      totalGross       += parseFloat(r.gross_profit     || 0);
      totalDebt        += parseFloat(r.total_debt       || r.debt || 0);
      paidBilling      += parseInt(r.paid_billing_count  || 0, 10);
      unpaidBilling    += parseInt(r.unpaid_billing_count || 0, 10);

      if (r.warehouse || r.warehouse_code) {
        const wh = r.warehouse || r.warehouse_code;
        if (!whMap[wh]) whMap[wh] = { total_with_vat: 0, paid_count: 0, unpaid_count: 0 };
        whMap[wh].total_with_vat += parseFloat(r.billing_total_with_vat || r.total_with_vat || 0);
        whMap[wh].paid_count     += parseInt(r.paid_count  || 0, 10);
        whMap[wh].unpaid_count   += parseInt(r.unpaid_count || 0, 10);
      }

      if (r.client) {
        clientMap[r.client] = (clientMap[r.client] || 0) + parseFloat(r.total_revenue_with_vat || r.charged_with_vat || 0);
      }
    });

    // KPI cards
    const kpisEl = document.getElementById('dashboard-kpis');
    if (kpisEl) {
      kpisEl.innerHTML = [
        { label: 'Выручка с НДС',    value: formatCurrency(totalRevWithVat),  icon: '💰' },
        { label: 'Выручка без НДС',  value: formatCurrency(totalRevNoVat),    icon: '💵' },
        { label: 'Расходы',          value: formatCurrency(totalExpenses),     icon: '📉' },
        { label: 'Валовая прибыль',  value: formatCurrency(totalGross),        icon: '📈' },
        { label: 'Долг',             value: formatCurrency(totalDebt),         icon: '⚠️' },
        { label: 'Оплачено (billing)',    value: String(paidBilling),   icon: '✅' },
        { label: 'Не оплачено (billing)', value: String(unpaidBilling), icon: '🔴' },
      ].map(k => `
        <div class="kpi-card">
          <div class="kpi-icon">${k.icon}</div>
          <div class="kpi-label">${escHtml(k.label)}</div>
          <div class="kpi-value">${escHtml(k.value)}</div>
        </div>
      `).join('');
    }

    // Warehouse breakdown
    const whEl = document.getElementById('dashboard-warehouse-list');
    if (whEl && Object.keys(whMap).length > 0) {
      whEl.innerHTML = Object.entries(whMap).map(([wh, info]) => `
        <div class="receivables-row">
          <span class="receivables-label">${escHtml(wh)}</span>
          <span class="receivables-amount">${formatCurrency(info.total_with_vat || 0)}</span>
          <span class="receivables-meta">✅ ${info.paid_count || 0} / 🔴 ${info.unpaid_count || 0}</span>
        </div>
      `).join('');
    }

    // Top clients (sorted by revenue desc, top 10)
    const clientsEl = document.getElementById('dashboard-clients-list');
    if (clientsEl && Object.keys(clientMap).length > 0) {
      const topClients = Object.entries(clientMap)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10);
      clientsEl.innerHTML = topClients.map(([client, revenue], i) => `
        <div class="receivables-row">
          <span class="receivables-rank">#${i + 1}</span>
          <span class="receivables-label">${escHtml(client || '—')}</span>
          <span class="receivables-amount">${formatCurrency(revenue || 0)}</span>
        </div>
      `).join('');
    }

    if (contentEl) contentEl.style.display = 'block';
  } catch (err) {
    if (loadingEl) loadingEl.style.display = 'none';
    if (emptyEl)   emptyEl.style.display   = 'flex';
    showToast(`Ошибка загрузки дашборда: ${getErrorMessage(err)}`, 'error');
  }
}

// ==========================================
// RECEIVABLES / DEBT CONTROL
// ==========================================
function initReceivablesHandlers() {
  const loadBtn = document.getElementById('load-receivables-btn');
  if (loadBtn) loadBtn.addEventListener('click', loadReceivables);

  const applyBtn = document.getElementById('apply-receivables-filter-btn');
  if (applyBtn) applyBtn.addEventListener('click', loadReceivables);

  // Report download buttons inside receivables tab
  document.querySelectorAll('#tab-receivables [data-report]').forEach(btn => {
    btn.addEventListener('click', () => {
      downloadReport(btn.dataset.report, btn.dataset.fmt);
    });
  });
}

async function loadReceivables() {
  const loadingEl = document.getElementById('receivables-loading');
  const contentEl = document.getElementById('receivables-content');
  const emptyEl   = document.getElementById('receivables-empty');

  if (loadingEl) loadingEl.style.display = 'flex';
  if (contentEl) contentEl.style.display = 'none';
  if (emptyEl)   emptyEl.style.display   = 'none';

  try {
    const month = document.getElementById('receivables-month-filter')?.value || '';
    const qs = month ? `?month=${encodeURIComponent(month)}` : '';
    const role = localStorage.getItem('user_role') || '';
    const data = await apiFetch(`/receivables${qs}`, {
      headers: { 'X-User-Role': role },
    });

    if (loadingEl) loadingEl.style.display = 'none';
    if (!data) { if (emptyEl) emptyEl.style.display = 'flex'; return; }

    // Status KPIs
    const statusEl = document.getElementById('receivables-status-kpis');
    if (statusEl && data.status_summary) {
      const s = data.status_summary;
      statusEl.innerHTML = [
        { label: 'Всего долг',       value: formatCurrency(data.total_debt || 0),  icon: '💳' },
        { label: 'Оплачено',         value: String(s.paid || 0),                   icon: '✅' },
        { label: 'Частично',         value: String(s.partial || 0),                icon: '⏳' },
        { label: 'Не оплачено',      value: String(s.unpaid || 0),                 icon: '🔴' },
        { label: 'Просрочено',       value: String(s.overdue || 0),                icon: '⚠️' },
      ].map(k => `
        <div class="kpi-card">
          <div class="kpi-icon">${k.icon}</div>
          <div class="kpi-label">${escHtml(k.label)}</div>
          <div class="kpi-value">${escHtml(k.value)}</div>
        </div>
      `).join('');
    }

    // Debt by client
    const clientEl = document.getElementById('receivables-by-client');
    if (clientEl && data.debt_by_client) {
      const entries = Object.entries(data.debt_by_client);
      if (entries.length === 0) {
        clientEl.innerHTML = '<p style="color:var(--color-text-secondary);font-size:13px;">Нет данных</p>';
      } else {
        clientEl.innerHTML = entries.map(([client, debt]) => `
          <div class="receivables-row">
            <span class="receivables-label">${escHtml(client)}</span>
            <span class="receivables-amount" style="color:${debt > 0 ? 'var(--color-danger, #ef4444)' : 'var(--color-success, #22c55e)'}">${formatCurrency(debt)}</span>
          </div>
        `).join('');
      }
    }

    // Debt by warehouse
    const whEl = document.getElementById('receivables-by-warehouse');
    if (whEl && data.debt_by_warehouse) {
      whEl.innerHTML = Object.entries(data.debt_by_warehouse).map(([wh, debt]) => `
        <div class="receivables-row">
          <span class="receivables-label">${escHtml(wh)}</span>
          <span class="receivables-amount">${formatCurrency(debt)}</span>
        </div>
      `).join('');
    }

    // Debt by month
    const monthEl = document.getElementById('receivables-by-month');
    if (monthEl && data.debt_by_month) {
      const entries = Object.entries(data.debt_by_month);
      if (entries.length === 0) {
        monthEl.innerHTML = '<p style="color:var(--color-text-secondary);font-size:13px;">Нет данных</p>';
      } else {
        monthEl.innerHTML = entries.map(([m, debt]) => `
          <div class="receivables-row">
            <span class="receivables-label">${escHtml(m)}</span>
            <span class="receivables-amount">${formatCurrency(debt)}</span>
          </div>
        `).join('');
      }
    }

    if (contentEl) contentEl.style.display = 'block';
  } catch (err) {
    if (loadingEl) loadingEl.style.display = 'none';
    if (emptyEl)   emptyEl.style.display   = 'flex';
    showToast(`Ошибка загрузки задолженности: ${getErrorMessage(err)}`, 'error');
  }
}

// ==========================================
// MONTH CLOSE (admin / operations_director)
// ==========================================

function initMonthClose() {
  const tab = document.getElementById('tab-month-close');
  if (!tab) return;

  // Dry-run archive
  const dryRunBtn = document.getElementById('month-close-dry-run-btn');
  if (dryRunBtn) dryRunBtn.addEventListener('click', () => runMonthArchive(true));

  // Real archive
  const archiveBtn = document.getElementById('month-close-archive-btn');
  if (archiveBtn) archiveBtn.addEventListener('click', () => runMonthArchive(false));

  // Cleanup
  const cleanupBtn = document.getElementById('month-close-cleanup-btn');
  if (cleanupBtn) cleanupBtn.addEventListener('click', runMonthCleanup);

  // Close month
  const closeBtn = document.getElementById('month-close-close-btn');
  if (closeBtn) closeBtn.addEventListener('click', runMonthClose);

  // Load archive batches
  const loadBatchesBtn = document.getElementById('month-close-load-batches-btn');
  if (loadBatchesBtn) loadBatchesBtn.addEventListener('click', loadArchiveBatches);
}

function _getMonthCloseParams() {
  const yearInput = document.getElementById('month-close-year');
  const monthInput = document.getElementById('month-close-month');
  const year = parseInt(yearInput?.value || new Date().getFullYear(), 10);
  const month = parseInt(monthInput?.value || (new Date().getMonth() + 1), 10);
  return { year, month };
}

function _showMonthCloseResult(resultEl, data, error = null) {
  if (!resultEl) return;
  if (error) {
    resultEl.innerHTML = `<div class="month-close-error">❌ ${escHtml(String(error))}</div>`;
    return;
  }
  if (!data || data.length === 0) {
    resultEl.innerHTML = '<div class="month-close-ok">✅ Готово (нет данных для отображения)</div>';
    return;
  }

  // Highlight key summary fields prominently
  const summaryKeys = ['archive_batch_id', 'status', 'total_deals', 'archived_count', 'dry_run'];
  const summaryItems = [];
  const detailRows = data.map(row => {
    return Object.entries(row).map(([k, v]) => {
      const rowClass = summaryKeys.includes(k)
        ? 'month-close-row month-close-highlight'
        : 'month-close-row';
      return `<div class="${rowClass}"><span class="month-close-key">${escHtml(k)}</span><span class="month-close-val">${escHtml(String(v ?? ''))}</span></div>`;
    }).join('');
  }).join('<hr>');

  // Show count summary line if recognisable fields are present
  const first = data[0] || {};
  if (first.dry_run !== undefined) {
    const count = first.total_deals ?? first.archived_count ?? data.length;
    const isDry = first.dry_run === true || first.dry_run === 'true';
    summaryItems.push(`${isDry ? '🔍 Dry-run:' : '📦 Архивировано:'} <b>${escHtml(String(count))}</b> записей`);
  }
  if (first.archive_batch_id !== undefined) {
    summaryItems.push(`📋 Batch ID: <b>${escHtml(String(first.archive_batch_id))}</b>`);
  }

  const summaryHtml = summaryItems.length
    ? `<div class="month-close-summary">${summaryItems.join(' &nbsp;|&nbsp; ')}</div>`
    : '';

  resultEl.innerHTML = `${summaryHtml}<div class="month-close-result">${detailRows}</div>`;
}

async function runMonthArchive(dryRun) {
  const { year, month } = _getMonthCloseParams();
  const monthLabel = `${year}-${String(month).padStart(2, '0')}`;

  if (!dryRun && !confirm(`Архивирование месяца ${monthLabel}.\nЭта операция переносит сделки в архив.\nПродолжить?`)) {
    return;
  }

  console.log(`[month-close] runMonthArchive dryRun=${dryRun}`, { year, month });
  const resultEl = document.getElementById('month-close-result');
  if (resultEl) resultEl.innerHTML = '<div class="loading-spinner"></div>';
  try {
    const data = await apiFetch('/month/archive', {
      method: 'POST',
      body: JSON.stringify({ year, month, dry_run: dryRun }),
    });
    _showMonthCloseResult(resultEl, data);
    showToast(dryRun ? 'Dry-run завершён' : 'Архивирование завершено', 'success');
    // After a real archive, refresh the archive batches list automatically
    if (!dryRun) {
      setTimeout(loadArchiveBatches, 500);
    }
  } catch (err) {
    _showMonthCloseResult(resultEl, null, getErrorMessage(err));
    showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
  }
}

async function runMonthCleanup() {
  const { year, month } = _getMonthCloseParams();
  const monthLabel = `${year}-${String(month).padStart(2, '0')}`;

  if (!confirm(`Очистка месяца ${monthLabel} — это необратимая операция.\nПродолжить?`)) {
    return;
  }

  console.log('[month-close] runMonthCleanup', { year, month });
  const resultEl = document.getElementById('month-close-result');
  if (resultEl) resultEl.innerHTML = '<div class="loading-spinner"></div>';
  try {
    const data = await apiFetch('/month/cleanup', {
      method: 'POST',
      body: JSON.stringify({ year, month }),
    });
    _showMonthCloseResult(resultEl, data);
    showToast('Очистка завершена', 'success');
    // Refresh archive batches after cleanup
    setTimeout(loadArchiveBatches, 500);
  } catch (err) {
    _showMonthCloseResult(resultEl, null, getErrorMessage(err));
    showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
  }
}

async function runMonthClose() {
  const { year, month } = _getMonthCloseParams();
  const monthLabel = `${year}-${String(month).padStart(2, '0')}`;

  if (!confirm(`Закрытие месяца ${monthLabel} — это необратимая операция.\nУбедитесь, что dry-run архивирования прошёл успешно.\nПродолжить?`)) {
    return;
  }

  console.log('[month-close] runMonthClose', { year, month });
  const comment = document.getElementById('month-close-comment')?.value?.trim() || null;
  const resultEl = document.getElementById('month-close-result');
  if (resultEl) resultEl.innerHTML = '<div class="loading-spinner"></div>';
  try {
    const data = await apiFetch('/month/close', {
      method: 'POST',
      body: JSON.stringify({ year, month, comment }),
    });
    _showMonthCloseResult(resultEl, data);
    showToast('Месяц закрыт', 'success');
    // Refresh archive batches after closing the month
    setTimeout(loadArchiveBatches, 500);
  } catch (err) {
    _showMonthCloseResult(resultEl, null, getErrorMessage(err));
    showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
  }
}

async function loadArchiveBatches() {
  const { year, month } = _getMonthCloseParams();
  const listEl = document.getElementById('month-close-batches-list');
  if (listEl) listEl.innerHTML = '<div class="loading-spinner"></div>';
  try {
    const params = `?year=${year}&month=${month}`;
    const data = await apiFetch(`/month/archive-batches${params}`);
    if (!listEl) return;
    if (!data || data.length === 0) {
      listEl.innerHTML = '<p style="color:var(--color-text-secondary)">Нет архивных батчей для выбранного периода</p>';
      return;
    }
    listEl.innerHTML = data.map(batch => `
      <div class="month-close-batch-item">
        <span class="batch-period">${escHtml(String(batch.year || ''))}-${escHtml(String(batch.month || '').padStart(2, '0'))}</span>
        <span class="batch-status">${escHtml(batch.status || '')}</span>
        <span class="batch-date">${escHtml(batch.created_at || '')}</span>
        ${batch.archive_batch_id ? `<span class="batch-id">ID: ${escHtml(String(batch.archive_batch_id))}</span>` : ''}
      </div>
    `).join('');
  } catch (err) {
    if (listEl) listEl.innerHTML = `<div class="month-close-error">❌ ${escHtml(getErrorMessage(err))}</div>`;
    showToast(`Ошибка: ${getErrorMessage(err)}`, 'error');
  }
}
