"""
Manual / legacy tests for Smart Alarm heuristic logic.

Updated to work with the async predict_optimal_wakeup function.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import app.logic as logic
from app.models import CleanSleepData, SleepSegment, SleepPhase


@pytest.mark.asyncio
async def test_heuristic_alarm():
    """Verify heuristic alarm picks correct slots based on hypnogram and HRV."""
    target_time = datetime(2025, 4, 30, 7, 0, 0, tzinfo=timezone.utc)

    # Base Data
    base_data = CleanSleepData(
        start_at_timestamp=target_time - timedelta(hours=8),
        end_at_timestamp=target_time,
        duration=8 * 3600 * 1000,
        hypnogram=[],
        media_HR=60, var_HR=20, HRV=60,
        sleep_duration_deep=0, sleep_duration_light=0,
        sleep_duration_rem=0, sleep_duration_awake=0,
    )

    # Disable Gemini for all sub-tests so we get pure heuristic reasoning
    with patch("app.services.reasoning_service.settings") as ms:
        ms.GROQ_API_KEY = ""

        # Test 1: No Hypnogram → returns target time
        pred = await logic.predict_optimal_wakeup(base_data, target_time)
        assert pred.suggested_time == target_time

        # Test 2: All Deep Sleep → should wait until target
        deep_segment = SleepSegment(
            start_at=target_time - timedelta(minutes=40),
            end_at=target_time + timedelta(minutes=10),
            phase=SleepPhase.DEEP,
        )
        base_data.hypnogram = [deep_segment]
        pred = await logic.predict_optimal_wakeup(base_data, target_time)
        assert pred.suggested_time == target_time
        assert "sueño profundo" in pred.reasoning

        # Test 3: Light Sleep Available → should pick
        s1 = SleepSegment(
            start_at=target_time - timedelta(minutes=60),
            end_at=target_time - timedelta(minutes=15),
            phase=SleepPhase.DEEP,
        )
        s2 = SleepSegment(
            start_at=target_time - timedelta(minutes=15),
            end_at=target_time,
            phase=SleepPhase.LIGHT,
        )
        base_data.hypnogram = [s1, s2]
        base_data.HRV = 60
        pred = await logic.predict_optimal_wakeup(base_data, target_time)
        assert pred.suggested_time.minute == 0 or pred.suggested_time.minute == 59
        assert "optimiza duración" in pred.reasoning

        # Test 4: Low HRV → should pick earliest valid slot
        base_data.HRV = 30
        pred = await logic.predict_optimal_wakeup(base_data, target_time)
        assert pred.suggested_time.minute == 45
        assert "HRV bajo" in pred.reasoning
