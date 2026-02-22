from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models import SleepRecord
from app.routers.deps import get_session
from app.services.reasoning_service import AISleepAnalyzer

router = APIRouter()

_B2B_MOCK_PATIENT_LABELS: dict[UUID, str] = {
    UUID("e9f7e4d0-2e3e-4ebf-b77a-18011e5897fa"): "Paciente Sano (Control)",
    UUID("f05277dc-ecee-4ea2-9c4c-3de9b54008f1"): "Paciente Fatigado (Alerta IA)",
    UUID("2013db39-79dd-45ec-b9ae-9eeaa7b1b6ad"): "Paciente Fragmentado (Alerta IA)",
}


class DailyMetrics(BaseModel):
    date: date
    hrv: float | None = None
    deep_minutes: float | None = None
    efficiency: float | None = None


class AggregateStats(BaseModel):
    hrv_avg: float | None = None
    deep_minutes_avg: float | None = None
    efficiency_avg: float | None = None


class WeeklyInsightsResponse(BaseModel):
    patient_id: UUID
    previous_week: AggregateStats
    current_week: AggregateStats
    hrv_trend_percent: float | None = None
    deep_trend_percent: float | None = None
    efficiency_trend_percent: float | None = None
    daily: list[DailyMetrics]
    weekly_recap: str


class MonthlyInsightsOk(BaseModel):
    status: str = "ok"
    alert: str | None = None


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _parse_segment_dt(value: Any, base_date: date) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        raw = value.strip()
        # HH:MM
        try:
            if len(raw) == 5 and raw[2] == ":":
                hour = int(raw[:2])
                minute = int(raw[3:])
                return datetime.combine(base_date, datetime.min.time()).replace(
                    hour=hour, minute=minute
                )
        except Exception:
            pass
        # ISO/RFC3339
        normalized = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
        except Exception:
            return None
    else:
        return None

    if dt.tzinfo is not None:
        dt = dt.astimezone(tz=None).replace(tzinfo=None)
    return dt


def _extract_deep_minutes(payload: dict[str, Any], record_date: date) -> float | None:
    hypnogram = payload.get("hypnogram")
    if not isinstance(hypnogram, list):
        metrics = payload.get("metrics")
        if isinstance(metrics, dict):
            raw = metrics.get("sleep_duration_deep")
            if isinstance(raw, (int, float)) and raw > 0:
                return float(raw) / 1000.0 / 60.0
        return None

    total_seconds = 0.0
    for seg in hypnogram:
        if not isinstance(seg, dict):
            continue
        phase = seg.get("phase")
        if not isinstance(phase, str) or phase.strip().lower() != "deep":
            continue

        start_raw = seg.get("start_time") if seg.get("start_time") is not None else seg.get("start_at")
        end_raw = seg.get("end_time") if seg.get("end_time") is not None else seg.get("end_at")

        start_dt = _parse_segment_dt(start_raw, record_date)
        end_dt = _parse_segment_dt(end_raw, record_date)
        if start_dt is None or end_dt is None:
            continue
        if end_dt <= start_dt:
            end_dt = end_dt + timedelta(days=1)

        total_seconds += (end_dt - start_dt).total_seconds()

    return total_seconds / 60.0


def _extract_hrv(payload: dict[str, Any]) -> float | None:
    hrv = payload.get("hrv")
    if isinstance(hrv, (int, float)):
        return float(hrv)

    metrics = payload.get("metrics")
    if isinstance(metrics, dict):
        hrv2 = metrics.get("hrv_sdnn")
        if isinstance(hrv2, (int, float)):
            return float(hrv2)

    return None


def _extract_duration_seconds(payload: dict[str, Any]) -> float | None:
    duration = payload.get("duration")
    if isinstance(duration, (int, float)) and duration >= 0:
        # duration is ms in our ingestion paths
        return float(duration) / 1000.0
    metrics = payload.get("metrics")
    if isinstance(metrics, dict):
        raw = metrics.get("sleep_duration")
        if isinstance(raw, (int, float)) and raw >= 0:
            return float(raw) / 1000.0
    return None


def _extract_bed_seconds(payload: dict[str, Any], record_date: date) -> float | None:
    start_raw = payload.get("start_at_timestamp")
    end_raw = payload.get("end_at_timestamp")
    if start_raw is not None and end_raw is not None:
        start_dt = _parse_segment_dt(start_raw, record_date)
        end_dt = _parse_segment_dt(end_raw, record_date)
        if start_dt and end_dt:
            if end_dt <= start_dt:
                end_dt = end_dt + timedelta(days=1)
            seconds = (end_dt - start_dt).total_seconds()
            return seconds if seconds > 0 else None

    hypnogram = payload.get("hypnogram")
    if isinstance(hypnogram, list) and hypnogram:
        starts: list[datetime] = []
        ends: list[datetime] = []
        for seg in hypnogram:
            if not isinstance(seg, dict):
                continue
            s_raw = seg.get("start_time") if seg.get("start_time") is not None else seg.get("start_at")
            e_raw = seg.get("end_time") if seg.get("end_time") is not None else seg.get("end_at")
            s_dt = _parse_segment_dt(s_raw, record_date)
            e_dt = _parse_segment_dt(e_raw, record_date)
            if s_dt is None or e_dt is None:
                continue
            if e_dt <= s_dt:
                e_dt = e_dt + timedelta(days=1)
            starts.append(s_dt)
            ends.append(e_dt)
        if starts and ends:
            seconds = (max(ends) - min(starts)).total_seconds()
            return seconds if seconds > 0 else None

    return None


def _extract_efficiency(payload: dict[str, Any], record_date: date) -> float | None:
    sleep_s = _extract_duration_seconds(payload)
    bed_s = _extract_bed_seconds(payload, record_date)
    if sleep_s is None or bed_s is None or bed_s <= 0:
        return None
    eff = sleep_s / bed_s
    if eff < 0:
        return None
    return min(eff, 1.0)


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    if previous == 0:
        return None
    return ((current - previous) / previous) * 100.0


@router.get("/weekly/{patient_id}", response_model=WeeklyInsightsResponse, status_code=200)
async def get_weekly_insights(
    patient_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> WeeklyInsightsResponse:
    since = date.today() - timedelta(days=13)
    statement = (
        select(SleepRecord.date, SleepRecord.payload)
        .where(SleepRecord.patient_id == patient_id, SleepRecord.date >= since)
        .order_by(SleepRecord.date.asc())
    )
    result = await session.exec(statement)
    records = result.all()

    last_14 = records[-14:]
    if len(last_14) < 14:
        raise HTTPException(status_code=400, detail="Datos insuficientes para el análisis")

    prev_rows = last_14[:7]
    cur_rows = last_14[7:]

    daily: list[DailyMetrics] = []
    prev_hrv_vals: list[float] = []
    prev_deep_vals: list[float] = []
    prev_eff_vals: list[float] = []
    for rec_date, payload in prev_rows:
        if not isinstance(payload, dict):
            continue
        hrv = _extract_hrv(payload)
        deep = _extract_deep_minutes(payload, rec_date)
        eff = _extract_efficiency(payload, rec_date)
        daily.append(DailyMetrics(date=rec_date, hrv=hrv, deep_minutes=deep, efficiency=eff))
        if hrv is not None:
            prev_hrv_vals.append(hrv)
        if deep is not None:
            prev_deep_vals.append(deep)
        if eff is not None:
            prev_eff_vals.append(eff)

    cur_hrv_vals: list[float] = []
    cur_deep_vals: list[float] = []
    cur_eff_vals: list[float] = []
    for rec_date, payload in cur_rows:
        if not isinstance(payload, dict):
            continue
        hrv = _extract_hrv(payload)
        deep = _extract_deep_minutes(payload, rec_date)
        eff = _extract_efficiency(payload, rec_date)
        daily.append(DailyMetrics(date=rec_date, hrv=hrv, deep_minutes=deep, efficiency=eff))
        if hrv is not None:
            cur_hrv_vals.append(hrv)
        if deep is not None:
            cur_deep_vals.append(deep)
        if eff is not None:
            cur_eff_vals.append(eff)

    if len(prev_rows) < 7 or len(cur_rows) < 7:
        raise HTTPException(status_code=400, detail="Datos insuficientes para el análisis")

    prev_stats = AggregateStats(
        hrv_avg=_mean(prev_hrv_vals),
        deep_minutes_avg=_mean(prev_deep_vals),
        efficiency_avg=_mean(prev_eff_vals),
    )
    cur_stats = AggregateStats(
        hrv_avg=_mean(cur_hrv_vals),
        deep_minutes_avg=_mean(cur_deep_vals),
        efficiency_avg=_mean(cur_eff_vals),
    )

    analyzer = AISleepAnalyzer()
    patient_label = _B2B_MOCK_PATIENT_LABELS.get(patient_id)
    recap = await analyzer.generate_weekly_recap(
        current_week=cur_stats.model_dump(),
        prev_week=prev_stats.model_dump(),
        patient_label=patient_label,
    )

    hrv_trend = _pct_change(cur_stats.hrv_avg, prev_stats.hrv_avg)
    deep_trend = _pct_change(cur_stats.deep_minutes_avg, prev_stats.deep_minutes_avg)
    eff_trend = _pct_change(cur_stats.efficiency_avg, prev_stats.efficiency_avg)

    return WeeklyInsightsResponse(
        patient_id=patient_id,
        previous_week=prev_stats,
        current_week=cur_stats,
        hrv_trend_percent=round(hrv_trend, 1) if hrv_trend is not None else None,
        deep_trend_percent=round(deep_trend, 1) if deep_trend is not None else None,
        efficiency_trend_percent=round(eff_trend, 1) if eff_trend is not None else None,
        daily=daily,
        weekly_recap=recap,
    )


@router.get("/monthly/{patient_id}", response_model=MonthlyInsightsOk, status_code=200)
async def get_monthly_insights(
    patient_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> MonthlyInsightsOk:
    since = date.today() - timedelta(days=29)
    statement = (
        select(SleepRecord.date, SleepRecord.payload)
        .where(SleepRecord.patient_id == patient_id, SleepRecord.date >= since)
        .order_by(SleepRecord.date.asc())
    )
    result = await session.exec(statement)
    records = result.all()

    last_30 = records[-30:]
    if len(last_30) < 30:
        raise HTTPException(status_code=400, detail="Datos insuficientes para el análisis")

    # Intra-mes: primera mitad vs segunda mitad para estimar caída sostenida
    baseline_rows = last_30[:15]
    current_rows = last_30[15:]

    base_hrv_vals: list[float] = []
    base_deep_vals: list[float] = []
    base_eff_vals: list[float] = []
    for rec_date, payload in baseline_rows:
        if not isinstance(payload, dict):
            continue
        hrv = _extract_hrv(payload)
        deep = _extract_deep_minutes(payload, rec_date)
        eff = _extract_efficiency(payload, rec_date)
        if hrv is not None:
            base_hrv_vals.append(hrv)
        if deep is not None:
            base_deep_vals.append(deep)
        if eff is not None:
            base_eff_vals.append(eff)

    cur_hrv_vals: list[float] = []
    cur_deep_vals: list[float] = []
    cur_eff_vals: list[float] = []
    for rec_date, payload in current_rows:
        if not isinstance(payload, dict):
            continue
        hrv = _extract_hrv(payload)
        deep = _extract_deep_minutes(payload, rec_date)
        eff = _extract_efficiency(payload, rec_date)
        if hrv is not None:
            cur_hrv_vals.append(hrv)
        if deep is not None:
            cur_deep_vals.append(deep)
        if eff is not None:
            cur_eff_vals.append(eff)

    if len(baseline_rows) < 15 or len(current_rows) < 15:
        raise HTTPException(status_code=400, detail="Datos insuficientes para el análisis")

    baseline_stats = AggregateStats(
        hrv_avg=_mean(base_hrv_vals),
        deep_minutes_avg=_mean(base_deep_vals),
        efficiency_avg=_mean(base_eff_vals),
    )
    current_stats = AggregateStats(
        hrv_avg=_mean(cur_hrv_vals),
        deep_minutes_avg=_mean(cur_deep_vals),
        efficiency_avg=_mean(cur_eff_vals),
    )

    analyzer = AISleepAnalyzer()
    patient_label = _B2B_MOCK_PATIENT_LABELS.get(patient_id)
    alert = await analyzer.generate_monthly_anomaly_alert(
        current_month=current_stats.model_dump(),
        baseline_month=baseline_stats.model_dump(),
        patient_label=patient_label,
    )
    alert_clean = alert.strip() or None
    return MonthlyInsightsOk(status="ok", alert=alert_clean)

