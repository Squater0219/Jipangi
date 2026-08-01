#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
MYSQLADMIN_BIN="${MYSQLADMIN_BIN:-/opt/homebrew/bin/mysqladmin}"
SOCKET_PATH="$PROJECT_ROOT/.mysql-run/mysql.sock"

"$MYSQLADMIN_BIN" --socket="$SOCKET_PATH" -uroot shutdown
echo "MySQL stopped."
