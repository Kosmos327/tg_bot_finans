'use strict';

/**
 * API-клиент: обёртка над fetch для общения с backend.
 * Автоматически подставляет userId в заголовок X-User-Id.
 */
class ApiClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
    this.userId = null;
  }

  setUser(userId) {
    this.userId = userId;
  }

  _headers() {
    const h = { 'Content-Type': 'application/json' };
    if (this.userId) h['X-User-Id'] = this.userId;
    return h;
  }

  async _request(method, path, body) {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: this._headers(),
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      const err = new Error(data.error || `HTTP ${res.status}`);
      err.status = res.status;
      err.data = data;
      throw err;
    }

    return data;
  }

  // ── Пользователь ──────────────────────────────────────────────────────

  getMe() { return this._request('GET', '/api/me'); }
  getDemoUsers() { return this._request('GET', '/api/demo-users'); }

  // ── Сделки ────────────────────────────────────────────────────────────

  getDeals() { return this._request('GET', '/api/deals'); }
  getDeal(id) { return this._request('GET', `/api/deals/${id}`); }
  createDeal(data) { return this._request('POST', '/api/deals', data); }
  updateDeal(id, data) { return this._request('PATCH', `/api/deals/${id}`, data); }
  deleteDeal(id) { return this._request('DELETE', `/api/deals/${id}`); }

  // ── Журнал ────────────────────────────────────────────────────────────

  getJournal() { return this._request('GET', '/api/journal'); }
  createJournalEntry(data) { return this._request('POST', '/api/journal', data); }

  // ── Аналитика ─────────────────────────────────────────────────────────

  getAnalyticsSummary() { return this._request('GET', '/api/analytics/summary'); }
  getAnalyticsByMonth() { return this._request('GET', '/api/analytics/deals-by-month'); }
}

window.ApiClient = ApiClient;
