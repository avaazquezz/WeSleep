# Guía completa de endpoints + pruebas en Thunder Client (WeSleep)

## Resumen del proyecto (análisis funcional)

El backend actualmente expone **3 endpoints**:

1. `GET /health`
2. `POST /api/v1/webhooks/wearable/`
3. `POST /api/v1/sleep/smart-alarm`

Flujo real de uso:

1. Ingestas datos crudos del wearable en `/api/v1/webhooks/wearable/`.
2. Recibes un `sleep_record_id` (UUID).
3. Llamas `/api/v1/sleep/smart-alarm` con ese UUID + `target_time`.

---

## 1) Health Check

**Endpoint:** `GET /health`

### Respuesta esperada (200)

```json
{
  "status": "ok",
  "project": "WeSleep"
}
```

---

## 2) Ingesta Wearable

**Endpoint:** `POST /api/v1/webhooks/wearable/`

**Headers:**

- `Content-Type: application/json`

**Respuesta esperada (200):**

```json
"<sleep_record_id_uuid>"
```

### Campos críticos requeridos en el body

- `record_id`
- `modified_at`
- `start_at_timestamp`
- `end_at_timestamp`
- `duration`
- `metrics` (objeto)
- `provider_source`
- `provider_slug`

---

## 3) Smart Alarm

**Endpoint:** `POST /api/v1/sleep/smart-alarm`

**Headers:**

- `Content-Type: application/json`

**Body base:**

```json
{
  "sleep_record_id": "<uuid_devuelto_por_ingesta>",
  "target_time": "2026-02-12T07:00:00Z"
}
```

**Respuesta tipo (200):**

```json
{
  "suggested_time": "2026-02-12T07:00:00Z",
  "confidence": 0.9,
  "reasoning": "...",
  "quality_score": 91.0,
  "anomalies": []
}
```

---

## Casos de prueba de wearable para forzar cambios en `reasoning`

> Todos los ejemplos fueron probados contra `http://localhost:8000`.

### A) Sueño deficiente (HRV bajo) → reasoning de despertar temprano

#### Ingesta

```json
{
  "record_id": "3b4fd9de-4f80-4db0-a31b-5fd3de1a72f1",
  "modified_at": "2026-02-12T09:00:00Z",
  "start_at_timestamp": "2026-02-11T23:00:00Z",
  "end_at_timestamp": "2026-02-12T07:00:00Z",
  "duration": 28800000,
  "metrics": {
    "heartrate": 64,
    "hrv_sdnn": 20,
    "spo2": 93.0,
    "spo2_min": 91.0,
    "sleep_duration": 28800000,
    "sleep_duration_deep": 3600000,
    "sleep_duration_light": 14400000,
    "sleep_duration_rem": 9000000,
    "sleep_duration_awake": 1800000,
    "sleep_interruptions": 12
  },
  "provider_source": "simulator_wearable",
  "provider_slug": "sim"
}
```

#### Smart Alarm (usar el UUID que te devuelva la ingesta)

```json
{
  "sleep_record_id": "<uuid_de_esta_ingesta>",
  "target_time": "2026-02-12T07:00:00Z"
}
```

#### Resultado observado

```json
{
  "suggested_time": "2026-02-12T06:30:00Z",
  "confidence": 0.9,
  "reasoning": "HRV bajo (20.0ms). Se prioriza despertar temprano (06:30) para mitigar inercia.",
  "quality_score": 79.0,
  "anomalies": []
}
```

---

### B) Sueño normal (HRV normal) → reasoning de optimizar duración

#### Ingesta

```json
{
  "record_id": "4f160ec7-1bc4-4ef7-a65f-0211a90ba57f",
  "modified_at": "2026-02-12T09:00:00Z",
  "start_at_timestamp": "2026-02-11T23:00:00Z",
  "end_at_timestamp": "2026-02-12T07:00:00Z",
  "duration": 28800000,
  "metrics": {
    "heartrate": 58,
    "hrv_sdnn": 55,
    "spo2": 96.0,
    "spo2_min": 94.0,
    "sleep_duration": 28800000,
    "sleep_duration_deep": 5400000,
    "sleep_duration_light": 15300000,
    "sleep_duration_rem": 6300000,
    "sleep_duration_awake": 1800000,
    "sleep_interruptions": 5
  },
  "provider_source": "simulator_wearable",
  "provider_slug": "sim"
}
```

#### Smart Alarm

```json
{
  "sleep_record_id": "<uuid_de_esta_ingesta>",
  "target_time": "2026-02-12T07:00:00Z"
}
```

#### Resultado observado

```json
{
  "suggested_time": "2026-02-12T07:00:00Z",
  "confidence": 0.9,
  "reasoning": "HRV normal. Se optimiza duración de sueño despertando en fase ligera/despierto a las 07:00.",
  "quality_score": 91.0,
  "anomalies": []
}
```

---

### C) Sueño excelente pero target fuera de ventana → reasoning de “No hay datos”

#### Ingesta

```json
{
  "record_id": "5b3ac58f-65d4-4b8b-8cfd-0807be20329f",
  "modified_at": "2026-02-12T09:00:00Z",
  "start_at_timestamp": "2026-02-11T23:00:00Z",
  "end_at_timestamp": "2026-02-12T07:00:00Z",
  "duration": 28800000,
  "metrics": {
    "heartrate": 54,
    "hrv_sdnn": 75,
    "spo2": 97.0,
    "spo2_min": 95.0,
    "sleep_duration": 28800000,
    "sleep_duration_deep": 7200000,
    "sleep_duration_light": 13800000,
    "sleep_duration_rem": 6600000,
    "sleep_duration_awake": 1200000,
    "sleep_interruptions": 2
  },
  "provider_source": "simulator_wearable",
  "provider_slug": "sim"
}
```

#### Smart Alarm (target adrede fuera del sueño)

```json
{
  "sleep_record_id": "<uuid_de_esta_ingesta>",
  "target_time": "2026-02-12T10:00:00Z"
}
```

#### Resultado observado

```json
{
  "suggested_time": "2026-02-12T10:00:00Z",
  "confidence": 0.1,
  "reasoning": "No hay datos de sueño dentro de la ventana de 30 min.",
  "quality_score": 95.0,
  "anomalies": []
}
```

---

### D) Sueño óptimo pero toda la ventana en profundo → reasoning de “hora límite”

#### Ingesta

```json
{
  "record_id": "38c0f7ad-35f1-4c01-a62c-a958f2ce9cd6",
  "modified_at": "2026-02-12T09:00:00Z",
  "start_at_timestamp": "2026-02-11T23:00:00Z",
  "end_at_timestamp": "2026-02-12T07:00:00Z",
  "duration": 28800000,
  "metrics": {
    "heartrate": 52,
    "hrv_sdnn": 85,
    "spo2": 98.0,
    "spo2_min": 96.0,
    "sleep_duration": 28800000,
    "sleep_duration_deep": 28800000,
    "sleep_duration_light": 0,
    "sleep_duration_rem": 0,
    "sleep_duration_awake": 0,
    "sleep_interruptions": 0
  },
  "provider_source": "simulator_wearable",
  "provider_slug": "sim"
}
```

#### Smart Alarm (target en 06:59 para que la ventana completa sea profundo)

```json
{
  "sleep_record_id": "<uuid_de_esta_ingesta>",
  "target_time": "2026-02-12T06:59:00Z"
}
```

#### Resultado observado

```json
{
  "suggested_time": "2026-02-12T06:59:00Z",
  "confidence": 0.5,
  "reasoning": "Usuario en sueño profundo durante toda la ventana. Se despierta a la hora límite.",
  "quality_score": 97.0,
  "anomalies": []
}
```

---

## Casos de error útiles en Thunder Client

### Smart Alarm con UUID inexistente

**Body:**

```json
{
  "sleep_record_id": "11111111-1111-1111-1111-111111111111",
  "target_time": "2026-02-12T07:00:00Z"
}
```

**Esperado:** `404`

```json
{
  "detail": "Sleep record not found"
}
```

### Smart Alarm con UUID inválido

**Body:**

```json
{
  "sleep_record_id": "uuid-invalido",
  "target_time": "2026-02-12T07:00:00Z"
}
```

**Esperado:** `422`

### Ingesta wearable sin `record_id`

**Esperado:** `422`

---

## Orden recomendado de pruebas en Thunder Client

1. `GET /health`
2. `POST /api/v1/webhooks/wearable/` (uno de los perfiles A/B/C/D)
3. Copiar UUID de respuesta
4. `POST /api/v1/sleep/smart-alarm` con ese UUID
5. Repetir para cada perfil y comparar `reasoning`

---

## Nota clave para interpretar `reasoning`

Para que cambie el `reasoning` en `smart-alarm`, importan sobre todo dos cosas:

- **HRV (`metrics.hrv_sdnn`)**: bajo vs normal.
- **`target_time`** respecto a la noche registrada: si queda fuera de ventana, verás “No hay datos...”.

Por eso un sueño muy bueno puede dar un `reasoning` “malo” si el `target_time` está mal alineado.
