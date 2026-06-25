#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
RUN_DIR="${ROOT_DIR}/.run"
DB_PATH="${DB_PATH:-${ROOT_DIR}/data/market_review.db}"
PORT="${PORT:-8765}"
HOST="${HOST:-127.0.0.1}"
BACKFILL_DAYS="${BACKFILL_DAYS:-30}"
KLINE_LIMIT="${KLINE_LIMIT:-10}"
DAILY_UPDATE_AT="${DAILY_UPDATE_AT:-17:30}"
PREMARKET_UPDATE_AT="${PREMARKET_UPDATE_AT:-08:30}"

mkdir -p "${LOG_DIR}" "${RUN_DIR}"

find_python() {
  if command -v python3.11 >/dev/null 2>&1; then
    command -v python3.11
  elif [ -x /usr/local/bin/python3 ]; then
    /usr/local/bin/python3
  else
    command -v python3
  fi
}

PYTHON_BIN="${PYTHON_BIN:-$(find_python)}"

usage() {
  cat <<EOF
用法: scripts/auto_review.sh <命令>

命令:
  once        立即补最近 ${BACKFILL_DAYS} 个交易日数据，并生成复盘
  server      后台启动/重启数据展示页 http://${HOST}:${PORT}
  schedule    后台启动每日自动调度：盘前 ${PREMARKET_UPDATE_AT}，复盘 ${DAILY_UPDATE_AT}
  status      查看数据库、数据页、调度器状态
  stop        停止本脚本启动的数据页和调度器

常用环境变量:
  BACKFILL_DAYS=30
  KLINE_LIMIT=10
  PORT=8765
  DAILY_UPDATE_AT=17:30
  PREMARKET_UPDATE_AT=08:30
  PYTHON_BIN=/usr/local/bin/python3
EOF
}

is_running() {
  local pid_file="$1"
  if [ ! -f "${pid_file}" ]; then
    return 1
  fi
  local pid
  pid="$(cat "${pid_file}")"
  [ -n "${pid}" ] && kill -0 "${pid}" >/dev/null 2>&1
}

server_pid_for_port() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null | head -n 1
  fi
}

scheduler_pid() {
  pgrep -f "src/daily_scheduler.py" 2>/dev/null | head -n 1 || true
}

server_responds() {
  local url="http://${HOST}:${PORT}"
  "${PYTHON_BIN}" - <<PY >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("${url}", timeout=1).read(1)
PY
}

stop_pid_file() {
  local name="$1"
  local pid_file="$2"
  if is_running "${pid_file}"; then
    local pid
    pid="$(cat "${pid_file}")"
    echo "停止 ${name}: pid=${pid}"
    kill "${pid}" >/dev/null 2>&1 || true
    sleep 1
    if kill -0 "${pid}" >/dev/null 2>&1; then
      kill -9 "${pid}" >/dev/null 2>&1 || true
    fi
  fi
  rm -f "${pid_file}"
}

wait_for_server() {
  local url="http://${HOST}:${PORT}"
  for _ in $(seq 1 20); do
    if server_responds; then
      echo "数据页已启动: ${url}"
      return 0
    fi
    sleep 0.5
  done
  echo "数据页启动后没有及时响应，请看日志: ${LOG_DIR}/data_server.log"
  return 1
}

cmd_once() {
  cd "${ROOT_DIR}"
  echo "开始补数: 最近 ${BACKFILL_DAYS} 个交易日"
  "${PYTHON_BIN}" src/fetch_daily_review.py \
    --days "${BACKFILL_DAYS}" \
    --kline-limit "${KLINE_LIMIT}" \
    --db "${DB_PATH}" \
    2>&1 | tee -a "${LOG_DIR}/auto_update.log"
  echo "补数完成"
}

cmd_server() {
  cd "${ROOT_DIR}"
  if server_responds; then
    local existing_pid
    existing_pid="$(server_pid_for_port || true)"
    if [ -n "${existing_pid}" ]; then
      echo "${existing_pid}" > "${RUN_DIR}/data_server.pid"
      echo "数据页已在运行: http://${HOST}:${PORT} pid=${existing_pid}"
    else
      echo "数据页已在运行: http://${HOST}:${PORT}"
    fi
    return 0
  fi

  stop_pid_file "数据页" "${RUN_DIR}/data_server.pid"
  nohup "${PYTHON_BIN}" src/data_server.py \
    --host "${HOST}" \
    --port "${PORT}" \
    --db "${DB_PATH}" \
    > "${LOG_DIR}/data_server.log" 2>&1 &
  echo "$!" > "${RUN_DIR}/data_server.pid"
  wait_for_server
}

cmd_schedule() {
  cd "${ROOT_DIR}"
  stop_pid_file "自动调度器" "${RUN_DIR}/daily_scheduler.pid"
  nohup env \
    DAILY_UPDATE_AT="${DAILY_UPDATE_AT}" \
    PREMARKET_UPDATE_AT="${PREMARKET_UPDATE_AT}" \
    DAILY_KLINE_LIMIT="${KLINE_LIMIT}" \
    "${PYTHON_BIN}" src/daily_scheduler.py \
      --db "${DB_PATH}" \
      --run-at "${DAILY_UPDATE_AT}" \
      --premarket-at "${PREMARKET_UPDATE_AT}" \
      --kline-limit "${KLINE_LIMIT}" \
    > "${LOG_DIR}/daily_scheduler.log" 2>&1 &
  echo "$!" > "${RUN_DIR}/daily_scheduler.pid"
  echo "自动调度器已启动: pid=$(cat "${RUN_DIR}/daily_scheduler.pid")"
  echo "日志: ${LOG_DIR}/daily_scheduler.log"
}

cmd_status() {
  cd "${ROOT_DIR}"
  echo "Python: ${PYTHON_BIN}"
  echo "数据库: ${DB_PATH}"
  "${PYTHON_BIN}" src/db_inventory.py

  if is_running "${RUN_DIR}/data_server.pid"; then
    echo "数据页: 运行中 pid=$(cat "${RUN_DIR}/data_server.pid") http://${HOST}:${PORT}"
  elif server_responds; then
    local existing_pid
    existing_pid="$(server_pid_for_port || true)"
    if [ -n "${existing_pid}" ]; then
      echo "${existing_pid}" > "${RUN_DIR}/data_server.pid"
      echo "数据页: 运行中 pid=${existing_pid} http://${HOST}:${PORT}"
    else
      echo "数据页: 运行中 http://${HOST}:${PORT}"
    fi
  else
    echo "数据页: 未运行"
  fi

  if is_running "${RUN_DIR}/daily_scheduler.pid"; then
    echo "自动调度器: 运行中 pid=$(cat "${RUN_DIR}/daily_scheduler.pid")"
  else
    local existing_scheduler_pid
    existing_scheduler_pid="$(scheduler_pid)"
    if [ -n "${existing_scheduler_pid}" ]; then
      echo "${existing_scheduler_pid}" > "${RUN_DIR}/daily_scheduler.pid"
      echo "自动调度器: 运行中 pid=${existing_scheduler_pid}"
    else
      echo "自动调度器: 未运行"
    fi
  fi
}

cmd_stop() {
  stop_pid_file "数据页" "${RUN_DIR}/data_server.pid"
  stop_pid_file "自动调度器" "${RUN_DIR}/daily_scheduler.pid"
}

case "${1:-}" in
  once) cmd_once ;;
  server) cmd_server ;;
  schedule) cmd_schedule ;;
  status) cmd_status ;;
  stop) cmd_stop ;;
  -h|--help|help|"") usage ;;
  *)
    echo "未知命令: $1"
    usage
    exit 2
    ;;
esac
