"""
AI service for generating personalized sleep analysis reasoning.

Uses Groq's free API with Llama 3.3 70B — the highest quality
open-source model available, with the fastest inference on the market.

Fallback strategy: if Groq is unavailable or the API key is not set,
the function silently returns the heuristic reasoning so the Smart Alarm
feature continues to work without interruption.

Why Groq + Llama 3.3 70B:
  - 100% free tier (30 RPM, 14,400 RPD, 6,000 tokens/min)
  - Llama 3.3 70B quality rivals GPT-4 on reasoning tasks
  - Groq's LPU delivers ~500 tokens/sec — real-time responses
"""
import logging
from typing import Any, List

from groq import AsyncGroq

from app.config import settings
from app.models import CleanSleepData

logger = logging.getLogger(__name__)

# Llama 3.3 70B — best open-source model for reasoning tasks
_MODEL = "llama-3.3-70b-versatile"

_WEEKLY_RECAP_SYSTEM_PROMPT = (
    "Eres un coach de bienestar. Analiza la comparativa de dos semanas de sueño. "
    "Da un resumen breve (3 líneas), motivador y amigable. NUNCA diagnostiques."
)

_MONTHLY_ALERT_SYSTEM_PROMPT = (
    "Eres un sistema de alerta temprana B2B para una mutua de salud. NUNCA "
    "DIAGNOSTIQUES. Analiza tendencias de 30 días. Si detectas una caída sostenida "
    ">15% en HRV o eficiencia de sueño, redacta una advertencia MUY FORMAL y seria "
    "recomendando encarecidamente agendar una revisión con un especialista médico "
    "de su mutua. Si no hay caída grave, devuelve un string vacío (no hay alerta)."
)

_PREVENTIVE_FALLBACK = "Métricas procesadas. Consulta tu historial completo en el dashboard."


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    if previous == 0:
        return None
    return ((current - previous) / previous) * 100.0


def _fmt(value: float | None, unit: str = "") -> str:
    if value is None:
        return "N/D"
    if unit:
        return f"{value:.2f}{unit}"
    return f"{value:.2f}"


def _clean_to_max_4_lines(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    return "\n".join(lines[:4])


class AISleepAnalyzer:
    def __init__(self, *, model: str = _MODEL, api_key: str | None = None) -> None:
        self._model = model
        self._api_key = api_key if api_key is not None else settings.GROQ_API_KEY

    async def _call_groq(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_completion_tokens: int,
    ) -> str:
        if not self._api_key:
            return ""

        try:
            client = AsyncGroq(api_key=self._api_key)
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_completion_tokens=max_completion_tokens,
            )

            generated_text = (
                response.choices[0].message.content.strip() if response.choices else ""
            )
            return generated_text
        except Exception as exc:
            logger.error("Error al llamar a Groq API (ai): %s", exc, exc_info=True)
            return ""

    async def generate_weekly_recap(
        self,
        current_week: dict[str, Any],
        prev_week: dict[str, Any],
    ) -> str:
        if not self._api_key:
            return _PREVENTIVE_FALLBACK

        current_hrv = (
            float(current_week["hrv_avg"]) if current_week.get("hrv_avg") is not None else None
        )
        prev_hrv = float(prev_week["hrv_avg"]) if prev_week.get("hrv_avg") is not None else None
        current_deep = (
            float(current_week["deep_minutes_avg"])
            if current_week.get("deep_minutes_avg") is not None
            else None
        )
        prev_deep = (
            float(prev_week["deep_minutes_avg"]) if prev_week.get("deep_minutes_avg") is not None else None
        )

        hrv_pct = _pct_change(current_hrv, prev_hrv)
        deep_pct = _pct_change(current_deep, prev_deep)

        current_eff = (
            float(current_week["efficiency_avg"])
            if current_week.get("efficiency_avg") is not None
            else None
        )
        prev_eff = (
            float(prev_week["efficiency_avg"]) if prev_week.get("efficiency_avg") is not None else None
        )
        eff_pct = _pct_change(current_eff, prev_eff)

        user_prompt = "\n".join(
            [
                "Comparativa de dos semanas de sueño (valores medios):",
                f"- HRV anterior: {_fmt(prev_hrv, ' ms')} | HRV actual: {_fmt(current_hrv, ' ms')} | Δ%: {_fmt(hrv_pct, '%')}",
                f"- Deep anterior: {_fmt(prev_deep, ' min')} | Deep actual: {_fmt(current_deep, ' min')} | Δ%: {_fmt(deep_pct, '%')}",
                f"- Eficiencia anterior: {_fmt(prev_eff)} | Eficiencia actual: {_fmt(current_eff)} | Δ%: {_fmt(eff_pct, '%')}",
            ]
        )

        generated = await self._call_groq(
            system_prompt=_WEEKLY_RECAP_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.4,
            max_completion_tokens=160,
        )
        if not generated.strip():
            return _PREVENTIVE_FALLBACK

        lines = [ln.strip() for ln in generated.splitlines() if ln.strip()]
        return "\n".join(lines[:3]) if lines else _PREVENTIVE_FALLBACK

    async def generate_monthly_anomaly_alert(
        self,
        current_month: dict[str, Any],
        baseline_month: dict[str, Any],
    ) -> str:
        if not self._api_key:
            return ""

        current_hrv = (
            float(current_month["hrv_avg"])
            if current_month.get("hrv_avg") is not None
            else None
        )
        baseline_hrv = (
            float(baseline_month["hrv_avg"])
            if baseline_month.get("hrv_avg") is not None
            else None
        )
        current_eff = (
            float(current_month["efficiency_avg"])
            if current_month.get("efficiency_avg") is not None
            else None
        )
        baseline_eff = (
            float(baseline_month["efficiency_avg"])
            if baseline_month.get("efficiency_avg") is not None
            else None
        )

        hrv_pct = _pct_change(current_hrv, baseline_hrv)
        eff_pct = _pct_change(current_eff, baseline_eff)

        # Hard gate to avoid false positives and unnecessary Groq calls.
        severe_hrv = hrv_pct is not None and hrv_pct <= -15.0
        severe_eff = eff_pct is not None and eff_pct <= -15.0
        if not (severe_hrv or severe_eff):
            return ""

        user_prompt = "\n".join(
            [
                "Comparativa 30 días vs 30 días anteriores (valores medios):",
                f"- HRV baseline: {_fmt(baseline_hrv, ' ms')} | HRV actual: {_fmt(current_hrv, ' ms')} | Δ%: {_fmt(hrv_pct, '%')}",
                f"- Eficiencia baseline: {_fmt(baseline_eff)} | Eficiencia actual: {_fmt(current_eff)} | Δ%: {_fmt(eff_pct, '%')}",
                "Instrucción: si no hay caída grave, responde con string vacío.",
            ]
        )

        generated = await self._call_groq(
            system_prompt=_MONTHLY_ALERT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
            max_completion_tokens=220,
        )

        text = generated.strip()
        if not text:
            return ""

        cleaned = _clean_to_max_4_lines(text)
        return cleaned


def _build_sleep_analysis_prompt(
    data: CleanSleepData,
    quality_score: float,
    anomalies: List[str],
    suggested_time_str: str,
    heuristic_reason: str,
) -> str:
    """
    Construye el prompt que se envía a Llama con todos los datos del sueño.

    El prompt está diseñado para que el modelo actúe como un especialista en
    medicina del sueño y genere un análisis conciso, profesional y
    personalizado basado en los datos biométricos reales del usuario.
    """
    total_hours = round(data.duration / 1000 / 3600, 1)
    deep_pct = round((data.sleep_duration_deep / data.duration) * 100, 1) if data.duration > 0 else 0
    light_pct = round((data.sleep_duration_light / data.duration) * 100, 1) if data.duration > 0 else 0
    rem_pct = round((data.sleep_duration_rem / data.duration) * 100, 1) if data.duration > 0 else 0
    awake_pct = round((data.sleep_duration_awake / data.duration) * 100, 1) if data.duration > 0 else 0

    anomalies_text = ", ".join(anomalies) if anomalies else "Ninguna detectada"

    prompt = f"""Eres un especialista en medicina del sueño con 20 años de experiencia clínica.
        Analiza los siguientes datos biométricos de sueño de un usuario y genera un breve análisis
        personalizado de EXACTAMENTE 3-4 líneas.

        DATOS DEL SUEÑO:
        - Duración total: {total_hours} horas
        - Distribución de fases: Profundo {deep_pct}%, Ligero {light_pct}%, REM {rem_pct}%, Despierto {awake_pct}%
        - Frecuencia cardíaca media: {data.media_HR or 'N/D'} bpm
        - HRV (SDNN): {data.HRV or 'N/D'} ms
        - SpO2 promedio: {data.SpO2 or 'N/D'}% | SpO2 mínimo: {data.SpO2_min or 'N/D'}%
        - Frecuencia respiratoria: {data.breathing_rate or 'N/D'} rpm
        - Índice de movimiento: {data.movimiento or 'N/D'}
        - Puntuación de calidad: {quality_score}/100
        - Anomalías detectadas: {anomalies_text}
        - Hora sugerida de despertar: {suggested_time_str}
        - Análisis heurístico: {heuristic_reason}

        INSTRUCCIONES:
        1. Escribe en español profesional, en segunda persona (tuteo).
        2. Menciona datos concretos del usuario (ej: "tu HRV de 45ms indica...").
        3. Explica POR QUÉ se sugiere esa hora de despertar basándote en las fases.
        4. Si hay anomalías, menciónalas brevemente con recomendación.
        5. Sé conciso: MÁXIMO 4 líneas. Sin saludos ni despedidas.
        6. No uses markdown, listas, ni bullet points. Solo texto corrido."""

    return prompt


async def generate_sleep_reasoning(
    data: CleanSleepData,
    quality_score: float,
    anomalies: List[str],
    suggested_time_str: str,
    heuristic_reason: str,
) -> str:
    """
    Genera un análisis personalizado del sueño usando Groq + Llama 3.3 70B.

    Si la API key no está configurada o la llamada falla, retorna
    el reasoning heurístico como fallback silencioso.

    Args:
        data: Datos limpios del sueño del usuario.
        quality_score: Puntuación de calidad calculada (0-100).
        anomalies: Lista de anomalías detectadas.
        suggested_time_str: Hora sugerida formateada como string.
        heuristic_reason: Reasoning heurístico original (fallback).

    Returns:
        Análisis personalizado de 3-4 líneas o el heuristic_reason si falla.
    """
    if not settings.GROQ_API_KEY:
        logger.info("GROQ_API_KEY no configurada — usando reasoning heurístico")
        return heuristic_reason

    try:
        client = AsyncGroq(api_key=settings.GROQ_API_KEY)

        prompt = _build_sleep_analysis_prompt(
            data=data,
            quality_score=quality_score,
            anomalies=anomalies,
            suggested_time_str=suggested_time_str,
            heuristic_reason=heuristic_reason,
        )

        response = await client.chat.completions.create(
            model=_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Eres un especialista en medicina del sueño. Respondes siempre en español con análisis concisos y profesionales.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_completion_tokens=300,
        )

        generated_text = response.choices[0].message.content.strip() if response.choices else ""

        if not generated_text:
            logger.warning("Groq retornó respuesta vacía — fallback a heurístico")
            return heuristic_reason

        return generated_text

    except Exception as exc:
        logger.error("Error al llamar a Groq API: %s", exc, exc_info=True)
        return heuristic_reason
