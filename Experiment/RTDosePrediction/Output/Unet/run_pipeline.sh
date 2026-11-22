#!/bin/bash
# Train Unet, then inference -> evaluation -> DVH figures -> result.md.
set -euo pipefail

REPO=/home/zihanli/project/LENAS
OUT="$REPO/Experiment/RTDosePrediction/Output/Unet"
PY=/home/zihanli/anaconda3/envs/lenas/bin/python
# Unet/train.py calls torchviz, which needs the conda env's `dot` binary.
export PATH="$(dirname "$PY"):$PATH"
command -v dot >/dev/null || { echo "ERROR: graphviz dot not found on PATH" >&2; exit 1; }

mkdir -p "$OUT"
echo $$ > "$OUT/pipeline.pid"

cleanup() {
    rc=$?
    # train.py renders a graphviz diagram into the tracked Unet/model.pdf
    git -C "$REPO" checkout -- RTDosePrediction/Unet/model.pdf 2>/dev/null || true
    rm -f "$REPO/RTDosePrediction/Unet/model"
    rm -rf "$REPO/RTDosePrediction/Unet/wandb"
    if [ "$rc" -ne 0 ]; then
        echo "FAILED rc=$rc at $(date -Is)" > "$OUT/pipeline.status"
    fi
}
trap cleanup EXIT

cd "$REPO/RTDosePrediction/Unet"

echo "START $(date -Is)" > "$OUT/pipeline.status"

"$PY" train.py --batch_size 2 --list_GPU_ids 0 --max_iter 80000 \
    > "$OUT/train_stdout.log" 2>&1
echo "TRAIN_DONE $(date -Is)" > "$OUT/pipeline.status"

"$PY" test.py --GPU_id 0 --TTA True \
    > "$OUT/test_stdout.log" 2>&1
echo "TEST_DONE $(date -Is)" > "$OUT/pipeline.status"

"$PY" "$OUT/dvh_analysis.py" > "$OUT/analysis.log" 2>&1
echo "ANALYSIS_DONE $(date -Is)" > "$OUT/pipeline.status"

"$PY" "$OUT/make_result_md.py" > "$OUT/result_md.log" 2>&1
echo "DONE $(date -Is)" > "$OUT/pipeline.status"
