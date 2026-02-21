from __future__ import annotations

from datetime import date

import pytest

from app.logic import calculate_optimal_wakeup_time


def _record(d: date) -> dict:
    # Window target 07:30, minute-by-minute scoring should pick 07:18.
    return {
        "date": d.isoformat(),
        "hypnogram": [
            {"start_time": "06:50", "end_time": "07:00", "phase": "light"},
            {"start_time": "07:00", "end_time": "07:10", "phase": "deep"},
            {"start_time": "07:10", "end_time": "07:18", "phase": "rem"},
            {"start_time": "07:18", "end_time": "07:30", "phase": "light"},
            {"start_time": "07:30", "end_time": "07:40", "phase": "awake"},
        ],
    }


def test_calculate_optimal_wakeup_time_deterministic():
    historical = [_record(date(2026, 2, i)) for i in range(1, 8)]
    assert (
        calculate_optimal_wakeup_time(historical_records=historical, target_time_str="07:30")
        == "07:18"
    )


def test_calculate_optimal_wakeup_time_fallback_no_data():
    assert calculate_optimal_wakeup_time([], "07:30") == "07:30"


def test_calculate_optimal_wakeup_time_invalid_target():
    assert (
        calculate_optimal_wakeup_time([_record(date(2026, 2, 1))], "07-30") == "07-30"
    )

