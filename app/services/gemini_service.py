"""
Gemini AI service for generating personalized sleep analysis reasoning.

This service encapsulates all interaction with the Google Gemini API
via the modern `google-genai` SDK.

Fallback strategy: if Gemini is unavailable or the API key is not set,
the function silently returns the heuristic reasoning so the Smart Alarm
feature continues to work without interruption.
"""
import logging
from typing import List

from google import genai
from google.genai import types

from app.config import settings
from app.models import CleanSleepData

logger = logging.getLogger(__name__)

# Gemini model — flash is the fastest and cheapest option
_GEMINI_MODEL = "gemini-2.0-flash"


def _build_sleep_analysis_prompt(
    data: CleanSleepData,
    quality_score: float,
    anomalies: List[str],
    suggested_time_str: str,
    heuristic_reason: str,
) -> str:
    """
    Construye el prompt que se envía a Gemini con todos los datos del sueño.

    El prompt está diseñado para que Gemini actúe como un especialista en
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
    Genera un análisis personalizado del sueño usando Gemini.

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
    if not settings.GEMINI_API_KEY:
        logger.info("GEMINI_API_KEY no configurada — usando reasoning heurístico")
        return heuristic_reason

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        prompt = _build_sleep_analysis_prompt(
            data=data,
            quality_score=quality_score,
            anomalies=anomalies,
            suggested_time_str=suggested_time_str,
            heuristic_reason=heuristic_reason,
        )

        response = await client.aio.models.generate_content(
            model=_GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=300,
            ),
        )

        generated_text = response.text.strip() if response.text else ""

        if not generated_text:
            logger.warning("Gemini retornó respuesta vacía — fallback a heurístico")
            return heuristic_reason

        return generated_text

    except Exception as exc:
        logger.error("Error al llamar a Gemini API: %s", exc, exc_info=True)
        return heuristic_reason
