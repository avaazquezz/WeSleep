# Ejemplos de POST para Smart Alarm con Gemini Reasoning

## Instrucciones

Primero, crea un sleep record con `POST /api/v1/wearable/ingest`, luego usa el `id` devuelto para llamar a `POST /api/v1/smart-alarm`.

---

## 1. Durmiente Saludable — Noche perfecta

```bash
# Paso 1: Ingestar datos de sueño
curl -X POST http://localhost:8000/api/v1/wearable/ingest \
  -H "Content-Type: application/json" \
  -H "X-User-ID: 11111111-1111-1111-1111-111111111111" \
  -d '{
    "record_id": "a1a1a1a1-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "modified_at": "2025-04-30T08:00:00Z",
    "start_at_timestamp": "2025-04-29T23:00:00Z",
    "end_at_timestamp": "2025-04-30T07:00:00Z",
    "duration": 28800000,
    "metrics": {
      "heartrate": 55,
      "hrv_sdnn": 72.0,
      "spo2": 97.0,
      "spo2_min": 95.0,
      "spo2_max": 99.0,
      "sleep_duration": 28800000,
      "sleep_duration_deep": 5760000,
      "sleep_duration_light": 14400000,
      "sleep_duration_rem": 5760000,
      "sleep_duration_awake": 2880000,
      "sleep_interruptions": 3,
      "sleep_breathing_rate": 14.2
    },
    "provider_source": "apple_healthkit_sleep_aggregation",
    "provider_slug": "apple"
  }'

# Paso 2: Smart Alarm (usar el ID devuelto en step 1)
curl -X POST http://localhost:8000/api/v1/smart-alarm \
  -H "Content-Type: application/json" \
  -d '{
    "sleep_record_id": "<ID_FROM_STEP_1>",
    "target_time": "2025-04-30T07:00:00Z"
  }'
```

**Perfil**: 8h de sueño, HRV 72ms (excelente), SpO2 97%, 20% profundo.
**Reasoning esperado**: Análisis positivo, recuperación óptima, despertar en fase ligera.

---

## 2. Durmiente Estresado — HRV bajo, noche agitada

```bash
curl -X POST http://localhost:8000/api/v1/wearable/ingest \
  -H "Content-Type: application/json" \
  -H "X-User-ID: 22222222-2222-2222-2222-222222222222" \
  -d '{
    "record_id": "b2b2b2b2-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    "modified_at": "2025-04-30T08:00:00Z",
    "start_at_timestamp": "2025-04-29T23:30:00Z",
    "end_at_timestamp": "2025-04-30T06:30:00Z",
    "duration": 25200000,
    "metrics": {
      "heartrate": 72,
      "hrv_sdnn": 28.0,
      "spo2": 95.0,
      "spo2_min": 92.0,
      "spo2_max": 98.0,
      "sleep_duration": 25200000,
      "sleep_duration_deep": 2520000,
      "sleep_duration_light": 12600000,
      "sleep_duration_rem": 5040000,
      "sleep_duration_awake": 5040000,
      "sleep_interruptions": 12,
      "sleep_breathing_rate": 16.8
    },
    "provider_source": "apple_healthkit_sleep_aggregation",
    "provider_slug": "apple"
  }'

curl -X POST http://localhost:8000/api/v1/smart-alarm \
  -H "Content-Type: application/json" \
  -d '{
    "sleep_record_id": "<ID_FROM_STEP_1>",
    "target_time": "2025-04-30T07:00:00Z"
  }'
```

**Perfil**: 7h, HRV 28ms (estrés), FC alta 72bpm, 12 interrupciones, sueño fragmentado.
**Reasoning esperado**: Gemini detectará estrés, priorizará despertar temprano para mitigar inercia.

---

## 3. Posible Apnea — SpO2 crítico

```bash
curl -X POST http://localhost:8000/api/v1/wearable/ingest \
  -H "Content-Type: application/json" \
  -H "X-User-ID: 33333333-3333-3333-3333-333333333333" \
  -d '{
    "record_id": "c3c3c3c3-cccc-cccc-cccc-cccccccccccc",
    "modified_at": "2025-04-30T08:00:00Z",
    "start_at_timestamp": "2025-04-30T00:00:00Z",
    "end_at_timestamp": "2025-04-30T06:00:00Z",
    "duration": 21600000,
    "metrics": {
      "heartrate": 68,
      "hrv_sdnn": 35.0,
      "spo2": 89.0,
      "spo2_min": 83.0,
      "spo2_max": 95.0,
      "sleep_duration": 21600000,
      "sleep_duration_deep": 1080000,
      "sleep_duration_light": 10800000,
      "sleep_duration_rem": 4320000,
      "sleep_duration_awake": 5400000,
      "sleep_interruptions": 18,
      "sleep_breathing_rate": 19.5
    },
    "provider_source": "apple_healthkit_sleep_aggregation",
    "provider_slug": "apple"
  }'

curl -X POST http://localhost:8000/api/v1/smart-alarm \
  -H "Content-Type: application/json" \
  -d '{
    "sleep_record_id": "<ID_FROM_STEP_1>",
    "target_time": "2025-04-30T06:30:00Z"
  }'
```

**Perfil**: 6h, SpO2 min 83% (crítico), 18 interrupciones, respiración alta 19.5rpm.
**Reasoning esperado**: Alerta de posible apnea, recomendación de consulta médica.

---

## 4. Atleta Recuperado — Métricas excelentes

```bash
curl -X POST http://localhost:8000/api/v1/wearable/ingest \
  -H "Content-Type: application/json" \
  -H "X-User-ID: 44444444-4444-4444-4444-444444444444" \
  -d '{
    "record_id": "d4d4d4d4-dddd-dddd-dddd-dddddddddddd",
    "modified_at": "2025-04-30T08:30:00Z",
    "start_at_timestamp": "2025-04-29T22:00:00Z",
    "end_at_timestamp": "2025-04-30T06:30:00Z",
    "duration": 30600000,
    "metrics": {
      "heartrate": 48,
      "hrv_sdnn": 95.0,
      "spo2": 98.0,
      "spo2_min": 96.0,
      "spo2_max": 100.0,
      "sleep_duration": 30600000,
      "sleep_duration_deep": 7650000,
      "sleep_duration_light": 12240000,
      "sleep_duration_rem": 7650000,
      "sleep_duration_awake": 3060000,
      "sleep_interruptions": 1,
      "sleep_breathing_rate": 12.0
    },
    "provider_source": "apple_healthkit_sleep_aggregation",
    "provider_slug": "apple"
  }'

curl -X POST http://localhost:8000/api/v1/smart-alarm \
  -H "Content-Type: application/json" \
  -d '{
    "sleep_record_id": "<ID_FROM_STEP_1>",
    "target_time": "2025-04-30T07:00:00Z"
  }'
```

**Perfil**: 8.5h, HRV 95ms (atleta), FC 48bpm (bradicardia deportiva), 25% profundo.
**Reasoning esperado**: Elogio de recuperación excepcional, maximizar duración de sueño.

---

## 5. Durmiente con datos mínimos — Sin métricas opcionales

```bash
curl -X POST http://localhost:8000/api/v1/wearable/ingest \
  -H "Content-Type: application/json" \
  -H "X-User-ID: 55555555-5555-5555-5555-555555555555" \
  -d '{
    "record_id": "e5e5e5e5-eeee-eeee-eeee-eeeeeeeeeeee",
    "modified_at": "2025-04-30T08:00:00Z",
    "start_at_timestamp": "2025-04-30T01:00:00Z",
    "end_at_timestamp": "2025-04-30T07:00:00Z",
    "duration": 21600000,
    "metrics": {
      "heartrate": 62,
      "sleep_duration": 21600000,
      "sleep_duration_deep": 3240000,
      "sleep_duration_light": 10800000,
      "sleep_duration_rem": 4320000,
      "sleep_duration_awake": 3240000
    },
    "provider_source": "apple_healthkit_sleep_aggregation",
    "provider_slug": "apple"
  }'

curl -X POST http://localhost:8000/api/v1/smart-alarm \
  -H "Content-Type: application/json" \
  -d '{
    "sleep_record_id": "<ID_FROM_STEP_1>",
    "target_time": "2025-04-30T07:30:00Z"
  }'
```

**Perfil**: 6h, sin HRV/SpO2/respiración (dispositivo básico). Solo fases y FC.
**Reasoning esperado**: Análisis con datos parciales, Gemini interpreta con lo disponible.
