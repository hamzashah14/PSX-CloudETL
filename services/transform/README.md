# Transform Service

> FastAPI microservice that processes raw stock data through a 5-phase financial analysis pipeline, producing enriched datasets with technical indicators, sector analysis, and risk metrics.

## Overview

The Transform Service is the **analytical engine** of the CloudETL pipeline. It takes raw OHLCV data from the Extract Service and applies comprehensive financial transformations — from basic daily returns to advanced risk metrics like Sharpe Ratio and Value at Risk.

## 5-Phase Transformation Pipeline

### Phase 1 — Data Cleaning & Validation
- Validates required OHLCV fields and ensures price logic (`Low ≤ Open/Close ≤ High`)
- Standardizes tickers to uppercase (1–5 letter format)
- Converts dates to UTC ISO format
- Removes corrupted or invalid records

### Phase 2 — Basic Financial Metrics
| Metric | Description |
|--------|-------------|
| `Daily_Return` | Percentage change from Open to Close |
| `Price_Range` | High − Low spread |
| `Typical_Price` | Average of (High + Low + Close) / 3 |
| `Relative_Volume` | Current volume / average volume ratio |
| `Market_Cap_Category` | Small (<$2B), Mid ($2B–$10B), Large (>$10B) |

### Phase 3 — Technical Indicators
| Indicator | Description |
|-----------|-------------|
| `MA_7`, `MA_30` | 7-day and 30-day Simple Moving Averages |
| `RSI_14` | 14-period Relative Strength Index (0–100) |
| `Volatility_7`, `Volatility_30` | Rolling standard deviation of returns |
| `Price_vs_MA7`, `Price_vs_MA30` | % above/below moving averages |
| `Volume_MA_7`, `Volume_Trend` | Volume moving average and trend ratio |
| `Price_Change_Pct` | Day-over-day price change percentage |

### Phase 4 — Sector & Industry Analysis
| Metric | Description |
|--------|-------------|
| `Sector_Relative_Performance` | Stock return minus sector average |
| `Industry_Relative_Performance` | Stock return minus industry average |
| `PE_vs_Sector_Avg` | P/E ratio versus sector average P/E |

### Phase 5 — Risk Metrics
| Metric | Description |
|--------|-------------|
| `Max_Drawdown` | Largest peak-to-trough decline |
| `Sharpe_Ratio` | Risk-adjusted return (annualized, 0% risk-free) |
| `Value_at_Risk_5` | 5th percentile of return distribution |
| `Return_Skewness` | Asymmetry of return distribution |
| `Return_Kurtosis` | Tail heaviness of return distribution |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Service metadata |
| `GET` | `/health` | Health check with CPU, memory, and dependency status |
| `GET` | `/config` | Current feature flags and calculation parameters |
| `POST` | `/transform` | Transform raw data (accepts `raw_data` array) |
| `POST` | `/transform_batch` | Fetch from Extract Service and transform in one call |

### `/transform_batch` — Primary Integration Endpoint

```bash
curl -X POST http://localhost:8001/transform_batch \
  -H "Content-Type: application/json" \
  -d '{"tickers": "AAPL", "period": "1mo"}'
```

**Request Body:**
```json
{
  "tickers": "AAPL,MSFT,GOOGL",
  "period": "1mo",
  "extract_service_url": "http://extract-service:8000"
}
```

**Response:** Array of enriched records with all 5 phases of calculated fields.

### `/transform` — Direct Transform

```bash
curl -X POST http://localhost:8001/transform \
  -H "Content-Type: application/json" \
  -d '{"raw_data": [{"Ticker": "AAPL", "Date": "2024-01-01", "Open": 150.0, "High": 155.0, "Low": 149.0, "Close": 154.0, "Volume": 1000000}]}'
```

## Configuration

Feature flags and parameters are controlled via `TransformConfig`:

```python
enable_technical_indicators = True    # Phase 3
enable_sector_analysis = True         # Phase 4
enable_risk_metrics = True            # Phase 5

ma_short_period = 7                   # Short-term MA window
ma_long_period = 30                   # Long-term MA window
volatility_window = 30                # Volatility calculation window
rsi_period = 14                       # RSI period
max_batch_size = 100                  # Max records per batch
```

## Data Safety

All output is guaranteed JSON-serializable:
- `NaN` and `Infinity` values are replaced with `None` or `0.0`
- NumPy scalars are converted to native Python types
- All floats are rounded to 4 decimal places via `safe_float()`

## Running Locally

```bash
cd services/transform
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

## Docker

```bash
docker build -t transform-service .
docker run -p 8001:8001 transform-service
```

## Dependencies

- `fastapi` + `uvicorn` — API framework
- `pandas` + `numpy` — Data processing
- `httpx` — Async HTTP client for Extract Service calls
- `psutil` — System resource monitoring

## Service Integration

```
Extract Service ──→ Transform Service ──→ Load Service
                         ↑                     ↓
                    Visualization         PostgreSQL
                     (consumer)           Warehouse
```

The Transform Service is the central hub — called by the Visualization dashboard for on-demand analytics and by the Scheduler for periodic warehouse loading.