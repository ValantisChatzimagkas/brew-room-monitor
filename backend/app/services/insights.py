"""What a batch's temperature history against its yeast range may mean for the beer.

Phases count hours since the batch's `started_at`. These constants are the only place the rules'
thresholds live; the frontend shows the numbers each note carries.
"""

from datetime import timedelta
from typing import NamedTuple

from app.models import NoteCode, TemperatureNote

EARLY_PHASE = timedelta(hours=72)  # readings before this are "early"; late_cold counts after it
LATE_WARM_FROM = timedelta(hours=96)
EARLY_WARM_MIN = timedelta(hours=6)
EARLY_HOT_MARGIN_C = 5.0
EARLY_HOT_MIN = timedelta(hours=2)
LATE_COLD_MIN = timedelta(hours=24)
SHARP_DROP_C = 4.0
SHARP_DROP_WINDOW = timedelta(hours=12)


class TemperatureStats(NamedTuple):
    """Totals over a batch's temperature_c readings, from one SQL row. Seconds are reading spans."""

    reading_count: int
    outside_count: int  # readings below the range's min or above its max
    below_s: float
    inside_s: float
    above_s: float
    early_above_s: float  # above max, recorded before EARLY_PHASE
    early_hot_s: float  # at or above max + EARLY_HOT_MARGIN_C, recorded before EARLY_PHASE
    late_below_s: float  # below min, recorded from EARLY_PHASE
    late_above_count: int  # readings above max, recorded from LATE_WARM_FROM
    late_above_s: float
    max_drop_c: float  # largest fall from the highest reading in the preceding SHARP_DROP_WINDOW


def temperature_notes(stats: TemperatureStats) -> list[TemperatureNote]:
    """The notes that apply, in a fixed order; [] without readings."""
    if stats.reading_count == 0:
        return []
    notes: list[TemperatureNote] = []

    def add(code: NoteCode, duration_s: float, delta_c: float | None = None) -> None:
        notes.append(TemperatureNote(code=code, duration_s=round(duration_s), delta_c=delta_c))

    # The stronger early finding replaces the weaker one: one note per finding.
    if stats.early_hot_s >= EARLY_HOT_MIN.total_seconds():
        add(NoteCode.EARLY_HOT, stats.early_hot_s, EARLY_HOT_MARGIN_C)
    elif stats.early_above_s >= EARLY_WARM_MIN.total_seconds():
        add(NoteCode.EARLY_WARM, stats.early_above_s)
    if stats.late_below_s >= LATE_COLD_MIN.total_seconds():
        add(NoteCode.LATE_COLD, stats.late_below_s)
    if stats.max_drop_c >= SHARP_DROP_C:
        add(NoteCode.SHARP_DROP, SHARP_DROP_WINDOW.total_seconds(), stats.max_drop_c)
    # Any late warm reading counts, even the newest one whose span is 0 s.
    if stats.late_above_count > 0:
        add(NoteCode.LATE_WARM, stats.late_above_s)
    if not notes and stats.outside_count == 0:
        add(NoteCode.IN_RANGE, stats.inside_s)
    return notes
