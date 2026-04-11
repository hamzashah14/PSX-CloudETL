# Scheduler Service

> Flask-based orchestration service that periodically triggers ETL pipeline runs across the CloudETL microservices ecosystem.

## Overview

The Scheduler Service is the **orchestration layer** of the CloudETL pipeline. It runs as a headless background service, periodically triggering data loads to the warehouse and cache refreshes on the visualization dashboard.

## How It Works

The scheduler runs a background thread that:

1. **Every 30 seconds** — Triggers a full pipeline run:
   - `POST` to Load Service (`/load/batch`) with default tickers (`AAPL,GOOGL,MSFT`, period `1mo`)
   - `GET` to Visualization Service (`/refresh`) to clear the dashboard cache
2. **Tracks job status** — Last run time, run count, success/partial/error state
3. **Retains error log** — Last 10 errors for debugging

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Comprehensive health check (CPU, memory, service connectivity) |
| `GET` | `/status` | Current scheduler job status and run history |
| `GET` | `/trigger` | Manually trigger a pipeline run |
| `GET` | `/trigger/<service>` | Trigger a specific service (`load` or `visualization`) |

### Job Status Response

```json
{
  "last_run": "2026-04-10T23:45:00.000000",
  "next_run": "2026-04-10T23:45:30.000000",
  "status": "completed",
  "runs_count": 42,
  "errors": []
}
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `VISUALIZATION_SERVICE_URL` | `http://visualization-service:8002` | Dashboard service URL |
| `LOAD_SERVICE_URL` | `http://load-service:8003` | Warehouse load service URL |

### Schedule

| Job | Frequency | Action |
|-----|-----------|--------|
| `trigger_data_update` | Every 30 seconds | Full pipeline run (Load + Visualization refresh) |
| Initial run | 10 seconds after startup | One-time bootstrap run |

## Service Dependencies

```
              ┌──── Load Service (POST /load/batch)
Scheduler ────┤
              └──── Visualization Service (GET /refresh)
```

The Scheduler depends on **all other services being healthy** before starting (configured via `docker-compose.yml` health checks).

## Running Locally

```bash
cd services/scheduler
pip install -r requirements.txt
python app.py
```

Service available at: http://localhost:8004

## Docker

```bash
docker build -t scheduler-service .
docker run -p 8004:8004 \
  -e LOAD_SERVICE_URL=http://load-service:8003 \
  -e VISUALIZATION_SERVICE_URL=http://visualization-service:8002 \
  scheduler-service
```

## Dependencies

- `flask` + `flask-cors` — Web framework
- `schedule` — Lightweight job scheduler
- `requests` — HTTP client for service communication
- `psutil` — System resource monitoring

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No services could be triggered" | Verify Load and Visualization services are healthy |
| Scheduler not starting | Check that all dependent services pass health checks |
| High error count | Review `/status` endpoint for error details |
| Pipeline runs too frequently | Adjust `schedule.every(30).seconds` in `run_scheduler()` |
