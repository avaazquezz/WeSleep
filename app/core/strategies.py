from abc import ABC, abstractmethod
from datetime import datetime
from pydantic import BaseModel
from app.schemas.wearable import CleanSleepData

class WakeupPrediction(BaseModel):
    """
    Resultado de la predicción del Smart Alarm.
    """
    suggested_time: datetime
    confidence: float  # 0.0 a 1.0
    reasoning: str

class SmartAlarmStrategy(ABC):
    """
    Interface abstracta para diferentes estrategias de Smart Alarm.
    """
    @abstractmethod
    def calculate_wakeup_window(self, data: CleanSleepData, target_alarm_time: datetime) -> WakeupPrediction:
        """
        Calcula el momento óptimo para despertar dado un registro de sueño y una hora objetivo.
        """
        pass
