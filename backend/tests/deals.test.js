'use strict';

const request = require('supertest');
const app = require('../server');

// Сброс хранилища перед тестами с осторожностью: используем живые данные,
// поэтому тесты проверяют поведение API, а не конкретные записи.

const headers = {
  admin: { 'x-user-id': 'user_admin' },
  sales: { 'x-user-id': 'user_sales' },
  accounting: { 'x-user-id': 'user_acc' },
  viewer: { 'x-user-id': 'user_view' },
};

// ── Аутентификация ────────────────────────────────────────────────────────

describe('GET /api/me', () => {
  test('401 без заголовка', async () => {
    const res = await request(app).get('/api/me');
    expect(res.status).toBe(401);
  });

  test('401 с неизвестным userId', async () => {
    const res = await request(app).get('/api/me').set('x-user-id', 'nobody');
    expect(res.status).toBe(401);
  });

  test('возвращает профиль admin', async () => {
    const res = await request(app).get('/api/me').set(headers.admin);
    expect(res.status).toBe(200);
    expect(res.body.role).toBe('admin');
    expect(res.body.permissions.canManageUsers).toBe(true);
  });

  test('возвращает профиль sales', async () => {
    const res = await request(app).get('/api/me').set(headers.sales);
    expect(res.status).toBe(200);
    expect(res.body.role).toBe('sales');
    expect(res.body.permissions.canViewAllDeals).toBe(false);
  });
});

// ── Сделки ────────────────────────────────────────────────────────────────

describe('GET /api/deals', () => {
  test('admin получает все сделки', async () => {
    const res = await request(app).get('/api/deals').set(headers.admin);
    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
  });

  test('sales получает только свои сделки', async () => {
    const res = await request(app).get('/api/deals').set(headers.sales);
    expect(res.status).toBe(200);
    res.body.forEach((d) => expect(d.createdBy).toBe('user_sales'));
  });

  test('accounting получает все сделки', async () => {
    const res = await request(app).get('/api/deals').set(headers.accounting);
    expect(res.status).toBe(200);
    expect(res.body.length).toBeGreaterThan(0);
  });
});

describe('POST /api/deals', () => {
  test('sales может создать сделку', async () => {
    const res = await request(app)
      .post('/api/deals')
      .set(headers.sales)
      .send({ name: 'Тестовая сделка', client: 'ООО Тест' });
    expect(res.status).toBe(201);
    expect(res.body.name).toBe('Тестовая сделка');
  });

  test('accounting НЕ может создать сделку', async () => {
    const res = await request(app)
      .post('/api/deals')
      .set(headers.accounting)
      .send({ name: 'Тест', client: 'ООО' });
    expect(res.status).toBe(403);
  });

  test('viewer НЕ может создать сделку', async () => {
    const res = await request(app)
      .post('/api/deals')
      .set(headers.viewer)
      .send({ name: 'Тест', client: 'ООО' });
    expect(res.status).toBe(403);
  });

  test('400 при отсутствии обязательных полей', async () => {
    const res = await request(app)
      .post('/api/deals')
      .set(headers.admin)
      .send({ comment: 'нет названия' });
    expect(res.status).toBe(400);
  });
});

describe('PATCH /api/deals/:id', () => {
  let dealId;

  beforeAll(async () => {
    // Создаём сделку от имени admin для дальнейших тестов
    const res = await request(app)
      .post('/api/deals')
      .set(headers.admin)
      .send({ name: 'Сделка для PATCH', client: 'ООО Патч' });
    dealId = res.body.id;
  });

  test('admin может обновить поля продаж', async () => {
    const res = await request(app)
      .patch(`/api/deals/${dealId}`)
      .set(headers.admin)
      .send({ name: 'Обновлённое название' });
    expect(res.status).toBe(200);
    expect(res.body.name).toBe('Обновлённое название');
  });

  test('admin может обновить бухгалтерские поля', async () => {
    const res = await request(app)
      .patch(`/api/deals/${dealId}`)
      .set(headers.admin)
      .send({ invoice: '2024-999', paid: true });
    expect(res.status).toBe(200);
    expect(res.body.invoice).toBe('2024-999');
    expect(res.body.paid).toBe(true);
  });

  test('accounting НЕ может обновить поля продаж', async () => {
    const res = await request(app)
      .patch(`/api/deals/${dealId}`)
      .set(headers.accounting)
      .send({ name: 'Попытка изменить' });
    expect(res.status).toBe(403);
  });

  test('accounting может обновить бухгалтерские поля', async () => {
    const res = await request(app)
      .patch(`/api/deals/${dealId}`)
      .set(headers.accounting)
      .send({ accountingComment: 'Бухгалтерская заметка' });
    expect(res.status).toBe(200);
    expect(res.body.accountingComment).toBe('Бухгалтерская заметка');
  });

  test('viewer НЕ может обновить никакие поля', async () => {
    const res = await request(app)
      .patch(`/api/deals/${dealId}`)
      .set(headers.viewer)
      .send({ name: 'Изменение от наблюдателя' });
    expect(res.status).toBe(403);
  });

  test('sales НЕ может обновить бухгалтерские поля', async () => {
    const res = await request(app)
      .patch(`/api/deals/${dealId}`)
      .set(headers.sales)
      .send({ invoice: '0000' });
    expect(res.status).toBe(403);
  });
});

describe('DELETE /api/deals/:id', () => {
  test('admin может удалить сделку', async () => {
    const create = await request(app)
      .post('/api/deals')
      .set(headers.admin)
      .send({ name: 'Удалить меня', client: 'ООО Удалить' });
    const res = await request(app)
      .delete(`/api/deals/${create.body.id}`)
      .set(headers.admin);
    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
  });

  test('sales НЕ может удалить сделку', async () => {
    const allDeals = await request(app).get('/api/deals').set(headers.admin);
    const id = allDeals.body[0]?.id;
    if (!id) return;
    const res = await request(app).delete(`/api/deals/${id}`).set(headers.sales);
    expect(res.status).toBe(403);
  });
});

// ── Журнал ────────────────────────────────────────────────────────────────

describe('GET /api/journal', () => {
  test('admin может просматривать журнал', async () => {
    const res = await request(app).get('/api/journal').set(headers.admin);
    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
  });

  test('sales НЕ может просматривать журнал', async () => {
    const res = await request(app).get('/api/journal').set(headers.sales);
    expect(res.status).toBe(403);
  });

  test('accounting может просматривать журнал', async () => {
    const res = await request(app).get('/api/journal').set(headers.accounting);
    expect(res.status).toBe(200);
  });

  test('viewer может просматривать журнал', async () => {
    const res = await request(app).get('/api/journal').set(headers.viewer);
    expect(res.status).toBe(200);
  });
});

// ── Аналитика ─────────────────────────────────────────────────────────────

describe('GET /api/analytics/summary', () => {
  test('admin получает сводку', async () => {
    const res = await request(app).get('/api/analytics/summary').set(headers.admin);
    expect(res.status).toBe(200);
    expect(res.body.deals).toBeDefined();
    expect(res.body.journal).toBeDefined();
  });

  test('sales НЕ имеет доступа к аналитике', async () => {
    const res = await request(app).get('/api/analytics/summary').set(headers.sales);
    expect(res.status).toBe(403);
  });

  test('accounting имеет доступ к аналитике', async () => {
    const res = await request(app).get('/api/analytics/summary').set(headers.accounting);
    expect(res.status).toBe(200);
  });
});
