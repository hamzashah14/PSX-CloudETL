# CloudETL — Quantum Analytics Platform

> A production-grade, cloud-native ETL pipeline for real-time stock market analytics, built on a microservices architecture with Docker, Kubernetes, and a premium **Quantum Glass** dashboard.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                       CloudETL Pipeline                              │
├──────────────┬────────────────┬───────────────┬──────────────────────┤
│   EXTRACT    │   TRANSFORM    │     LOAD      │   VISUALIZATION      │
│   Service    │    Service     │    Service    │     Service           │
│  (Port 8000) │  (Port 8001)   │  (Port 8003)  │   (Port 8002)        │
│              │                │               │                      │
│  Yahoo       │  Technical     │  Star Schema  │  Quantum Glass       │
│  Finance     │  Indicators    │  SCD Type 2   │  Dashboard           │
│  yfinance    │  RSI, MA, VaR  │  PostgreSQL   │  Dash + Plotly       │
└──────┬───────┴───────┬────────┴───────┬───────┴──────────┬───────────┘
       │               │               │                  │
       └───────────────┴───────┬───────┴──────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │  SCHEDULER SERVICE  │
                    │     (Port 8004)     │
                    │  Orchestrates the   │
                    │  entire pipeline    │
                    └─────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │    POSTGRES DB      │
                    │    (Port 5432)      │
                    │  Star Schema DWH    │
                    └─────────────────────┘
```

## Services

| Service           | Port   | Stack                           | Purpose                                                                              |
| ----------------- | ------ | ------------------------------- | ------------------------------------------------------------------------------------ |
| **Extract**       | `8000` | FastAPI, yfinance               | Fetches OHLCV data and company metadata from Yahoo Finance                           |
| **Transform**     | `8001` | FastAPI, pandas, numpy          | Applies 5-phase financial analysis (cleaning → metrics → technicals → sector → risk) |
| **Load**          | `8003` | FastAPI, SQLAlchemy, PostgreSQL | Persists enriched data into a Star Schema warehouse with SCD Type 2                  |
| **Visualization** | `8002` | Dash, Plotly, Bootstrap         | Premium "Quantum Glass" analytics dashboard with three modular views                 |
| **Scheduler**     | `8004` | Flask, schedule                 | Orchestrates periodic ETL runs across all services                                   |
| **PostgreSQL**    | `5432` | postgres:15-alpine              | Persistent data warehouse backend                                                    |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Git

### 1. Clone & Configure

```bash
git clone <repo-url>
cd psx-etl

# Create .env file (required for PostgreSQL)
cp .env.example .env
# Edit .env with your credentials
```

### 2. Launch

```bash
# Build and start all 6 services
docker-compose up --build

# Or run in detached mode
docker-compose up --build -d
```

### 3. Access

| URL                        | Description                    |
| -------------------------- | ------------------------------ |
| **http://localhost:8002**  | 📊 Quantum Analytics Dashboard |
| http://localhost:8000/docs | Extract Service API Docs       |
| http://localhost:8001/docs | Transform Service API Docs     |
| http://localhost:8003/docs | Load Service API Docs          |

### 4. Stop

```bash
docker-compose down        # Stop services
docker-compose down -v     # Stop + delete database volumes
```

## Dashboard — Quantum Glass UI

The visualization service features a premium **Quantum Glass** design system with:

- **Sidebar Navigation** — Three specialized views accessible via glassmorphic sidebar
- **Markets View** — Candlestick charts + Volume analysis with color-coded bars
- **Intelligence View** — RSI oscillator, Moving Averages (MA7/MA30), and Volume Profile
- **Risk Analysis View** — Return distribution histogram, 7-day volatility tracking, correlation matrix
- **Stat Cards** — Hover-activated neon glows, animated gradient title, and real-time price panels
- **Design Tokens** — `#00F2FF` cyan, `#A78BFA` purple, `#F472B6` pink on `#0A0E1A` midnight base

## Data Pipeline Flow

```
1. EXTRACT   → Fetches OHLCV + company info from Yahoo Finance via yfinance
2. TRANSFORM → Cleans data, calculates Daily Return, RSI, Moving Averages,
                Volatility, Sharpe Ratio, VaR, sector/industry performance
3. LOAD      → Stores in PostgreSQL Star Schema (Fact + 3 Dimension tables)
                with SCD Type 2 for historical ticker metadata tracking
4. VISUALIZE → Renders interactive charts via Plotly with 5-minute LRU caching
5. SCHEDULE  → Triggers pipeline runs every 30 seconds (configurable)
```

## CI/CD Pipeline

The project includes a comprehensive **Jenkinsfile** for IBM Cloud Kubernetes deployment:

- **Manifest check**: the kustomize overlays must render before anything is built
- **Unit tests** (offline, same as `make test`) before any image is built
- **Parallel container builds** for all 5 services
- **Trivy security scanning** on production branches
- **Manual approval gate** for production deployments
- **Secret from Jenkins credentials**: the database password is created in the cluster by `infra/scripts/create-db-secret.sh` and never lives in Git (Jenkins credential id `etl-postgres-credentials`)
- **Autoscaling**: CPU-based HorizontalPodAutoscalers for the stateless services
- **Production smoke test**: every service must answer `/health` with 200 after the deploy
- **Automatic rollback** on deployment failure
- **Branch-based namespace targeting** (`dev`, `qa-test`, `master` → `prod`)

The manifests are kustomize bases with an overlay per cloud (`infra/k8s/overlays/ibm` and `azure`); see [infra/README.md](infra/README.md) for the layout, how to deploy by hand, and the decisions behind it.

## Tests

The tests run offline (in-memory SQLite and mocked HTTP), so they need no database and no network:

```bash
make install   # test dependencies are in the root requirements.txt
make test      # same as: pytest tests/
```

They cover the Transform and Load services: how Transform's indicator fields map onto the warehouse columns, the SCD Type 2 behaviour of `dim_ticker`, and a Transform-to-Load run end to end. The extract, scheduler and visualization test folders are still empty.

## Project Structure

```
psx-etl/
├── docker-compose.yml          # Multi-service orchestration
├── Jenkinsfile                 # CI/CD pipeline (IBM Cloud + K8s)
├── Makefile                    # Development shortcuts
├── .env                        # PostgreSQL credentials
├── .env.example                # Template for .env
├── requirements.txt            # Root-level Python dependencies
├── services/
│   ├── extract/                # Yahoo Finance data extraction
│   │   ├── app.py, Dockerfile, requirements.txt, README.md
│   ├── transform/              # Financial analysis engine
│   │   ├── app.py, Dockerfile, requirements.txt, README.md
│   ├── load/                   # Star Schema data warehouse
│   │   ├── app.py, Dockerfile, requirements.txt, README.md
│   ├── visualization/          # Quantum Glass dashboard
│   │   ├── app.py, Dockerfile, requirements.txt, README.md
│   ├── scheduler/              # Pipeline orchestrator
│   │   ├── app.py, Dockerfile, requirements.txt
│   └── dashboard/              # Legacy placeholder (unused)
│       ├── app.py, Dockerfile, requirements.txt
├── infra/
│   ├── k8s/
│   │   ├── base/               # services (+ autoscalers), database, ingress
│   │   ├── overlays/           # ibm/ and azure/, each with database, services, ingress
│   │   └── examples/           # reference-only manifests (never applied)
│   └── scripts/                # create-db-secret.sh
└── tests/
    ├── infra_tests/            # kustomize overlays and the secret script
    ├── extract_tests/
    ├── transform_tests/
    ├── load_tests/
    ├── scheduler_tests/
    └── visualization_tests/
```

## Environment Variables

| Variable                    | Default                             | Used By                          |
| --------------------------- | ----------------------------------- | -------------------------------- |
| `POSTGRES_USER`             | —                                   | postgres-db, load-service        |
| `POSTGRES_PASSWORD`         | —                                   | postgres-db, load-service        |
| `POSTGRES_DB`               | `psx_warehouse`                     | postgres-db, load-service        |
| `TRANSFORM_SERVICE_URL`     | `http://transform-service:8001`     | visualization-service            |
| `EXTRACT_SERVICE_URL`       | `http://extract-service:8000`       | visualization-service, scheduler |
| `LOAD_SERVICE_URL`          | `http://load-service:8003`          | scheduler                        |
| `VISUALIZATION_SERVICE_URL` | `http://visualization-service:8002` | scheduler                        |

## API Quick Reference

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

# Warehouse statistics
curl http://localhost:8003/stats

# Health checks
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
```

## Troubleshooting

| Problem                                    | Solution                                                                             |
| ------------------------------------------ | ------------------------------------------------------------------------------------ |
| Dashboard shows "DATA FEED UNAVAILABLE"    | Ensure Transform Service is healthy: `curl http://localhost:8001/health`             |
| `visualization-service exited with code 1` | Check logs: `docker-compose logs -f visualization-service`                           |
| Port conflicts                             | Edit `docker-compose.yml` port mappings                                              |
| PostgreSQL connection refused              | Verify `.env` credentials and that `postgres-db` container is healthy                |
| Stale chart data                           | Click the **REFRESH** button on the dashboard or hit `http://localhost:8002/refresh` |

## License

MIT License
