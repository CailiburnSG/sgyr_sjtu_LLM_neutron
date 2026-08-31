#!/usr/bin/env bash
# P0 runner: query formulation × historical chunk grid (MiniLM)
# Models cache under paper_claude_pack/.cache/huggingface (gitignored).
# Corpus: paper_claude_pack/corpus/md
# Outputs: evidence/rag_results/query_formulation_sensitivity/historical_chunk_grid_minilm/
set -euo pipefail
PACK="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PACK"
export HF_HOME="$PACK/.cache/huggingface"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export HF_HUB_ENDPOINT="$HF_ENDPOINT"
export HUGGINGFACE_HUB_CACHE="$HF_HOME/hub"
export TRANSFORMERS_CACHE="$HF_HOME/transformers"
export SENTENCE_TRANSFORMERS_HOME="$HF_HOME/sentence-transformers"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

PY="$PACK/.venv/bin/python"
OUT_ROOT="$PACK/evidence/rag_results/query_formulation_sensitivity/historical_chunk_grid_minilm"
mkdir -p "$OUT_ROOT"
LOG="$OUT_ROOT/run.log"

"$PY" paper/scripts/run_query_formulation_old_chunk_grid.py \
  --config 800:80 \
  --config 1200:120 \
  --config 1500:150 \
  --model sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 \
  --model sentence-transformers/all-MiniLM-L6-v2 \
  --device cuda \
  --batch-size "${BATCH_SIZE:-64}" \
  "$@" 2>&1 | tee -a "$LOG"
