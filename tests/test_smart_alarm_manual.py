import sys
import os
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.append(os.getcwd())

from app.services.smart_alarm import HeuristicAlarmStrategy
from app.schemas.wearable import CleanSleepData, SleepSegment, SleepPhase

def test_heuristic_alarm():
    strategy = HeuristicAlarmStrategy()
    target_time = datetime(2025, 4, 30, 7, 0, 0, tzinfo=timezone.utc)
    
    # Base Data
    base_data = CleanSleepData(
        start_at_timestamp=target_time - timedelta(hours=8),
        end_at_timestamp=target_time,
        duration=8*3600*1000,
        hypnogram=[],
        # Dummy required fields
        mean_HR=60, var_HR=20, HRV=60,
        sleep_duration_deep=0, sleep_duration_light=0, sleep_duration_rem=0, sleep_duration_awake=0
    )

    print("--- Test 1: No Hypnogram ---")
    pred = strategy.calculate_wakeup_window(base_data, target_time)
    print(f"Result: {pred.suggested_time}, Reason: {pred.reasoning}")
    assert pred.suggested_time == target_time

    print("\n--- Test 2: All Deep Sleep (Should wait) ---")
    deep_segment = SleepSegment(
        start_at=target_time - timedelta(minutes=40),
        end_at=target_time + timedelta(minutes=10),
        phase=SleepPhase.DEEP
    )
    base_data.hypnogram = [deep_segment]
    pred = strategy.calculate_wakeup_window(base_data, target_time)
    print(f"Result: {pred.suggested_time}, Reason: {pred.reasoning}")
    assert pred.suggested_time == target_time
    assert "sueño profundo" in pred.reasoning

    print("\n--- Test 3: Light Sleep Available (Should pick) ---")
    # 30 mins window: 6:30 - 7:00
    # Deep until 6:45, Light from 6:45 to 7:00
    s1 = SleepSegment(
        start_at=target_time - timedelta(minutes=60),
        end_at=target_time - timedelta(minutes=15), # 6:00 - 6:45
        phase=SleepPhase.DEEP
    )
    s2 = SleepSegment(
        start_at=target_time - timedelta(minutes=15), # 6:45
        end_at=target_time,                           # 7:00
        phase=SleepPhase.LIGHT
    )
    base_data.hypnogram = [s1, s2]
    # Reset HRV to normal
    base_data.HRV = 60
    
    pred = strategy.calculate_wakeup_window(base_data, target_time)
    print(f"Result: {pred.suggested_time}, Reason: {pred.reasoning}")
    # Should pick closest to 7:00 that is LIGHT -> 7:00 is valid (phase is None/Light boundary)
    assert pred.suggested_time.minute == 0 or pred.suggested_time.minute == 59
    assert "optimiza duración" in pred.reasoning

    print("\n--- Test 4: Low HRV (Should pick early) ---")
    base_data.HRV = 30 # Stress
    pred = strategy.calculate_wakeup_window(base_data, target_time)
    print(f"Result: {pred.suggested_time}, Reason: {pred.reasoning}")
    # Should pick earliest valid slot in window. Window starts 6:30.
    # Segments: Deep until 6:45. Light starting 6:45.
    # Earliest valid slot is 6:45.
    assert pred.suggested_time.minute == 45
    assert "HRV bajo" in pred.reasoning

    print("\n=== SUCCESS ===")

if __name__ == "__main__":
    test_heuristic_alarm()
