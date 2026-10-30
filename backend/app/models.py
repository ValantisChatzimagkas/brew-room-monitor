"""Database tables + API schemas.

Convention: `XBase` = shared fields, `X` (table=True) = DB row, `XCreate` / `XPublic` = API in/out.
Never return a table model with secrets (e.g. token_hash) directly from a route.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import NamedTuple, Self

from pydantic import AwareDatetime, ConfigDict, model_validator
from sqlalchemy import Column, DateTime, Index, String, func, text
from sqlmodel import Field, Relationship, SQLModel


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


class MetricSpec(NamedTuple):
    kinds: frozenset[DeviceKind]  # which device kinds may send this metric
    min_value: float  # inclusive. Sensor-rated, not brewing, range: a 422 drops the whole batch
    max_value: float  # inclusive


def metric_spec(metric: Metric) -> MetricSpec:
    # No `case _`: mypy then fails here when a Metric member has no spec.
    match metric:
        case Metric.TEMPERATURE_C:
            return MetricSpec(
                kinds=frozenset({DeviceKind.AMBIENT, DeviceKind.IN_VESSEL}),
                min_value=-40,
                max_value=125,
            )
        case Metric.HUMIDITY_PCT:
            return MetricSpec(kinds=frozenset({DeviceKind.AMBIENT}), min_value=0, max_value=100)
        case Metric.PRESSURE_HPA:
            return MetricSpec(kinds=frozenset({DeviceKind.AMBIENT}), min_value=300, max_value=1100)
        case Metric.SPECIFIC_GRAVITY:
            return MetricSpec(
                kinds=frozenset({DeviceKind.IN_VESSEL}), min_value=0.980, max_value=1.200
            )
        case Metric.BATTERY_V:
            return MetricSpec(
                kinds=frozenset({DeviceKind.AMBIENT, DeviceKind.IN_VESSEL}),
                min_value=0,
                max_value=5.5,
            )


# --- Location -------------------------------------------------------------


class LocationBase(SQLModel):
    name: str = Field(min_length=1, max_length=64)  # a room, e.g. "garage"


class Location(LocationBase, table=True):
    # "Garage" and "garage" are the same room.
    __table_args__ = (Index("uq_location_name_lower", func.lower(text("name")), unique=True),)

    id: int | None = Field(default=None, primary_key=True)


class LocationCreate(LocationBase):
    model_config = ConfigDict(str_strip_whitespace=True)  # type: ignore[assignment]


class LocationPublic(LocationBase):
    id: int


# --- Device ---------------------------------------------------------------


class DeviceBase(SQLModel):
    name: str = Field(min_length=1, max_length=64, unique=True)
    kind: DeviceKind = Field(sa_type=String(32))  # str, not PG enum: new values need no migration
    # Nullable in the DB so pre-location ambient rows stay valid; the API requires it on create.
    location_id: int | None = Field(default=None, foreign_key="location.id", ondelete="RESTRICT")


class Device(DeviceBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(max_length=64, unique=True)
    created_at: datetime = Field(default_factory=utcnow, sa_column=tz_column())

    location: Location | None = Relationship()


class DeviceCreate(DeviceBase):
    @model_validator(mode="after")
    def _ambient_needs_location(self) -> Self:
        # An ambient device measures a room; an in-vessel one gets its place from the vessel later.
        if self.kind == DeviceKind.AMBIENT and self.location_id is None:
            raise ValueError("ambient devices need a location_id")
        return self


class DeviceUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    location_id: int | None = None

    @model_validator(mode="after")
    def _name_not_null(self) -> Self:
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        return self


class DevicePublic(DeviceBase):
    id: int
    created_at: datetime
    location: LocationPublic | None


class DeviceCreated(DevicePublic):
    token: str  # plaintext, returned exactly once at creation


# --- Reading --------------------------------------------------------------


class Reading(SQLModel, table=True):
    __table_args__ = (
        Index("ix_reading_device_metric_time", "device_id", "metric", "recorded_at"),
        # Dedupes resent backlogs. Server-stamped readings (recorded_at == received_at) are
        # exempt: they share one `now` per batch, so two clockless same-metric readings would clash.
        Index(
            "uq_reading_device_metric_time",
            "device_id",
            "metric",
            "recorded_at",
            unique=True,
            postgresql_where=text("recorded_at <> received_at"),
        ),
    )

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

    @model_validator(mode="after")
    def _value_in_range(self) -> Self:
        spec = metric_spec(self.metric)
        if not spec.min_value <= self.value <= spec.max_value:
            raise ValueError(f"{self.metric} must be between {spec.min_value} and {spec.max_value}")
        return self


class ReadingBatch(SQLModel):
    readings: list[ReadingIn] = Field(min_length=1, max_length=500)


class ReadingPublic(SQLModel):
    device_id: int
    metric: Metric
    value: float
    recorded_at: datetime


class IngestResult(SQLModel):
    accepted: int
