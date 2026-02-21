## WeSleep Backend — README Tècnic (B2B Multi‑Tenant)

### 1) Arquitectura d’execució (nivell superior)
- **Framework**: FastAPI.
- **Accés a BD**: SQLModel + SQLAlchemy 2.x amb **sessions asíncrones**.
- **Base de dades objectiu**: PostgreSQL (compatible amb Supabase). En local, `docker-compose.yml` engega un Postgres per a desenvolupament.
- **Estratègia d’IDs**: UUID v4 generats a l’aplicació (ORM). El DDL de Supabase també admet valors per defecte a BD.
- **Payload wearable**: JSON persistit a `sleep_records.payload` com a **JSONB** a Postgres.
- **IA (Groq)**: `groq.AsyncGroq` per a generació de text (sense diagnòstic). La lògica de negoci es troba a `app/services/reasoning_service.py`.

### 2) Model de dades (B2B Multi‑Tenant)
Relació d’entitats:

- `Tenant` (Mutua / client B2B)
  - `id: UUID` (PK)
  - `name: str` (NOT NULL)
  - `api_key: str` (UNIQUE, NOT NULL)
  - `created_at: timestamptz`
- `Patient` (usuari final)
  - `id: UUID` (PK)
  - `tenant_id: UUID` (FK → `tenants.id`)
  - `internal_mock_id: str` (UNIQUE, NOT NULL)
  - `created_at: timestamptz`
- `SleepRecord` (Dades de son)
  - `id: UUID` (PK)
  - `patient_id: UUID` (FK → `patients.id`)
  - `date: date` (NOT NULL)
  - `payload: jsonb/json` (NOT NULL)
  - `created_at: timestamptz`

Índexs rellevants:
- `patients(tenant_id)` (acelera consultes per tenant)
- `sleep_records(patient_id)` (acelera consultes per pacient)

DDL recomanat (Supabase): veure `supabase_setup.sql`.

### 3) Capa de base de dades
Fitxer: `app/database.py`
- `engine`: `AsyncEngine` creat amb `create_async_engine(settings.DATABASE_URL, ...)`.
- `async_session_maker`: `async_sessionmaker` amb `expire_on_commit=False`.
- `init_db()`: crea les taules amb `SQLModel.metadata.create_all` (mode dev). 

### 4) Encaminament de l’API
Punt d’entrada: `app/main.py`
- Munta `api_router` amb el prefix `settings.API_V1_STR` (per defecte `/api/v1`).

Registre de routers: `app/routers/__init__.py`
- `wearable`:
  - `/api/v1/webhooks/wearable/*`
  - `/api/v1/wearable/*`
- `sleep` (Smart Alarm):
  - `/api/v1/sleep/smart-alarm`
- `alarm` (estadístic):
  - `/api/v1/alarm/predict/{patient_id}`
- `insights`:
  - `/api/v1/insights/weekly/{patient_id}`
  - `/api/v1/insights/monthly/{patient_id}`

### 5) Ingestió wearable
Fitxer: `app/routers/wearable.py`

#### 5.1) POST `/api/v1/webhooks/wearable/`
- Entrada: `WearableRawPayload` (esquema Pydantic a `app/models.py`).
- Persistència:
  - Crea o reutilitza un `Tenant` de dev (`api_key="dev_default_tenant"`).
  - Crea o reutilitza un `Patient` amb `internal_mock_id = "wearable_{record_id}"`.
  - Insereix `SleepRecord` amb:
    - `patient_id` del Patient anterior
    - `date = start_at_timestamp.date()`
    - `payload = payload.model_dump(mode="json")`
- Sortida: `sleep_record_id` (UUID) del registre inserit.

Notes tècniques:
- Aquest endpoint **encara no implementa** autenticació ni identitat real d’usuari/tenant des del proveïdor.
- El vincle actual amb l’«usuari» és una estratègia de dev (`wearable_{record_id}`) per permetre ingesta i pipelines.

#### 5.2) POST `/api/v1/wearable/mock-webhook`
- Entrada: JSON simplificat (mock) amb:
  - `internal_mock_id`, `date`, `duration`, `hypnogram`, `avg_hr`, `hrv`, `spo2`
- Comportament:
  - Cerca `Patient` per `internal_mock_id`
  - Si no existeix: **404**
  - Si existeix: insereix `SleepRecord` amb el `payload` cru

### 6) Smart Alarm (heurístic + enriquiment opcional)
Fitxer: `app/routers/alarm.py` (ruta `/sleep/smart-alarm`) + `app/logic.py`

Flux:
1. L’endpoint rep `{sleep_record_id, target_time}`.
2. Carrega `SleepRecord.payload`.
3. Normalitza a `CleanSleepData` amb `parse_sleep_payload(payload)`.
4. Calcula `quality_score` i `anomalies`.
5. Executa `predict_optimal_wakeup(...)`:
   - Finestra de 30 minuts prèvia a `target_time`
   - Selecció de slot evitant `deep`
   - Regla addicional: HRV baix → despertar abans
6. (Opcional) Si hi ha `GROQ_API_KEY`, crida `generate_sleep_reasoning(...)` per enriquir el text.

### 7) Alarm predict (estadística pura per històric)
Endpoint: `GET /api/v1/alarm/predict/{patient_id}?target_time=HH:MM`
Fitxer: `app/routers/alarm.py` + funció `app/logic.py:calculate_optimal_wakeup_time(...)`

Algorisme:
- Utilitza fins als **últims 7 `sleep_records`** del pacient.
- Avaluació minut a minut a l’interval \([target-window, target]\).
- Pesos per fase històrica en aquell minut:
  - `light` / `awake`: +2
  - `rem`: +1
  - `deep`: -2
- Retorna el `HH:MM` amb el score agregat més alt.
- Fallback: si no hi ha dades o segments vàlids, retorna `target_time`.

Assumpció del payload:
- `payload.hypnogram`: llista amb `{start_time, end_time, phase}` (també es suporta `{start_at, end_at, phase}`).

### 8) Insights (Weekly Recap + Monthly Anomaly)
Fitxer: `app/routers/insights.py`

Extraccions (per nit):
- **HRV**: `payload.hrv` o `payload.metrics.hrv_sdnn`
- **Son profund (min)**:
  - preferent: suma dels segments `phase=="deep"` a `payload.hypnogram`
  - fallback: `payload.metrics.sleep_duration_deep` (ms → min)
- **Eficiència**:
  - \(eff = sleep_seconds / bed_seconds\)
  - `sleep_seconds`: `payload.duration` (ms) o `payload.metrics.sleep_duration`
  - `bed_seconds`: `start_at_timestamp/end_at_timestamp` si existeixen, o el rang \([min(start), max(end)]\) de l’hipnograma

#### 8.1) GET `/api/v1/insights/weekly/{patient_id}`
- Requeriments: **14 dies** (si no, HTTP 400 `"Datos insuficientes para el análisis"`).
- Calcula agregats i tendències per a:
  - `previous_week` (dies 1–7) vs `current_week` (dies 8–14)
- Retorna:
  - agregats (HRV/Son profund/Eficiència)
  - tendències en %
  - sèrie `daily` (per a gràfiques)
  - `weekly_recap` (text de Groq)

#### 8.2) GET `/api/v1/insights/monthly/{patient_id}`
- Requeriments: **30 dies** d’històric recent (si no, HTTP 400).
- Analitza:
  - `current_month` (**últims 30 dies**) i la seva tendència interna (p. ex. deteriorament sostingut en HRV o eficiència dins del mateix període)
- Crida `AISleepAnalyzer.generate_monthly_anomaly_alert(...)`:
  - si no hi ha caiguda greu → string buit → resposta `{status:"ok", alert:null}`
  - si hi ha alerta → text formal (màx. 4 línies)

### 9) Integració Groq (sense diagnòstic)
Fitxer: `app/services/reasoning_service.py`

Client:
- `AsyncGroq(api_key=settings.GROQ_API_KEY)`

Mètodes rellevants:
- `AISleepAnalyzer.generate_weekly_recap(current_week, prev_week) -> str`
  - Prompt: «coach de benestar», 3 línies, motivador, **no diagnosticar**.
  - Fallback si falla Groq o falta API key: missatge genèric de dashboard.
- `AISleepAnalyzer.generate_monthly_anomaly_alert(current_month, baseline_month) -> str`
  - Prompt: «alerta primerenca B2B», formal, **no diagnosticar**.
  - Si no hi ha caiguda greu: retorna string buit.

### 10) Mock Engine (injecció de dades sintètiques)
Fitxer: `scripts/mock_engine.py`
- Injecta contra `POST /api/v1/wearable/mock-webhook`.
- Genera 30 dies d’històric per als perfils:
  - `mock_healthy`
  - `mock_fatigue`
  - `mock_fragmented`

Nota: els `Patient` per a aquests perfils han d’existir (o crear-se via SQL a Supabase / seed local).

### 11) Estratègia de testing (QA)
Framework:
- `pytest`, `pytest-asyncio`, `httpx`

Aïllament de BD:
- `tests/conftest.py` crea un **SQLite async in-memory** i sobreescriu `get_session` (per no tocar Supabase).

Suites destacades:
- `tests/test_mock_engine.py`: valida la persistència per `internal_mock_id`.
- `tests/test_alarm_logic.py`: determinisme de l’algorisme matemàtic.
- `tests/test_insights.py`: weekly/monthly; **mock de Groq** amb `unittest.mock.patch` a `AsyncGroq`.

Estat esperat: `pytest -v tests/` en verd.

### 12) Limitacions conegudes / TO DOs
- Autenticació i **mapeig real** provider→patient→tenant per a `/webhooks/wearable/`.
- Migracions (Alembic) per a producció.
- RLS a Supabase si s’exposa accés directe per tenant.
