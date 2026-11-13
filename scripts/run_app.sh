#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
export HF_HOME="${HF_HOME:-$ROOT/.cache/huggingface}"
if [[ ! -d .venv ]]; then
  echo "请先创建虚拟环境并安装依赖，见 README。"
  exit 1
fi
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8765
