# Extract Service

> FastAPI microservice that fetches real-time and historical stock market data from Yahoo Finance via `yfinance`.

## Overview

The Extract Service is the **data ingestion layer** of the CloudETL pipeline. It retrieves OHLCV (Open, High, Low, Close, Volume) price data and company metadata, then standardizes it for downstream consumption by the Transform Service.

## Features

- **Historical OHLCV Data** — Configurable periods from 1 day to 5 years
- **Company Metadata** — Industry, sector, market cap, P/E ratios, dividend info
- **Real-Time Prices** — Low-latency `/price/{ticker}` endpoint using `yfinance.fast_info`
- **Concurrent Fetching** — `/extract_many` processes multiple tickers in parallel via `asyncio.gather`
- **Retry Logic** — Exponential backoff with `tenacity` (3 attempts, 2–10s delays)
- **Health Monitoring** — CPU, memory, and response time checks via `/health`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health with system resource metrics |
| `GET` | `/extract/{ticker}?period=1mo` | Full data: OHLCV + company info merged per row |
| `GET` | `/price/{ticker}` | Real-time price, change, and change % (fast) |
| `GET` | `/history/{ticker}?period=1mo` | OHLCV data only (no company metadata) |
| `GET` | `/extract_many?ticker=AAPL,MSFT&period=1mo` | Multi-ticker concurrent extraction |

### Response Format — `/extract/{ticker}`

```json
{
  "data": [
    {
      "Date": "2024-01-02T00:00:00+00:00",
      "Open": 187.15,
      "High": 188.44,
      "Low": 183.89,
      "Close": 185.64,
      "Volume": 82488700,
      "Dividend": 0.0,
      "Ticker": "AAPL",
      "industry": "Consumer Electronics",
      "sector": "Technology",
      "marketCap": 2890000000000,
      "trailingPE": 30.2,
      "forwardPE": 27.5,
      "averageVolume": 58000000
    }
  ]
}
```

### Response Format — `/price/{ticker}`

```json
{
  "ticker": "AAPL",
  "price": 227.48,
  "change": 1.23,
  "change_percent": 0.54,
  "currency": "USD",
  "market_state": "REGULAR",
  "timestamp": "2026-04-10 18:30:00"
}
```

## Configuration

| Setting | Value |
|---------|-------|
| **Port** | `8000` |
| **Framework** | FastAPI + Uvicorn |
| **Data Provider** | Yahoo Finance (`yfinance`) |
| **Retry Policy** | 3 attempts, exponential backoff (2–10s) |
| **CORS Origins** | `localhost:8000–8004` |

### Company Info Fields Extracted

`industry`, `sector`, `fullTimeEmployees`, `marketCap`, `previousClose`, `averageVolume`, `currency`, `dividendRate`, `dividendYield`, `trailingPE`, `forwardPE`

## Running Locally

```bash
cd services/extract
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

API docs at: http://localhost:8000/docs

## Docker

```bash
docker build -t extract-service .
docker run -p 8000:8000 extract-service
```

## Dependencies

- `fastapi` + `uvicorn` — API framework
- `yfinance` — Yahoo Finance data provider
- `tenacity` — Retry with exponential backoff
- `psutil` — System resource monitoring

## Service Integration

```
Extract Service ──→ Transform Service ──→ Load Service
     ↑                                        ↑
     └──── Scheduler (triggers pipeline) ─────┘
```

The Extract Service is called by the Transform Service's `/transform_batch` endpoint, which fetches raw data and applies financial analysis transformations.
