#!/bin/bash
# Run NAS_37, NAS_42 and NAS_35 sequentially on OpenKBP, committing and
# pushing each model's result.md + DVH figures as soon as it finishes.
#
# Usage: bash run_all_nas.sh [branch]
set -euo pipefail

REPO=/home/zihanli/project/LENAS
BRANCH=${1:-exp/nas37-42-35-results}
OUT_BASE="$REPO/Experiment/RTDosePrediction/Output"
LOG="$OUT_BASE/run_all_nas.log"

{
  echo "=== run_all_nas start $(date -Is) branch=$BRANCH ==="
} >> "$LOG"

cd "$REPO"

for MODEL in NAS_37 NAS_42 NAS_35; do
  echo "=== $MODEL START $(date -Is) ===" | tee -a "$LOG"

  bash "$OUT_BASE/run_nas_model_pipeline.sh" "$MODEL" 2>&1 | tee -a "$LOG"

  echo "=== $MODEL pipeline done, committing $(date -Is) ===" | tee -a "$LOG"
  git add "$OUT_BASE/$MODEL" "RTDosePrediction/$MODEL/CONFIG.md" \
          "$OUT_BASE/dvh_analysis_model.py" "$OUT_BASE/make_result_md_model.py" \
          "$OUT_BASE/write_config_md.py" "$OUT_BASE/run_nas_model_pipeline.sh" \
          "$OUT_BASE/run_all_nas.sh"

  if git diff --cached --quiet; then
    echo "WARNING: nothing staged for $MODEL" | tee -a "$LOG"
  else
    git commit -m "Add $MODEL OpenKBP results: result.md, DVH figures, evaluation artifacts" \
         -m "Trained with the NAS_29/Unet protocol (OpenKBP, 80k iterations, TTA)."
    echo "=== $MODEL committed $(date -Is) ===" | tee -a "$LOG"
  fi

  pushed=0
  for attempt in 1 2 3; do
    if git push origin "$BRANCH"; then
      pushed=1
      break
    fi
    echo "push attempt $attempt failed for $MODEL; retrying in 30s" | tee -a "$LOG"
    sleep 30
  done
  if [ "$pushed" -ne 1 ]; then
    echo "ERROR: could not push $MODEL after 3 attempts" | tee -a "$LOG"
    exit 1
  fi
  echo "=== $MODEL PUSHED $(date -Is) ===" | tee -a "$LOG"
done

echo "=== run_all_nas DONE $(date -Is) ===" | tee -a "$LOG"
