'use strict';

const { ROLES, getPermissionsForRole } = require('../permissions');

/**
 * Список демо-пользователей с назначенными ролями.
 * В production ролі хранятся в базе данных.
 */
const DEMO_USERS = {
  user_admin: { id: 'user_admin', name: 'Иван Администратов', role: ROLES.ADMIN },
  user_sales: { id: 'user_sales', name: 'Мария Продажина', role: ROLES.SALES },
  user_acc: { id: 'user_acc', name: 'Пётр Бухгалтеров', role: ROLES.ACCOUNTING },
  user_view: { id: 'user_view', name: 'Анна Наблюдатова', role: ROLES.VIEWER },
};

/**
 * Middleware: аутентификация и прикрепление пользователя к запросу.
 *
 * Заголовок: X-User-Id: <userId>
 *
 * В Telegram Mini App заголовок заполняется на основе
 * проверенного initData (Telegram.WebApp.initData).
 * Для демо-режима принимается любой из DEMO_USERS.
 */
function authenticate(req, res, next) {
  const userId = req.headers['x-user-id'];

  if (!userId) {
    return res.status(401).json({ error: 'Не авторизован: отсутствует X-User-Id' });
  }

  const user = DEMO_USERS[userId];
  if (!user) {
    return res.status(401).json({ error: 'Пользователь не найден' });
  }

  // Прикрепляем пользователя и его права к объекту запроса
  req.user = user;
  req.userPermissions = getPermissionsForRole(user.role);
  next();
}

/**
 * Фабрика middleware для проверки конкретного права.
 * @param {string} permission - Название права из матрицы разрешений
 * @returns Express middleware
 */
function requirePermission(permission) {
  return (req, res, next) => {
    if (!req.userPermissions || !req.userPermissions[permission]) {
      return res.status(403).json({
        error: `Доступ запрещён: недостаточно прав (${permission})`,
      });
    }
    next();
  };
}

module.exports = { authenticate, requirePermission, DEMO_USERS };
