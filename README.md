# Log Investigator

Log Investigator is an agentic log analysis service built with FastAPI, with a Next.js web interface. Given a short description of an incident and a time range, it queries application logs stored in MariaDB, detects the anomalous period, groups errors, traces failing requests across services and builds a timeline of events. An LLM then proposes a root cause, which is checked against the logs themselves. If the hypothesis cannot be verified, the system retries once with feedback and finally falls back to a rule-based hypothesis. The result is returned as structured JSON or as a Markdown report.

The web interface lets you see errors over time, run investigations and read the results, search raw logs, and follow a single request across services.

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

The included generator produces synthetic data in this format, but any logs loaded into this table can be investigated. Timestamps have no timezone and are treated as plain wall-clock values everywhere.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- Docker and Docker Compose (for the MariaDB database)
- Node.js 18.17 or newer (for the web interface)
- An API key for an OpenAI-compatible LLM endpoint (the default configuration uses Google Gemini)

## Setup

### Backend

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
   | `CORS_ORIGINS` | Optional. Comma-separated origins allowed to call the API directly from a browser, for example `http://localhost:3000`. Not needed when using the frontend's built-in proxy |

   To see which models your key can access, run `uv run python -m scripts.list_models`.

### Frontend

```
cd frontend
npm install
cp .env.local.example .env.local
```

On Windows, use `copy .env.local.example .env.local` for the last command.

`.env.local` contains one setting:

| Variable | Description |
|---|---|
| `API_URL` | Where the FastAPI backend runs. The frontend proxies `/api/*` to this address. Default `http://127.0.0.1:8000` |

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

## Running the Project

Run the backend and the frontend in two terminals, from the project root.

**Terminal 1: database, sample data and API**

```
docker compose up -d
uv run python -m app.generator --n 20000 --kind db_failure --truncate
uv run uvicorn app.main:app
```

The API is available at `http://127.0.0.1:8000`, and interactive documentation is served at `http://127.0.0.1:8000/docs`.

**Terminal 2: web interface**

```
cd frontend
npm run dev
```

Open `http://localhost:3000`. The green dot in the header shows that the frontend can reach the API.

For a production build of the frontend, run `npm run build` followed by `npm start` inside `frontend/`.

## Using the Web Interface

| Page | Path | What it does |
|---|---|---|
| Dashboard | `/` | Row count, data range and a chart of errors and warnings over time. Drag across the chart to zoom, then jump to Investigate or Logs for that period |
| Investigate | `/investigate` | Enter a description and a time range, run an investigation and read the result: root cause, verification status, propagation path, timeline, attempts, services and error groups, request traces, the Markdown report and the raw JSON |
| Logs | `/logs` | Filter raw log lines by time, service, level, error type, request id and message text, with paging. Filters are kept in the URL |
| Request trace | `/requests/<request-id>` | Every log line of one request across services, in order, with time offsets |

An investigation can be started from a link by adding `run=1`, for example `/investigate?description=checkout%20failing&start=2026-10-01T00:00&end=2026-10-01T23:59&run=1`. Running the same investigation again can give a slightly different model answer.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/investigate` | Run an investigation and return the full structured result as JSON |
| POST | `/investigate/report` | Run an investigation and return a Markdown report |
| POST | `/report/render` | Render the Markdown report for a result you already have (the JSON from `/investigate`), without running a new investigation |
| GET | `/meta` | Data time range, row count, and the distinct services, levels and error types |
| GET | `/logs/overview` | Error, warning and total counts per time bucket, for charts |
| GET | `/logs` | Filterable, paginated log lines |
| GET | `/requests/{request_id}` | All log lines of one request across services, in time order |

Request body for both investigation endpoints:

```json
{
  "description": "Users reported checkout failures around 2 PM",
  "start": "2026-10-01T00:00:00",
  "end": "2026-10-01T23:59:59"
}
```

The description must not be blank, `end` must be after `start`, and the range is limited to 31 days. Invalid input returns 422 with the error attached to the field.

Example:

```
curl -X POST http://127.0.0.1:8000/investigate/report \
  -H "Content-Type: application/json" \
  -d '{"description": "Users reported checkout failures around 2 PM", "start": "2026-10-01T00:00:00", "end": "2026-10-01T23:59:59"}'
```

If no anomaly is found in the given range, the response has the status `no_anomaly_found`.

Query parameters of the read-only endpoints:

| Endpoint | Parameters |
|---|---|
| `/logs/overview` | `start`, `end` (required); `bucket_minutes` (1, 5, 15, 30 or 60; chosen automatically if omitted); `service` |
| `/logs` | `start`, `end` (required); `service`, `level`, `error_type`, `request_id`, `q` (text contained in the message); `order` (`asc` or `desc`); `limit` (1 to 500, default 100); `offset` |
| `/requests/{request_id}` | `request_id` must be a UUID. Returns 404 if no lines exist for it |

All read-only endpoints use bound query parameters and never run user-supplied SQL. A Bruno collection with the investigation requests is included in `bruno/apis.json`, and a sample report is available in `output/report.md`.

## Project Structure

```
app/
  main.py            FastAPI application, investigation routes, request validation
  schemas.py         Response models for the explorer endpoints
  config.py          Environment configuration
  db.py              Database engine and query helper
  generator.py       Fake log record generator
  explore/
    queries.py       SQL and pandas for meta, overview, log search and request trace
    router.py        Explorer endpoints (/meta, /logs/overview, /logs, /requests/{id})
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
tests/
  unit/              Fast tests, no database or LLM needed
  integration/       Tests against a real MariaDB (opt-in)
frontend/            Next.js web interface
bruno/               API request collection
output/              Sample report
pytest.ini           Test configuration
```

## Tests

### Backend

The backend test suite lives in `tests/` and is configured by `pytest.ini`.

Unit tests (no database or LLM needed; the DB helper and the LLM client are faked):

```
uv run pytest
```

Integration tests run the real SQL against MariaDB. They write synthetic rows dated 2001-01-01, run the full pipeline and the explorer endpoints over that day, and delete those rows afterwards. They refuse to run if that day already contains data. Start the database and create the table first (see Setup), then:

```
# macOS / Linux
INTEGRATION_DB_URL=mysql+pymysql://loguser:logpass@127.0.0.1:3306/logsdb uv run pytest -m integration

# Windows PowerShell
$env:INTEGRATION_DB_URL="mysql+pymysql://loguser:logpass@127.0.0.1:3306/logsdb"
uv run pytest -m integration
```

Without `INTEGRATION_DB_URL` the integration tests are skipped. The unit tests never use your `.env` or your real API key.

What is covered:

| Area | What the tests check |
|---|---|
| Anomaly detection | Quiet data, background noise, window merging, picking the largest window, thresholds |
| Correlation and tracing | Message templating, error grouping, service ordering by first error, request path counts |
| Verification | A correct root cause passes; downstream symptoms, invented errors, low coverage and noise are rejected |
| LLM hypothesis | JSON extraction from chatty replies, retry feedback in the prompt, bad replies raise, rule-based fallback |
| Reasoning loop | Verified on first try, retry with feedback, fallback after two failures, fallback on LLM errors |
| Pipeline and report | JSON-safe output, no-anomaly path, Markdown sections |
| API | Health, both investigation endpoints, request validation (blank description, bad range, range limit), report rendering |
| Explorer queries and endpoints | Bucket sizes and gap filling, filters as bound parameters, LIKE escaping, paging, request trace offsets, 404 and 422 cases |
| Generator | Request shape for each incident type, incident confined to its window, reproducibility |

### Frontend

Run these from inside `frontend/`:

```
npm test              # unit tests for formatting, API error handling and timeline math
npm run typecheck     # TypeScript check
npm run lint          # ESLint
npm run build         # production build
```

## Troubleshooting

| Problem | What to check |
|---|---|
| Header dot is red, pages show "Cannot reach the backend" | The API is not running on `API_URL`. Start it with `uv run uvicorn app.main:app` |
| Dashboard says there are no logs | Generate data with `uv run python -m app.generator --truncate` |
| Investigation fails after a long wait | The LLM call may be slow or the key invalid. Check `LLM_API_KEY` and `LLM_BASE_URL`. With a bad key the system should still return the rule-based fallback |
| Browser reports a CORS error | Only happens when calling the API directly. Use the frontend proxy, or set `CORS_ORIGINS=http://localhost:3000` in `.env` and restart the API |