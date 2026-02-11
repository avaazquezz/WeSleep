from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import ValidationError

from app.models import CleanSleepData, WakeupPrediction, SleepPhase, SleepSegment

# --- Exceptions ---
class DataParsingError(Exception):
    """Excepción lanzada cuando ocurre un error crítico al parsear los datos."""
    pass

# --- Parser Logic ---

def parse_sleep_payload(payload: Dict[str, Any]) -> CleanSleepData:
    """
    Transforma un payload crudo (dict) en un objeto CleanSleepData.
    """
    try:
        # 1. Validación de campos críticos
        required_fields = ["start_at_timestamp", "end_at_timestamp", "duration", "metrics"]
        for field in required_fields:
            if field not in payload:
                raise DataParsingError(f"Campo crítico faltante: {field}")
        
        metrics = payload.get("metrics", {})
        if not isinstance(metrics, dict):
                raise DataParsingError("El campo 'metrics' debe ser un diccionario.")

        # 2. Extracción y Normalización (Mapping)
        
        # Cálculo de varianza de FC (var_HR)
        # Prioridad: var_HR explicito > hrv_sdnn como proxy > None
        hr_variance = metrics.get("hr_variance") 
        if hr_variance is None:
            hr_variance = metrics.get("hrv_sdnn") # Proxy
        
        # Movimiento Normalizado (0-1)
        movimiento: Optional[float] = None
        interruptions = metrics.get("sleep_interruptions")
        if interruptions is not None and isinstance(interruptions, (int, float)):
                movimiento = min(float(interruptions) / 20.0, 1.0) # E.g. 20 interrupciones = 1.0 (mucho movimiento)

        # Construcción del diccionario para CleanSleepData
        clean_data_dict = {
            # Tiempos
            "start_at_timestamp": payload["start_at_timestamp"],
            "end_at_timestamp": payload["end_at_timestamp"],
            "duration": payload["duration"],
            
            # Métricas Cardíacas
            "media_HR": metrics.get("heartrate"),
            "var_HR": hr_variance,
            "HRV": metrics.get("hrv_sdnn"),
            
            # Oxigenación
            "SpO2": metrics.get("spo2"),
            "SpO2_min": metrics.get("spo2_min"),
            "SpO2_max": metrics.get("spo2_max"),
            
            # Movimiento y Respiración
            "movimiento": movimiento,
            "breathing_rate": metrics.get("sleep_breathing_rate"),
            
            # Fases del Sueño (Default a 0 si no existen)
            "sleep_duration_deep": metrics.get("sleep_duration_deep") or 0,
            "sleep_duration_light": metrics.get("sleep_duration_light") or 0,
            "sleep_duration_rem": metrics.get("sleep_duration_rem") or 0,
            "sleep_duration_awake": metrics.get("sleep_duration_awake") or 0,
        }
        
        # 3. Creación y validación final del modelo Pydantic
        return CleanSleepData(**clean_data_dict)

    except (ValidationError, ValueError, TypeError) as e:
        raise DataParsingError(f"Error de validación al parsear datos: {str(e)}") from e
    except Exception as e:
        raise DataParsingError(f"Error inesperado en el parser: {str(e)}") from e


# --- Evaluator Logic ---

def calculate_sleep_score(data: CleanSleepData) -> float:
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
    # Note: CleanSleepData doesn't explicitly store time_in_bed, 
    # but we can infer it from start/end timestamps.
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

def detect_sleep_anomalies(data: CleanSleepData) -> List[str]:
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


# --- Smart Alarm Logic ---

def predict_optimal_wakeup(data: CleanSleepData, target_alarm_time: datetime) -> WakeupPrediction:
    """
    Estrategia v1: Heurística basada en fases de sueño y HRV.
    """
    WINDOW_MINUTES = 30
    HRV_THRESHOLD = 50.0

    # Aseguarnos de que target_alarm_time tenga timezone si los datos lo tienen
    if data.end_at_timestamp.tzinfo and not target_alarm_time.tzinfo:
            target_alarm_time = target_alarm_time.replace(tzinfo=timezone.utc)

    window_start = target_alarm_time - timedelta(minutes=WINDOW_MINUTES)
    window_end = target_alarm_time

    # 1. Validar si tenemos hipnograma
    if not data.hypnogram:
        return WakeupPrediction(
            suggested_time=target_alarm_time,
            confidence=0.0,
            reasoning="Faltan datos de fases de sueño (hypnogram empty). Se retorna hora objetivo."
        )

    # 2. Buscar segmentos dentro de la ventana
    relevant_segments = []
    for segment in data.hypnogram:
        if segment.end_at > window_start and segment.start_at < window_end:
            relevant_segments.append(segment)

    if not relevant_segments:
            return WakeupPrediction(
            suggested_time=target_alarm_time,
            confidence=0.1,
            reasoning="No hay datos de sueño dentro de la ventana de 30 min."
        )

    # 3. Identificar momentos 'aptos' (No DEEP)
    valid_slots: List[datetime] = []
    current_check = window_start
    while current_check <= window_end:
        # Check phase at current_check
        phase = None
        for seg in relevant_segments:
            if seg.start_at <= current_check < seg.end_at:
                phase = seg.phase
                break
        
        if phase != SleepPhase.DEEP:
            valid_slots.append(current_check)
        current_check += timedelta(minutes=1)

    if not valid_slots:
            return WakeupPrediction(
            suggested_time=target_alarm_time,
            confidence=0.5,
            reasoning="Usuario en sueño profundo durante toda la ventana. Se despierta a la hora límite."
        )

    # 4. Regla 3: HRV bajo -> Despertar antes
    hrv_val = data.HRV or 0.0
    is_stressed = hrv_val < HRV_THRESHOLD and hrv_val > 0 

    best_time = target_alarm_time
    reason = ""

    if is_stressed:
        best_time = valid_slots[0]
        reason = f"HRV bajo ({hrv_val}ms). Se prioriza despertar temprano ({best_time.strftime('%H:%M')}) para mitigar inercia."
    else:
        best_time = valid_slots[-1]
        reason = f"HRV normal. Se optimiza duración de sueño despertando en fase ligera/despierto a las {best_time.strftime('%H:%M')}."

    return WakeupPrediction(
        suggested_time=best_time,
        confidence=0.9,
        reasoning=reason
    )
