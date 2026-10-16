# Load Service — Star Schema Data Warehouse

> FastAPI microservice implementing a **Star Schema** data warehouse with **SCD Type 2** for persisting enriched stock market data into PostgreSQL.

## Overview

The Load Service is the **persistence layer** of the CloudETL pipeline. It receives transformed stock data from the Transform Service and stores it in a dimensional model optimized for analytical queries — including full historical tracking of changes to company metadata.

## Star Schema Design

```
                    ┌─────────────────┐
                    │   dim_ticker    │
                    │   (SCD Type 2)  │
                    │─────────────────│
                    │ ticker_key (PK) │
                    │ ticker_symbol   │
                    │ company_name    │
                    │ sector          │
                    │ industry        │
                    │ market_cap      │
                    │ effective_date  │
                    │ end_date        │
                    │ is_current      │
                    │ version         │
                    └────────┬────────┘
                             │
┌──────────────┐    ┌────────┴────────┐    ┌──────────────┐
│   dim_date   │    │  fact_stock_    │    │   dim_time   │
│──────────────│    │    prices       │    │──────────────│
│ date_key (PK)│◄───│────────────────│───►│ time_key (PK)│
│ full_date    │    │ fact_id (PK)   │    │ hour         │
│ year         │    │ ticker_key (FK)│    │ minute       │
│ quarter      │    │ date_key (FK)  │    │ period       │
│ month        │    │ time_key (FK)  │    │ trading_     │
│ day          │    │ open_price     │    │   session    │
│ day_of_week  │    │ high_price     │    └──────────────┘
│ day_name     │    │ low_price      │
│ month_name   │    │ close_price    │
│ is_weekend   │    │ volume         │
│ is_holiday   │    │ ma_7, ma_30    │
└──────────────┘    │ rsi            │
                    │ daily_return   │
                    │ volatility     │
                    └────────────────┘
```

## SCD Type 2 — Historical Tracking

The `dim_ticker` dimension tracks changes to company metadata over time:

| Field | Purpose |
|-------|---------|
| `is_current` | `True` for the active record, `False` for expired versions |
| `effective_date` | When this version became active |
| `end_date` | When this version was superseded (`NULL` if current) |
| `version` | Sequential version number |

When a company's sector, industry, or market cap changes, a new dimension record is inserted and the previous one is closed — preserving full audit history.

How a change is detected: the incoming `sector`, `industry` and `market_cap` are compared with the current row. Empty values mean "unknown", never "changed". On a change the old row gets `end_date = today` and `is_current = False`, and the new row gets `version + 1`, in one transaction. Attributes that were not received are carried over.

Facts stay attached to the version that was current when they were loaded, so the duplicate check and `GET /data/{ticker}` look at every version of the symbol. Transform does not return a company name, so `company_name` is `NULL` for now.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health with database connectivity check |
| `GET` | `/stats` | Warehouse statistics (row counts, table sizes) |
| `GET` | `/data/{ticker}?limit=100` | Query fact data for a specific ticker |
| `POST` | `/load/{ticker}?period=1mo` | ETL a single ticker into the warehouse |
| `POST` | `/load/batch` | ETL multiple tickers in one request |

### Load a Ticker

```bash
curl -X POST "http://localhost:8003/load/AAPL?period=1mo"
```

### Batch Load

```bash
curl -X POST http://localhost:8003/load/batch \
  -H "Content-Type: application/json" \
  -d '{"tickers": "AAPL,MSFT,GOOGL", "period": "3mo"}'
```

### Query Data

```bash
curl "http://localhost:8003/data/AAPL?limit=100"
```

### Sample Response

```json
{
  "ticker": "AAPL",
  "total_records": 23,
  "data": [
    {
      "date_key": 20241201,
      "open": 228.50,
      "high": 241.32,
      "low": 223.78,
      "close": 228.93,
      "volume": 48661973,
      "ma_7": 230.15,
      "ma_30": 225.80,
      "rsi": 55.23,
      "daily_return": 0.0044,
      "volatility": 0.009
    }
  ]
}
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://...@postgres-db:5432/psx_warehouse` | PostgreSQL connection string |
| `POSTGRES_USER` | — | Database username (from `.env`) |
| `POSTGRES_PASSWORD` | — | Database password (from `.env`) |
| `POSTGRES_DB` | `psx_warehouse` | Database name |
| `POSTGRES_HOST` | `postgres-db` | Database hostname |

## Data Pipeline

```
Transform Service ──POST──→ Load Service
                                │
                    ┌───────────┼───────────┐
                    │           │           │
               dim_ticker  dim_date   dim_time
                (SCD T2)      │           │
                    └───────── │ ──────────┘
                               ▼
                       fact_stock_prices
                               │
                               ▼
                        PostgreSQL DB
```

### Loading Process

1. Receives enriched data from Transform Service
2. Creates or updates `dim_ticker` records (SCD Type 2 logic)
3. Generates `dim_date` and `dim_time` entries if not present
4. Creates surrogate keys for all dimension relationships
5. Inserts fact records with composite key deduplication

### Indicator columns

`rsi` comes from `RSI_14` and `volatility` from `Volatility_7` (the 7-day value). `ma_7`, `ma_30` and `daily_return` come from the Transform fields of the same name. Missing or NaN values are stored as `NULL`; `0.0` is kept as a value.

## Running Locally

```bash
cd services/load
pip install -r requirements.txt

# Ensure PostgreSQL is running
python app.py
```

Service available at: http://localhost:8003/docs

## Docker

```bash
docker build -t load-service .
docker run -p 8003:8003 \
  -e DATABASE_URL=postgresql://user:pass@host:5432/psx_warehouse \
  load-service
```

## Dependencies

- `fastapi` + `uvicorn` — API framework
- `sqlalchemy` — ORM and database abstraction
- `psycopg2-binary` — PostgreSQL driver
- `psutil` — System resource monitoring
- `requests` — HTTP client for Transform Service calls

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Transform service unavailable" | Check `curl http://localhost:8001/health` |
| Database connection errors | Verify `.env` credentials and `postgres-db` container health |
| Duplicate records | The service auto-deduplicates via composite key checking |
| Slow loading | Consider reducing the period or number of tickers per batch |