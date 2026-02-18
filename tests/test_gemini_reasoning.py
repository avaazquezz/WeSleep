"""
Exhaustive test suite for the Gemini reasoning integration.

Tests cover:
- gemini_service: prompt building, API call with mock, fallback on errors
- predict_optimal_wakeup: async behavior, Gemini integration, edge cases
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models import CleanSleepData, SleepSegment, SleepPhase, WakeupPrediction
from app.services.gemini_service import (
    _build_sleep_analysis_prompt,
    generate_sleep_reasoning,
)
import app.logic as logic


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

TARGET_TIME = datetime(2025, 4, 30, 7, 0, 0, tzinfo=timezone.utc)

def _make_clean_data(
    hrv: float = 60.0,
    spo2: float = 96.0,
    spo2_min: float = 93.0,
    media_hr: float = 58.0,
    breathing_rate: float = 14.5,
    movimiento: float = 0.3,
    duration_hours: float = 7.5,
    deep_pct: float = 0.20,
    light_pct: float = 0.50,
    rem_pct: float = 0.20,
    awake_pct: float = 0.10,
    hypnogram: list | None = None,
) -> CleanSleepData:
    """Helper factory for creating CleanSleepData with realistic defaults."""
    duration_ms = int(duration_hours * 3600 * 1000)
    start = TARGET_TIME - timedelta(hours=duration_hours)

    if hypnogram is None:
        # Build default hypnogram matching phase percentages
        deep_ms = int(duration_ms * deep_pct)
        light_ms = int(duration_ms * light_pct)
        rem_ms = int(duration_ms * rem_pct)
        awake_ms = int(duration_ms * awake_pct)

        cursor = start
        segments: List[SleepSegment] = []
        for phase, ms in [
            (SleepPhase.DEEP, deep_ms),
            (SleepPhase.LIGHT, light_ms),
            (SleepPhase.REM, rem_ms),
            (SleepPhase.AWAKE, awake_ms),
        ]:
            if ms > 0:
                end = cursor + timedelta(milliseconds=ms)
                segments.append(SleepSegment(start_at=cursor, end_at=end, phase=phase))
                cursor = end
        hypnogram = segments

    return CleanSleepData(
        start_at_timestamp=start,
        end_at_timestamp=TARGET_TIME,
        duration=duration_ms,
        media_HR=media_hr,
        var_HR=hrv,
        HRV=hrv,
        SpO2=spo2,
        SpO2_min=spo2_min,
        SpO2_max=99.0,
        movimiento=movimiento,
        breathing_rate=breathing_rate,
        sleep_duration_deep=int(duration_ms * deep_pct),
        sleep_duration_light=int(duration_ms * light_pct),
        sleep_duration_rem=int(duration_ms * rem_pct),
        sleep_duration_awake=int(duration_ms * awake_pct),
        hypnogram=hypnogram,
    )


# ──────────────────────────────────────────────
# 1. PROMPT BUILDING TESTS
# ──────────────────────────────────────────────

class TestBuildSleepAnalysisPrompt:
    """Tests for _build_sleep_analysis_prompt."""

    def test_prompt_contains_user_metrics(self):
        """Prompt must reference concrete user data."""
        data = _make_clean_data(hrv=45.0, spo2=95.0, media_hr=62.0)
        prompt = _build_sleep_analysis_prompt(
            data=data,
            quality_score=72.5,
            anomalies=[],
            suggested_time_str="06:48",
            heuristic_reason="HRV normal.",
        )
        assert "45" in prompt, "HRV value should appear in prompt"
        assert "62" in prompt, "Heart rate should appear in prompt"
        assert "95" in prompt, "SpO2 should appear in prompt"
        assert "72.5" in prompt, "Quality score should appear in prompt"
        assert "06:48" in prompt, "Suggested time should appear in prompt"

    def test_prompt_includes_anomalies(self):
        """When anomalies exist, they should appear in the prompt."""
        data = _make_clean_data(spo2_min=85.0)
        anomalies = ["Posible Apnea (SpO2 Min: 85.0)", "Sueño Fragmentado (15 despertares)"]
        prompt = _build_sleep_analysis_prompt(
            data=data,
            quality_score=55.0,
            anomalies=anomalies,
            suggested_time_str="06:45",
            heuristic_reason="test",
        )
        assert "Posible Apnea" in prompt
        assert "Sueño Fragmentado" in prompt

    def test_prompt_no_anomalies_text(self):
        """When no anomalies, the placeholder text should appear."""
        data = _make_clean_data()
        prompt = _build_sleep_analysis_prompt(
            data=data,
            quality_score=85.0,
            anomalies=[],
            suggested_time_str="06:55",
            heuristic_reason="test",
        )
        assert "Ninguna detectada" in prompt

    def test_prompt_handles_none_metrics(self):
        """Prompt should gracefully handle None metrics with N/D."""
        data = _make_clean_data()
        data.media_HR = None
        data.HRV = None
        data.SpO2 = None
        data.breathing_rate = None
        prompt = _build_sleep_analysis_prompt(
            data=data,
            quality_score=30.0,
            anomalies=[],
            suggested_time_str="07:00",
            heuristic_reason="test",
        )
        assert "N/D" in prompt

    def test_prompt_contains_instructions(self):
        """Prompt must include key instruction words for Gemini."""
        data = _make_clean_data()
        prompt = _build_sleep_analysis_prompt(
            data=data,
            quality_score=80.0,
            anomalies=[],
            suggested_time_str="06:50",
            heuristic_reason="test",
        )
        assert "especialista" in prompt.lower()
        assert "3-4 líneas" in prompt
        assert "español" in prompt.lower()

    def test_prompt_includes_heuristic_reason(self):
        """The heuristic analysis should be passed to Gemini for context."""
        data = _make_clean_data()
        heuristic = "HRV bajo (30ms). Se prioriza despertar temprano."
        prompt = _build_sleep_analysis_prompt(
            data=data,
            quality_score=40.0,
            anomalies=[],
            suggested_time_str="06:30",
            heuristic_reason=heuristic,
        )
        assert heuristic in prompt


# ──────────────────────────────────────────────
# 2. GEMINI SERVICE TESTS (generate_sleep_reasoning)
# ──────────────────────────────────────────────

class TestGenerateSleepReasoning:
    """Tests for generate_sleep_reasoning — mocked Gemini API."""

    @pytest.mark.asyncio
    async def test_fallback_when_no_api_key(self):
        """Without API key, must return heuristic reasoning."""
        heuristic = "HRV normal. Despertando en fase ligera."
        with patch("app.services.gemini_service.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = ""
            result = await generate_sleep_reasoning(
                data=_make_clean_data(),
                quality_score=80.0,
                anomalies=[],
                suggested_time_str="06:55",
                heuristic_reason=heuristic,
            )
        assert result == heuristic

    @pytest.mark.asyncio
    async def test_returns_gemini_text_on_success(self):
        """When Gemini API succeeds, return its generated text."""
        gemini_text = (
            "Tu sueño profundo del 20% es adecuado y tu HRV de 60ms refleja "
            "buena recuperación. Se recomienda despertar a las 06:55 en fase ligera "
            "para minimizar la inercia del sueño."
        )
        mock_response = MagicMock()
        mock_response.text = gemini_text

        mock_aio_models = MagicMock()
        mock_aio_models.generate_content = AsyncMock(return_value=mock_response)
        mock_aio = MagicMock()
        mock_aio.models = mock_aio_models
        mock_client = MagicMock()
        mock_client.aio = mock_aio

        with patch("app.services.gemini_service.settings") as mock_settings, \
             patch("app.services.gemini_service.genai.Client", return_value=mock_client):
            mock_settings.GEMINI_API_KEY = "test-key-123"

            result = await generate_sleep_reasoning(
                data=_make_clean_data(),
                quality_score=80.0,
                anomalies=[],
                suggested_time_str="06:55",
                heuristic_reason="fallback text",
            )

        assert result == gemini_text

    @pytest.mark.asyncio
    async def test_fallback_on_api_exception(self):
        """On any Gemini API error, gracefully fall back to heuristic."""
        heuristic = "Fallback: HRV bajo."

        mock_aio_models = MagicMock()
        mock_aio_models.generate_content = AsyncMock(
            side_effect=Exception("API quota exceeded")
        )
        mock_aio = MagicMock()
        mock_aio.models = mock_aio_models
        mock_client = MagicMock()
        mock_client.aio = mock_aio

        with patch("app.services.gemini_service.settings") as mock_settings, \
             patch("app.services.gemini_service.genai.Client", return_value=mock_client):
            mock_settings.GEMINI_API_KEY = "test-key-123"

            result = await generate_sleep_reasoning(
                data=_make_clean_data(),
                quality_score=50.0,
                anomalies=["Posible Apnea"],
                suggested_time_str="06:45",
                heuristic_reason=heuristic,
            )

        assert result == heuristic

    @pytest.mark.asyncio
    async def test_fallback_on_empty_response(self):
        """If Gemini returns empty text, fall back to heuristic."""
        heuristic = "HRV normal. Optimiza duración."
        mock_response = MagicMock()
        mock_response.text = "   "

        mock_aio_models = MagicMock()
        mock_aio_models.generate_content = AsyncMock(return_value=mock_response)
        mock_aio = MagicMock()
        mock_aio.models = mock_aio_models
        mock_client = MagicMock()
        mock_client.aio = mock_aio

        with patch("app.services.gemini_service.settings") as mock_settings, \
             patch("app.services.gemini_service.genai.Client", return_value=mock_client):
            mock_settings.GEMINI_API_KEY = "test-key"

            result = await generate_sleep_reasoning(
                data=_make_clean_data(),
                quality_score=75.0,
                anomalies=[],
                suggested_time_str="06:50",
                heuristic_reason=heuristic,
            )

        assert result == heuristic


# ──────────────────────────────────────────────
# 3. PREDICT_OPTIMAL_WAKEUP (async, con Gemini mock)
# ──────────────────────────────────────────────

class TestPredictOptimalWakeup:
    """Tests for predict_optimal_wakeup with mocked Gemini."""

    @pytest.mark.asyncio
    async def test_no_hypnogram_returns_target_time(self):
        """Without hypnogram, return target time with zero confidence."""
        data = _make_clean_data(hypnogram=[])
        with patch("app.services.gemini_service.settings") as ms:
            ms.GEMINI_API_KEY = ""
            pred = await logic.predict_optimal_wakeup(data, TARGET_TIME)

        assert pred.suggested_time == TARGET_TIME
        assert pred.confidence == 0.0
        assert "Faltan datos" in pred.reasoning

    @pytest.mark.asyncio
    async def test_all_deep_sleep_returns_target_time(self):
        """If entire window is deep sleep, return target time."""
        deep_seg = SleepSegment(
            start_at=TARGET_TIME - timedelta(minutes=40),
            end_at=TARGET_TIME + timedelta(minutes=10),
            phase=SleepPhase.DEEP,
        )
        data = _make_clean_data(hypnogram=[deep_seg])
        with patch("app.services.gemini_service.settings") as ms:
            ms.GEMINI_API_KEY = ""
            pred = await logic.predict_optimal_wakeup(data, TARGET_TIME)

        assert pred.suggested_time == TARGET_TIME
        assert "sueño profundo" in pred.reasoning

    @pytest.mark.asyncio
    async def test_light_sleep_with_normal_hrv_picks_latest_slot(self):
        """With normal HRV, pick the latest valid (non-deep) slot."""
        s1 = SleepSegment(
            start_at=TARGET_TIME - timedelta(minutes=60),
            end_at=TARGET_TIME - timedelta(minutes=15),
            phase=SleepPhase.DEEP,
        )
        s2 = SleepSegment(
            start_at=TARGET_TIME - timedelta(minutes=15),
            end_at=TARGET_TIME,
            phase=SleepPhase.LIGHT,
        )
        data = _make_clean_data(hrv=60.0, hypnogram=[s1, s2])

        with patch("app.services.gemini_service.settings") as ms:
            ms.GEMINI_API_KEY = ""
            pred = await logic.predict_optimal_wakeup(data, TARGET_TIME)

        # Latest valid slot is 07:00 (or close to it)
        assert pred.suggested_time.minute == 0 or pred.suggested_time.minute == 59
        assert pred.confidence == 0.9

    @pytest.mark.asyncio
    async def test_low_hrv_picks_earliest_slot(self):
        """With low HRV (<50ms), pick the earliest valid slot."""
        s1 = SleepSegment(
            start_at=TARGET_TIME - timedelta(minutes=60),
            end_at=TARGET_TIME - timedelta(minutes=15),
            phase=SleepPhase.DEEP,
        )
        s2 = SleepSegment(
            start_at=TARGET_TIME - timedelta(minutes=15),
            end_at=TARGET_TIME,
            phase=SleepPhase.LIGHT,
        )
        data = _make_clean_data(hrv=30.0, hypnogram=[s1, s2])

        with patch("app.services.gemini_service.settings") as ms:
            ms.GEMINI_API_KEY = ""
            pred = await logic.predict_optimal_wakeup(data, TARGET_TIME)

        # Earliest non-deep slot starts at T-15min = 06:45
        assert pred.suggested_time.minute == 45

    @pytest.mark.asyncio
    async def test_gemini_enriches_reasoning_when_api_key_set(self):
        """When Gemini API key is set, reasoning should be enriched text."""
        enriched = "Tu HRV de 60ms indica recuperación adecuada. Despertar a las 06:55."

        s = SleepSegment(
            start_at=TARGET_TIME - timedelta(minutes=40),
            end_at=TARGET_TIME,
            phase=SleepPhase.LIGHT,
        )
        data = _make_clean_data(hrv=60.0, hypnogram=[s])

        mock_response = MagicMock()
        mock_response.text = enriched
        mock_aio_models = MagicMock()
        mock_aio_models.generate_content = AsyncMock(return_value=mock_response)
        mock_aio = MagicMock()
        mock_aio.models = mock_aio_models
        mock_client = MagicMock()
        mock_client.aio = mock_aio

        with patch("app.services.gemini_service.settings") as ms, \
             patch("app.services.gemini_service.genai.Client", return_value=mock_client):
            ms.GEMINI_API_KEY = "real-key"

            pred = await logic.predict_optimal_wakeup(
                data, TARGET_TIME, quality_score=80.0, anomalies=[]
            )

        assert pred.reasoning == enriched

    @pytest.mark.asyncio
    async def test_prediction_returns_wakeup_prediction_type(self):
        """Return type must be WakeupPrediction."""
        s = SleepSegment(
            start_at=TARGET_TIME - timedelta(minutes=40),
            end_at=TARGET_TIME,
            phase=SleepPhase.LIGHT,
        )
        data = _make_clean_data(hypnogram=[s])

        with patch("app.services.gemini_service.settings") as ms:
            ms.GEMINI_API_KEY = ""
            pred = await logic.predict_optimal_wakeup(data, TARGET_TIME)

        assert isinstance(pred, WakeupPrediction)
        assert isinstance(pred.suggested_time, datetime)
        assert isinstance(pred.confidence, float)
        assert isinstance(pred.reasoning, str)

    @pytest.mark.asyncio
    async def test_no_segments_in_window(self):
        """If hypnogram exists but no segments overlap the 30min window."""
        # Segments are hours before the window
        s = SleepSegment(
            start_at=TARGET_TIME - timedelta(hours=5),
            end_at=TARGET_TIME - timedelta(hours=4),
            phase=SleepPhase.LIGHT,
        )
        data = _make_clean_data(hypnogram=[s])

        with patch("app.services.gemini_service.settings") as ms:
            ms.GEMINI_API_KEY = ""
            pred = await logic.predict_optimal_wakeup(data, TARGET_TIME)

        assert pred.suggested_time == TARGET_TIME
        assert pred.confidence == 0.1

    @pytest.mark.asyncio
    async def test_timezone_naive_target_gets_utc(self):
        """Naive target_alarm_time should be made timezone-aware."""
        s = SleepSegment(
            start_at=TARGET_TIME - timedelta(minutes=40),
            end_at=TARGET_TIME,
            phase=SleepPhase.LIGHT,
        )
        data = _make_clean_data(hypnogram=[s])
        naive_target = datetime(2025, 4, 30, 7, 0, 0)  # No tzinfo

        with patch("app.services.gemini_service.settings") as ms:
            ms.GEMINI_API_KEY = ""
            pred = await logic.predict_optimal_wakeup(data, naive_target)

        # Should not crash — timezone is assigned internally
        assert pred.suggested_time is not None

    @pytest.mark.asyncio
    async def test_quality_score_and_anomalies_passed_to_gemini(self):
        """Verify that quality_score and anomalies reach the Gemini prompt."""
        captured_prompt = {}

        async def capture_prompt(*args, **kwargs):
            # The prompt is passed as the `contents` kwarg
            captured_prompt["text"] = kwargs.get("contents", args[0] if args else "")
            mock_resp = MagicMock()
            mock_resp.text = "Análisis generado."
            return mock_resp

        s = SleepSegment(
            start_at=TARGET_TIME - timedelta(minutes=40),
            end_at=TARGET_TIME,
            phase=SleepPhase.LIGHT,
        )
        data = _make_clean_data(hrv=60.0, hypnogram=[s])

        mock_aio_models = MagicMock()
        mock_aio_models.generate_content = capture_prompt
        mock_aio = MagicMock()
        mock_aio.models = mock_aio_models
        mock_client = MagicMock()
        mock_client.aio = mock_aio

        with patch("app.services.gemini_service.settings") as ms, \
             patch("app.services.gemini_service.genai.Client", return_value=mock_client):
            ms.GEMINI_API_KEY = "key-123"

            await logic.predict_optimal_wakeup(
                data, TARGET_TIME,
                quality_score=67.3,
                anomalies=["Posible Apnea (SpO2 Min: 88.0)"],
            )

        assert "67.3" in captured_prompt["text"]
        assert "Posible Apnea" in captured_prompt["text"]


# ──────────────────────────────────────────────
# 4. INTEGRATION-STYLE: calculate_sleep_score + anomalies + predict
# ──────────────────────────────────────────────

class TestEndToEndFlow:
    """Full pipeline: score → anomalies → predict (with mocked Gemini)."""

    @pytest.mark.asyncio
    async def test_full_pipeline_healthy_sleeper(self):
        """Healthy sleeper: high score, no anomalies, good reasoning."""
        data = _make_clean_data(
            hrv=70.0, spo2=97.0, spo2_min=94.0,
            duration_hours=8.0, deep_pct=0.20,
        )
        score = logic.calculate_sleep_score(data)
        anomalies = logic.detect_sleep_anomalies(data)

        assert score > 70, f"Healthy sleeper should have high score, got {score}"
        assert len(anomalies) == 0

        with patch("app.services.gemini_service.settings") as ms:
            ms.GEMINI_API_KEY = ""
            pred = await logic.predict_optimal_wakeup(
                data, TARGET_TIME, quality_score=score, anomalies=anomalies
            )

        assert pred.confidence == 0.9

    @pytest.mark.asyncio
    async def test_full_pipeline_poor_sleeper_with_apnea(self):
        """Poor sleeper with low SpO2: should detect apnea anomaly."""
        # Build a hypnogram that covers the alarm window so HRV logic activates
        s1 = SleepSegment(
            start_at=TARGET_TIME - timedelta(hours=5, minutes=30),
            end_at=TARGET_TIME - timedelta(minutes=15),
            phase=SleepPhase.DEEP,
        )
        s2 = SleepSegment(
            start_at=TARGET_TIME - timedelta(minutes=15),
            end_at=TARGET_TIME,
            phase=SleepPhase.LIGHT,
        )
        data = _make_clean_data(
            hrv=25.0, spo2=88.0, spo2_min=82.0,
            duration_hours=5.5, deep_pct=0.08,
            hypnogram=[s1, s2],
        )
        score = logic.calculate_sleep_score(data)
        anomalies = logic.detect_sleep_anomalies(data)

        assert score < 80, f"Poor sleeper should have below-average score, got {score}"
        assert any("Apnea" in a for a in anomalies)

        with patch("app.services.gemini_service.settings") as ms:
            ms.GEMINI_API_KEY = ""
            pred = await logic.predict_optimal_wakeup(
                data, TARGET_TIME, quality_score=score, anomalies=anomalies
            )

        # Low HRV should trigger early wakeup
        assert "HRV bajo" in pred.reasoning
