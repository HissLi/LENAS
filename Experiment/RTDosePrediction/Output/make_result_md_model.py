#!/usr/bin/env python
"""Build result.md for one model from Evaluation/*.csv and DVH/*.png.

Usage:
    python make_result_md_model.py --model NAS_37 --params 13195493 \
        --output-dir Experiment/RTDosePrediction/Output/NAS_37
"""

import argparse
import collections
import csv
import os

import numpy as np

ORDER = ["PTV70", "PTV63", "PTV56", "Brainstem", "SpinalCord", "RightParotid",
         "LeftParotid", "Esophagus", "Larynx", "Mandible"]

TRAIN_CONFIG = [
    ("Batch size", "2"),
    ("Iterations", "80,000"),
    ("Iterations / epoch", "500 (batch_size × 500 samples)"),
    ("Epochs", "160"),
    ("Optimizer", "Adam"),
    ("Learning rate", "3e-4, cosine decay to 1e-7"),
    ("Weight decay", "3e-5 effective"),
    ("Loss", "masked L1 on dose / 70"),
    ("Validation", "dose MAE on patients 201–240"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--params", required=True, type=int,
                    help="Parameter count (commas added automatically)")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--arch-desc", default="searched U-NAS architecture")
    ap.add_argument("--checkpoint", default="best_val_evaluation_index.pkl")
    args = ap.parse_args()

    model = args.model
    params = f"{args.params:,}"
    out_dir = os.path.abspath(args.output_dir)
    ps_path = os.path.join(out_dir, "Evaluation", "per_structure_metrics.csv")
    pp_path = os.path.join(out_dir, "Evaluation", "per_patient_metrics.csv")
    md_path = os.path.join(out_dir, "result.md")

    pp = list(csv.DictReader(open(pp_path)))
    ps = list(csv.DictReader(open(ps_path)))
    by_patient = collections.defaultdict(list)
    for r in ps:
        by_patient[r["patient"]].append(r)

    keys = sorted({(r["structure"], r["metric"]) for r in ps},
                  key=lambda k: (ORDER.index(k[0]), k[1]))

    dose = np.array([float(r["dose_mae"]) for r in pp])
    all_diffs = np.array([float(r["abs_diff"]) for r in ps])
    best = sorted(pp, key=lambda r: float(r["mean_abs_dvh_diff"]))[:3]
    worst = sorted(pp, key=lambda r: float(r["mean_abs_dvh_diff"]), reverse=True)[:3]

    L = []
    L.append(f"# {model} — test-set results and DVH curves\n")
    L.append(f"Model: `{model}` ({args.arch_desc}, {params} parameters)  ")
    L.append(f"Checkpoint: `{args.checkpoint}`  ")
    L.append("Test split: OpenKBP patients **241–340** (100 patients)  ")
    L.append("Inference: `python test.py --GPU_id 0 --TTA True`, TTA enabled "
             "(4 flips averaged)  ")
    L.append("Metric definitions: same as `evaluate.py` (D1/D95/D99 for targets, "
             "D_0.1cc/mean for OARs; DVH score = mean absolute difference over all "
             "structure-metric entries).\n")

    L.append("## Training configuration\n")
    L.append("| Item | Value |")
    L.append("|---|---|")
    for k, v in TRAIN_CONFIG:
        L.append(f"| {k} | {v} |")
    L.append("")

    L.append("## Test-set scores\n")
    L.append("| Metric | Value |")
    L.append("|---|---:|")
    L.append(f"| **Dose score (mean MAE)** | **{dose.mean():.6f} ± {dose.std():.6f} Gy** |")
    L.append(f"| **DVH score (mean absolute difference)** | **{all_diffs.mean():.6f} ± "
             f"{all_diffs.std():.6f}** |")
    L.append(f"| Patients | {len(pp)} |")
    L.append(f"| DVH metric entries | {len(ps)} |")
    L.append("")

    L.append("## Per-structure test scores\n")
    L.append("| Structure | Metric | n | GT mean | Pred mean | Mean abs diff |")
    L.append("|---|---|---:|---:|---:|---:|")
    for structure, metric in keys:
        rows = [r for r in ps if r["structure"] == structure and r["metric"] == metric]
        g = np.mean([float(r["gt"]) for r in rows])
        p = np.mean([float(r["pred"]) for r in rows])
        d = np.mean([float(r["abs_diff"]) for r in rows])
        L.append(f"| {structure} | {metric} | {len(rows)} | {g:.4f} | {p:.4f} | {d:.4f} |")
    L.append("")
    L.append("Ranking for the patient-level DVH curves below: **mean absolute DVH metric "
             "difference** across all delineated structures (lower is better).\n")

    def section(title, rows, prefix):
        L.append(f"## {title}\n")
        L.append("| Rank | Patient | Dose MAE (Gy) | Mean abs DVH diff | Structures | "
                 "Largest metric error |")
        L.append("|---:|---|---:|---:|---:|---|")
        for i, r in enumerate(rows, 1):
            items = by_patient[r["patient"]]
            top = max(items, key=lambda x: float(x["abs_diff"]))
            L.append(f"| {i} | {r['patient']} | {float(r['dose_mae']):.4f} | "
                     f"{float(r['mean_abs_dvh_diff']):.4f} | {r['n_structures']} | "
                     f"{top['structure']} {top['metric']} "
                     f"({float(top['abs_diff']):.3f} Gy) |")
        L.append("")
        for i, r in enumerate(rows, 1):
            pid = r["patient"]
            L.append(f"### {prefix}{i}: {pid}\n")
            L.append(f"Dose MAE **{float(r['dose_mae']):.4f} Gy**, "
                     f"mean absolute DVH difference **{float(r['mean_abs_dvh_diff']):.4f}**.\n")
            items = sorted(by_patient[pid], key=lambda x: float(x["abs_diff"]),
                           reverse=True)[:3]
            L.append("| Structure | Metric | GT | Prediction | Abs diff |")
            L.append("|---|---|---:|---:|---:|")
            for x in items:
                L.append(f"| {x['structure']} | {x['metric']} | {float(x['gt']):.3f} | "
                         f"{float(x['pred']):.3f} | {float(x['abs_diff']):.3f} |")
            L.append("")
            L.append(f"![{pid} DVH](DVH/{pid}_dvh.png)\n")
            L.append(f"<sub>Solid = ground truth, dashed = {model} prediction. "
                     f"Full figure: `DVH/{pid}_dvh.png`.</sub>\n")

    section("Best 3 patients by DVH agreement", best, "Best ")
    section("Worst 3 patients by DVH agreement", worst, "Worst ")

    L.append("## All outputs\n")
    L.append("- `Evaluation/EVALUATION.md` — full evaluation report")
    L.append(f"- `Evaluation/per_patient_metrics.csv` — {len(pp)} rows")
    L.append(f"- `Evaluation/per_structure_metrics.csv` — {len(ps)} metric rows")
    L.append("- `Evaluation/ci_hi_metrics.csv` — PTV conformity/homogeneity raw values")
    L.append("- `DVH/pt_241_dvh.png` … `DVH/pt_340_dvh.png` — one DVH figure per test patient")
    L.append("- `DVH/all_patients_dvh.pdf` — multi-page PDF with the mean summary")
    L.append("- `DVH/mean_dvh_per_structure.png` — mean GT/prediction DVH per structure")
    L.append("- `DVH/dvh_curves.npz` — raw curves on a 0.25 Gy grid")

    with open(md_path, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"wrote {md_path}")


if __name__ == "__main__":
    main()
