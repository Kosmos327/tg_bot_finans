'use strict';

/** =========================================================================
 * app.js — Главный модуль Telegram Mini App «Финансовый менеджер»
 *
 * Архитектура:
 *   App          — точка входа, инициализация, навигация между вкладками
 *   DealsScreen  — список и редактирование сделок
 *   JournalScreen— журнал операций (только для разрешённых ролей)
 *   AnalyticsScreen — аналитика (только для разрешённых ролей)
 *   SettingsScreen  — настройки (только для admin)
 * ========================================================================= */

const DEAL_STATUS_LABELS = {
  new: 'Новая',
  in_progress: 'В работе',
  completed: 'Завершена',
  cancelled: 'Отменена',
};

const JOURNAL_TYPE_LABELS = {
  income: 'Приход',
  expense: 'Расход',
};

// ── Утилиты ───────────────────────────────────────────────────────────────

function formatMoney(n) {
  return Number(n || 0).toLocaleString('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 });
}

function formatDate(s) {
  if (!s) return '—';
  return new Date(s).toLocaleDateString('ru-RU');
}

function showToast(msg, type = 'info') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `toast toast--${type} toast--visible`;
  setTimeout(() => t.classList.remove('toast--visible'), 3000);
}

function showLoading(show) {
  document.getElementById('loading').classList.toggle('hidden', !show);
}

// ── Главное приложение ────────────────────────────────────────────────────

class App {
  constructor() {
    this.api = new ApiClient('http://localhost:3000');
    this.perms = null;
    this.currentUser = null;
    this.activeTab = 'deals';

    this.screens = {};
  }

  async init() {
    showLoading(true);

    try {
      await this._setupUser();
      this._buildTabs();
      this._initScreens();
      this._navigate('deals');
    } catch (e) {
      showToast('Ошибка инициализации: ' + e.message, 'error');
    } finally {
      showLoading(false);
    }
  }

  /** Определяем пользователя: либо из Telegram initData, либо из демо-переключателя */
  async _setupUser() {
    const demoUsers = await this.api.getDemoUsers();
    this._renderDemoSelector(demoUsers);

    // Берём первого пользователя по умолчанию (admin)
    const defaultUser = demoUsers[0];
    await this._setActiveUser(defaultUser.id);
  }

  async _setActiveUser(userId) {
    this.api.setUser(userId);

    const me = await this.api.getMe();
    this.currentUser = me;
    this.perms = new Permissions(me.role);

    // Обновляем отображение пользователя
    document.getElementById('user-name').textContent = me.name;
    document.getElementById('user-role').textContent = this.perms.roleLabel;

    // Перестраиваем вкладки и перезагружаем экраны
    this._buildTabs();
    if (this.screens[this.activeTab]) {
      await this.screens[this.activeTab].load();
    }
  }

  /** Рендерим демо-переключатель ролей */
  _renderDemoSelector(users) {
    const sel = document.getElementById('demo-user-select');
    if (!sel) return;
    sel.innerHTML = users
      .map((u) => `<option value="${u.id}">${u.name} (${ROLE_LABELS[u.role]})</option>`)
      .join('');
    sel.addEventListener('change', async () => {
      showLoading(true);
      try {
        await this._setActiveUser(sel.value);
        // Если текущая вкладка недоступна — переходим на сделки
        if (!this._isTabAllowed(this.activeTab)) {
          this._navigate('deals');
        } else {
          await this.screens[this.activeTab].load();
        }
      } catch (e) {
        showToast(e.message, 'error');
      } finally {
        showLoading(false);
      }
    });
  }

  /** Строим вкладки согласно правам текущего пользователя */
  _buildTabs() {
    const tabs = [
      { id: 'deals', label: 'Сделки', icon: '📋', always: true },
      { id: 'journal', label: 'Журнал', icon: '📒', perm: () => this.perms.canViewJournal() },
      { id: 'analytics', label: 'Аналитика', icon: '📊', perm: () => this.perms.canViewAnalytics() },
      { id: 'settings', label: 'Настройки', icon: '⚙️', perm: () => this.perms.canViewSettings() },
    ];

    const nav = document.getElementById('tab-bar');
    nav.innerHTML = '';

    tabs.forEach(({ id, label, icon, always, perm }) => {
      const visible = always || (perm && perm());
      if (!visible) return;

      const btn = document.createElement('button');
      btn.className = 'tab-btn' + (id === this.activeTab ? ' tab-btn--active' : '');
      btn.dataset.tab = id;
      btn.innerHTML = `<span class="tab-icon">${icon}</span><span class="tab-label">${label}</span>`;
      btn.addEventListener('click', () => this._navigate(id));
      nav.appendChild(btn);
    });
  }

  _isTabAllowed(tabId) {
    const permMap = {
      journal: () => this.perms.canViewJournal(),
      analytics: () => this.perms.canViewAnalytics(),
      settings: () => this.perms.canViewSettings(),
    };
    return !permMap[tabId] || permMap[tabId]();
  }

  _initScreens() {
    this.screens = {
      deals: new DealsScreen(this),
      journal: new JournalScreen(this),
      analytics: new AnalyticsScreen(this),
      settings: new SettingsScreen(this),
    };
  }

  async _navigate(tabId) {
    // Скрываем все экраны
    document.querySelectorAll('.screen').forEach((s) => s.classList.add('hidden'));

    // Показываем нужный
    const screen = document.getElementById(`screen-${tabId}`);
    if (screen) screen.classList.remove('hidden');

    this.activeTab = tabId;
    this._buildTabs();

    if (this.screens[tabId]) {
      showLoading(true);
      try {
        await this.screens[tabId].load();
      } catch (e) {
        showToast(e.message, 'error');
      } finally {
        showLoading(false);
      }
    }
  }
}

// ── Экран «Сделки» ────────────────────────────────────────────────────────

class DealsScreen {
  constructor(app) {
    this.app = app;
    this.deals = [];
    this.selectedDeal = null;
  }

  async load() {
    this.deals = await this.app.api.getDeals();
    this._render();
  }

  _render() {
    const perms = this.app.perms;
    const container = document.getElementById('deals-list');

    // Кнопка «Новая сделка» — только если есть право
    const addBtn = document.getElementById('btn-add-deal');
    if (addBtn) {
      addBtn.classList.toggle('hidden', !perms.canCreateDeals());
    }

    if (this.deals.length === 0) {
      container.innerHTML = '<p class="empty-msg">Сделок нет</p>';
      return;
    }

    container.innerHTML = this.deals.map((d) => this._dealCard(d)).join('');

    container.querySelectorAll('.deal-card').forEach((card) => {
      card.addEventListener('click', () => this._openDeal(card.dataset.id));
    });
  }

  _dealCard(deal) {
    const statusClass = `status--${deal.status}`;
    const statusLabel = DEAL_STATUS_LABELS[deal.status] || deal.status;
    return `
      <div class="deal-card" data-id="${deal.id}">
        <div class="deal-card__header">
          <span class="deal-card__name">${deal.name}</span>
          <span class="deal-badge ${statusClass}">${statusLabel}</span>
        </div>
        <div class="deal-card__meta">
          <span>${deal.client}</span>
          <span class="deal-card__amount">${formatMoney(deal.amount)}</span>
        </div>
        <div class="deal-card__date">${formatDate(deal.date)}</div>
      </div>`;
  }

  async _openDeal(id) {
    this.selectedDeal = this.deals.find((d) => d.id === id);
    if (!this.selectedDeal) return;
    this._renderModal(this.selectedDeal);
    document.getElementById('deal-modal').classList.remove('hidden');
  }

  _renderModal(deal) {
    const perms = this.app.perms;
    const modal = document.getElementById('deal-modal');
    const content = document.getElementById('deal-modal-content');

    content.innerHTML = `
      <h2 class="modal__title">${deal.name}</h2>

      <fieldset class="fieldset">
        <legend class="fieldset__legend">Поля продаж</legend>

        <label class="field-label">Название
          <input class="field-input" data-perm="canEditSalesFields" data-field="name" value="${deal.name || ''}" />
        </label>

        <label class="field-label">Клиент
          <input class="field-input" data-perm="canEditSalesFields" data-field="client" value="${deal.client || ''}" />
        </label>

        <label class="field-label">Статус
          <select class="field-input" data-perm="canEditSalesFields" data-field="status">
            ${Object.entries(DEAL_STATUS_LABELS).map(([v, l]) =>
              `<option value="${v}" ${deal.status === v ? 'selected' : ''}>${l}</option>`
            ).join('')}
          </select>
        </label>

        <label class="field-label">Сумма, ₽
          <input class="field-input" type="number" data-perm="canEditSalesFields" data-field="amount" value="${deal.amount || 0}" />
        </label>

        <label class="field-label">Дата
          <input class="field-input" type="date" data-perm="canEditSalesFields" data-field="date" value="${deal.date || ''}" />
        </label>

        <label class="field-label">Комментарий
          <textarea class="field-input" data-perm="canEditSalesFields" data-field="comment">${deal.comment || ''}</textarea>
        </label>
      </fieldset>

      <fieldset class="fieldset">
        <legend class="fieldset__legend">Бухгалтерские поля</legend>

        <label class="field-label">Счёт-фактура №
          <input class="field-input" data-perm="canEditAccountingFields" data-field="invoice" value="${deal.invoice || ''}" />
        </label>

        <label class="field-label">
          <span>Оплачено</span>
          <input class="field-checkbox" type="checkbox" data-perm="canEditAccountingFields" data-field="paid" ${deal.paid ? 'checked' : ''} />
        </label>

        <label class="field-label">Дата оплаты
          <input class="field-input" type="date" data-perm="canEditAccountingFields" data-field="paymentDate" value="${deal.paymentDate || ''}" />
        </label>

        <label class="field-label">Бухгалтерский комментарий
          <textarea class="field-input" data-perm="canEditAccountingFields" data-field="accountingComment">${deal.accountingComment || ''}</textarea>
        </label>
      </fieldset>

      <div class="modal__actions">
        <button class="btn btn--primary" id="btn-save-deal">Сохранить</button>
        ${perms.canDeleteDeals()
          ? `<button class="btn btn--danger" id="btn-delete-deal">Удалить</button>`
          : ''}
        <button class="btn btn--secondary" id="btn-close-modal">Закрыть</button>
      </div>`;

    // Применяем ограничения доступа к полям
    perms.applyFormRestrictions(content);

    // Кнопка «Сохранить» отключена, если нет прав на редактирование ни одного поля
    const canEdit = perms.canEditSalesFields() || perms.canEditAccountingFields();
    const saveBtn = document.getElementById('btn-save-deal');
    if (!canEdit) {
      saveBtn.disabled = true;
      saveBtn.title = 'Недостаточно прав для редактирования';
    }

    // Привязка событий
    modal.querySelector('#btn-close-modal').addEventListener('click', () => {
      modal.classList.add('hidden');
    });

    if (perms.canDeleteDeals()) {
      modal.querySelector('#btn-delete-deal').addEventListener('click', () =>
        this._deleteDeal(deal.id));
    }

    if (canEdit) {
      modal.querySelector('#btn-save-deal').addEventListener('click', () =>
        this._saveDeal(deal.id, content));
    }
  }

  async _saveDeal(id, formEl) {
    const updates = {};
    formEl.querySelectorAll('[data-field]').forEach((el) => {
      if (el.disabled) return; // Не отправляем заблокированные поля
      if (el.type === 'checkbox') {
        updates[el.dataset.field] = el.checked;
      } else {
        updates[el.dataset.field] = el.value;
      }
    });

    showLoading(true);
    try {
      await this.app.api.updateDeal(id, updates);
      showToast('Сделка обновлена', 'success');
      document.getElementById('deal-modal').classList.add('hidden');
      await this.load();
    } catch (e) {
      showToast(e.message, 'error');
    } finally {
      showLoading(false);
    }
  }

  async _deleteDeal(id) {
    if (!confirm('Удалить сделку?')) return;
    showLoading(true);
    try {
      await this.app.api.deleteDeal(id);
      showToast('Сделка удалена', 'success');
      document.getElementById('deal-modal').classList.add('hidden');
      await this.load();
    } catch (e) {
      showToast(e.message, 'error');
    } finally {
      showLoading(false);
    }
  }
}

// ── Экран «Журнал» ────────────────────────────────────────────────────────

class JournalScreen {
  constructor(app) {
    this.app = app;
  }

  async load() {
    const entries = await this.app.api.getJournal();
    this._render(entries);
  }

  _render(entries) {
    const container = document.getElementById('journal-list');

    // Кнопка добавления — только для бухгалтера/admin
    const addBtn = document.getElementById('btn-add-journal');
    if (addBtn) {
      addBtn.classList.toggle('hidden', !this.app.perms.canEditAccountingFields());
    }

    if (!entries.length) {
      container.innerHTML = '<p class="empty-msg">Журнал пуст</p>';
      return;
    }

    container.innerHTML = entries.map((e) => `
      <div class="journal-entry">
        <div class="journal-entry__header">
          <span class="journal-entry__date">${formatDate(e.date)}</span>
          <span class="journal-badge journal-badge--${e.type}">${JOURNAL_TYPE_LABELS[e.type]}</span>
        </div>
        <div class="journal-entry__desc">${e.description}</div>
        <div class="journal-entry__amount">${formatMoney(e.amount)}</div>
      </div>`).join('');
  }
}

// ── Экран «Аналитика» ─────────────────────────────────────────────────────

class AnalyticsScreen {
  constructor(app) {
    this.app = app;
  }

  async load() {
    const [summary, byMonth] = await Promise.all([
      this.app.api.getAnalyticsSummary(),
      this.app.api.getAnalyticsByMonth(),
    ]);
    this._render(summary, byMonth);
  }

  _render(summary, byMonth) {
    const { deals: ds, journal: js } = summary;

    document.getElementById('analytics-content').innerHTML = `
      <section class="analytics-section">
        <h3 class="section-title">Сделки</h3>
        <div class="stats-grid">
          <div class="stat-card"><div class="stat-value">${ds.total}</div><div class="stat-label">Всего</div></div>
          <div class="stat-card"><div class="stat-value">${formatMoney(ds.totalAmount)}</div><div class="stat-label">Общая сумма</div></div>
          <div class="stat-card stat-card--green"><div class="stat-value">${formatMoney(ds.paidAmount)}</div><div class="stat-label">Оплачено</div></div>
          <div class="stat-card stat-card--red"><div class="stat-value">${formatMoney(ds.unpaidAmount)}</div><div class="stat-label">Не оплачено</div></div>
        </div>

        <h4 class="section-subtitle">По статусам</h4>
        <div class="status-breakdown">
          ${Object.entries(ds.byStatus || {}).map(([status, count]) =>
            `<div class="status-row">
              <span class="deal-badge status--${status}">${DEAL_STATUS_LABELS[status] || status}</span>
              <span class="status-count">${count}</span>
            </div>`
          ).join('')}
        </div>
      </section>

      <section class="analytics-section">
        <h3 class="section-title">Финансы</h3>
        <div class="stats-grid">
          <div class="stat-card stat-card--green"><div class="stat-value">${formatMoney(js.totalIncome)}</div><div class="stat-label">Общий приход</div></div>
          <div class="stat-card stat-card--red"><div class="stat-value">${formatMoney(js.totalExpense)}</div><div class="stat-label">Общий расход</div></div>
          <div class="stat-card ${js.balance >= 0 ? 'stat-card--green' : 'stat-card--red'}">
            <div class="stat-value">${formatMoney(js.balance)}</div>
            <div class="stat-label">Баланс</div>
          </div>
        </div>
      </section>

      ${byMonth.length ? `
      <section class="analytics-section">
        <h3 class="section-title">Сделки по месяцам</h3>
        <table class="data-table">
          <thead><tr><th>Месяц</th><th>Кол-во</th><th>Сумма</th></tr></thead>
          <tbody>
            ${byMonth.map((r) => `
              <tr>
                <td>${r.month}</td>
                <td>${r.count}</td>
                <td>${formatMoney(r.amount)}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </section>` : ''}`;
  }
}

// ── Экран «Настройки» (только admin) ─────────────────────────────────────

class SettingsScreen {
  constructor(app) {
    this.app = app;
  }

  async load() {
    const container = document.getElementById('settings-content');
    const { DEMO_USERS } = await this.app.api.getDemoUsers().then((users) => ({ DEMO_USERS: users }));

    container.innerHTML = `
      <section class="analytics-section">
        <h3 class="section-title">Пользователи системы</h3>
        <table class="data-table">
          <thead><tr><th>Имя</th><th>Роль</th><th>Права</th></tr></thead>
          <tbody>
            ${DEMO_USERS.map((u) => `
              <tr>
                <td>${u.name}</td>
                <td><span class="role-badge role--${u.role}">${ROLE_LABELS[u.role]}</span></td>
                <td class="perms-cell">${this._formatPerms(u.permissions)}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </section>`;
  }

  _formatPerms(perms) {
    const allowed = Object.entries(perms)
      .filter(([, v]) => v)
      .map(([k]) => `<span class="perm-tag">${k}</span>`)
      .join(' ');
    return allowed || '<span class="text-muted">нет прав</span>';
  }
}

// ── Добавить новую сделку (модальное окно) ────────────────────────────────

function initAddDealModal(app) {
  const btn = document.getElementById('btn-add-deal');
  const modal = document.getElementById('add-deal-modal');
  if (!btn || !modal) return;

  btn.addEventListener('click', () => modal.classList.remove('hidden'));
  document.getElementById('btn-cancel-add-deal').addEventListener('click', () =>
    modal.classList.add('hidden'));

  document.getElementById('form-add-deal').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const data = Object.fromEntries(fd.entries());
    showLoading(true);
    try {
      await app.api.createDeal(data);
      showToast('Сделка создана', 'success');
      modal.classList.add('hidden');
      e.target.reset();
      await app.screens.deals.load();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      showLoading(false);
    }
  });
}

// ── Запуск ────────────────────────────────────────────────────────────────

window.addEventListener('DOMContentLoaded', async () => {
  const app = new App();
  window._app = app; // для отладки в консоли
  await app.init();
  initAddDealModal(app);
});
