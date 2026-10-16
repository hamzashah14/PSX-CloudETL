"""Load service: Transform-to-warehouse mapping and SCD Type 2 on dim_ticker. Offline."""
from datetime import date, datetime, timedelta

import pytest


# ---------- indicator mapping ----------

def test_indicators_use_the_names_transform_emits(load_app):
    record = {"MA_7": 101.5, "MA_30": 99.25, "RSI_14": 55.5, "Daily_Return": 1.2,
              "Volatility_7": 0.0123, "Volatility_30": 0.02}
    assert load_app.fact_indicators(record) == {
        "ma_7": 101.5, "ma_30": 99.25, "rsi": 55.5, "daily_return": 1.2, "volatility": 0.0123,
    }


def test_indicators_keep_zero_and_drop_missing_or_nan(load_app):
    out = load_app.fact_indicators({"Daily_Return": 0.0, "RSI_14": float("nan"), "MA_7": None, "MA_30": "n/a"})
    assert out["daily_return"] == 0.0  # a flat day is a value, not "missing"
    assert out["rsi"] is None and out["ma_7"] is None and out["ma_30"] is None


def test_indicators_fall_back_to_the_old_names(load_app):
    out = load_app.fact_indicators({"RSI": 40.0, "Volatility": 0.5})
    assert out["rsi"] == 40.0 and out["volatility"] == 0.5


# ---------- SCD Type 2 ----------

def versions(db, load_app, symbol="AAPL"):
    return (db.query(load_app.DimTicker)
            .filter(load_app.DimTicker.ticker_symbol == symbol)
            .order_by(load_app.DimTicker.version).all())


def test_new_ticker_is_version_1_without_invented_defaults(db, load_app):
    key = load_app.get_or_create_ticker_key(db, "AAPL", sector="Technology", industry="Consumer Electronics",
                                            market_cap=3_000_000_000_000)
    (row,) = versions(db, load_app)
    assert (row.ticker_key, row.version, row.is_current, row.end_date) == (key, 1, True, None)
    assert row.sector == "Technology" and row.market_cap == 3_000_000_000_000
    assert row.company_name is None  # not "AAPL Corporation"


def test_same_attributes_return_the_same_key(db, load_app):
    first = load_app.get_or_create_ticker_key(db, "AAPL", sector="Technology", market_cap=5)
    second = load_app.get_or_create_ticker_key(db, "AAPL", sector="Technology", market_cap=5)
    assert first == second
    assert len(versions(db, load_app)) == 1


def test_unknown_values_are_not_a_change(db, load_app):
    first = load_app.get_or_create_ticker_key(db, "AAPL", sector="Technology")
    assert load_app.get_or_create_ticker_key(db, "AAPL") == first
    assert load_app.get_or_create_ticker_key(db, "AAPL", sector="", industry=None) == first
    assert len(versions(db, load_app)) == 1


def test_changed_attribute_closes_the_old_row_and_adds_version_2(db, load_app):
    old_key = load_app.get_or_create_ticker_key(db, "AAPL", sector="Technology", industry="Hardware", market_cap=5)
    new_key = load_app.get_or_create_ticker_key(db, "AAPL", sector="Communication Services", market_cap=5)

    old, new = versions(db, load_app)
    assert new_key != old_key
    assert (old.ticker_key, old.is_current, old.end_date) == (old_key, False, date.today())
    assert (new.ticker_key, new.version, new.is_current, new.end_date) == (new_key, 2, True, None)
    assert new.sector == "Communication Services"
    assert new.industry == "Hardware"  # not received this time, carried over

    assert load_app.get_or_create_ticker_key(db, "AAPL", sector="Communication Services") == new_key
    assert len(versions(db, load_app)) == 2  # repeating the load does not add version 3


def test_failed_commit_leaves_the_old_row_current(db, load_app, monkeypatch):
    load_app.get_or_create_ticker_key(db, "AAPL", sector="Technology")

    def boom():
        raise RuntimeError("database down")

    monkeypatch.setattr(db, "commit", boom)
    with pytest.raises(RuntimeError):
        load_app.get_or_create_ticker_key(db, "AAPL", sector="Energy")
    monkeypatch.undo()

    (row,) = versions(db, load_app)
    assert row.is_current is True and row.end_date is None and row.sector == "Technology"


# ---------- Transform -> Load, end to end ----------

def raw_prices(days=20, sector="Technology"):
    """Valid raw price records for one ticker, as the extract service returns them."""
    start = datetime(2024, 1, 1)
    records = []
    for i in range(days):
        open_price = 100.0 + i
        close = open_price + (1.0 if i % 2 else -0.5)
        records.append({
            "Ticker": "AAPL", "Date": (start + timedelta(days=i)).strftime("%Y-%m-%d"),
            "Open": open_price, "High": max(open_price, close) + 1, "Low": min(open_price, close) - 1,
            "Close": close, "Volume": 1_000_000 + i * 1000, "Dividend": 0.0,
            "sector": sector, "industry": "Consumer Electronics", "marketCap": 3_000_000_000_000,
        })
    return records


class FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_real_transform_output_fills_the_indicator_columns(db, load_app, transform_app, monkeypatch):
    transformed = transform_app.transform_data({"raw_data": raw_prices()})
    monkeypatch.setattr(load_app.requests, "post", lambda *a, **k: FakeResponse({"data": transformed["data"]}))

    result = load_app.load_stock_data_to_warehouse(db, "AAPL", "1mo")

    assert result["loaded_records"] == 20
    last = db.query(load_app.FactStockPrices).order_by(load_app.FactStockPrices.date_key.desc()).first()
    assert last.ma_7 is not None and last.ma_30 is None  # 20 days: 7-day average yes, 30-day not yet
    assert last.rsi is not None and last.volatility is not None and last.daily_return is not None
    (ticker,) = versions(db, load_app)
    assert (ticker.sector, ticker.industry, ticker.market_cap) == ("Technology", "Consumer Electronics", 3_000_000_000_000)


def test_reload_adds_nothing_even_after_a_ticker_attribute_changes(db, load_app, transform_app, monkeypatch):
    def load(sector):
        transformed = transform_app.transform_data({"raw_data": raw_prices(sector=sector)})
        monkeypatch.setattr(load_app.requests, "post", lambda *a, **k: FakeResponse({"data": transformed["data"]}))
        return load_app.load_stock_data_to_warehouse(db, "AAPL", "1mo")["loaded_records"]

    assert load("Technology") == 20
    assert load("Technology") == 0
    assert load("Communication Services") == 0  # new ticker version, same dates: no duplicate facts
    assert len(versions(db, load_app)) == 2
    assert db.query(load_app.FactStockPrices).count() == 20
