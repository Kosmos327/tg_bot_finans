"""CRUD operations for billing entries."""

from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import BillingEntry
from app.database.schemas import BillingCreate

_VAT_RATE = Decimal("0.20")


def _calc_vat_fields(entry: BillingEntry) -> None:
    """Auto-calculate VAT breakdown and totals for billing entry."""
    def _breakdown(with_vat_attr: str, vat_attr: str, without_vat_attr: str) -> None:
        with_vat = getattr(entry, with_vat_attr) or Decimal("0")
        without_vat = round(with_vat / (1 + _VAT_RATE), 2)
        vat_val = round(with_vat - without_vat, 2)
        setattr(entry, without_vat_attr, without_vat)
        setattr(entry, vat_attr, vat_val)

    _breakdown("shipments_with_vat", "shipments_vat", "shipments_without_vat")
    _breakdown("storage_with_vat", "storage_vat", "storage_without_vat")
    _breakdown(
        "returns_pickup_with_vat", "returns_pickup_vat", "returns_pickup_without_vat"
    )
    _breakdown(
        "additional_services_with_vat",
        "additional_services_vat",
        "additional_services_without_vat",
    )

    penalties = entry.penalties or Decimal("0")
    entry.total_without_vat = round(
        (entry.shipments_without_vat or Decimal("0"))
        + (entry.storage_without_vat or Decimal("0"))
        + (entry.returns_pickup_without_vat or Decimal("0"))
        + (entry.additional_services_without_vat or Decimal("0"))
        - penalties,
        2,
    )
    entry.total_vat = round(
        (entry.shipments_vat or Decimal("0"))
        + (entry.storage_vat or Decimal("0"))
        + (entry.returns_pickup_vat or Decimal("0"))
        + (entry.additional_services_vat or Decimal("0")),
        2,
    )
    entry.total_with_vat = round(
        (entry.total_without_vat or Decimal("0"))
        + (entry.total_vat or Decimal("0")),
        2,
    )


async def create_billing(db: AsyncSession, data: BillingCreate) -> BillingEntry:
    entry = BillingEntry(**data.model_dump(exclude_none=True))
    _calc_vat_fields(entry)
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


async def get_billing_entries(
    db: AsyncSession, skip: int = 0, limit: int = 200
) -> Sequence[BillingEntry]:
    result = await db.execute(select(BillingEntry).offset(skip).limit(limit))
    return result.scalars().all()


async def get_billing_entry(
    db: AsyncSession, entry_id: int
) -> Optional[BillingEntry]:
    result = await db.execute(
        select(BillingEntry).where(BillingEntry.id == entry_id)
    )
    return result.scalar_one_or_none()
