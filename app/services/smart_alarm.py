from datetime import datetime, timedelta, timezone
from typing import List, Optional
from app.core.strategies import SmartAlarmStrategy, WakeupPrediction
from app.schemas.wearable import CleanSleepData, SleepPhase, SleepSegment

class HeuristicAlarmStrategy(SmartAlarmStrategy):
    """
    Estrategia v1: Heurística basada en fases de sueño y HRV.
    """
    
    WINDOW_MINUTES = 30
    HRV_THRESHOLD = 50.0  # ms. Umbral arbitrario para 'stress alto'

    def calculate_wakeup_window(self, data: CleanSleepData, target_alarm_time: datetime) -> WakeupPrediction:
        # Aseguarnos de que target_alarm_time tenga timezone si los datos lo tienen
        if data.end_at_timestamp.tzinfo and not target_alarm_time.tzinfo:
             target_alarm_time = target_alarm_time.replace(tzinfo=timezone.utc) # Asumimos UTC si no hay info

        window_start = target_alarm_time - timedelta(minutes=self.WINDOW_MINUTES)
        window_end = target_alarm_time

        # 1. Validar si tenemos hipnograma
        if not data.hypnogram:
            return WakeupPrediction(
                suggested_time=target_alarm_time,
                confidence=0.0,
                reasoning="Faltan datos de fases de sueño (hypnogram empty). Se retorna hora objetivo."
            )

        # 2. Buscar segmentos dentro de la ventana
        # Filtramos segmentos que se solapan con [window_start, window_end]
        relevant_segments = []
        for segment in data.hypnogram:
            # Check overlap
            if segment.end_at > window_start and segment.start_at < window_end:
                relevant_segments.append(segment)

        if not relevant_segments:
             return WakeupPrediction(
                suggested_time=target_alarm_time,
                confidence=0.1,
                reasoning="No hay datos de sueño dentro de la ventana de 30 min."
            )

        # 3. Identificar momentos 'aptos' (No DEEP)
        # Discretizamos la ventana minuto a minuto para simplificar la lógica de busqueda
        valid_slots: List[datetime] = []
        current_check = window_start
        while current_check <= window_end:
            phase = self._get_phase_at(current_check, relevant_segments)
            # Regla 1: Evitar DEEP
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
        is_stressed = hrv_val < self.HRV_THRESHOLD and hrv_val > 0 # Si hrv es 0 o None, ignoramos esta regla o asumimos normal

        best_time = target_alarm_time
        reason = ""

        if is_stressed:
            # Priorizamos el PRIMER momento válido (para maximizar tiempo post-despertar?)
            # Prompt: "Si HRV es bajo... intentar despertar antes para evitar inercia"
            # Interpretación: Despertar lo antes posible dentro de la ventana válida.
            best_time = valid_slots[0]
            reason = f"HRV bajo ({hrv_val}ms). Se prioriza despertar temprano ({best_time.strftime('%H:%M')}) para mitigar inercia."
        else:
            # Comportamiento normal: Dormir lo más posible (ÚLTIMO slot válido)
            best_time = valid_slots[-1]
            reason = f"HRV normal. Se optimiza duración de sueño despertando en fase ligera/despierto a las {best_time.strftime('%H:%M')}."

        return WakeupPrediction(
            suggested_time=best_time,
            confidence=0.9,
            reasoning=reason
        )

    def _get_phase_at(self, time: datetime, segments: List[SleepSegment]) -> Optional[SleepPhase]:
        for seg in segments:
            if seg.start_at <= time < seg.end_at:
                return seg.phase
        return None
