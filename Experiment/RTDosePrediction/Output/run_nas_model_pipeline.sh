#!/bin/bash
# Train one searched NAS model on OpenKBP, then run inference, evaluation,
# DVH figures and result.md — the same artifact set as NAS_29 / Unet.
#
# Usage: bash run_nas_model_pipeline.sh NAS_37
set -euo pipefail

REPO=/home/zihanli/project/LENAS
MODEL=${1:?usage: run_nas_model_pipeline.sh MODEL}
PY=/home/zihanli/anaconda3/envs/lenas/bin/python
OUT="$REPO/Experiment/RTDosePrediction/Output/$MODEL"

case "$MODEL" in
  NAS_37) PARAMS=13195493 ;;
  NAS_42) PARAMS=10947337 ;;
  NAS_35) PARAMS=8392937 ;;
  *) echo "ERROR: unsupported model '$MODEL'" >&2; exit 2 ;;
esac

export PATH="$(dirname "$PY"):$PATH"
mkdir -p "$OUT"

finish() {
    rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "FAILED rc=$rc at $(date -Is)" > "$OUT/pipeline.status"
    fi
    exit "$rc"
}
trap finish EXIT

cd "$REPO/RTDosePrediction/$MODEL"

echo "START $MODEL $(date -Is)" > "$OUT/pipeline.status"
echo "$(date -Is)" > "$OUT/train_start.txt"

"$PY" geno.py > "$OUT/geno.log" 2>&1

"$PY" train.py --batch_size 2 --list_GPU_ids 0 --max_iter 80000 \
    > "$OUT/train_stdout.log" 2>&1
echo "$(date -Is)" > "$OUT/train_end.txt"
echo "TRAIN_DONE $MODEL $(date -Is)" > "$OUT/pipeline.status"

"$PY" test.py --GPU_id 0 --TTA True > "$OUT/test_stdout.log" 2>&1
echo "TEST_DONE $MODEL $(date -Is)" > "$OUT/pipeline.status"

"$PY" "$REPO/Experiment/RTDosePrediction/Output/dvh_analysis_model.py" \
    --model "$MODEL" --output-dir "$OUT" > "$OUT/analysis.log" 2>&1
echo "ANALYSIS_DONE $MODEL $(date -Is)" > "$OUT/pipeline.status"

"$PY" "$REPO/Experiment/RTDosePrediction/Output/make_result_md_model.py" \
    --model "$MODEL" --params "$PARAMS" --output-dir "$OUT" > "$OUT/result_md.log" 2>&1

"$PY" "$REPO/Experiment/RTDosePrediction/Output/ci_hi_analysis.py" \
    --output-dir "$OUT" --model "$MODEL" >> "$OUT/analysis.log" 2>&1

"$PY" "$REPO/Experiment/RTDosePrediction/Output/per_patient_table.py" \
    --output-dir "$OUT" >> "$OUT/analysis.log" 2>&1

"$PY" "$REPO/Experiment/RTDosePrediction/Output/dvh_single_axes.py" \
    --output-dir "$OUT" --model "$MODEL" >> "$OUT/analysis.log" 2>&1
echo "DVH_DONE $MODEL $(date -Is)" > "$OUT/pipeline.status"

"$PY" "$REPO/Experiment/RTDosePrediction/Output/write_config_md.py" \
    --model "$MODEL" --params "$PARAMS" --output-dir "$OUT" >> "$OUT/analysis.log" 2>&1

echo "DONE $MODEL $(date -Is)" > "$OUT/pipeline.status"
