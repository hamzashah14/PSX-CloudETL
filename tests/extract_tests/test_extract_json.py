"""Extract service: endpoints with yfinance mocked, retries without waiting, no network."""
import collections
import uuid

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from tenacity import wait_none


class Psutil:
    """Stands in for psutil.virtual_memory() so the health status does not depend on this machine."""

    def __init__(self, percent):
        self.percent = percent


def prices(rows=2, tz="America/New_York"):
    """A frame shaped like yfinance's Ticker.history(): a tz-aware DatetimeIndex named Date."""
    index = pd.DatetimeIndex(pd.date_range("2024-01-02", periods=rows, tz=tz), name="Date")
    return pd.DataFrame(
        {
            "Open": [100.0 + i for i in range(rows)],
            "High": [105.0 + i for i in range(rows)],
            "Low": [95.0 + i for i in range(rows)],
            "Close": [102.0 + i for i in range(rows)],
            "Volume": [1_000_000 + i for i in range(rows)],
            "Dividends": [0.0] * rows,
            "Stock Splits": [0.0] * rows,
        },
        index=index,
    )


INFO = {"industry": "Software", "sector": "Technology", "marketCap": 3_000_000_000_000, "currency": "USD",
        "somethingElse": "not exposed"}


@pytest.fixture()
def client(extract_app):
    return TestClient(extract_app.app)


@pytest.fixture()
def yahoo(monkeypatch, extract_app):
    """Replace yfinance.Ticker. `yahoo.add(symbol, history=..., info=..., fast_info=...)`.

    `history` is a DataFrame, or a list of outcomes (exceptions are raised, frames returned) used one per call.
    `yahoo.calls[symbol]` counts history() calls so retries can be checked.
    """
    # The retry decorators wait 2-10 s between attempts. Keep the attempt count, skip the waiting.
    for fn in (extract_app.get_ticker_history, extract_app.get_ticker_info):
        monkeypatch.setattr(fn.retry, "wait", wait_none())

    specs, calls = {}, collections.Counter()

    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol
            self.spec = specs[symbol]
            self.info = self.spec.get("info", INFO)
            self.fast_info = self.spec.get("fast_info", {})

        def history(self, period):
            calls[self.symbol] += 1
            outcomes = self.spec["history"]
            outcome = outcomes[min(calls[self.symbol], len(outcomes)) - 1] if isinstance(outcomes, list) else outcomes
            if isinstance(outcome, Exception):
                raise outcome
            return outcome.copy()

    monkeypatch.setattr(extract_app.yf, "Ticker", FakeTicker)

    class Yahoo:
        def add(self, symbol, **spec):
            specs[symbol] = spec

    yahoo = Yahoo()
    yahoo.calls = calls
    return yahoo


# --- /health ----------------------------------------------------------------------------------

@pytest.mark.parametrize("memory, expected", [(30, "healthy"), (85, "degraded"), (95, "unhealthy")])
def test_health_status_follows_memory_usage(client, monkeypatch, memory, expected):
    monkeypatch.setattr("psutil.virtual_memory", lambda: Psutil(memory))
    body = client.get("/health").json()
    assert body["status"] == expected
    assert body["service"] == "extract-service"
    assert body["memory_usage_percent"] == memory


# --- /extract/{ticker} ------------------------------------------------------------------------

def test_extract_returns_utc_dates_prices_and_selected_company_info(client, yahoo):
    yahoo.add("AAPL", history=prices(rows=2))

    body = client.get("/extract/AAPL?period=1mo").json()

    first = body["data"][0]
    assert first["Date"] == "2024-01-02T05:00:00+00:00"  # midnight in New York is 05:00 UTC
    assert (first["Open"], first["Close"], first["Volume"], first["Dividend"]) == (100.0, 102.0, 1_000_000, 0.0)
    assert first["Ticker"] == "AAPL"
    assert first["sector"] == "Technology" and first["marketCap"] == 3_000_000_000_000
    assert first["dividendRate"] is None  # selected fields that Yahoo did not send come back as null
    assert "somethingElse" not in first  # only the selected info fields are exposed
    assert len(body["data"]) == 2


def test_extract_unknown_ticker_reports_no_data(client, yahoo):
    yahoo.add("NOPE", history=prices(rows=0))

    body = client.get("/extract/NOPE").json()

    assert "No data found for ticker 'NOPE'" in body["error"]


def test_extract_retries_transient_failures_then_returns_data(client, yahoo):
    yahoo.add("AAPL", history=[RuntimeError("429 rate limited"), RuntimeError("429 rate limited"), prices()])

    body = client.get("/extract/AAPL").json()

    assert len(body["data"]) == 2
    assert yahoo.calls["AAPL"] == 3


def test_extract_gives_up_after_three_attempts(client, yahoo):
    yahoo.add("AAPL", history=RuntimeError("yahoo is down"))

    body = client.get("/extract/AAPL").json()

    assert body["error"].startswith("Failed to fetch data for AAPL")
    assert yahoo.calls["AAPL"] == 3


# --- /history/{ticker} ------------------------------------------------------------------------

def test_history_returns_only_prices(client, yahoo):
    yahoo.add("AAPL", history=prices())

    record = client.get("/history/AAPL").json()["data"][0]

    assert set(record) == {"Date", "Open", "High", "Low", "Close", "Volume", "Dividend"}


def test_history_of_a_ticker_without_rows_is_an_empty_list(client, yahoo):
    yahoo.add("AAPL", history=prices(rows=0))

    assert client.get("/history/AAPL").json() == {"data": []}


def test_history_failure_is_reported_not_raised(client, yahoo):
    yahoo.add("AAPL", history=RuntimeError("boom"))

    assert client.get("/history/AAPL").json()["error"].startswith("Failed to fetch history for AAPL")


# --- /extract_many ----------------------------------------------------------------------------

def test_extract_many_reports_each_ticker_on_its_own(client, yahoo):
    yahoo.add("AAPL", history=prices())
    yahoo.add("DEAD", history=RuntimeError("delisted"))
    yahoo.add("EMPTY", history=prices(rows=0))

    data = client.get("/extract_many?ticker=AAPL,DEAD,EMPTY").json()["data"]

    assert len(data["AAPL"]) == 2 and data["AAPL"][0]["Ticker"] == "AAPL"
    assert data["DEAD"]["error"].startswith("Failed to fetch data")
    assert "No data found for ticker 'EMPTY'" in data["EMPTY"]["error"]


def test_extract_many_ignores_blank_names_and_keeps_the_batch_id(client, yahoo):
    yahoo.add("AAPL", history=prices())
    yahoo.add("MSFT", history=prices())

    body = client.get("/extract_many?ticker=AAPL, ,MSFT,&batch_id=batch-42").json()

    assert body["batch_id"] == "batch-42"
    assert sorted(body["data"]) == ["AAPL", "MSFT"]


def test_extract_many_generates_a_batch_id_when_none_is_given(client, yahoo):
    yahoo.add("AAPL", history=prices())

    batch_id = client.get("/extract_many?ticker=AAPL").json()["batch_id"]

    assert str(uuid.UUID(batch_id)) == batch_id


# --- /price/{ticker} --------------------------------------------------------------------------

def test_price_returns_last_price_change_and_percentage(client, yahoo):
    yahoo.add("AAPL", history=prices(), fast_info={"lastPrice": 110.456, "previousClose": 100.0,
                                                    "currency": "USD", "marketState": "REGULAR"})

    body = client.get("/price/AAPL").json()

    assert body["ticker"] == "AAPL"
    assert (body["price"], body["change"], body["change_percent"]) == (110.46, 10.46, 10.46)
    assert (body["currency"], body["market_state"]) == ("USD", "REGULAR")
    assert len(body["timestamp"]) == 19  # YYYY-MM-DD HH:MM:SS


def test_price_with_a_zero_previous_close_does_not_divide_by_zero(client, yahoo):
    yahoo.add("IPO", history=prices(), fast_info={"lastPrice": 12.0, "previousClose": 0})

    body = client.get("/price/IPO").json()

    assert body["change_percent"] == 0
    assert body["currency"] == "USD"  # default when Yahoo sends none


def test_price_failure_is_reported_not_raised(client, yahoo):
    yahoo.add("AAPL", history=prices(), fast_info={})  # no lastPrice

    assert client.get("/price/AAPL").json()["error"].startswith("Failed to fetch price for AAPL")


# --- JSON safety ------------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/extract/AAPL", "/history/AAPL", "/extract_many?ticker=AAPL"])
def test_missing_values_come_back_as_null_not_a_server_error(client, yahoo, path):
    frame = prices(rows=2)
    frame.loc[frame.index[0], "Open"] = float("nan")  # Yahoo leaves gaps for halted or partial sessions
    yahoo.add("AAPL", history=frame)

    response = client.get(path)

    assert response.status_code == 200
    rows = response.json()["data"]
    rows = rows["AAPL"] if isinstance(rows, dict) else rows
    assert rows[0]["Open"] is None
    assert rows[1]["Open"] == 101.0
