'use strict';

/**
 * Централизованная матрица прав доступа.
 *
 * Роли:
 *   admin      — Администратор: полный доступ
 *   sales      — Менеджер по продажам: только свои сделки, редактирование полей продаж
 *   accounting — Бухгалтер: просмотр всех сделок, редактирование бухгалтерских полей
 *   viewer     — Наблюдатель: только чтение
 */

const ROLES = {
  ADMIN: 'admin',
  SALES: 'sales',
  ACCOUNTING: 'accounting',
  VIEWER: 'viewer',
};

/**
 * Матрица разрешений: для каждой роли перечислены допустимые действия.
 * Принцип «запрещено по умолчанию» — все права явно указаны.
 */
const PERMISSION_MATRIX = {
  [ROLES.ADMIN]: {
    canViewAllDeals: true,
    canCreateDeals: true,
    canDeleteDeals: true,
    canEditSalesFields: true,
    canEditAccountingFields: true,
    canViewJournal: true,
    canViewAnalytics: true,
    canViewSettings: true,
    canManageUsers: true,
  },
  [ROLES.SALES]: {
    // Менеджер видит только свои сделки (canViewAllDeals: false)
    canViewAllDeals: false,
    canCreateDeals: true,
    canDeleteDeals: false,
    canEditSalesFields: true,
    canEditAccountingFields: false,
    canViewJournal: false,
    canViewAnalytics: false,
    canViewSettings: false,
    canManageUsers: false,
  },
  [ROLES.ACCOUNTING]: {
    canViewAllDeals: true,
    canCreateDeals: false,
    canDeleteDeals: false,
    canEditSalesFields: false,
    canEditAccountingFields: true,
    canViewJournal: true,
    canViewAnalytics: true,
    canViewSettings: false,
    canManageUsers: false,
  },
  [ROLES.VIEWER]: {
    canViewAllDeals: true,
    canCreateDeals: false,
    canDeleteDeals: false,
    canEditSalesFields: false,
    canEditAccountingFields: false,
    canViewJournal: true,
    canViewAnalytics: true,
    canViewSettings: false,
    canManageUsers: false,
  },
};

/**
 * Базовая проверка конкретного права для роли.
 * @param {string} role
 * @param {string} permission
 * @returns {boolean}
 */
function hasPermission(role, permission) {
  const perms = PERMISSION_MATRIX[role];
  if (!perms) return false;
  return perms[permission] === true;
}

// Именованные хелперы для удобного использования в роутах и middleware

/** Может ли роль видеть все сделки (а не только свои). */
function canViewAllDeals(role) {
  return hasPermission(role, 'canViewAllDeals');
}

/** Может ли роль редактировать поля продаж (название, клиент, статус, сумма, комментарий). */
function canEditSalesFields(role) {
  return hasPermission(role, 'canEditSalesFields');
}

/** Может ли роль редактировать бухгалтерские поля (счёт-фактура, оплата, дата оплаты). */
function canEditAccountingFields(role) {
  return hasPermission(role, 'canEditAccountingFields');
}

/** Может ли роль просматривать журнал операций. */
function canViewJournal(role) {
  return hasPermission(role, 'canViewJournal');
}

/** Может ли роль просматривать раздел аналитики. */
function canViewAnalytics(role) {
  return hasPermission(role, 'canViewAnalytics');
}

/** Может ли роль создавать новые сделки. */
function canCreateDeals(role) {
  return hasPermission(role, 'canCreateDeals');
}

/** Может ли роль удалять сделки. */
function canDeleteDeals(role) {
  return hasPermission(role, 'canDeleteDeals');
}

/**
 * Возвращает полный объект разрешений для роли.
 * Используется для передачи на фронтенд.
 * @param {string} role
 * @returns {object}
 */
function getPermissionsForRole(role) {
  return { ...(PERMISSION_MATRIX[role] || {}) };
}

module.exports = {
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
};
