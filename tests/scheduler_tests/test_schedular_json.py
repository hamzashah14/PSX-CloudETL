"""Scheduler service: the update job, its health report, manual triggers and the scheduling loop.

The background thread is stubbed at import (see conftest), HTTP is mocked, and `time.sleep` is replaced,
so nothing waits and nothing touches the network.
"""
import datetime
from unittest import mock

import pytest
import requests
import schedule


class Reply:
    def __init__(self, status):
        self.status_code = status


@pytest.fixture(autouse=True)
def clean_state(monkeypatch, scheduler_app):
    """Each test starts with an empty job history and no scheduled jobs."""
    monkeypatch.setattr(scheduler_app, "job_status", {"last_run": None, "next_run": None, "status": "initialized",
                                                       "runs_count": 0, "errors": []})
    schedule.clear()
    yield
    schedule.clear()


@pytest.fixture()
def http(monkeypatch, scheduler_app):
    """Mock the module's `requests`; `http.order()` lists the calls made, in order."""
    fake = mock.MagicMock()
    fake.exceptions = requests.exceptions  # the service catches requests' own exception types
    monkeypatch.setattr(scheduler_app, "requests", fake)
    manager = mock.Mock()
    manager.attach_mock(fake.post, "post")
    manager.attach_mock(fake.get, "get")
    fake.order = lambda: [c[0] for c in manager.mock_calls]
    return fake


@pytest.fixture()
def client(scheduler_app):
    return scheduler_app.app.test_client()


# --- trigger_data_update ----------------------------------------------------------------------

def test_update_posts_the_load_batch_then_refreshes_the_dashboard(scheduler_app, http):
    http.post.return_value = Reply(200)
    http.get.return_value = Reply(200)

    scheduler_app.trigger_data_update()

    assert http.order() == ["post", "get"]
    http.post.assert_called_once_with(f"{scheduler_app.LOAD_SERVICE_URL}/load/batch",
                                      json={"tickers": "AAPL,GOOGL,MSFT", "period": "1mo"}, timeout=30)
    http.get.assert_called_once_with(f"{scheduler_app.VISUALIZATION_SERVICE_URL}/refresh", timeout=10)
    status = scheduler_app.job_status
    assert (status["status"], status["runs_count"]) == ("completed", 1)
    datetime.datetime.fromisoformat(status["last_run"])


@pytest.mark.parametrize("load, dashboard, expected", [
    (200, 200, "completed"),
    (201, 200, "completed"),  # the load service may answer 201
    (500, 200, "partial"),
    (200, 503, "partial"),
    (500, 500, "error"),
])
def test_update_status_reflects_which_services_answered_ok(scheduler_app, http, load, dashboard, expected):
    http.post.return_value = Reply(load)
    http.get.return_value = Reply(dashboard)

    scheduler_app.trigger_data_update()

    assert scheduler_app.job_status["status"] == expected
    assert scheduler_app.job_status["runs_count"] == 1  # a failed run still counts as a run
    assert http.get.call_count == 1  # a failing load service never stops the dashboard refresh


def test_update_continues_when_the_load_service_is_unreachable(scheduler_app, http):
    http.post.side_effect = requests.exceptions.ConnectionError("no route to host")
    http.get.return_value = Reply(200)

    scheduler_app.trigger_data_update()

    assert http.order() == ["post", "get"]
    assert scheduler_app.job_status["status"] == "partial"


def test_update_with_both_services_unreachable_is_an_error(scheduler_app, http):
    http.post.side_effect = requests.exceptions.Timeout("slow")
    http.get.side_effect = requests.exceptions.ConnectionError("down")

    scheduler_app.trigger_data_update()

    assert scheduler_app.job_status["status"] == "error"
    assert scheduler_app.job_status["runs_count"] == 1


def test_unexpected_failures_are_recorded_and_only_the_last_ten_kept(scheduler_app, http):
    # RuntimeError is not a requests error, so it reaches the outer handler instead of the per-service ones
    http.post.side_effect = [RuntimeError(f"boom {n}") for n in range(12)]

    for n in range(12):
        scheduler_app.trigger_data_update()  # must never raise, or the scheduling thread would die
        assert len(scheduler_app.job_status["errors"]) == min(n + 1, 10)  # the list never shrinks below ten

    errors = scheduler_app.job_status["errors"]
    assert [e["error"] for e in errors] == [f"boom {n}" for n in range(2, 12)]
    assert scheduler_app.job_status["status"] == "error"


# --- manual triggers and plain routes ---------------------------------------------------------

@pytest.mark.parametrize("service, load, dashboard, ok", [
    ("load", 201, None, True),
    ("load", 500, None, False),
    ("visualization", None, 200, True),
    ("visualization", None, 404, False),
    ("nonsense", None, None, False),
])
def test_trigger_specific_service(scheduler_app, http, service, load, dashboard, ok):
    http.post.return_value = Reply(load)
    http.get.return_value = Reply(dashboard)

    assert scheduler_app.trigger_specific_service(service) is ok


def test_trigger_specific_service_swallows_exceptions(scheduler_app, http):
    http.post.side_effect = RuntimeError("boom")

    assert scheduler_app.trigger_specific_service("load") is False


def test_trigger_endpoint_runs_the_update_in_a_background_thread(scheduler_app, client):
    started = []

    class FakeThread:
        def __init__(self, target, daemon):
            started.append((target, daemon))

        def start(self):
            started.append("started")

    with mock.patch.object(scheduler_app.threading, "Thread", FakeThread):
        response = client.get("/trigger")

    assert response.status_code == 200
    assert started == [(scheduler_app.trigger_data_update, True), "started"]


def test_trigger_service_endpoint_returns_200_or_500(scheduler_app, client, http):
    http.post.return_value = Reply(200)
    assert client.get("/trigger/load").status_code == 200
    assert "Successfully triggered load" in client.get("/trigger/load").get_json()["message"]

    http.post.return_value = Reply(500)
    response = client.get("/trigger/load")
    assert response.status_code == 500
    assert "Failed to trigger load" in response.get_json()["error"]


def test_status_reports_job_history_and_number_of_jobs(client):
    schedule.every(30).seconds.do(lambda: None)

    body = client.get("/status").get_json()

    assert body["scheduled_jobs"] == 1
    assert body["job_status"]["status"] == "initialized"


def test_home_lists_the_endpoints(client):
    body = client.get("/").get_json()

    assert body["service"] == "scheduler"
    assert "/trigger/<service_name>" in body["endpoints"]


# --- /health ----------------------------------------------------------------------------------

@pytest.fixture()
def healthy_machine(monkeypatch):
    monkeypatch.setattr("psutil.virtual_memory", lambda: mock.Mock(percent=20.0))
    monkeypatch.setattr("psutil.cpu_percent", lambda interval=None: 10.0)


def a_working_scheduler(scheduler_app):
    schedule.every(30).seconds.do(lambda: None)
    scheduler_app.job_status.update(runs_count=3, status="completed")


def test_health_is_healthy_when_everything_works(scheduler_app, client, http, healthy_machine):
    a_working_scheduler(scheduler_app)
    http.get.return_value = Reply(200)

    body = client.get("/health").get_json()

    assert body["status"] == "healthy"
    assert body["active_jobs"] == 1 and body["total_runs"] == 3
    assert body["checks"]["service_connectivity"] == {"load_service": "healthy", "visualization_service": "healthy"}


def test_health_is_degraded_right_after_start(client, http, healthy_machine):
    http.get.return_value = Reply(200)  # no jobs and no runs yet: not an error, but not fully healthy either

    body = client.get("/health").get_json()

    assert body["status"] == "degraded"
    assert body["checks"]["job_execution"] == "degraded - no runs yet"
    assert body["checks"]["scheduler"] == "degraded - no scheduled jobs"


def test_health_is_degraded_when_one_service_is_down(scheduler_app, client, http, healthy_machine):
    a_working_scheduler(scheduler_app)
    http.get.side_effect = [requests.exceptions.ConnectionError("down"), Reply(200)]  # load first, then dashboard

    body = client.get("/health").get_json()

    assert body["checks"]["service_connectivity"]["load_service"].startswith("unhealthy")
    assert body["checks"]["services_overall"] == "degraded - some services struggling"
    assert body["status"] == "degraded"


def test_health_is_unhealthy_when_both_services_are_down(scheduler_app, client, http, healthy_machine):
    a_working_scheduler(scheduler_app)
    http.get.side_effect = requests.exceptions.ConnectionError("down")

    body = client.get("/health").get_json()

    assert body["checks"]["services_overall"] == "unhealthy - multiple services down"
    assert body["status"] == "unhealthy"


def test_health_is_unhealthy_when_the_last_job_failed(scheduler_app, client, http, healthy_machine):
    a_working_scheduler(scheduler_app)
    scheduler_app.job_status["status"] = "error"
    http.get.return_value = Reply(200)

    body = client.get("/health").get_json()

    assert body["checks"]["job_execution"] == "unhealthy - last job failed"
    assert body["status"] == "unhealthy"


def test_health_is_unhealthy_when_memory_is_nearly_full(scheduler_app, client, http, monkeypatch):
    a_working_scheduler(scheduler_app)
    monkeypatch.setattr("psutil.virtual_memory", lambda: mock.Mock(percent=95.0))
    monkeypatch.setattr("psutil.cpu_percent", lambda interval=None: 5.0)
    http.get.return_value = Reply(200)

    assert client.get("/health").get_json()["status"] == "unhealthy"


# --- configuration and scheduling loop --------------------------------------------------------

def test_service_urls_come_from_the_environment(monkeypatch, import_scheduler):
    monkeypatch.setenv("LOAD_SERVICE_URL", "http://load.internal:9003")
    monkeypatch.setenv("VISUALIZATION_SERVICE_URL", "http://viz.internal:9002")

    module = import_scheduler()

    assert (module.LOAD_SERVICE_URL, module.VISUALIZATION_SERVICE_URL) == ("http://load.internal:9003",
                                                                          "http://viz.internal:9002")


def test_service_urls_default_to_the_cluster_service_names(monkeypatch, import_scheduler):
    monkeypatch.delenv("LOAD_SERVICE_URL", raising=False)
    monkeypatch.delenv("VISUALIZATION_SERVICE_URL", raising=False)

    module = import_scheduler()

    assert module.LOAD_SERVICE_URL == "http://load-service:8003"
    assert module.VISUALIZATION_SERVICE_URL == "http://visualization-service:8002"


def test_scheduler_thread_is_started_only_once(monkeypatch, scheduler_app):
    started = []

    class FakeThread:
        def __init__(self, target, daemon):
            pass

        def start(self):
            started.append(1)

    monkeypatch.setattr(scheduler_app.threading, "Thread", FakeThread)
    monkeypatch.setattr(scheduler_app, "scheduler_started", False)

    scheduler_app.init_scheduler()
    scheduler_app.init_scheduler()

    assert started == [1]


def run_loop(scheduler_app, monkeypatch, sleeps):
    """Run run_scheduler() until the scripted `time.sleep` side effects reach a KeyboardInterrupt."""
    sleep = mock.Mock(side_effect=sleeps)
    monkeypatch.setattr(scheduler_app.time, "sleep", sleep)
    with pytest.raises(KeyboardInterrupt):
        scheduler_app.run_scheduler()
    return sleep


def test_loop_schedules_a_30_second_job_and_publishes_the_next_run(scheduler_app, monkeypatch):
    run_loop(scheduler_app, monkeypatch, [None, KeyboardInterrupt])

    intervals = sorted((job.interval, job.unit) for job in schedule.get_jobs())
    assert intervals == [(1, "minutes"), (30, "seconds")]  # the 30 s job and the one-off startup job
    datetime.datetime.fromisoformat(scheduler_app.job_status["next_run"])


def test_startup_job_is_dropped_after_the_first_run(scheduler_app, monkeypatch):
    scheduler_app.job_status["runs_count"] = 1

    run_loop(scheduler_app, monkeypatch, [None, KeyboardInterrupt])

    assert schedule.get_jobs("initial") == []
    assert len(schedule.get_jobs()) == 1


def test_loop_survives_an_error_and_backs_off_five_seconds(scheduler_app, monkeypatch):
    monkeypatch.setattr(scheduler_app.schedule, "run_pending", mock.Mock(side_effect=[RuntimeError("x"), None]))

    sleep = run_loop(scheduler_app, monkeypatch, [None, KeyboardInterrupt])

    assert sleep.call_args_list == [mock.call(5), mock.call(1)]


def test_trigger_of_an_unknown_service_is_a_client_error(client, http):
    response = client.get("/trigger/nonsense")

    assert response.status_code == 404
    assert "nonsense" in response.get_json()["error"]
    http.post.assert_not_called()
    http.get.assert_not_called()
