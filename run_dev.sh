#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

CLEANUP_FILE="${SCRIPT_DIR}/data/gschemas.compiled"

cleanup() {
    if [ -f "${CLEANUP_FILE}" ]; then
        rm -f "${CLEANUP_FILE}"
        echo "Cleaned up temporary GSettings schema."
    fi
}

trap cleanup EXIT INT TERM

echo "Compiling temporary GSettings schema..."
glib-compile-schemas "${SCRIPT_DIR}/data"

export PYTHONPATH="${SCRIPT_DIR}/src:${PYTHONPATH}"
export GSETTINGS_SCHEMA_DIR="${SCRIPT_DIR}/data:${GSETTINGS_SCHEMA_DIR}"

echo "Launching Parch Driver Manager locally..."
python3 main.py "$@"
