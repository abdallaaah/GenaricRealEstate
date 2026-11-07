#!/bin/bash
# Run one Odoo gate on a fresh database and write a log with its run ID, start time and exit code.
#
# No password lives here (rule 3). The database credentials come from an Odoo config file whose
# path is given in GRE_CONF, or ./gre_test.conf if that is unset. Build that config per
# `claude/plan_status.md`, section "Test invocation" - the addons_path must list all four paths,
# and `logfile` must NOT be set, so the run's output lands in the gate log.
#
#   GRE_CONF=/path/to/gre_test.conf claude/scripts/run_gate.sh <db> <log-name> <modules> [tags]
#
#   db         database name, dropped and recreated
#   log-name   file name inside claude/logs/
#   modules    comma-separated list for -i
#   tags       comma-separated test tags WITHOUT the leading slash on the first one;
#              defaults to <modules>. Each becomes /<tag>.
#
# Example:
#   GRE_CONF=~/gre_test.conf claude/scripts/run_gate.sh p8_modeb p8_modeb.log \
#       isky_18_realestate_developer_commission \
#       isky_18_realestate_developer_sales_crm,/isky_18_realestate_developer_unit_inventory
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONF="${GRE_CONF:-$PWD/gre_test.conf}"
ODOO_BIN="${GRE_ODOO_BIN:-/opt/odoo/odoo18/odoo/odoo-bin}"
PYTHON="${GRE_PYTHON:-/opt/odoo/odoo18/venv18/bin/python3}"

if [ "$#" -lt 3 ]; then
    sed -n '2,20p' "${BASH_SOURCE[0]}"
    exit 2
fi
if [ ! -r "$CONF" ]; then
    echo "config not readable: $CONF (set GRE_CONF)" >&2
    exit 2
fi

DB="$1"; LOG="$REPO/claude/logs/$2"; MODULES="$3"; TAGS="${4:-$3}"
mkdir -p "$REPO/claude/logs"
cd "$REPO" || exit 1

RUNID="$(date +%Y%m%d-%H%M%S)-$$"
PW="$(grep -oP '^db_password\s*=\s*\K.*' "$CONF")"

{
    echo "### RUN_ID=$RUNID"
    echo "### START=$(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "### DB=$DB"
    echo "### ARGS=-i $MODULES --test-enable --test-tags /$TAGS --log-level=test"
} > "$LOG"

PGPASSWORD="$PW" dropdb -h localhost -U odoo18 --if-exists "$DB" >/dev/null 2>&1

"$PYTHON" "$ODOO_BIN" -c "$CONF" -d "$DB" \
    -i "$MODULES" --test-enable --test-tags "/$TAGS" \
    --without-demo=all --stop-after-init --log-level=test >> "$LOG" 2>&1
RC=$?

{
    echo "### END=$(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "### EXIT=$RC"
    echo "### RUN_ID=$RUNID (end)"
} >> "$LOG"

echo "RUN_ID=$RUNID EXIT=$RC db=$DB log=claude/logs/$2"
exit $RC
