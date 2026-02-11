from typing import Dict, Any, Optional
from datetime import datetime
from app.schemas.wearable import CleanSleepData
from pydantic import ValidationError

class DataParsingError(Exception):
    """Excepción lanzada cuando ocurre un error crítico al parsear los datos."""
    pass

class SleepDataParser:
    """
    Servicio de dominio para transformar y limpiar datos crudos de wearables.
    Patrón Adapter/Mapper.
    """

    @staticmethod
    def parse_payload(payload: Dict[str, Any]) -> CleanSleepData:
        """
        Transforma un payload crudo (dict) en un objeto CleanSleepData.
        
        Args:
            payload: Diccionario con los datos crudos (estructura WearableRawPayload).
            
        Returns:
            CleanSleepData: Objeto validado y normalizado.
            
        Raises:
            DataParsingError: Si faltan campos críticos o hay errores de validación.
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
            # Si sleep_interruptions existe, intentamos normalizarlo (asumiendo un max razonable o logica simple)
            # Por ahora, mapeamos directamente si es un valor pequeño, o null si no existe.
            # El requerimiento dice: "Inferir de metrics.sleep_interruptions (normalizado 0-1) o dejar null"
            # Asumiremos que si hay interrupciones, cada una cuenta como un 'evento'. 
            # Sin un maximo claro, este mapeo es subjetivo. 
            # Vamos a usar una logica simple: min(interruptions / 10, 1.0) par este MVP si no hay logica especifica.
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
