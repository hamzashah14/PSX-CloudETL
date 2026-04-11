# Visualization Service — Quantum Glass Dashboard

> Premium financial analytics dashboard built with Dash and Plotly, featuring a **Quantum Glass** glassmorphic design system with three modular analytical views.

## Overview

The Visualization Service is the **presentation layer** of the CloudETL pipeline. It provides a professional-grade, interactive stock analytics dashboard with sidebar navigation, animated design tokens, and comprehensive financial charting — powered by real-time data from the Transform Service.

## Design System — Quantum Glass

The dashboard implements a custom glassmorphic aesthetic:

| Token | Value | Usage |
|-------|-------|-------|
| **Background** | `#0A0E1A` | Midnight primary background |
| **Card** | `rgba(18, 24, 41, 0.7)` | Glassmorphic panels with `backdrop-filter: blur(30px)` |
| **Accent Cyan** | `#00F2FF` | Primary interactive color, neon glows |
| **Accent Purple** | `#A78BFA` | Secondary accent, chart series |
| **Accent Pink** | `#F472B6` | Tertiary accent, trend indicators |
| **Positive** | `#10B981` | Gains, bullish signals |
| **Negative** | `#EF4444` | Losses, bearish signals |
| **Typography** | Inter + JetBrains Mono | Sans-serif UI + monospace data values |

### Interactive Features
- **Neon hover glows** on all glass panels with `translateY(-2px)` lift
- **Gradient-shifting** logo animation with cyber gradient
- **Sidebar pill navigation** with left-edge indicator bars
- **Custom scrollbar** with cyan-to-purple gradient thumb

## Three Analytical Views

### 📈 Markets View
- **Candlestick Chart** — Full OHLC price action with gain/loss color coding
- **Volume Chart** — Color-coded trading volume bars (green for up days, red for down)

### 🧠 Intelligence View
- **RSI Indicator** — 14-period Relative Strength Index with overbought (70) and oversold (30) zones
- **Price & Moving Averages** — Close price overlaid with MA7 (pink dash) and MA30 (purple dot)
- **Volume Profile** — Volume bars with gain/loss coloring

### 🛡️ Risk Analysis View
- **Return Distribution** — Histogram of daily returns with mean indicator line
- **Volatility Analysis** — 7-day rolling volatility with area fill
- **Correlation Matrix** — Heatmap of Close, Volume, RSI, and Daily Return correlations

## Stat Cards

The header displays four premium stat cards:

| Card | Metric |
|------|--------|
| **Current Price** | Latest close with $ change and % change (arrow indicators) |
| **Period High** | Maximum high price in the selected period |
| **Period Low** | Minimum low price in the selected period |
| **Avg Volume** | Average daily trading volume (in millions) |

## Controls

| Control | Function |
|---------|----------|
| **Ticker Dropdown** | Select from AAPL, MSFT, GOOGL, TSLA, NVDA, AMD, META, AMZN, NFLX, GOOG |
| **1M / 1Y Buttons** | Switch between 1-month and 1-year historical periods |
| **REFRESH Button** | Clears the 5-minute cache and fetches fresh data |
| **Sidebar Nav** | Switch between Markets, Intelligence, and Risk Analysis views |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serve the dashboard UI |
| `GET` | `/health` | Health check with Transform Service connectivity |
| `GET` | `/refresh` | Clear data cache and trigger fresh fetch |

## Data Flow

```
User selects ticker + period
        │
        ▼
  refresh_engine callback
        │
        ▼
  get_data_with_cache()
        │ (5-min LRU cache)
        ▼
  POST transform-service:8001/transform_batch
        │
        ▼
  pd.DataFrame(data)
        │
   ┌────┼────┬─────────┐
   │    │    │         │
Markets Intel Risk   Stats
 View   View View   Panel
```

## Caching Strategy

- **LRU Cache** with 128 max entries
- **5-minute time buckets** — `cache_key = int(time.time() / 300)`
- **Manual clear** via REFRESH button or `/refresh` endpoint

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TRANSFORM_SERVICE_URL` | `http://transform-service:8001` | Transform Service base URL |
| `EXTRACT_SERVICE_URL` | `http://extract-service:8000` | Extract Service base URL |

## Running Locally

```bash
cd services/visualization
pip install -r requirements.txt

# Ensure Transform Service is running on port 8001
python app.py
```

Dashboard at: http://localhost:8002

## Docker

```bash
docker build -t visualization-service .
docker run -p 8002:8002 \
  -e TRANSFORM_SERVICE_URL=http://transform-service:8001 \
  visualization-service
```

## Dependencies

- `dash` + `dash-bootstrap-components` — Dashboard framework
- `plotly` — Interactive charting
- `pandas` + `numpy` — Data processing
- `requests` — HTTP client for Transform Service
- `psutil` — System resource monitoring
- `flask` — Underlying server (via Dash)

## Plotly Compatibility Notes

The container runs **Plotly 5.x** (Python 3.9). Key constraints:
- `Candlestick` traces do **not** support `hovertemplate`
- Font `weight` is **not** a valid property — only `color`, `family`, `size`
- `dcc.Loading` does **not** support `display_periods` in Dash 2.16

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Loader spins forever | Check `docker-compose logs -f visualization-service` for Python errors |
| "DATA FEED UNAVAILABLE" | Transform Service is not reachable — verify health |
| White/blank charts | Look for `ValueError` in logs (invalid Plotly properties) |
| Stale data | Click REFRESH or hit `http://localhost:8002/refresh` |