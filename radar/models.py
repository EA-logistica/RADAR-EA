from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Text, Date, DateTime, Numeric, JSON, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from radar.db import Base

def now():
    return datetime.now(timezone.utc)

class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))
    parameters: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)

class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(60))
    url: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    period: Mapped[dict] = mapped_column(JSON, default=dict)
    bytes: Mapped[int]

class Operation(Base):
    __tablename__ = "operations"
    id: Mapped[int] = mapped_column(primary_key=True)
    country: Mapped[str] = mapped_column(String(2), default="PE")
    regime: Mapped[str] = mapped_column(String(2), default="10")
    customs: Mapped[str] = mapped_column(String(3))
    year: Mapped[int]
    declaration: Mapped[str] = mapped_column(String(8))
    series: Mapped[int]
    numbered_on: Mapped[date] = mapped_column(Date, index=True)
    importer_ruc: Mapped[str | None] = mapped_column(String(11), index=True)
    importer: Mapped[str | None] = mapped_column(Text)
    supplier: Mapped[str | None] = mapped_column(Text)
    supplier_status: Mapped[str] = mapped_column(String(30), default="unavailable")
    origin: Mapped[str | None] = mapped_column(String(3), index=True)
    acquisition_country: Mapped[str | None] = mapped_column(String(3))
    hs_code: Mapped[str] = mapped_column(String(10), index=True)
    description: Mapped[str] = mapped_column(Text)
    plastics_scope: Mapped[bool] = mapped_column(default=True, index=True)
    material: Mapped[str] = mapped_column(String(30), index=True)
    classification_reason: Mapped[str] = mapped_column(Text)
    needs_review: Mapped[bool] = mapped_column(default=False)
    classification_locked: Mapped[bool] = mapped_column(default=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(22,6))
    unit: Mapped[str | None] = mapped_column(String(20))
    net_kg: Mapped[Decimal | None] = mapped_column(Numeric(22,6))
    kg_method: Mapped[str | None] = mapped_column(Text)
    fob_usd: Mapped[Decimal | None] = mapped_column(Numeric(22,6))
    freight_usd: Mapped[Decimal | None] = mapped_column(Numeric(22,6))
    insurance_usd: Mapped[Decimal | None] = mapped_column(Numeric(22,6))
    cif_usd: Mapped[Decimal | None] = mapped_column(Numeric(22,6))
    usd_kg: Mapped[Decimal | None] = mapped_column(Numeric(22,8))
    search_text: Mapped[str] = mapped_column(Text)
    quality_flags: Mapped[list] = mapped_column(JSON, default=list)
    raw: Mapped[dict] = mapped_column(JSON)
    record_hash: Mapped[str] = mapped_column(String(64))
    source_priority: Mapped[int] = mapped_column(default=10)
    source_modified_on: Mapped[date | None] = mapped_column(Date)
    source_url: Mapped[str] = mapped_column(Text)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("country","regime","customs","year","declaration","series", name="uq_operation"),)

class Revision(Base):
    __tablename__ = "revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    operation_id: Mapped[int] = mapped_column(ForeignKey("operations.id"), index=True)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"))
    record_hash: Mapped[str] = mapped_column(String(64))
    raw: Mapped[dict] = mapped_column(JSON)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("operation_id","record_hash", name="uq_revision"),)

class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    operation_id: Mapped[int] = mapped_column(ForeignKey("operations.id"), index=True)
    previous_material: Mapped[str] = mapped_column(String(30))
    material: Mapped[str] = mapped_column(String(30))
    note: Mapped[str] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(100), unique=True)
    kind: Mapped[str] = mapped_column(String(30))
    operation_id: Mapped[int] = mapped_column(ForeignKey("operations.id"))
    title: Mapped[str] = mapped_column(Text)
    detail: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    read: Mapped[bool] = mapped_column(default=False)

Index("ix_operations_importer_date", Operation.importer_ruc, Operation.numbered_on)
