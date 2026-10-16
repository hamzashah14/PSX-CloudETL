"""Visualization service: layout wiring, the 5-minute data cache, the refresh callback, charts and routes.

The Transform service is mocked and nothing opens a socket. Dash callbacks are called as plain functions
with a callback context set by hand.
"""
import datetime
import json
from unittest import mock

import dash
import pandas as pd
import pytest
import requests
from dash._callback_context import context_value
from dash._utils import AttributeDict


class Reply:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


def rows(n=40, start=100.0):
    """Rows shaped like the Transform service's /transform_batch output (one rising stock)."""
    out = []
    for i in range(n):
        close = start + i
        out.append({
            "Date": (datetime.date(2024, 1, 1) + datetime.timedelta(days=i)).isoformat(),
            "Open": close - 1, "High": close + 2, "Low": close - 2, "Close": close,
            "Volume": 2_000_000 + i * 1000, "RSI_14": 50 + (i % 20), "MA_7": close - 0.5, "MA_30": close - 3,
            "Daily_Return": 0.01 * ((i % 5) - 2), "Volatility_7": 0.02 + i * 0.0001,
        })
    return out


@pytest.fixture(autouse=True)
def empty_cache(visualization_app):
    visualization_app.get_cached_data.cache_clear()
    yield
    visualization_app.get_cached_data.cache_clear()


@pytest.fixture()
def transform(monkeypatch, visualization_app):
    """Mock the module's `requests`; configure `transform.post.return_value` / `.side_effect`."""
    fake = mock.MagicMock()
    fake.exceptions = requests.exceptions
    fake.post.return_value = Reply(200, {"data": rows()})
    monkeypatch.setattr(visualization_app, "requests", fake)
    return fake


def trigger(prop_id):
    """Pretend Dash fired a callback because `prop_id` changed."""
    token = context_value.set(AttributeDict(triggered_inputs=[{"prop_id": prop_id}]))
    return token


def call_with_trigger(fn, prop_id, *args):
    token = trigger(prop_id)
    try:
        return fn(*args)
    finally:
        context_value.reset(token)


def graphs(component):
    return [c for c in [component, *component._traverse()] if isinstance(c, dash.dcc.Graph)]


def texts(component):
    """Every text fragment inside a Dash component tree."""
    found = []
    for item in [component, *component._traverse()]:  # _traverse() yields the descendants only
        children = getattr(item, "children", None)
        if isinstance(children, str):
            found.append(children)
    return found


# --- layout and callback wiring ---------------------------------------------------------------

def test_every_callback_input_and_output_exists_in_the_layout(visualization_app):
    layout_ids = {c.id for c in visualization_app.app.layout._traverse() if getattr(c, "id", None)}
    callbacks = visualization_app.app.callback_map

    assert len(callbacks) == 2  # view switching and the data refresh
    for output_key, spec in callbacks.items():
        referenced = {i["id"] for i in spec["inputs"]} | {s["id"] for s in spec["state"]}
        referenced |= {part.rsplit(".", 1)[0] for part in output_key.strip(".").split("...")}
        assert referenced <= layout_ids, f"callback uses ids that are not in the layout: {referenced - layout_ids}"


def test_ticker_dropdown_offers_ten_tickers_and_starts_on_aapl(visualization_app):
    dropdown = next(c for c in visualization_app.app.layout._traverse() if getattr(c, "id", None) == "ticker-dropdown")

    assert dropdown.value == "AAPL"
    assert len(dropdown.options) == 10
    assert "AAPL" in {o["value"] for o in dropdown.options}


# --- data fetch and cache ---------------------------------------------------------------------

def test_data_comes_from_the_transform_service(monkeypatch, visualization_app, transform):
    monkeypatch.setenv("TRANSFORM_SERVICE_URL", "http://transform.internal:9001")

    data = visualization_app.get_data_with_cache("MSFT", "1y")

    assert len(data) == 40
    transform.post.assert_called_once_with("http://transform.internal:9001/transform_batch",
                                           json={"tickers": "MSFT", "period": "1y"}, timeout=30)


def test_data_is_cached_for_five_minutes_per_ticker_and_period(monkeypatch, visualization_app, transform):
    clock = mock.Mock(return_value=1_000_000.0)
    monkeypatch.setattr(visualization_app.time, "time", clock)

    visualization_app.get_data_with_cache("AAPL", "1mo")
    visualization_app.get_data_with_cache("AAPL", "1mo")
    assert transform.post.call_count == 1  # same five-minute bucket: served from the cache

    visualization_app.get_data_with_cache("AAPL", "1y")
    visualization_app.get_data_with_cache("MSFT", "1mo")
    assert transform.post.call_count == 3  # other period or ticker: a new request

    clock.return_value += 300  # the next bucket
    visualization_app.get_data_with_cache("AAPL", "1mo")
    assert transform.post.call_count == 4


def test_a_failed_fetch_returns_an_empty_list(visualization_app, transform):
    transform.post.return_value = Reply(500)

    assert visualization_app.get_data_with_cache("AAPL", "1mo") == []

    transform.post.side_effect = requests.exceptions.ConnectionError("transform is down")
    visualization_app.get_cached_data.cache_clear()
    assert visualization_app.get_data_with_cache("AAPL", "1mo") == []


# --- refresh_engine callback ------------------------------------------------------------------

def refresh(visualization_app, prop_id, view="markets", ticker="AAPL"):
    return call_with_trigger(visualization_app.refresh_engine, prop_id, view, ticker, None, None, None)


def test_refresh_renders_the_chosen_view_with_stats(visualization_app, transform):
    content, stats, month_class, year_class = refresh(visualization_app, "ticker-dropdown.value")

    candles, volume = (g.figure for g in graphs(content))
    assert candles.data[0].type == "candlestick" and len(candles.data[0].x) == 40
    assert volume.data[0].type == "bar"
    assert stats is not None
    assert (month_class, year_class) == ("btn-ghost active", "btn-ghost")
    assert transform.post.call_args.kwargs["json"] == {"tickers": "AAPL", "period": "1mo"}


def test_year_button_requests_a_year_and_swaps_the_active_button(visualization_app, transform):
    _, _, month_class, year_class = refresh(visualization_app, "btn-1y.n_clicks")

    assert transform.post.call_args.kwargs["json"]["period"] == "1y"
    assert (month_class, year_class) == ("btn-ghost", "btn-ghost active")


def test_refresh_button_clears_the_cache_and_fetches_again(visualization_app, transform):
    refresh(visualization_app, "ticker-dropdown.value")
    refresh(visualization_app, "ticker-dropdown.value")
    assert transform.post.call_count == 1

    refresh(visualization_app, "refresh-btn.n_clicks")

    assert transform.post.call_count == 2


@pytest.mark.parametrize("view", ["markets", "intel", "risk", "something-unknown"])
def test_every_view_renders_from_real_shaped_data(visualization_app, transform, view):
    content, stats, _, _ = refresh(visualization_app, "active-view.data", view=view)

    expected_charts = {"markets": 2, "intel": 1, "risk": 2, "something-unknown": 2}[view]  # unknown falls back to markets
    assert len(graphs(content)) == expected_charts
    assert stats is not None


def test_no_data_shows_the_unavailable_message_and_no_stats(visualization_app, transform):
    transform.post.return_value = Reply(200, {"data": []})

    content, stats, _, _ = refresh(visualization_app, "ticker-dropdown.value")

    assert "DATA FEED UNAVAILABLE" in texts(content)
    assert stats is None


# --- view switching ---------------------------------------------------------------------------

@pytest.mark.parametrize("button, view, classes", [
    ("view-markets.n_clicks", "markets", ("nav-pill active", "nav-pill", "nav-pill")),
    ("view-intel.n_clicks", "intel", ("nav-pill", "nav-pill active", "nav-pill")),
    ("view-risk.n_clicks", "risk", ("nav-pill", "nav-pill", "nav-pill active")),
])
def test_clicking_a_nav_pill_selects_its_view(visualization_app, button, view, classes):
    result = call_with_trigger(visualization_app.switch_dashboard_view, button, 1, 1, 1, "markets")

    assert result == (view, *classes)


def test_view_switch_without_a_click_keeps_the_current_view(visualization_app):
    token = context_value.set(AttributeDict(triggered_inputs=[]))
    try:
        result = visualization_app.switch_dashboard_view(None, None, None, "risk")
    finally:
        context_value.reset(token)

    assert result[0] == "risk"


# --- charts and stats panel -------------------------------------------------------------------

def test_candlestick_has_one_candle_per_row(visualization_app):
    fig = visualization_app.create_candlestick_chart(pd.DataFrame(rows(10)), "AAPL")

    assert len(fig.data) == 1 and len(fig.data[0].x) == 10
    assert fig.layout.title.text == "AAPL Price Action"


def test_empty_data_gives_a_chart_that_says_so(visualization_app):
    fig = visualization_app.create_candlestick_chart(pd.DataFrame(), "AAPL")

    assert fig.layout.annotations[0].text == "No Data Available"
    assert visualization_app.create_volume_chart(pd.DataFrame()).data == ()


def test_volume_bars_are_green_when_the_close_is_above_the_open(visualization_app):
    df = pd.DataFrame(rows(2))
    df.loc[1, "Close"] = df.loc[1, "Open"] - 5  # a down day

    bar = visualization_app.create_volume_chart(df).data[0]

    colors = visualization_app.colors
    assert list(bar.marker.color) == [colors["positive"], colors["negative"]]


def test_stats_panel_shows_price_change_high_low_and_average_volume(visualization_app):
    df = pd.DataFrame(rows(3, start=100.0))  # closes 100, 101, 102; highs up to 104; lows from 98

    shown = texts(visualization_app.create_stats_panel(df))

    assert "$102.00" in shown
    assert "$1.00 (0.99%)" in shown  # 102 vs 101
    assert "$104.00" in shown and "$98.00" in shown
    assert "2.0M" in shown


def test_stats_panel_with_a_single_row_has_no_change(visualization_app):
    shown = texts(visualization_app.create_stats_panel(pd.DataFrame(rows(1))))

    assert "$0.00 (0.00%)" in shown


def test_stats_panel_without_data_says_so(visualization_app):
    assert texts(visualization_app.create_stats_panel(pd.DataFrame())) == ["No Data Available"]


def test_correlation_matrix_uses_only_the_columns_that_exist(visualization_app):
    df = pd.DataFrame(rows(10)).drop(columns=["RSI_14"])

    heatmap = visualization_app.create_correlation_matrix(df).data[0]

    assert list(heatmap.x) == ["Close", "Volume", "Daily_Return"]


# --- Flask routes -----------------------------------------------------------------------------

@pytest.fixture()
def server(visualization_app):
    return visualization_app.server.test_client()


@pytest.fixture()
def calm_machine(monkeypatch):
    monkeypatch.setattr("psutil.virtual_memory", lambda: mock.Mock(percent=20.0))
    monkeypatch.setattr("psutil.cpu_percent", lambda interval=None: 10.0)


def test_health_is_healthy_when_the_transform_service_answers(server, transform, calm_machine):
    transform.get.return_value = Reply(200)

    body = server.get("/health").get_json()

    assert body["status"] == "healthy"
    assert body["checks"]["transform_service"] == "healthy"


def test_health_is_degraded_when_the_transform_service_misbehaves(server, transform, calm_machine):
    transform.get.return_value = Reply(500)

    assert server.get("/health").get_json()["status"] == "degraded"


def test_health_is_unhealthy_when_the_transform_service_is_unreachable(server, transform, calm_machine):
    transform.get.side_effect = requests.exceptions.ConnectionError("down")

    body = server.get("/health").get_json()

    assert body["status"] == "unhealthy"
    assert body["checks"]["transform_service"].startswith("unhealthy")


def test_refresh_route_clears_the_data_cache(visualization_app, server, transform):
    visualization_app.get_data_with_cache("AAPL", "1mo")
    assert visualization_app.get_cached_data.cache_info().currsize == 1

    response = server.get("/refresh")

    assert response.get_json()["status"] == "success"
    assert visualization_app.get_cached_data.cache_info().currsize == 0
