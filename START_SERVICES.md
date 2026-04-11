# 🚀 CloudETL — Quick Start Guide

## One-Command Launch

```bash
# Build and start all services
docker-compose up --build

# Or run in background
docker-compose up --build -d
```

## Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| 📊 **Dashboard** | http://localhost:8002 | Quantum Glass Analytics Dashboard |
| 🔄 Extract API | http://localhost:8000/docs | Yahoo Finance data extraction |
| ⚡ Transform API | http://localhost:8001/docs | Financial analysis engine |
| 🏛️ Load API | http://localhost:8003/docs | Star Schema data warehouse |
| 🔧 Scheduler | http://localhost:8004/health | Pipeline orchestration |

## Dashboard Usage

1. Open **http://localhost:8002**
2. Select a stock ticker (AAPL, MSFT, GOOGL, TSLA, etc.)
3. Choose period: **1M** or **1Y**
4. Navigate views via the sidebar:
   - **Markets** — Candlestick + Volume charts
   - **Intelligence** — RSI, Moving Averages, Volume Profile
   - **Risk Analysis** — Return distribution, Volatility, Correlations
5. Click **REFRESH** for latest data

## Stop Services

```bash
docker-compose down          # Stop services
docker-compose down -v       # Stop + delete database volumes
```

## View Logs

```bash
docker-compose logs -f                          # All services
docker-compose logs -f visualization-service    # Dashboard only
docker-compose logs -f transform-service        # Transform only
```

## Rebuild a Single Service

```bash
docker-compose up --build visualization-service
```

## API Testing

```bash
# Extract raw data
curl http://localhost:8000/extract/AAPL?period=1mo

# Transform batch
curl -X POST http://localhost:8001/transform_batch \
  -H "Content-Type: application/json" \
  -d '{"tickers": "AAPL", "period": "1mo"}'

# Load to warehouse
curl -X POST http://localhost:8003/load/AAPL?period=1mo

# Query warehouse
curl http://localhost:8003/data/AAPL?limit=50

# Health checks
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8003/health
curl http://localhost:8004/health
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Dashboard shows "DATA FEED UNAVAILABLE" | `curl http://localhost:8001/health` — ensure Transform is healthy |
| Service won't start | `docker-compose logs -f <service-name>` for error details |
| Port conflicts | Edit port mappings in `docker-compose.yml` |
| Stale data | Click **REFRESH** on dashboard or `curl http://localhost:8002/refresh` |
| PostgreSQL connection error | Verify `.env` file has correct `POSTGRES_USER` and `POSTGRES_PASSWORD` |

## Local Development (without Docker)

```bash
# Terminal 1 — Extract Service
cd services/extract && pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Transform Service
cd services/transform && pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8001 --reload

# Terminal 3 — Visualization Dashboard
cd services/visualization && pip install -r requirements.txt
python app.py
```

## 🎉 Success

When all services are running, you'll have:
- Professional stock data extraction from Yahoo Finance
- 5-phase financial analysis pipeline
- Star Schema data warehouse with SCD Type 2
- Premium Quantum Glass analytics dashboard
- Automated pipeline orchestration

**Main Dashboard: http://localhost:8002**