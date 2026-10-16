#!/usr/bin/env bash
# Creates or updates `postgres-secret` in the database namespace and in the application namespace.
#
#   POSTGRES_USER=etluser POSTGRES_PASSWORD=... POSTGRES_DB=etldb \
#     infra/scripts/create-db-secret.sh database prod
#
# Why a script and not a manifest: a secret committed to Git ends up either as a placeholder that
# every deploy applies over the real password, or as the real password in the repository. The
# pipelines read the values from their own secret store (Jenkins credentials, GitHub environment
# secrets) and run this script instead.
#
# The database namespace needs the secret for Postgres itself. The application namespace needs a
# copy because a pod can only read secrets from its own namespace; its DATABASE_URL points at the
# Postgres service in the database namespace.
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: POSTGRES_USER=... POSTGRES_PASSWORD=... POSTGRES_DB=... $0 <database-namespace> <app-namespace>" >&2
  exit 2
fi
db_ns=$1
app_ns=$2
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"

for value in "$POSTGRES_USER" "$POSTGRES_PASSWORD" "$POSTGRES_DB"; do
  case $value in *$'\n'*) echo "error: values must not contain a newline" >&2; exit 2 ;; esac
done

# Percent-encode byte by byte so a password such as p@ss/w:rd#1 is safe inside the URL.
urlencode() {
  local LC_ALL=C s=$1 out='' c i
  for ((i = 0; i < ${#s}; i++)); do
    c=${s:i:1}
    case $c in
      [a-zA-Z0-9._~-]) out+=$c ;;
      *) out+=$(printf '%%%02X' "'$c") ;;
    esac
  done
  printf '%s' "$out"
}

# Values go through a private file, never through command-line arguments (those show up in `ps`).
env_file=$(mktemp)
chmod 600 "$env_file"
trap 'rm -f "$env_file"' EXIT
{
  printf 'POSTGRES_DB=%s\n' "$POSTGRES_DB"
  printf 'POSTGRES_USER=%s\n' "$POSTGRES_USER"
  printf 'POSTGRES_PASSWORD=%s\n' "$POSTGRES_PASSWORD"
  printf 'DATABASE_URL=postgresql://%s:%s@postgres.%s.svc.cluster.local:5432/%s\n' \
    "$(urlencode "$POSTGRES_USER")" "$(urlencode "$POSTGRES_PASSWORD")" "$db_ns" "$POSTGRES_DB"
} >"$env_file"

for ns in "$db_ns" "$app_ns"; do
  kubectl get namespace "$ns" >/dev/null 2>&1 || kubectl create namespace "$ns"
  kubectl create secret generic postgres-secret -n "$ns" --from-env-file="$env_file" --dry-run=client -o yaml |
    kubectl apply -n "$ns" -f - >/dev/null
  echo "postgres-secret is in place in namespace $ns"
done
