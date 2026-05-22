#!/usr/bin/env bash
# Run ingest pipeline for every .md file in the specified directory

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/.."

INGEST_CMD="uv run $PROJECT_ROOT/src/main/ingest.py"

# Allow overriding the directory via env INGEST_INPUT_DIR or --dir argument
INPUT_DIR=".data/ingest"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir|-d)
            INPUT_DIR="$2"; shift 2;;
        *)
            break;;
    esac
done

INPUT_DIR="${INGEST_INPUT_DIR:-$INPUT_DIR}"
INPUT_DIR="$(realpath "$INPUT_DIR")"

if [[ ! -d "$INPUT_DIR" ]]; then
    echo "Error: directory $INPUT_DIR does not exist" >&2
    exit 1
fi

shopt -s nullglob
md_files=("$INPUT_DIR"/*.md)

if [[ ${#md_files[@]} -eq 0 ]]; then
    echo "No .md files found in $INPUT_DIR, nothing to do." >&2
    exit 0
fi

echo "Found ${#md_files[@]} .md file(s) in $INPUT_DIR, running ingest..."

for file in "${md_files[@]}"; do
    echo "=> Ingesting $file"
    $INGEST_CMD "$file" --config "$PROJECT_ROOT/config/ingest.yaml" \
                 --db "$PROJECT_ROOT/.data/db/ingest.db" \
                 --filestore "$PROJECT_ROOT/.data/filestore"
    echo "=> Finished $file"
done

echo "All files ingested successfully."
