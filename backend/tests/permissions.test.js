'use strict';

const {
  ROLES,
  PERMISSION_MATRIX,
  hasPermission,
  canViewAllDeals,
  canEditSalesFields,
  canEditAccountingFields,
  canViewJournal,
  canViewAnalytics,
  canCreateDeals,
  canDeleteDeals,
  getPermissionsForRole,
} = require('../permissions');

describe('Матрица разрешений', () => {
  test('все роли определены', () => {
    expect(ROLES.ADMIN).toBe('admin');
    expect(ROLES.SALES).toBe('sales');
    expect(ROLES.ACCOUNTING).toBe('accounting');
    expect(ROLES.VIEWER).toBe('viewer');
  });

  test('у каждой роли есть запись в матрице', () => {
    Object.values(ROLES).forEach((role) => {
      expect(PERMISSION_MATRIX[role]).toBeDefined();
    });
  });
});

describe('hasPermission', () => {
  test('возвращает false для несуществующей роли', () => {
    expect(hasPermission('unknown_role', 'canViewJournal')).toBe(false);
  });

  test('возвращает false для несуществующего права', () => {
    expect(hasPermission(ROLES.ADMIN, 'canFlyToMoon')).toBe(false);
  });
});

describe('canViewAllDeals', () => {
  test('admin видит все сделки', () => expect(canViewAllDeals(ROLES.ADMIN)).toBe(true));
  test('sales НЕ видит все сделки', () => expect(canViewAllDeals(ROLES.SALES)).toBe(false));
  test('accounting видит все сделки', () => expect(canViewAllDeals(ROLES.ACCOUNTING)).toBe(true));
  test('viewer видит все сделки', () => expect(canViewAllDeals(ROLES.VIEWER)).toBe(true));
});

describe('canEditSalesFields', () => {
  test('admin может редактировать поля продаж', () => expect(canEditSalesFields(ROLES.ADMIN)).toBe(true));
  test('sales может редактировать поля продаж', () => expect(canEditSalesFields(ROLES.SALES)).toBe(true));
  test('accounting НЕ может редактировать поля продаж', () => expect(canEditSalesFields(ROLES.ACCOUNTING)).toBe(false));
  test('viewer НЕ может редактировать поля продаж', () => expect(canEditSalesFields(ROLES.VIEWER)).toBe(false));
});

describe('canEditAccountingFields', () => {
  test('admin может редактировать бухгалтерские поля', () => expect(canEditAccountingFields(ROLES.ADMIN)).toBe(true));
  test('sales НЕ может редактировать бухгалтерские поля', () => expect(canEditAccountingFields(ROLES.SALES)).toBe(false));
  test('accounting может редактировать бухгалтерские поля', () => expect(canEditAccountingFields(ROLES.ACCOUNTING)).toBe(true));
  test('viewer НЕ может редактировать бухгалтерские поля', () => expect(canEditAccountingFields(ROLES.VIEWER)).toBe(false));
});

describe('canViewJournal', () => {
  test('admin может просматривать журнал', () => expect(canViewJournal(ROLES.ADMIN)).toBe(true));
  test('sales НЕ может просматривать журнал', () => expect(canViewJournal(ROLES.SALES)).toBe(false));
  test('accounting может просматривать журнал', () => expect(canViewJournal(ROLES.ACCOUNTING)).toBe(true));
  test('viewer может просматривать журнал', () => expect(canViewJournal(ROLES.VIEWER)).toBe(true));
});

describe('canViewAnalytics', () => {
  test('admin может просматривать аналитику', () => expect(canViewAnalytics(ROLES.ADMIN)).toBe(true));
  test('sales НЕ может просматривать аналитику', () => expect(canViewAnalytics(ROLES.SALES)).toBe(false));
  test('accounting может просматривать аналитику', () => expect(canViewAnalytics(ROLES.ACCOUNTING)).toBe(true));
  test('viewer может просматривать аналитику', () => expect(canViewAnalytics(ROLES.VIEWER)).toBe(true));
});

describe('canCreateDeals', () => {
  test('admin может создавать сделки', () => expect(canCreateDeals(ROLES.ADMIN)).toBe(true));
  test('sales может создавать сделки', () => expect(canCreateDeals(ROLES.SALES)).toBe(true));
  test('accounting НЕ может создавать сделки', () => expect(canCreateDeals(ROLES.ACCOUNTING)).toBe(false));
  test('viewer НЕ может создавать сделки', () => expect(canCreateDeals(ROLES.VIEWER)).toBe(false));
});

describe('canDeleteDeals', () => {
  test('admin может удалять сделки', () => expect(canDeleteDeals(ROLES.ADMIN)).toBe(true));
  test('sales НЕ может удалять сделки', () => expect(canDeleteDeals(ROLES.SALES)).toBe(false));
  test('accounting НЕ может удалять сделки', () => expect(canDeleteDeals(ROLES.ACCOUNTING)).toBe(false));
  test('viewer НЕ может удалять сделки', () => expect(canDeleteDeals(ROLES.VIEWER)).toBe(false));
});

describe('getPermissionsForRole', () => {
  test('возвращает копию объекта прав', () => {
    const perms = getPermissionsForRole(ROLES.ADMIN);
    expect(perms.canViewAllDeals).toBe(true);
    expect(perms.canManageUsers).toBe(true);
  });

  test('возвращает пустой объект для неизвестной роли', () => {
    expect(getPermissionsForRole('nonexistent')).toEqual({});
  });

  test('изменение возвращённого объекта не влияет на матрицу', () => {
    const perms = getPermissionsForRole(ROLES.VIEWER);
    perms.canDeleteDeals = true;
    expect(PERMISSION_MATRIX[ROLES.VIEWER].canDeleteDeals).toBe(false);
  });
});
