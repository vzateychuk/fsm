#!/bin/bash

INGEST_DIR=".data/ingest"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Проверяем, существует ли директория с файлами
if [ ! -d "$INGEST_DIR" ]; then
  echo "❌ Error: Directory '$INGEST_DIR' not found."
  exit 1
fi

# Находим все .md файлы и обрабатываем их по одному
find "$INGEST_DIR" -name "*.md" | while read -r file; do
  echo "=> Ingesting $file"

  # Конвертируем Unix-путь в Windows-путь для Python
  PYTHON_SCRIPT=$(cygpath -w "$SCRIPT_DIR/../src/main/ingest.py")

  # Проверяем, существует ли скрипт ingest.py
  if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "❌ Error: Python script not found at: $PYTHON_SCRIPT"
    echo "   Make sure src/main/ingest.py exists in your project."
    exit 1
  fi

  # Запускаем скрипт с путём к файлу
  python "$PYTHON_SCRIPT" "$file"

  # Проверяем код возврата
  if [ $? -ne 0 ]; then
    echo "❌ Error: Ingest failed for $file"
    exit 1
  fi
done

echo "✅ All files ingested successfully."