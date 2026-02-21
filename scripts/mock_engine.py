from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Iterable

import httpx


DEFAULT_ENDPOINT = "http://localhost:8000/api/v1/wearable/mock-webhook"


@dataclass(frozen=True)
class DayPayload:
    internal_mock_id: str
    date: date
    duration_ms: int
    hypnogram: list[dict[str, Any]]
    avg_hr: float | None
    hrv: float | None
    spo2: float | None

    def to_request_json(self) -> dict[str, Any]:
        return {
            "internal_mock_id": self.internal_mock_id,
            "date": self.date.isoformat(),
            "duration": self.duration_ms,
            "hypnogram": self.hypnogram,
            "avg_hr": self.avg_hr,
            "hrv": self.hrv,
            "spo2": self.spo2,
        }


def dates_back_from_today(days: int) -> list[date]:
    if days <= 0:
        return []
    today = date.today()
    start = today - timedelta(days=days - 1)
    return [start + timedelta(days=i) for i in range(days)]


def _iso(dt: datetime) -> str:
    # FastAPI/Pydantic accepts RFC3339; this keeps timezone and seconds.
    return dt.isoformat()


def build_hypnogram(
    night_date: date,
    *,
    total_ms: int,
    deep_ratio: float,
    rem_ratio: float,
    awake_ratio: float,
    interruptions: int,
    seed: int,
) -> list[dict[str, Any]]:
    """
    Returns a list of segments with keys:
    { start_at: datetime-iso, end_at: datetime-iso, phase: deep|light|rem|awake }
    """
    rng = random.Random(seed)

    total_s = max(0, total_ms // 1000)
    if total_s == 0:
        return []

    awake_s = int(total_s * max(0.0, min(awake_ratio, 0.9)))
    deep_s = int(total_s * max(0.0, min(deep_ratio, 0.9)))
    rem_s = int(total_s * max(0.0, min(rem_ratio, 0.9)))
    light_s = max(0, total_s - (awake_s + deep_s + rem_s))

    # Ensure at least 1 second for non-empty phases when present.
    def bump(x: int, minimum: int = 1) -> int:
        return x if x == 0 else max(x, minimum)

    awake_s = bump(awake_s) if awake_s > 0 else 0
    deep_s = bump(deep_s) if deep_s > 0 else 0
    rem_s = bump(rem_s) if rem_s > 0 else 0
    light_s = bump(light_s) if light_s > 0 else 0

    start_at = datetime.combine(night_date, time(23, 0), tzinfo=UTC)

    # Split awake into multiple interruptions.
    interruptions = max(0, interruptions)
    awake_chunks: list[int] = []
    if awake_s > 0 and interruptions > 0:
        base = max(1, awake_s // interruptions)
        awake_chunks = [base] * interruptions
        remaining = awake_s - base * interruptions
        for i in range(remaining):
            awake_chunks[i % interruptions] += 1
    elif awake_s > 0:
        awake_chunks = [awake_s]

    # Create a simple cycle pattern and sprinkle awake chunks between cycles.
    cycles = max(3, min(6, total_s // (90 * 60) or 3))
    deep_chunks = [deep_s // cycles] * cycles
    rem_chunks = [rem_s // cycles] * cycles
    light_chunks = [light_s // cycles] * cycles
    for chunks, total in (
        (deep_chunks, deep_s),
        (rem_chunks, rem_s),
        (light_chunks, light_s),
    ):
        diff = total - sum(chunks)
        for i in range(max(0, diff)):
            chunks[i % cycles] += 1

    segments: list[tuple[str, int]] = []
    for i in range(cycles):
        # Add light -> deep -> light -> rem per cycle
        if light_chunks[i] > 0:
            segments.append(("light", light_chunks[i]))
        if deep_chunks[i] > 0:
            segments.append(("deep", deep_chunks[i]))
        if light_chunks[i] > 0:
            segments.append(("light", max(1, light_chunks[i] // 2)))
        if rem_chunks[i] > 0:
            segments.append(("rem", rem_chunks[i]))
        if awake_chunks:
            # probabilistically insert an awake segment after this cycle
            if rng.random() < (len(awake_chunks) / max(1, cycles)):
                segments.append(("awake", awake_chunks.pop(0)))

    # Append any remaining awake chunks.
    for a in awake_chunks:
        segments.append(("awake", a))

    # Normalize total duration back to total_s (trim or extend last light).
    current_total = sum(d for _, d in segments)
    if current_total > total_s:
        over = current_total - total_s
        phase, dur = segments[-1]
        segments[-1] = (phase, max(1, dur - over))
    elif current_total < total_s:
        segments.append(("light", total_s - current_total))

    hypnogram: list[dict[str, Any]] = []
    cursor = start_at
    for phase, dur_s in segments:
        end = cursor + timedelta(seconds=dur_s)
        hypnogram.append({"start_at": _iso(cursor), "end_at": _iso(end), "phase": phase})
        cursor = end

    return hypnogram


def gen_healthy(days: int) -> Iterable[DayPayload]:
    for day_idx, d in enumerate(dates_back_from_today(days), start=1):
        duration_ms = int(7.5 * 60 * 60 * 1000)  # 7h30m
        hrv = random.uniform(60, 80)
        spo2 = random.uniform(96.0, 99.0)
        avg_hr = random.uniform(50.0, 58.0)
        hypnogram = build_hypnogram(
            d,
            total_ms=duration_ms,
            deep_ratio=random.uniform(0.22, 0.30),
            rem_ratio=random.uniform(0.18, 0.24),
            awake_ratio=random.uniform(0.02, 0.05),
            interruptions=random.randint(0, 1),
            seed=1000 + day_idx,
        )
        yield DayPayload(
            internal_mock_id="mock_healthy",
            date=d,
            duration_ms=duration_ms,
            hypnogram=hypnogram,
            avg_hr=avg_hr,
            hrv=hrv,
            spo2=spo2,
        )


def gen_fatigue(days: int) -> Iterable[DayPayload]:
    hrv_value = 60.0
    avg_hr_value = 55.0
    for day_idx, d in enumerate(dates_back_from_today(days), start=1):
        # Trend: HRV decreases, avg HR increases.
        if day_idx > 1:
            hrv_value = max(20.0, hrv_value - random.uniform(1.0, 2.0))
            avg_hr_value = min(85.0, avg_hr_value + random.uniform(0.3, 0.9))

        duration_ms = int(7.0 * 60 * 60 * 1000)  # 7h
        spo2 = random.uniform(94.0, 98.0)
        hypnogram = build_hypnogram(
            d,
            total_ms=duration_ms,
            deep_ratio=random.uniform(0.16, 0.22),
            rem_ratio=random.uniform(0.17, 0.23),
            awake_ratio=random.uniform(0.04, 0.08),
            interruptions=random.randint(1, 3),
            seed=2000 + day_idx,
        )
        yield DayPayload(
            internal_mock_id="mock_fatigue",
            date=d,
            duration_ms=duration_ms,
            hypnogram=hypnogram,
            avg_hr=avg_hr_value,
            hrv=hrv_value,
            spo2=spo2,
        )


def gen_fragmented(days: int) -> Iterable[DayPayload]:
    for day_idx, d in enumerate(dates_back_from_today(days), start=1):
        duration_ms = int(8.0 * 60 * 60 * 1000)  # 8h in bed
        # Efficiency < 75% via higher awake ratio.
        awake_ratio = random.uniform(0.25, 0.35)
        deep_ratio = random.uniform(0.10, 0.18)
        rem_ratio = random.uniform(0.14, 0.20)
        avg_hr = random.uniform(60.0, 72.0)
        hrv = random.uniform(25.0, 45.0)

        spo2_base = random.uniform(92.0, 96.0)
        if random.random() < 0.35:
            spo2_base = random.uniform(89.0, 91.0)

        hypnogram = build_hypnogram(
            d,
            total_ms=duration_ms,
            deep_ratio=deep_ratio,
            rem_ratio=rem_ratio,
            awake_ratio=awake_ratio,
            interruptions=random.randint(6, 14),
            seed=3000 + day_idx,
        )
        yield DayPayload(
            internal_mock_id="mock_fragmented",
            date=d,
            duration_ms=duration_ms,
            hypnogram=hypnogram,
            avg_hr=avg_hr,
            hrv=hrv,
            spo2=spo2_base,
        )


async def inject_profile(
    client: httpx.AsyncClient,
    *,
    profile_name: str,
    payloads: Iterable[DayPayload],
) -> None:
    for i, p in enumerate(payloads, start=1):
        print(f"Inyectando día {i} para {profile_name}... ", end="", flush=True)
        resp = await client.post(DEFAULT_ENDPOINT, json=p.to_request_json(), timeout=30.0)
        if resp.status_code >= 400:
            print(f"ERROR ({resp.status_code}): {resp.text}")
            continue
        print("OK")


async def main() -> None:
    days = 30
    async with httpx.AsyncClient() as client:
        await inject_profile(
            client,
            profile_name="mock_healthy",
            payloads=gen_healthy(days),
        )
        await inject_profile(
            client,
            profile_name="mock_fatigue",
            payloads=gen_fatigue(days),
        )
        await inject_profile(
            client,
            profile_name="mock_fragmented",
            payloads=gen_fragmented(days),
        )


if __name__ == "__main__":
    asyncio.run(main())

