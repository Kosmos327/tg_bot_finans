'use strict';

/**
 * Матрица разрешений на фронтенде — зеркало backend/permissions/index.js.
 * Используется для управления видимостью и доступностью элементов UI
 * без дополнительных запросов к серверу.
 */

const ROLES = {
  ADMIN: 'admin',
  SALES: 'sales',
  ACCOUNTING: 'accounting',
  VIEWER: 'viewer',
};

const ROLE_LABELS = {
  admin: 'Администратор',
  sales: 'Менеджер по продажам',
  accounting: 'Бухгалтер',
  viewer: 'Наблюдатель',
};

/** Матрица разрешений — должна соответствовать backend/permissions/index.js */
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

class Permissions {
  constructor(role) {
    this._role = role;
    this._perms = PERMISSION_MATRIX[role] || {};
  }

  get role() { return this._role; }
  get roleLabel() { return ROLE_LABELS[this._role] || this._role; }

  has(permission) {
    return this._perms[permission] === true;
  }

  /** Может ли пользователь видеть все сделки (а не только свои). */
  canViewAllDeals() { return this.has('canViewAllDeals'); }

  /** Может ли пользователь редактировать поля продаж. */
  canEditSalesFields() { return this.has('canEditSalesFields'); }

  /** Может ли пользователь редактировать бухгалтерские поля. */
  canEditAccountingFields() { return this.has('canEditAccountingFields'); }

  /** Может ли пользователь просматривать журнал операций. */
  canViewJournal() { return this.has('canViewJournal'); }

  /** Может ли пользователь просматривать аналитику. */
  canViewAnalytics() { return this.has('canViewAnalytics'); }

  canCreateDeals() { return this.has('canCreateDeals'); }
  canDeleteDeals() { return this.has('canDeleteDeals'); }
  canViewSettings() { return this.has('canViewSettings'); }

  /**
   * Применяет атрибут disabled/readonly к полям формы в зависимости от прав.
   * @param {HTMLElement} formEl — корневой элемент формы
   */
  applyFormRestrictions(formEl) {
    // Поля продаж
    formEl.querySelectorAll('[data-perm="canEditSalesFields"]').forEach((el) => {
      this._setFieldAccess(el, this.canEditSalesFields());
    });

    // Бухгалтерские поля
    formEl.querySelectorAll('[data-perm="canEditAccountingFields"]').forEach((el) => {
      this._setFieldAccess(el, this.canEditAccountingFields());
    });
  }

  _setFieldAccess(el, editable) {
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') {
      el.readOnly = !editable;
      el.disabled = !editable;
    }
    el.classList.toggle('field--readonly', !editable);
  }
}

// Экспорт
window.Permissions = Permissions;
window.ROLES = ROLES;
window.ROLE_LABELS = ROLE_LABELS;
