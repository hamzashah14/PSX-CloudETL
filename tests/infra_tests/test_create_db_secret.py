"""Runs infra/scripts/create-db-secret.sh against a fake kubectl and checks what it would send."""
import os
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "infra" / "scripts" / "create-db-secret.sh"

FAKE_KUBECTL = """#!/usr/bin/env bash
# records every call; saves the env file the script hands over; echoes a dummy manifest for `apply`
echo "$*" >> "$FAKE_LOG"
for a in "$@"; do
  case "$a" in --from-env-file=*) cp "${a#--from-env-file=}" "$FAKE_LOG.env.$ns" 2>/dev/null || cp "${a#--from-env-file=}" "$FAKE_LOG.env.last" ;; esac
done
case "$1 $2" in
  "get namespace") exit 1 ;;
  "create secret") echo "kind: Secret" ;;
  "apply -n") cat > /dev/null ;;
esac
"""


@pytest.fixture
def fake(tmp_path):
    kubectl = tmp_path / "kubectl"
    kubectl.write_text(FAKE_KUBECTL)
    kubectl.chmod(kubectl.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "calls.log"
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "FAKE_LOG": str(log)}
    for k in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
        env.pop(k, None)
    return env, log


def run(env, *args, **extra):
    return subprocess.run(["bash", str(SCRIPT), *args], env={**env, **extra}, capture_output=True, text=True)


def test_needs_both_namespaces_and_all_three_values(fake):
    env, _ = fake
    assert run(env).returncode == 2
    r = run(env, "database", "dev", POSTGRES_USER="u", POSTGRES_DB="d")  # password missing
    assert r.returncode != 0 and "POSTGRES_PASSWORD" in r.stderr


def test_rejects_newlines_in_values(fake):
    env, _ = fake
    r = run(env, "database", "dev", POSTGRES_USER="u", POSTGRES_PASSWORD="a\nb", POSTGRES_DB="d")
    assert r.returncode == 2 and "newline" in r.stderr


def test_creates_the_secret_in_both_namespaces_and_never_puts_values_in_arguments(fake):
    env, log = fake
    password = "p@ss/w:rd#1 %é"
    r = run(env, "database", "prod", POSTGRES_USER="etluser", POSTGRES_PASSWORD=password, POSTGRES_DB="etldb")
    assert r.returncode == 0, r.stderr
    calls = log.read_text()
    for ns in ("database", "prod"):
        assert f"create secret generic postgres-secret -n {ns}" in calls
        assert f"apply -n {ns}" in calls
    assert password not in calls and "etluser" not in calls  # values only travel through the private file
    assert password not in r.stdout + r.stderr


def test_database_url_is_percent_encoded_and_points_at_the_database_namespace(fake):
    env, log = fake
    r = run(env, "database", "dev", POSTGRES_USER="etl user", POSTGRES_PASSWORD="p@ss/w:rd#1é", POSTGRES_DB="etldb")
    assert r.returncode == 0, r.stderr
    saved = next(log.parent.glob("calls.log.env*")).read_text().splitlines()
    values = dict(line.split("=", 1) for line in saved)
    assert values["POSTGRES_DB"] == "etldb"
    assert values["DATABASE_URL"] == (
        "postgresql://etl%20user:p%40ss%2Fw%3Ard%231%C3%A9@postgres.database.svc.cluster.local:5432/etldb"
    )
