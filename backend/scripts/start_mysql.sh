#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
MYSQLD_BIN="${MYSQLD_BIN:-/opt/homebrew/opt/mysql@8.4/bin/mysqld}"
MYSQLADMIN_BIN="${MYSQLADMIN_BIN:-/opt/homebrew/bin/mysqladmin}"
SOCKET_PATH="$PROJECT_ROOT/.mysql-run/mysql.sock"

mkdir -p "$PROJECT_ROOT/.mysql-run"

if "$MYSQLADMIN_BIN" --socket="$SOCKET_PATH" ping >/dev/null 2>&1; then
    echo "MySQL is already running."
    exit 0
fi

"$MYSQLD_BIN" \
    --datadir="$PROJECT_ROOT/.mysql-data-84" \
    --socket="$SOCKET_PATH" \
    --pid-file="$PROJECT_ROOT/.mysql-run/mysql.pid" \
    --port=3307 \
    --log-error="$PROJECT_ROOT/.mysql-data-84/server.err" \
    --innodb-redo-log-capacity=8388608 \
    --daemonize

echo "MySQL started on 127.0.0.1:3307."
