"""
Deal router for the Telegram bot (aiogram 3).

Commands
--------
/newdeal  — start the multi-step "create deal" flow
/updatedeal <ID> <field>=<value> ... — update specific fields of a deal
/getdeal <ID> — display all fields of a deal

The router uses :mod:`services.deal_service` for all Google Sheets
interactions.  Spreadsheet clients and worksheet references are resolved
via :func:`routers.deal_router.get_worksheets` which is intended to be
called once at startup (e.g. from ``bot.py``) and injected via
middleware or stored in ``bot.data``.
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from services import deal_service

log = logging.getLogger(__name__)

router = Router()


# ---------------------------------------------------------------------------
# FSM states for /newdeal
# ---------------------------------------------------------------------------


class NewDealForm(StatesGroup):
    name = State()
    client = State()
    amount = State()
    date = State()
    status = State()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIELD_PROMPTS = {
    NewDealForm.name: "Введите название сделки:",
    NewDealForm.client: "Введите имя клиента:",
    NewDealForm.amount: "Введите сумму сделки:",
    NewDealForm.date: "Введите дату создания (дд.мм.гггг):",
    NewDealForm.status: "Введите статус сделки (например: новая, в работе, закрыта):",
}

_FORM_FIELD_MAP = {
    "name": "Название",
    "client": "Клиент",
    "amount": "Сумма",
    "date": "Дата создания",
    "status": "Статус",
}


def _get_sheets(message: Message) -> tuple[Any, Any]:
    """Extract (deals_ws, journal_ws) from ``bot.data``."""
    data: dict = message.bot.data  # type: ignore[union-attr]
    return data["deals_ws"], data["journal_ws"]


def _get_config(message: Message) -> tuple[list[str], str]:
    """Return (required_fields, id_prefix) from ``bot.data``."""
    data: dict = message.bot.data  # type: ignore[union-attr]
    return data.get("required_fields", ["Название", "Клиент", "Сумма"]), data.get(
        "id_prefix", "DEAL-"
    )


# ---------------------------------------------------------------------------
# /newdeal
# ---------------------------------------------------------------------------


@router.message(Command("newdeal"))
async def cmd_new_deal(message: Message, state: FSMContext) -> None:
    await state.set_state(NewDealForm.name)
    await message.answer(_FIELD_PROMPTS[NewDealForm.name])


@router.message(NewDealForm.name)
async def process_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)
    await state.set_state(NewDealForm.client)
    await message.answer(_FIELD_PROMPTS[NewDealForm.client])


@router.message(NewDealForm.client)
async def process_client(message: Message, state: FSMContext) -> None:
    await state.update_data(client=message.text)
    await state.set_state(NewDealForm.amount)
    await message.answer(_FIELD_PROMPTS[NewDealForm.amount])


@router.message(NewDealForm.amount)
async def process_amount(message: Message, state: FSMContext) -> None:
    await state.update_data(amount=message.text)
    await state.set_state(NewDealForm.date)
    await message.answer(_FIELD_PROMPTS[NewDealForm.date])


@router.message(NewDealForm.date)
async def process_date(message: Message, state: FSMContext) -> None:
    await state.update_data(date=message.text)
    await state.set_state(NewDealForm.status)
    await message.answer(_FIELD_PROMPTS[NewDealForm.status])


@router.message(NewDealForm.status)
async def process_status(message: Message, state: FSMContext) -> None:
    fsm_data = await state.get_data()
    await state.clear()

    fsm_data["status"] = message.text
    deal_data = {_FORM_FIELD_MAP[k]: v for k, v in fsm_data.items()}

    deals_ws, journal_ws = _get_sheets(message)
    required_fields, id_prefix = _get_config(message)
    user = message.from_user.id if message.from_user else "unknown"

    try:
        new_id = deal_service.create_deal(
            deals_ws=deals_ws,
            journal_ws=journal_ws,
            data=deal_data,
            required_fields=required_fields,
            id_prefix=id_prefix,
            user=user,
        )
        await message.answer(f"✅ Сделка создана с ID: {new_id}")
    except ValueError as exc:
        await message.answer(f"❌ Ошибка: {exc}")
    except Exception as exc:
        log.exception("Ошибка при создании сделки: %s", exc)
        await message.answer("❌ Произошла ошибка при создании сделки.")


# ---------------------------------------------------------------------------
# /updatedeal <ID> <field>=<value> ...
# ---------------------------------------------------------------------------


@router.message(Command("updatedeal"))
async def cmd_update_deal(message: Message) -> None:
    if message.text is None:
        await message.answer("Использование: /updatedeal <ID> <поле>=<значение> ...")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /updatedeal <ID> <поле>=<значение> ...")
        return

    args = parts[1].split()
    if not args:
        await message.answer("Использование: /updatedeal <ID> <поле>=<значение> ...")
        return

    deal_id = args[0]
    updates: dict[str, str] = {}
    for token in args[1:]:
        if "=" not in token:
            await message.answer(
                f"❌ Неверный формат токена '{token}'. Ожидается поле=значение."
            )
            return
        key, _, value = token.partition("=")
        updates[key.strip()] = value.strip()

    if not updates:
        await message.answer("Укажите хотя бы одно поле для обновления.")
        return

    deals_ws, journal_ws = _get_sheets(message)
    user = message.from_user.id if message.from_user else "unknown"

    try:
        merged = deal_service.update_deal(
            deals_ws=deals_ws,
            journal_ws=journal_ws,
            deal_id=deal_id,
            updates=updates,
            user=user,
        )
        lines = [f"✅ Сделка {deal_id} обновлена:\n"]
        for k, v in merged.items():
            lines.append(f"  {k}: {v}")
        await message.answer("\n".join(lines))
    except KeyError as exc:
        await message.answer(f"❌ {exc}")
    except ValueError as exc:
        await message.answer(f"❌ {exc}")
    except Exception as exc:
        log.exception("Ошибка при обновлении сделки: %s", exc)
        await message.answer("❌ Произошла ошибка при обновлении сделки.")


# ---------------------------------------------------------------------------
# /getdeal <ID>
# ---------------------------------------------------------------------------


@router.message(Command("getdeal"))
async def cmd_get_deal(message: Message) -> None:
    if message.text is None:
        await message.answer("Использование: /getdeal <ID>")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /getdeal <ID>")
        return

    deal_id = parts[1]
    deals_ws, _ = _get_sheets(message)

    try:
        row = deal_service.get_deal(deals_ws=deals_ws, deal_id=deal_id)
        lines = [f"📄 Сделка {deal_id}:\n"]
        for k, v in row.items():
            if v:
                lines.append(f"  {k}: {v}")
        await message.answer("\n".join(lines))
    except KeyError as exc:
        await message.answer(f"❌ {exc}")
    except Exception as exc:
        log.exception("Ошибка при получении сделки: %s", exc)
        await message.answer("❌ Произошла ошибка при получении сделки.")
