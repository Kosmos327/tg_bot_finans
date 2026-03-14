"""
SQLAlchemy ORM models matching the PostgreSQL schema.

Tables:
  roles, warehouses, business_directions, deal_statuses, vat_types, sources,
  expense_categories_level_1, expense_categories_level_2,
  app_users, managers, clients, deals,
  billing_entries, expenses, journal_entries
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Reference / lookup tables
# ---------------------------------------------------------------------------


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    users: Mapped[list["AppUser"]] = relationship("AppUser", back_populates="role_obj")


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    billing_entries: Mapped[list["BillingEntry"]] = relationship(
        "BillingEntry", back_populates="warehouse"
    )


class BusinessDirection(Base):
    __tablename__ = "business_directions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class DealStatus(Base):
    __tablename__ = "deal_statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)


class VatType(Base):
    __tablename__ = "vat_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class ExpenseCategoryLevel1(Base):
    __tablename__ = "expense_categories_level_1"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    sub_categories: Mapped[list["ExpenseCategoryLevel2"]] = relationship(
        "ExpenseCategoryLevel2", back_populates="parent"
    )


class ExpenseCategoryLevel2(Base):
    __tablename__ = "expense_categories_level_2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("expense_categories_level_1.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    parent: Mapped["ExpenseCategoryLevel1"] = relationship(
        "ExpenseCategoryLevel1", back_populates="sub_categories"
    )


# ---------------------------------------------------------------------------
# Core entity tables
# ---------------------------------------------------------------------------


class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(200))
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    role_obj: Mapped["Role"] = relationship("Role", back_populates="users")


class Manager(Base):
    __tablename__ = "managers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    manager_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # FK to the roles table; nullable so managers can be created without an explicit role
    role_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("roles.id"))
    telegram_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    deals: Mapped[list["Deal"]] = relationship("Deal", back_populates="manager_obj")


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client_name: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    deals: Mapped[list["Deal"]] = relationship("Deal", back_populates="client_obj")
    billing_entries: Mapped[list["BillingEntry"]] = relationship(
        "BillingEntry", back_populates="client_obj"
    )


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    manager_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("managers.id")
    )
    client_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("clients.id")
    )
    status: Mapped[Optional[str]] = mapped_column(String(50))
    business_direction: Mapped[Optional[str]] = mapped_column(String(100))
    deal_name: Mapped[Optional[str]] = mapped_column(String(300))
    description: Mapped[Optional[str]] = mapped_column(Text)
    amount_with_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    vat_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    vat_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    amount_without_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    paid_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), default=0)
    remaining_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    variable_expense_1: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    variable_expense_2: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    production_expense: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    manager_bonus_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    manager_bonus_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    marginal_income: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    gross_profit: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    source: Mapped[Optional[str]] = mapped_column(String(100))
    document_url: Mapped[Optional[str]] = mapped_column(Text)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    act_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    date_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    date_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    manager_obj: Mapped[Optional["Manager"]] = relationship(
        "Manager", back_populates="deals"
    )
    client_obj: Mapped[Optional["Client"]] = relationship(
        "Client", back_populates="deals"
    )
    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="deal")


class BillingEntry(Base):
    __tablename__ = "billing_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("clients.id")
    )
    warehouse_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("warehouses.id")
    )
    month: Mapped[Optional[str]] = mapped_column(String(7))  # YYYY-MM
    period: Mapped[Optional[str]] = mapped_column(String(10))  # p1 / p2
    shipments_with_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    shipments_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    shipments_without_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    units_count: Mapped[Optional[int]] = mapped_column(Integer)
    storage_with_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    storage_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    storage_without_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    pallets_count: Mapped[Optional[int]] = mapped_column(Integer)
    returns_pickup_with_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    returns_pickup_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    returns_pickup_without_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    returns_trips_count: Mapped[Optional[int]] = mapped_column(Integer)
    additional_services_with_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    additional_services_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    additional_services_without_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    penalties: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    total_without_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    total_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    total_with_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    payment_status: Mapped[Optional[str]] = mapped_column(String(50))
    payment_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    payment_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client_obj: Mapped[Optional["Client"]] = relationship(
        "Client", back_populates="billing_entries"
    )
    warehouse: Mapped[Optional["Warehouse"]] = relationship(
        "Warehouse", back_populates="billing_entries"
    )


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    deal_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("deals.id"))
    category_level_1: Mapped[Optional[str]] = mapped_column(String(100))
    category_level_2: Mapped[Optional[str]] = mapped_column(String(100))
    expense_type: Mapped[Optional[str]] = mapped_column(String(50))
    amount_with_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    vat_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    vat_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    amount_without_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    deal: Mapped[Optional["Deal"]] = relationship("Deal", back_populates="expenses")


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(100))
    role_name: Mapped[Optional[str]] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity: Mapped[Optional[str]] = mapped_column(String(100))
    entity_id: Mapped[Optional[str]] = mapped_column(String(100))
    details: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
