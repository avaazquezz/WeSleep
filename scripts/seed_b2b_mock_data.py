from __future__ import annotations

import argparse
import asyncio
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete
from sqlmodel import select

from app.database import async_session_maker
from app.models import Patient, SleepRecord, Tenant
from scripts.mock_engine import (
    DayPayload,
    gen_fatigue,
    gen_fragmented,
    gen_healthy,
)


@dataclass(frozen=True)
class MockPatientSeed:
    patient_id: UUID
    internal_mock_id: str
    profile: str


MOCK_PATIENTS: list[MockPatientSeed] = [
    MockPatientSeed(
        patient_id=UUID("e9f7e4d0-2e3e-4ebf-b77a-18011e5897fa"),
        internal_mock_id="b2b_e9f7e4d0_control",
        profile="healthy",
    ),
    MockPatientSeed(
        patient_id=UUID("f05277dc-ecee-4ea2-9c4c-3de9b54008f1"),
        internal_mock_id="b2b_f05277dc_fatigue",
        profile="fatigue",
    ),
    MockPatientSeed(
        patient_id=UUID("2013db39-79dd-45ec-b9ae-9eeaa7b1b6ad"),
        internal_mock_id="b2b_2013db39_fragmented",
        profile="fragmented",
    ),
]


def _compute_deep_ms(hypnogram: list[dict[str, Any]]) -> int:
    total = 0
    for seg in hypnogram:
        try:
            if (seg.get("phase") or "").strip().lower() != "deep":
                continue
            s = seg.get("start_at")
            e = seg.get("end_at")
            if not isinstance(s, str) or not isinstance(e, str):
                continue
            start = datetime.fromisoformat(s.replace("Z", "+00:00"))
            end = datetime.fromisoformat(e.replace("Z", "+00:00"))
            total += int((end - start).total_seconds() * 1000)
        except Exception:
            continue
    return max(0, total)


def _daypayload_to_sleeprecord_payload(p: DayPayload) -> dict[str, Any]:
    deep_ms = _compute_deep_ms(p.hypnogram)
    start_at = p.hypnogram[0]["start_at"] if p.hypnogram else None
    end_at = p.hypnogram[-1]["end_at"] if p.hypnogram else None

    payload: dict[str, Any] = {
        "duration": int(p.duration_ms),
        "hypnogram": p.hypnogram,
        "hrv": float(p.hrv) if p.hrv is not None else None,
        "avg_hr": float(p.avg_hr) if p.avg_hr is not None else None,
        "spo2": float(p.spo2) if p.spo2 is not None else None,
        "metrics": {
            "hrv_sdnn": float(p.hrv) if p.hrv is not None else None,
            "sleep_duration": int(p.duration_ms),
            "sleep_duration_deep": int(deep_ms),
        },
    }

    if isinstance(start_at, str) and isinstance(end_at, str):
        payload["start_at_timestamp"] = start_at
        payload["end_at_timestamp"] = end_at

    return payload


def _generate_days(profile: str, days: int) -> list[DayPayload]:
    if profile == "healthy":
        return list(gen_healthy(days))
    if profile == "fatigue":
        return list(gen_fatigue(days))
    if profile == "fragmented":
        return list(gen_fragmented(days))
    raise ValueError(f"Unknown profile: {profile}")


async def seed(days: int, *, tenant_api_key: str) -> None:
    # Ensure deterministic series for each run.
    random.seed(42)

    async with async_session_maker() as session:
        tenant = (await session.exec(select(Tenant).where(Tenant.api_key == tenant_api_key))).first()
        if tenant is None:
            tenant = Tenant(name="WeSleep B2B Demo", api_key=tenant_api_key)
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)

        for mp in MOCK_PATIENTS:
            patient = await session.get(Patient, mp.patient_id)
            if patient is None:
                patient = Patient(
                    id=mp.patient_id,
                    tenant_id=tenant.id,
                    internal_mock_id=mp.internal_mock_id,
                )
                session.add(patient)
                await session.commit()
            else:
                # Keep existing tenant_id; ensure internal_mock_id is set and stable.
                if patient.internal_mock_id != mp.internal_mock_id:
                    patient.internal_mock_id = mp.internal_mock_id
                    session.add(patient)
                    await session.commit()

            start_date = date.today() - timedelta(days=days - 1)
            await session.exec(
                delete(SleepRecord).where(
                    SleepRecord.patient_id == mp.patient_id,
                    SleepRecord.date >= start_date,
                )
            )
            await session.commit()

            payloads = _generate_days(mp.profile, days)
            records: list[SleepRecord] = []
            for p in payloads:
                records.append(
                    SleepRecord(
                        patient_id=mp.patient_id,
                        date=p.date,
                        payload=_daypayload_to_sleeprecord_payload(p),
                    )
                )
            session.add_all(records)
            await session.commit()

            print(f"Seeded {len(records)} sleep_records for {mp.patient_id} ({mp.profile}).")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed B2B mock sleep data for 3 demo patients.")
    parser.add_argument("--days", type=int, default=120, help="Days to seed per patient (default: 120)")
    parser.add_argument(
        "--tenant-api-key",
        type=str,
        default="tenant_b2b_demo",
        help="Tenant api_key to use/create (default: tenant_b2b_demo)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.days < 35:
        raise SystemExit("Use at least --days 35 to satisfy weekly (14) + monthly (30) insights reliably.")
    asyncio.run(seed(args.days, tenant_api_key=args.tenant_api_key))


if __name__ == "__main__":
    main()

