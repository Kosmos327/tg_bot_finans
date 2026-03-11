/**
 * Финансовая система учёта сделок — Mini App JavaScript
 *
 * Communicates with the FastAPI backend to create deals and load settings.
 * Uses Telegram WebApp SDK for user identification and native UI integration.
 */

'use strict';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/** Base URL of the FastAPI backend. Adjust before deploying. */
const API_BASE = window.location.origin;

// ---------------------------------------------------------------------------
// Telegram WebApp bootstrap
// ---------------------------------------------------------------------------

const tg = window.Telegram?.WebApp;

if (tg) {
  tg.ready();
  tg.expand();
}

/** Return the raw initData string for authentication headers. */
function getInitData() {
  return tg?.initData ?? '';
}

/** Return the current Telegram user object or null. */
function getTgUser() {
  return tg?.initDataUnsafe?.user ?? null;
}

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

function $(selector) {
  return document.querySelector(selector);
}

function showScreen(id) {
  document.querySelectorAll('.screen').forEach((s) => s.classList.remove('active'));
  const target = document.getElementById(id);
  if (target) target.classList.add('active');
}

function showError(message) {
  const el = $('#form-error');
  if (!el) return;
  el.textContent = message;
  el.classList.remove('hidden');
}

function clearError() {
  const el = $('#form-error');
  if (el) el.classList.add('hidden');
}

function setLoading(loading) {
  const btn = $('#submit-btn');
  if (!btn) return;
  btn.disabled = loading;
  btn.textContent = loading ? '⏳ Сохранение...' : '✅ Создать сделку';
}

function populateSelect(selectId, options) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  options.forEach((opt) => {
    const el = document.createElement('option');
    el.value = opt;
    el.textContent = opt;
    sel.appendChild(el);
  });
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

async function fetchSettings() {
  const res = await fetch(`${API_BASE}/settings`, {
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(`Settings fetch failed: ${res.status}`);
  return res.json();
}

async function fetchUserDeals(manager) {
  const res = await fetch(
    `${API_BASE}/deals/user?manager=${encodeURIComponent(manager)}`,
    {
      headers: {
        'Content-Type': 'application/json',
        'X-Init-Data': getInitData(),
      },
    },
  );
  if (!res.ok) throw new Error(`Deals fetch failed: ${res.status}`);
  return res.json();
}

async function postCreateDeal(payload) {
  const res = await fetch(`${API_BASE}/deal/create`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Init-Data': getInitData(),
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

async function loadAndApplySettings() {
  try {
    const settings = await fetchSettings();
    populateSelect('status', settings.statuses ?? []);
    populateSelect('business_direction', settings.business_directions ?? []);
    populateSelect('client', settings.clients ?? []);
    populateSelect('manager', settings.managers ?? []);
    populateSelect('vat_type', settings.vat_types ?? []);
  } catch (err) {
    console.warn('Could not load settings:', err.message);
  }
}

// ---------------------------------------------------------------------------
// Deals list
// ---------------------------------------------------------------------------

function renderDeals(deals) {
  const container = $('#deals-list');
  if (!container) return;

  if (!deals.length) {
    container.innerHTML = '<p class="loading-text">У вас пока нет сделок.</p>';
    return;
  }

  container.innerHTML = deals
    .map(
      (d) => `
      <div class="deal-card">
        <div class="deal-card-header">
          <span class="deal-card-id">${d['ID сделки'] ?? ''}</span>
          <span class="deal-card-status">${d['Статус сделки'] ?? ''}</span>
        </div>
        <div class="deal-card-info">
          <div>🏢 ${d['Клиент'] ?? '—'}</div>
          <div>💰 ${d['Начислено с НДС'] ?? '—'}</div>
          <div>📅 ${d['Дата начала проекта'] ?? '—'} – ${d['Дата окончания проекта'] ?? '—'}</div>
        </div>
      </div>`,
    )
    .join('');
}

async function loadMyDeals() {
  const container = $('#deals-list');
  if (container) container.innerHTML = '<p class="loading-text">Загрузка...</p>';

  const user = getTgUser();
  const managerField = $('#manager');
  const manager =
    (managerField && managerField.value) ||
    (user
      ? [user.first_name, user.last_name].filter(Boolean).join(' ')
      : '');

  if (!manager) {
    if (container)
      container.innerHTML = '<p class="loading-text">Не удалось определить менеджера.</p>';
    return;
  }

  try {
    const deals = await fetchUserDeals(manager);
    renderDeals(deals);
  } catch (err) {
    if (container)
      container.innerHTML = `<p class="loading-text" style="color:#ef4444">Ошибка: ${err.message}</p>`;
  }
}

// ---------------------------------------------------------------------------
// Form submission
// ---------------------------------------------------------------------------

async function handleFormSubmit(e) {
  e.preventDefault();
  clearError();

  const form = e.target;
  const data = Object.fromEntries(new FormData(form).entries());

  // Basic client-side validation
  const required = [
    'status', 'business_direction', 'client', 'manager',
    'amount_with_vat', 'vat_type', 'start_date', 'end_date',
  ];
  for (const field of required) {
    if (!data[field]) {
      showError('Пожалуйста, заполните все обязательные поля.');
      return;
    }
  }

  const payload = {
    status: data.status,
    business_direction: data.business_direction,
    client: data.client,
    manager: data.manager,
    amount_with_vat: parseFloat(data.amount_with_vat),
    vat_type: data.vat_type,
    start_date: data.start_date,
    end_date: data.end_date,
    document_link: data.document_link ?? '',
    comment: data.comment ?? '',
    source: 'Telegram Mini App',
  };

  setLoading(true);
  try {
    const result = await postCreateDeal(payload);
    form.reset();
    showSuccess(result.deal_id);
  } catch (err) {
    showError(`Ошибка при создании сделки: ${err.message}`);
  } finally {
    setLoading(false);
  }
}

// ---------------------------------------------------------------------------
// Success overlay
// ---------------------------------------------------------------------------

function showSuccess(dealId) {
  const overlay = $('#success-overlay');
  const idEl = $('#success-deal-id');
  if (idEl) idEl.textContent = dealId;
  if (overlay) overlay.classList.remove('hidden');
  tg?.HapticFeedback?.notificationOccurred('success');
}

function hideSuccess() {
  const overlay = $('#success-overlay');
  if (overlay) overlay.classList.add('hidden');
  showScreen('dashboard');
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  // Greet user
  const user = getTgUser();
  const greetingEl = $('#user-greeting');
  if (greetingEl && user) {
    greetingEl.textContent = `Привет, ${user.first_name ?? 'пользователь'}! 👋`;
  }

  // Load settings for form dropdowns
  loadAndApplySettings();

  // Navigation
  $('#btn-create-deal')?.addEventListener('click', () => showScreen('create-deal'));

  $('#btn-my-deals')?.addEventListener('click', () => {
    showScreen('my-deals');
    loadMyDeals();
  });

  $('#back-from-create')?.addEventListener('click', () => showScreen('dashboard'));
  $('#back-from-deals')?.addEventListener('click', () => showScreen('dashboard'));

  // Form
  $('#deal-form')?.addEventListener('submit', handleFormSubmit);

  // Success overlay
  $('#success-ok')?.addEventListener('click', hideSuccess);

  // Telegram back button
  if (tg?.BackButton) {
    tg.BackButton.onClick(() => {
      const active = document.querySelector('.screen.active');
      if (active && active.id !== 'dashboard') {
        showScreen('dashboard');
      } else {
        tg.close();
      }
    });

    // Show/hide native back button based on current screen
    const observer = new MutationObserver(() => {
      const active = document.querySelector('.screen.active');
      if (active && active.id !== 'dashboard') {
        tg.BackButton.show();
      } else {
        tg.BackButton.hide();
      }
    });
    document.querySelectorAll('.screen').forEach((s) =>
      observer.observe(s, { attributes: true, attributeFilter: ['class'] }),
    );
  }
});
