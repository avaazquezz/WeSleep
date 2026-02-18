# WeSleep - Smart Alarm Backend

Backend API for the WeSleep smart alarm application. Built with FastAPI, SQLModel, and Docker.

## 🏗 System Architecture

### Directory Structure

```ascii
WeSleep/
├── app/
│   ├── routers/             # API Route Handlers
│   │   ├── alarm.py         # Smart Alarm endpoints (prediction logic)
│   │   ├── deps.py          # API Dependencies (DB Session)
│   │   └── wearable.py      # Raw Data Ingestion endpoints
│   ├── services/            # External Service Integrations
│   │   └── reasoning_service.py # Google Gemini AI — personalized sleep reasoning
│   ├── config.py            # Environment Configuration (Pydantic)
│   ├── database.py          # Database Connection (Async SQLite)
│   ├── logic.py             # Core Business Logic (Parsing, Scoring, Algorithms)
│   ├── main.py              # Application Entry Point & Lifespan
│   └── models.py            # Database Models & Pydantic Schemas
├── data/                    # Persistent Storage (SQLite)
├── docs/                    # Documentation & Examples
│   └── smart_alarm_examples.md # cURL examples for Smart Alarm POST
├── tests/                   # Pytest Suite
├── .env.example             # Environment Variables Template
├── docker-compose.yml       # Container Orchestration
└── pyproject.toml           # Python Dependencies (Ruff, Pytest, FastAPI)
```

### Data Flow

The system follows a **"Store Raw, Process on Demand"** philosophy to ensure data integrity and auditability.

1.  **Ingestion (Webhook)**
    *   **Source**: Wearable Device (e.g., Apple Watch via Shortcut/App).
    *   **Endpoint**: `POST /api/v1/wearable/`
    *   **Action**: Validates the payload against `WearableRawPayload`.
    *   **Storage**: Saves the **entire raw JSON** into the `sleep_records` table in SQLite. No transformation is done at this stage to preserve original data.

2.  **Smart Alarm Request**
    *   **Source**: User App requesting an optimal wake-up time.
    *   **Endpoint**: `POST /api/v1/alarm/smart-alarm`
    *   **Input**: `sleep_record_id`, `target_time`.
    *   **Processing**:
        1.  Retrieves raw JSON from DB.
        2.  **Parser**: Transforms raw JSON -> `CleanSleepData` (Normalized Internal Format).
        3.  **Evaluator**: Calculates `quality_score` (0-100) and detects `anomalies` (Apnea, Fragmentation).
        4.  **Predictor**: Analyzes the Hypnogram (sleep phases) and HRV to find the best wake-up time within a 30-minute window.
        5.  **Gemini AI Reasoning**: Sends sleep metrics, score, and anomalies to Google Gemini to generate a **personalized 3-4 line analysis** in Spanish. Falls back to heuristic reasoning if the API key is missing or the call fails.
    *   **Output**: JSON with suggested time, AI-generated reasoning, and sleep score.

## 📖 Data Dictionary

### Key Data Models (`app/models.py`)

#### `SleepRecord` (Database Table)
| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary Key. Internal unique identifier. |
| `user_id` | UUID | Owner of the data. |
| `timestamp` | DateTime | When the sleep session ended (indexed). |
| `payload` | JSON | **Full original payload** from the provider. |
| `provider_source` | String | e.g., "apple_healthkit". |

#### `CleanSleepData` (Internal Logic Object)
Normalized view of the sleep data used for analysis.
| Field | Description |
|-------|-------------|
| `duration` | Total sleep time in milliseconds. |
| `hypnogram` | List of sleep segments (Start, End, Phase). Phases: `deep`, `light`, `rem`, `awake`. |
| `media_HR` | Average Heart Rate. |
| `HRV` | Heart Rate Variability (SDNN). Higher is generally better/more recovered. |
| `SpO2` | Blood Oxygen Saturation (Avg, Min, Max). <90% triggers apnea warning. |
| `movimiento` | Normalized movement index (0-1). |

## 🤖 AI Reasoning — Groq + Llama 3.3 70B

The Smart Alarm uses **Groq** (100% free) with **Llama 3.3 70B** to generate professional, personalized sleep analyses. Each response includes a 3-4 line reasoning in Spanish that considers:

- Sleep duration & efficiency
- HRV and heart rate patterns
- SpO2 levels & breathing rate
- Detected anomalies (apnea, fragmentation)
- Sleep architecture (deep/light/REM ratios)

**Why Groq?** Free tier (30 RPM, 14,400 RPD), fastest inference (~500 tokens/sec), and Llama 3.3 70B rivals GPT-4 on reasoning.

**Fallback**: If `GROQ_API_KEY` is not set or the API call fails, the system gracefully falls back to the original heuristic reasoning — no functionality is lost.

See [`docs/smart_alarm_examples.md`](docs/smart_alarm_examples.md) for 5 ready-to-use cURL examples.

## 🚀 Setup & Run

1.  **Environment Setup**
    ```bash
    cp .env.example .env
    # Edit .env with your config:
    #   GROQ_API_KEY=your-groq-api-key  (free at https://console.groq.com)
    ```

2.  **Run with Docker**
    ```bash
    docker compose up --build
    ```
    API will be available at: `http://localhost:8000`
    Docs: `http://localhost:8000/docs`

3.  **Run Tests**
    ```bash
    docker compose exec api pytest
    # Or locally:
    .venv/bin/python -m pytest tests/ -v
    ```