from datetime import timedelta
from typing import List
from app.schemas.wearable import CleanSleepData, SleepPhase

class SleepEvaluator:
    """
    Evaluates sleep quality and detects anomalies based on heuristic rules.
    """

    def calculate_score(self, data: CleanSleepData) -> float:
        """
        Calculates a sleep quality score (0-100) based on weighted metrics:
        - 30% Duration (vs 8h)
        - 30% Deep Sleep (vs 15%)
        - 20% Efficiency (Sleep / Bed)
        - 20% HRV (Normalized)
        """
        score = 0.0

        # 1. Total Duration (30%)
        # Goal: 8 hours (480 mins). 
        # duration is in milliseconds
        total_minutes = data.duration / 1000 / 60
        ideal_duration = 480  # 8 hours
        if total_minutes >= ideal_duration:
            score += 30.0
        else:
            # Proportional score: (actual / ideal) * 30
            score += (total_minutes / ideal_duration) * 30.0

        # 2. Deep Sleep Ratio (30%)
        # Goal: > 15%. 
        if data.hypnogram:
            deep_duration = sum(
                (seg.end_at - seg.start_at).total_seconds() 
                for seg in data.hypnogram 
                if seg.phase == SleepPhase.DEEP
            )
            # duration is in ms
            total_duration_sec = data.duration / 1000
            if total_duration_sec > 0:
                deep_ratio = deep_duration / total_duration_sec
                ideal_ratio = 0.15
                
                if deep_ratio >= ideal_ratio:
                    score += 30.0
                else:
                    score += (deep_ratio / ideal_ratio) * 30.0
        else:
            # If no hypnogram, we can't score this part accurately. 
            pass

        # 3. Efficiency (20%)
        # Time Asleep / Time in Bed
        # We assume duration is time sleep. We need Time in Bed.
        time_in_bed_sec = (data.end_at_timestamp - data.start_at_timestamp).total_seconds()
        if time_in_bed_sec > 0:
            efficiency = (data.duration / 1000) / time_in_bed_sec
            # Cap at 1.0 just in case
            efficiency = min(efficiency, 1.0)
            score += efficiency * 20.0

        # 4. HRV (20%)
        # User: "Más alto es mejor".
        hrv_val = data.HRV or 0.0
        # If HRV is 0/None, score 0.
        if hrv_val > 0:
            # Cap at 100ms for full points
            normalized_hrv = min(hrv_val, 100.0) / 100.0
            score += normalized_hrv * 20.0

        return round(score, 1)

    def detect_anomalies(self, data: CleanSleepData) -> List[str]:
        """
        Returns a list of anomaly tags.
        """
        anomalies = []

        # 1. SpO2 < 90 -> Posible Apnea
        # Check SpO2_min if available, else SpO2 (avg)
        if data.SpO2_min and data.SpO2_min < 90:
             anomalies.append(f"Posible Apnea (SpO2 Min: {data.SpO2_min})")
        elif data.SpO2 and data.SpO2 < 90:
             anomalies.append(f"Posible Apnea (SpO2 Avg: {data.SpO2})")
        
        # 2. Interruptions > 10 -> Sueño Fragmentado
        # Need to count 'awake' segments in hypnogram
        if data.hypnogram:
            interruptions = sum(
                1 for seg in data.hypnogram 
                if seg.phase == SleepPhase.AWAKE
            )
            if interruptions > 10:
                anomalies.append(f"Sueño Fragmentado ({interruptions} despertares)")

        return anomalies
