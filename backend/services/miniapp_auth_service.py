"""
miniapp_auth_service.py – PostgreSQL-based Mini App authentication service.

Handles:
  - Role validation and password check for miniapp-login
  - Create or update app_users record via public.upsert_app_user() SQL function
  - Manager auto-binding when role is 'manager'
  - Resolving the current user by telegram_id on protected endpoints

Uses public.upsert_app_user() as the authoritative write path for app_users.
ORM-based helpers are kept for read-only lookups (get_user_by_telegram_id).
"""

import logging
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AppUser, Manager, Role
from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Role password validation
# ---------------------------------------------------------------------------

_ROLE_PASSWORD_MAP = {
    "manager": "role_password_manager",
    "operations_director": "role_password_operations_director",
    "accounting": "role_password_accounting",
    "admin": "role_password_admin",
}


def _verify_role_password(selected_role: str, password: str) -> bool:
    """
    Verify the password for a given role using env-backed settings.

    Returns True if the password matches, False otherwise.
    An empty configured password always fails (role not yet set up).
    """
    attr = _ROLE_PASSWORD_MAP.get(selected_role)
    if attr is None:
        logger.warning("Unknown role for password check: %r", selected_role)
        return False
    expected = getattr(settings, attr, "")
    if not expected:
        logger.warning(
            "No password configured for role %r (env var is empty). "
            "Set ROLE_PASSWORD_%s to enable login.",
            selected_role,
            selected_role.upper(),
        )
        return False
    return password == expected


# ---------------------------------------------------------------------------
# Core login logic
# ---------------------------------------------------------------------------


async def miniapp_login(
    db: AsyncSession,
    telegram_id: int,
    full_name: str,
    username: Optional[str],
    selected_role: str,
    password: str,
) -> dict:
    """
    Full Mini App login flow:

    1. Validate selected_role exists in the roles table (by code).
    2. Validate password against env-configured role password.
    3. Create or update app_users record.
    4. If role is 'manager', ensure a matching managers record exists.
    5. Return a dict with user info for the Mini App response.

    Raises:
        ValueError: if the selected_role does not exist in the roles table.
        PermissionError: if the password is invalid for the selected role.
    """
    logger.info(
        "miniapp_login attempt: telegram_id=%s selected_role=%r",
        telegram_id,
        selected_role,
    )

    # Step 1 – validate role exists in DB
    role_obj = await _get_role_by_code(db, selected_role)
    if role_obj is None:
        logger.warning(
            "Login denied: role code %r not found in roles table. telegram_id=%s",
            selected_role,
            telegram_id,
        )
        raise ValueError(f"Role '{selected_role}' does not exist")

    # Step 2 – validate password
    if not _verify_role_password(selected_role, password):
        logger.warning(
            "Login denied: invalid password for role %r. telegram_id=%s",
            selected_role,
            telegram_id,
        )
        raise PermissionError(f"Invalid password for role '{selected_role}'")

    # Step 3 – upsert app_users via SQL function (authoritative write path)
    app_user = await _upsert_app_user_sql(
        db,
        telegram_id=telegram_id,
        full_name=full_name,
        username=username,
        role_code=selected_role,
    )

    # Step 4 – manager auto-binding
    if selected_role == "manager":
        await _ensure_manager_record(
            db,
            telegram_id=telegram_id,
            full_name=full_name,
            role_id=role_obj.id,
        )

    logger.info(
        "miniapp_login success: telegram_id=%s app_user_id=%s role=%r",
        telegram_id,
        app_user.id,
        selected_role,
    )

    return {
        "user_id": app_user.id,
        "telegram_id": app_user.telegram_id,
        "full_name": app_user.full_name,
        "username": app_user.username,
        "role": selected_role,
    }


# ---------------------------------------------------------------------------
# Current user resolution (used by protected endpoints)
# ---------------------------------------------------------------------------


async def get_user_by_telegram_id(
    db: AsyncSession,
    telegram_id: int,
) -> Optional[AppUser]:
    """
    Resolve the current app user from app_users by telegram_id.

    Returns the AppUser ORM instance (with role_obj loaded) if found and
    is_active=True, or None otherwise.

    Logs the outcome for production debugging.
    """
    logger.debug("Resolving app_user for telegram_id=%s", telegram_id)

    result = await db.execute(
        select(AppUser).where(AppUser.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        logger.info(
            "User resolution: telegram_id=%s NOT FOUND in app_users → deny",
            telegram_id,
        )
        return None

    if not user.is_active:
        logger.info(
            "User resolution: telegram_id=%s app_user_id=%s is_active=False → deny",
            telegram_id,
            user.id,
        )
        return None

    # Eagerly load role
    role_code = await _get_role_code_by_id(db, user.role_id)
    logger.info(
        "User resolution: telegram_id=%s app_user_id=%s role_id=%s role=%r → allow",
        telegram_id,
        user.id,
        user.role_id,
        role_code,
    )
    return user


async def get_role_code(db: AsyncSession, role_id: int) -> Optional[str]:
    """Return the role code string for a given role_id, or None."""
    return await _get_role_code_by_id(db, role_id)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _get_role_by_code(db: AsyncSession, code: str) -> Optional[Role]:
    result = await db.execute(select(Role).where(Role.code == code))
    return result.scalar_one_or_none()


async def _get_role_code_by_id(db: AsyncSession, role_id: int) -> Optional[str]:
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    return role.code if role else None


async def _upsert_app_user(
    db: AsyncSession,
    telegram_id: int,
    full_name: str,
    username: Optional[str],
    role_id: int,
) -> AppUser:
    """Create or update an app_users record. Returns the ORM instance."""
    result = await db.execute(
        select(AppUser).where(AppUser.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = AppUser(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            role_id=role_id,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        logger.info(
            "app_users: created new record id=%s telegram_id=%s role_id=%s",
            user.id,
            telegram_id,
            role_id,
        )
    else:
        user.full_name = full_name
        user.username = username
        user.role_id = role_id
        user.is_active = True
        await db.flush()
        await db.refresh(user)
        logger.info(
            "app_users: updated record id=%s telegram_id=%s role_id=%s",
            user.id,
            telegram_id,
            role_id,
        )

    return user


async def _upsert_app_user_sql(
    db: AsyncSession,
    telegram_id: int,
    full_name: str,
    username: Optional[str],
    role_code: str,
) -> AppUser:
    """
    Create or update an app_users record via the public.upsert_app_user() SQL function.

    Falls back to the ORM-based _upsert_app_user() if the SQL function is not
    available (e.g. during tests with a bare schema).
    Returns the ORM AppUser instance.
    """
    try:
        result = await db.execute(
            text(
                "SELECT * FROM public.upsert_app_user("
                ":p_telegram_id, :p_full_name, :p_username, :p_role_code"
                ")"
            ),
            {
                "p_telegram_id": telegram_id,
                "p_full_name": full_name,
                "p_username": username,
                "p_role_code": role_code,
            },
        )
        row = result.fetchone()
        if row is not None:
            # Reload the ORM object so callers get a proper AppUser instance.
            # The public.upsert_app_user() function is expected to return the
            # upserted row with an 'id' column (the app_users primary key).
            # We also check 'user_id' as an alternative column name for resilience
            # in case the function is redefined with a different output column name.
            mapping = dict(row._mapping)
            user_id = mapping.get("id") or mapping.get("user_id")
            if user_id:
                orm_result = await db.execute(
                    select(AppUser).where(AppUser.id == user_id)
                )
                user = orm_result.scalar_one_or_none()
                if user:
                    logger.info(
                        "app_users: upserted via SQL function id=%s telegram_id=%s role=%r",
                        user.id,
                        telegram_id,
                        role_code,
                    )
                    return user
    except Exception as exc:
        is_prod = getattr(settings, "app_env", "development").lower() == "production"
        if is_prod:
            # In production, the SQL function is required. Return a clear error
            # instead of silently falling back to ORM, which may bypass business rules.
            logger.error(
                "upsert_app_user SQL function failed in production (%s). "
                "Ensure public.upsert_app_user() is deployed on the database.",
                exc,
            )
            raise RuntimeError(
                "Login unavailable: public.upsert_app_user() SQL function is not accessible. "
                "Contact your database administrator."
            ) from exc
        logger.warning(
            "upsert_app_user SQL function unavailable (%s), falling back to ORM "
            "(allowed in %s environment only)",
            exc,
            getattr(settings, "app_env", "development"),
        )

    # Fallback: resolve role_id from ORM and use ORM upsert
    role_obj = await _get_role_by_code(db, role_code)
    role_id = role_obj.id if role_obj else 1
    return await _upsert_app_user(db, telegram_id, full_name, username, role_id)


async def _ensure_manager_record(
    db: AsyncSession,
    telegram_id: int,
    full_name: str,
    role_id: int,
) -> Manager:
    """Create or update a managers record for the given telegram_id."""
    result = await db.execute(
        select(Manager).where(Manager.telegram_user_id == telegram_id)
    )
    manager = result.scalar_one_or_none()

    if manager is None:
        manager = Manager(
            manager_name=full_name,
            role_id=role_id,
            telegram_user_id=telegram_id,
        )
        db.add(manager)
        await db.flush()
        await db.refresh(manager)
        logger.info(
            "managers: created new record id=%s telegram_user_id=%s",
            manager.id,
            telegram_id,
        )
    else:
        updated = False
        if manager.manager_name != full_name:
            manager.manager_name = full_name
            updated = True
        if manager.role_id != role_id:
            manager.role_id = role_id
            updated = True
        if updated:
            await db.flush()
            await db.refresh(manager)
            logger.info(
                "managers: updated record id=%s telegram_user_id=%s",
                manager.id,
                telegram_id,
            )
        else:
            logger.debug(
                "managers: no changes needed for telegram_user_id=%s",
                telegram_id,
            )

    return manager
