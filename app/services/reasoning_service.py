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
    "Eres un asistente clínico preventivo (B2B) para profesionales de salud. "
    "Tu tono es profesional, cercano y claro. Personaliza el mensaje con los números dados. "
    "NO diagnostiques, NO alarmes sin base y NO uses jerga innecesaria.\n"
    "Formato obligatorio: EXACTAMENTE 3 líneas, sin viñetas.\n"
    "Cada línea debe terminar en punto y tener <= 170 caracteres.\n"
    "La línea 1 debe empezar por 'Resumen:' y usar EXACTAMENTE este patrón:\n"
    "Resumen: HRV X ms (±Y%), Profundo A min (±B%), Eficiencia C% (±D%).\n"
    "La línea 2 debe empezar por 'Lectura:' y contener 1 punto fuerte + 1 área a vigilar, citando al menos 1 número.\n"
    "La línea 3 debe empezar por 'Acción:' y contener EXACTAMENTE 2 acciones para 7 días, cada una ligada a una métrica (HRV/Profundo/Eficiencia), y un cierre breve."
)

_MONTHLY_ALERT_SYSTEM_PROMPT = (
    "Eres un sistema de alerta temprana B2B para una mutua de salud. "
    "Tu objetivo es avisar con rigor y cercanía cuando hay una caída sostenida relevante.\n"
    "Reglas: NO diagnostiques. Si NO hay caída grave, devuelve string vacío.\n"
    "Si SÍ hay caída grave: devuelve EXACTAMENTE 4 líneas, sin viñetas.\n"
    "Cada línea debe terminar en punto y tener <= 170 caracteres.\n"
    "Formato: 'Alerta:' (evidencia), 'Lectura:' (interpretación), 'Recomendación:' (revisión profesional), 'Mientras tanto:' (2 acciones seguras)."
)

_PREVENTIVE_FALLBACK = (
    "Resumen semanal disponible. Revisa el detalle de tendencias y métricas en el dashboard."
)


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


def _fmt_eff(value: float | None) -> str:
    if value is None:
        return "N/D"
    return f"{value * 100:.0f}%"


def _fmt_delta(value: float | None) -> str:
    if value is None:
        return "N/D"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def _heuristic_weekly_recap(
    *,
    prev_hrv: float | None,
    current_hrv: float | None,
    prev_deep: float | None,
    current_deep: float | None,
    prev_eff: float | None,
    current_eff: float | None,
    hrv_pct: float | None,
    deep_pct: float | None,
    eff_pct: float | None,
) -> str:
    line1 = (
        "Últimas 2 semanas: "
        f"HRV {_fmt(current_hrv, ' ms')} ({_fmt_delta(hrv_pct)}), "
        f"Sueño profundo {_fmt(current_deep, ' min')} ({_fmt_delta(deep_pct)}), "
        f"Eficiencia {_fmt_eff(current_eff)} ({_fmt_delta(eff_pct)})."
    )

    improvements = sum(1 for v in (hrv_pct, deep_pct, eff_pct) if isinstance(v, (int, float)) and v > 3.0)
    declines = sum(1 for v in (hrv_pct, deep_pct, eff_pct) if isinstance(v, (int, float)) and v < -3.0)

    if improvements >= 2 and declines == 0:
        line2 = (
            "El patrón es consistente con una mejor recuperación: el sistema autónomo y la arquitectura del sueño van en buena dirección."
        )
    elif declines >= 2:
        line2 = (
            "Veo señales de carga/recuperación subóptima: no es un diagnóstico, pero merece ajustar hábitos para estabilizar el descanso."
        )
    else:
        line2 = (
            "El balance es mixto: hay avances puntuales y áreas por consolidar; lo importante es la consistencia más que un día aislado."
        )

    actions: list[str] = []
    if isinstance(deep_pct, (int, float)) and deep_pct < -3.0:
        actions.append("prioriza una hora fija de sueño 5/7 días")
    if isinstance(eff_pct, (int, float)) and eff_pct < -3.0:
        actions.append("reduce pantallas y alcohol 2–3 h antes de dormir")
    if isinstance(hrv_pct, (int, float)) and hrv_pct < -3.0:
        actions.append("añade 10–15 min/día de respiración o caminata suave")
    if not actions:
        actions = ["mantén horario regular y luz solar por la mañana", "protege una rutina de desconexión 30–45 min"]
    else:
        actions = actions[:2]

    line3 = (
        f"Para esta semana: {actions[0]} y {actions[1]}. "
        "Si notas somnolencia diurna marcada o ronquidos/pausas, consúltalo con tu profesional."
    )
    return "\n".join([line1, line2, line3])


def _heuristic_action_line(
    *,
    patient_label: str | None,
    hrv_pct: float | None,
    deep_pct: float | None,
    eff_pct: float | None,
) -> str:
    profile = (patient_label or "").lower()

    actions: list[str] = []

    # Metric-driven actions
    if isinstance(deep_pct, (int, float)) and deep_pct < -3.0:
        actions.append("fija hora de acostarte 5/7 días y protege 8 h en cama")
    if isinstance(eff_pct, (int, float)) and eff_pct < -3.0:
        actions.append("corta pantallas 60 min antes y evita alcohol tarde")
    if isinstance(hrv_pct, (int, float)) and hrv_pct < -3.0:
        actions.append("añade 10–15 min/día de respiración guiada o caminata suave")

    # Profile-specific emphasis (if we still need guidance)
    if len(actions) < 2:
        if "fragmentado" in profile:
            actions.append("prioriza rutina de desconexión (luz baja) 45 min y habitación fresca/oscura")
        elif "fatigado" in profile:
            actions.append("reduce carga intensa 2 días y busca luz solar por la mañana")
        else:
            actions.append("mantén regularidad y exposición a luz natural al despertar")

    if len(actions) < 2:
        actions.append("limita cafeína después de las 14:00 y cena ligera")

    a1, a2 = actions[0], actions[1]
    return f"Acción: Esta semana {a1}; además {a2}. Revaluamos en 7 días."


def _heuristic_lecture_line(
    *,
    patient_label: str | None,
    current_hrv: float | None,
    current_deep: float | None,
    current_eff: float | None,
    hrv_pct: float | None,
    deep_pct: float | None,
    eff_pct: float | None,
) -> str:
    profile = (patient_label or "").lower()
    hrv_d = _fmt_delta(hrv_pct)
    deep_d = _fmt_delta(deep_pct)
    eff_d = _fmt_delta(eff_pct)
    eff_now = _fmt_eff(current_eff)

    if "sano" in profile:
        return (
            f"Lectura: Buen mantenimiento: HRV ({hrv_d}) y profundo ({deep_d}) mejoran; objetivo es sostener eficiencia ~{eff_now} con regularidad."
        )
    if "fatigado" in profile:
        return (
            f"Lectura: Recuperación a vigilar: profundo ({deep_d}) y eficiencia ({eff_d}) bajan; el foco esta semana es continuidad y descarga para recuperar energía."
        )
    if "fragmentado" in profile:
        return (
            f"Lectura: Avance en HRV ({hrv_d}), pero profundo cae ({deep_d}); prioriza consolidación nocturna para ganar descanso reparador y estabilidad."
        )

    # Default, metric-driven
    return (
        f"Lectura: Tendencia mixta: HRV {hrv_d}, profundo {deep_d}, eficiencia {eff_d}; prioriza consistencia y monitoriza cómo te sientes durante el día."
    )


def _b2b_mock_weekly_recap(
    *,
    patient_label: str,
    current_hrv: float | None,
    current_deep: float | None,
    current_eff: float | None,
    hrv_pct: float | None,
    deep_pct: float | None,
    eff_pct: float | None,
) -> str:
    summary_line = (
        "Resumen: "
        f"HRV {_fmt(current_hrv, ' ms')} ({_fmt_delta(hrv_pct)}), "
        f"Profundo {_fmt(current_deep, ' min')} ({_fmt_delta(deep_pct)}), "
        f"Eficiencia {_fmt_eff(current_eff)} ({_fmt_delta(eff_pct)})."
    )
    lecture_line = _heuristic_lecture_line(
        patient_label=patient_label,
        current_hrv=current_hrv,
        current_deep=current_deep,
        current_eff=current_eff,
        hrv_pct=hrv_pct,
        deep_pct=deep_pct,
        eff_pct=eff_pct,
    )
    action_line = _heuristic_action_line(
        patient_label=patient_label,
        hrv_pct=hrv_pct,
        deep_pct=deep_pct,
        eff_pct=eff_pct,
    )
    return "\n".join([summary_line, lecture_line, action_line])

def _heuristic_monthly_alert(
    *,
    baseline_hrv: float | None,
    current_hrv: float | None,
    baseline_eff: float | None,
    current_eff: float | None,
    hrv_pct: float | None,
    eff_pct: float | None,
) -> str:
    line1 = (
        "Alerta preventiva 30 días: caída sostenida respecto a la primera mitad del mes."
    )
    line2 = (
        f"HRV {_fmt(baseline_hrv, ' ms')} → {_fmt(current_hrv, ' ms')} ({_fmt_delta(hrv_pct)}), "
        f"Eficiencia {_fmt_eff(baseline_eff)} → {_fmt_eff(current_eff)} ({_fmt_delta(eff_pct)})."
    )
    line3 = (
        "Recomendación: agenda una revisión con tu profesional de la mutua para descartar causas (estrés, carga, higiene del sueño, etc.)."
    )
    line4 = (
        "Mientras tanto: prioriza regularidad (hora fija) y limita estimulantes por la tarde; si hay síntomas relevantes, consulta antes."
    )
    return "\n".join([line1, line2, line3, line4])


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
        *,
        patient_label: str | None = None,
    ) -> str:
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

        # For B2B demo mock profiles, generate a consistent, highly-personalized recap without external LLM calls.
        if patient_label:
            return _b2b_mock_weekly_recap(
                patient_label=patient_label,
                current_hrv=current_hrv,
                current_deep=current_deep,
                current_eff=current_eff,
                hrv_pct=hrv_pct,
                deep_pct=deep_pct,
                eff_pct=eff_pct,
            )

        if not self._api_key:
            return _heuristic_weekly_recap(
                prev_hrv=prev_hrv,
                current_hrv=current_hrv,
                prev_deep=prev_deep,
                current_deep=current_deep,
                prev_eff=prev_eff,
                current_eff=current_eff,
                hrv_pct=hrv_pct,
                deep_pct=deep_pct,
                eff_pct=eff_pct,
            )

        summary_line = (
            "Resumen: "
            f"HRV {_fmt(current_hrv, ' ms')} ({_fmt_delta(hrv_pct)}), "
            f"Profundo {_fmt(current_deep, ' min')} ({_fmt_delta(deep_pct)}), "
            f"Eficiencia {_fmt_eff(current_eff)} ({_fmt_delta(eff_pct)})."
        )

        user_prompt = "\n".join(
            [
                f"Perfil del paciente (para tono): {patient_label or 'No especificado'}",
                "Comparativa de dos semanas de sueño (valores medios):",
                f"- HRV anterior: {_fmt(prev_hrv, ' ms')} | HRV actual: {_fmt(current_hrv, ' ms')} | Δ%: {_fmt(hrv_pct, '%')}",
                f"- Deep anterior: {_fmt(prev_deep, ' min')} | Deep actual: {_fmt(current_deep, ' min')} | Δ%: {_fmt(deep_pct, '%')}",
                f"- Eficiencia anterior: {_fmt_eff(prev_eff)} | Eficiencia actual: {_fmt_eff(current_eff)} | Δ%: {_fmt(eff_pct, '%')}",
                "Instrucciones:\n"
                f"- Copia EXACTAMENTE esta línea como tu línea 1:\n{summary_line}\n"
                "- Personaliza por perfil:\n"
                "  * Paciente Sano (Control): refuerza mantenimiento y prevención.\n"
                "  * Paciente Fatigado (Alerta IA): prioriza recuperación, carga/estrés y consistencia.\n"
                "  * Paciente Fragmentado (Alerta IA): prioriza consolidación (despertares/rutina) y eficiencia.\n"
                "- Evita frases genéricas. Nombra explícitamente qué sube/baja y enlaza cada acción con una métrica.",
            ]
        )

        generated = await self._call_groq(
            system_prompt=_WEEKLY_RECAP_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2,
            max_completion_tokens=240,
        )
        if not generated.strip():
            return _PREVENTIVE_FALLBACK

        lines = [ln.strip() for ln in generated.splitlines() if ln.strip()]
        if not lines:
            return _PREVENTIVE_FALLBACK

        # Preserve legacy behavior for tests/mocks that return arbitrary lines.
        looks_like_structured = any(
            ln.startswith(("Resumen:", "Lectura:", "Acción:")) for ln in lines
        )
        if not looks_like_structured:
            return "\n".join(lines[:3]) if lines else _PREVENTIVE_FALLBACK

        lecture_line = next((ln for ln in lines if ln.startswith("Lectura:")), "")
        if not lecture_line:
            lecture_line = "Lectura: Balance mixto; prioriza consistencia y sigue la tendencia semanal, no un día aislado."

        action_line = _heuristic_action_line(
            patient_label=patient_label,
            hrv_pct=hrv_pct,
            deep_pct=deep_pct,
            eff_pct=eff_pct,
        )

        # Ensure the quant line is correct and consistent.
        return "\n".join([summary_line, lecture_line, action_line])

    async def generate_monthly_anomaly_alert(
        self,
        current_month: dict[str, Any],
        baseline_month: dict[str, Any],
        *,
        patient_label: str | None = None,
    ) -> str:
        if not self._api_key:
            # Still return a helpful alert when the threshold is met, even without Groq.
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
            severe_hrv = hrv_pct is not None and hrv_pct <= -15.0
            severe_eff = eff_pct is not None and eff_pct <= -15.0
            if not (severe_hrv or severe_eff):
                return ""
            return _heuristic_monthly_alert(
                baseline_hrv=baseline_hrv,
                current_hrv=current_hrv,
                baseline_eff=baseline_eff,
                current_eff=current_eff,
                hrv_pct=hrv_pct,
                eff_pct=eff_pct,
            )

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
                f"Perfil del paciente (para tono): {patient_label or 'No especificado'}",
                "Tendencia en los últimos 30 días (primera mitad vs segunda mitad; valores medios):",
                f"- HRV (1ª mitad): {_fmt(baseline_hrv, ' ms')} | HRV (2ª mitad): {_fmt(current_hrv, ' ms')} | Δ%: {_fmt(hrv_pct, '%')}",
                f"- Eficiencia (1ª mitad): {_fmt(baseline_eff)} | Eficiencia (2ª mitad): {_fmt(current_eff)} | Δ%: {_fmt(eff_pct, '%')}",
                "Instrucción: si no hay caída grave, responde con string vacío (no hay alerta).",
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
