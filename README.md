# Log Investigator

Log Investigator is an agentic log analysis service built with FastAPI. Given a short description of an incident and a time range, it queries application logs stored in MariaDB, detects the anomalous period, groups errors, traces failing requests across services and builds a timeline of events. An LLM then proposes a root cause, which is checked against the logs themselves. If the hypothesis cannot be verified, the system retries once with feedback and finally falls back to a rule-based hypothesis. The result is returned as structured JSON or as a Markdown report.

## Data

The system works on structured application logs stored in a single MariaDB table named `logs`, with one row per log line. Logs come from a chain of services that handle each request in order (`api-gateway`, `auth-service`, `order-service`, `db-service`), and every line carries a request ID so that a request can be followed across services.

| Column | Type | Description |
|---|---|---|
| `id` | BIGINT | Auto-incrementing primary key |
| `ts` | DATETIME(3) | Timestamp with millisecond precision |
| `service` | VARCHAR(50) | Service that emitted the line |
| `level` | VARCHAR(10) | Log level such as `INFO`, `WARN` or `ERROR` |
| `request_id` | CHAR(36) | UUID shared by all lines of one request |
| `message` | TEXT | Free-text log message |
| `error_type` | VARCHAR(50) | Error code such as `DB_CONNECTION_FAILED` or `TIMEOUT` (null for healthy lines) |
| `latency_ms` | INT | Latency of the operation in milliseconds |

The included generator produces synthetic data in this format, but any logs loaded into this table can be investigated.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- Docker and Docker Compose (for the MariaDB database)
- An API key for an OpenAI-compatible LLM endpoint (the default configuration uses Google Gemini)

## Setup

1. Install dependencies:

   ```
   uv sync
   ```

2. Start the database:

   ```
   docker compose up -d
   ```

   This starts a MariaDB 11 container with the database `logsdb`, user `loguser` and password `logpass`, exposed on port 3306.

3. Create the `logs` table by running `scripts/schema.sql` against the database:

   ```
   docker exec -i mariadb mariadb -uloguser -plogpass logsdb < scripts/schema.sql
   ```

4. Create your environment file:

   ```
   cp .env.example .env
   ```

   Then edit `.env`:

   | Variable | Description |
   |---|---|
   | `DB_URL` | SQLAlchemy connection string for the database |
   | `LLM_BASE_URL` | Base URL of an OpenAI-compatible API |
   | `LLM_API_KEY` | API key for the LLM provider |
   | `LLM_MODEL` | Model name to use, for example `gemini-2.5-flash` |

   To see which models your key can access, run `uv run python -m scripts.list_models`.

## Generating Sample Data

`app/generator.py` populates the database with fake log records. Each request passes through `api-gateway`, `auth-service`, `order-service` and `db-service`, and a 12 minute incident is injected into the data at 14:05 on 2026-10-01.

```
uv run python -m app.generator
```

Options:

| Flag | Description | Default |
|---|---|---|
| `--n` | Number of requests to generate | `20000` |
| `--kind` | Incident type: `db_failure`, `auth_failure` or `high_latency` | `db_failure` |
| `--truncate` | Empty the `logs` table before generating | off |

Example:

```
uv run python -m app.generator --n 20000 --kind db_failure --truncate
```

## Running the Server

```
uv run uvicorn app.main:app
```

The API is available at `http://127.0.0.1:8000`, and interactive documentation is served at `http://127.0.0.1:8000/docs`.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/investigate` | Run an investigation and return the full structured result as JSON |
| POST | `/investigate/report` | Run an investigation and return a Markdown report |

Request body for both investigation endpoints:

```json
{
  "description": "Users reported checkout failures around 2 PM",
  "start": "2026-10-01T00:00:00",
  "end": "2026-10-01T23:59:59"
}
```

Example:

```
curl -X POST http://127.0.0.1:8000/investigate/report \
  -H "Content-Type: application/json" \
  -d '{"description": "Users reported checkout failures around 2 PM", "start": "2026-10-01T00:00:00", "end": "2026-10-01T23:59:59"}'
```

If no anomaly is found in the given range, the response has the status `no_anomaly_found`. A Bruno collection with these requests is included in `bruno/apis.json`, and a sample report is available in `output/report.md`.

## Project Structure

```
app/
  main.py            FastAPI application and routes
  config.py          Environment configuration
  db.py              Database engine and query helper
  generator.py       Fake log record generator
  investigator/
    anomaly.py       Detects the anomalous time window
    evidence.py      Collects evidence for the window
    correlate.py     Groups and correlates errors
    trace.py         Traces failing requests across services
    timeline.py      Builds the event timeline
    hypothesis.py    LLM and rule-based root cause hypotheses
    verify.py        Verifies a hypothesis against the logs
    reasoning.py     Generate, verify, retry and fallback loop
    pipeline.py      End-to-end investigation entry point
    report.py        Markdown report rendering
scripts/
  schema.sql         Database schema
  list_models.py     Lists available LLM models
bruno/               API request collection
```

## Tests

The `test_*.py` files in `app/` and `app/investigator/` are scripts for exercising individual stages of the pipeline. Some of them call the LLM and require a valid `.env` and a populated database. The `pytest` and `httpx` development dependencies are installed by `uv sync`.