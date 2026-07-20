#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env.integration"
COMPOSE=(docker compose --env-file "${ENV_FILE}" -f "${PROJECT_ROOT}/docker-compose.yml" -f "${PROJECT_ROOT}/deploy/docker-compose.integration.yml")

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "缺少 .env.integration，请先从 .env.integration.example 复制并修改。" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

mkdir -p "${PROJECT_ROOT}/reports/runtime"
"${COMPOSE[@]}" up -d --build mysql redis minio backend celery-worker celery-beat
"${COMPOSE[@]}" exec -T backend python scripts/init_data.py
"${COMPOSE[@]}" exec -T backend python scripts/verify_real_stack.py

cd "${PROJECT_ROOT}/backend"
INTEGRATION_DATABASE_URL="mysql+asyncmy://eduflow:${MYSQL_PASSWORD}@127.0.0.1:3307/eduflow_integration" \
INTEGRATION_REDIS_URL="redis://127.0.0.1:6381/0" \
INTEGRATION_MINIO_ENDPOINT="127.0.0.1:9002" \
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY}" \
MINIO_SECRET_KEY="${MINIO_SECRET_KEY}" \
.venv/bin/pytest integration_tests -q

BENCHMARK_BASE_URL="http://127.0.0.1:8003" \
BENCHMARK_ACCOUNT_PREFIX="benchmark_user_" \
BENCHMARK_ACCOUNT_COUNT="50" \
BENCHMARK_PASSWORD="BenchmarkUser2026!" \
.venv/bin/python scripts/prepare_benchmark_users.py

LOCUST_HOST="http://127.0.0.1:8003" \
LOCUST_ACCOUNT_PREFIX="benchmark_user_" \
LOCUST_ACCOUNT_COUNT="50" \
LOCUST_PASSWORD="BenchmarkUser2026!" \
.venv/bin/locust -f locustfile.py --headless \
  --users 50 --spawn-rate 5 --run-time 2m --stop-timeout 10 \
  --csv "${PROJECT_ROOT}/reports/runtime/locust" \
  --html "${PROJECT_ROOT}/reports/runtime/locust.html"
