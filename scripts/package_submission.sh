#!/usr/bin/env bash
set -euo pipefail

# Gera um ZIP pronto para submissão com caminhos relativos
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT_ZIP="$ROOT_DIR/atr_mina_submission.zip"

echo "Packaging project into $OUT_ZIP"
cd "$ROOT_DIR"

# Arquivos/dirs a incluir (relativos)
INCLUDE=(
  "CMakeLists.txt"
  "Dockerfile"
  "README.md"
  "include"
  "src"
  "interface"
  "docs"
  "scripts"
)

rm -f "$OUT_ZIP"
zip -r "$OUT_ZIP" "${INCLUDE[@]}"

echo "Created $OUT_ZIP"
