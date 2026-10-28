"""Database tables + API schemas.

Convention: `XBase` = shared fields, `X` (table=True) = DB row, `XCreate` / `XPublic` = API in/out.
Never return a table model with secrets (e.g. token_hash) directly from a route.
"""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import AwareDatetime, ConfigDict
from sqlalchemy import Column, DateTime, Index, String
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


def tz_column() -> Column[datetime]:
    """Every timestamp is timezone-aware UTC. Naive datetimes are a bug."""
    return Column(DateTime(timezone=True), nullable=False)


class DeviceKind(StrEnum):
    AMBIENT = "ambient"  # e.g. ESP32 + SHT/BME sensor on a shelf in the brew room
    IN_VESSEL = "in_vessel"  # capsule-style hydrometer floating in the fermenter


class Metric(StrEnum):
    """Unit is part of the name, so values are never ambiguous."""

    TEMPERATURE_C = "temperature_c"
    HUMIDITY_PCT = "humidity_pct"
    PRESSURE_HPA = "pressure_hpa"
    SPECIFIC_GRAVITY = "specific_gravity"
    BATTERY_V = "battery_v"


# --- Device ---------------------------------------------------------------


class DeviceBase(SQLModel):
    name: str = Field(min_length=1, max_length=64, unique=True)
    kind: DeviceKind = Field(sa_type=String(32))  # str, not PG enum: new values need no migration
    location: str = Field(default="", max_length=64)  # brewing room / fermenter label


class Device(DeviceBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(max_length=64, unique=True)
    created_at: datetime = Field(default_factory=utcnow, sa_column=tz_column())


class DeviceCreate(DeviceBase):
    pass


class DevicePublic(DeviceBase):
    id: int
    created_at: datetime


class DeviceCreated(DevicePublic):
    token: str  # plaintext, returned exactly once at creation


# --- Reading --------------------------------------------------------------


class Reading(SQLModel, table=True):
    __table_args__ = (Index("ix_reading_device_metric_time", "device_id", "metric", "recorded_at"),)

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="device.id", ondelete="CASCADE")
    metric: Metric = Field(sa_type=String(32))
    value: float
    recorded_at: datetime = Field(sa_column=tz_column())
    received_at: datetime = Field(default_factory=utcnow, sa_column=tz_column())


class ReadingIn(SQLModel):
    model_config = ConfigDict(allow_inf_nan=False)  # type: ignore[assignment]

    metric: Metric
    value: float
    # Optional: devices without NTP/RTC omit it and the server stamps receive time.
    recorded_at: AwareDatetime | None = None


class ReadingBatch(SQLModel):
    readings: list[ReadingIn] = Field(min_length=1, max_length=500)


class ReadingPublic(SQLModel):
    device_id: int
    metric: Metric
    value: float
    recorded_at: datetime


class IngestResult(SQLModel):
    accepted: int
