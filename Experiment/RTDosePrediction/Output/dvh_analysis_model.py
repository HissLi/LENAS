#!/usr/bin/env python
"""Test-set evaluation + per-patient DVH curves for one model.

This is the model-agnostic version of `Output/NAS_29/dvh_analysis.py`. For
every test patient (241-340) it:
  * recomputes the dose MAE and the OpenKBP DVH metrics (same definitions as
    `<model>/evaluate.py`),
  * writes per-patient and per-structure metric CSVs,
  * draws a DVH figure for that patient (GT vs prediction, all structures),
  * collects all figures into one multi-page PDF and draws mean DVH curves.

Usage:
    python dvh_analysis_model.py --model NAS_37 \
        --output-dir Experiment/RTDosePrediction/Output/NAS_37

Outputs live in:
  <output-dir>/Evaluation/   CSVs + EVALUATION.md
  <output-dir>/DVH/          pt_XXX_dvh.png, all_patients_dvh.pdf,
                             mean_dvh_per_structure.png, dvh_curves.npz
"""

import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import SimpleITK as sitk
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D

DATA_DIR = "/home/zihanli/project/LENAS/Data/RTDosePrediction/OpenKBP_C3D"
PATIENTS = [f"pt_{i}" for i in range(241, 341)]

# (structure, mode) in the same order as <model>/evaluate.py
STRUCTS = [
    ("Brainstem", "OAR"),
    ("SpinalCord", "OAR"),
    ("RightParotid", "OAR"),
    ("LeftParotid", "OAR"),
    ("Esophagus", "OAR"),
    ("Larynx", "OAR"),
    ("Mandible", "OAR"),
    ("PTV70", "target"),
    ("PTV63", "target"),
    ("PTV56", "target"),
]

# Panels are ordered for a readable figure: targets first, then OARs.
PANEL_ORDER = [
    ("PTV70", "target"),
    ("PTV63", "target"),
    ("PTV56", "target"),
    ("Brainstem", "OAR"),
    ("SpinalCord", "OAR"),
    ("RightParotid", "OAR"),
    ("LeftParotid", "OAR"),
    ("Esophagus", "OAR"),
    ("Larynx", "OAR"),
    ("Mandible", "OAR"),
]

COLORS = {
    "PTV70": "#d62728",
    "PTV63": "#ff7f0e",
    "PTV56": "#bcbd22",
    "Brainstem": "#2ca02c",
    "SpinalCord": "#17becf",
    "RightParotid": "#1f77b4",
    "LeftParotid": "#9467bd",
    "Esophagus": "#8c564b",
    "Larynx": "#e377c2",
    "Mandible": "#7f7f7f",
}

GRID = np.arange(0.0, 100.0 + 0.001, 0.25)  # Gy


def read_array(path, dtype=None):
    img = sitk.ReadImage(path) if dtype is None else sitk.ReadImage(path, dtype)
    return img, sitk.GetArrayFromImage(img)


def cumulative_dvh(dose, mask, grid=GRID):
    """Volume (%) receiving at least the dose in `grid`."""
    vals = np.sort(dose[mask > 0].astype(np.float64))
    n = vals.size
    if n == 0:
        return None
    idx = np.searchsorted(vals, grid, side="left")
    return 100.0 * (n - idx) / n


def dvh_metrics(dose, mask, mode, spacing):
    """Exact copy of <model>/evaluate.py:get_DVH_metrics."""
    roi_dose = dose[mask > 0]
    if mode == "target":
        return {
            "D1": float(np.percentile(roi_dose, 99)),
            "D95": float(np.percentile(roi_dose, 5)),
            "D99": float(np.percentile(roi_dose, 1)),
        }
    roi_size = len(roi_dose)
    voxel_size = np.prod(spacing)
    voxels_in_tenth_of_cc = np.maximum(1, np.round(100 / voxel_size))
    fractional_volume = 100 - voxels_in_tenth_of_cc / roi_size * 100
    return {
        "D_0.1_cc": float(np.percentile(roi_dose, fractional_volume)),
        "mean": float(np.mean(roi_dose)),
    }


def make_patient_figure(model, patient_id, dose_mae, mean_dvh_diff, patient_data):
    fig, axes = plt.subplots(2, 5, figsize=(20, 8.5), constrained_layout=True)
    for ax, (structure, mode) in zip(axes.flat, PANEL_ORDER):
        item = patient_data.get(structure)
        if item is None:
            ax.axis("off")
            ax.text(0.5, 0.5, f"{structure}\nnot delineated",
                    ha="center", va="center", fontsize=10, color="0.5")
            continue

        color = COLORS[structure]
        ax.plot(GRID, item["gt_curve"], color=color, lw=2.0, label="GT")
        ax.plot(GRID, item["pred_curve"], color=color, lw=2.0, ls="--", label="Prediction")
        ax.set_xlim(0, 85)
        ax.set_ylim(0, 102)
        ax.set_xlabel("Dose (Gy)", fontsize=9)
        ax.set_ylabel("Volume (%)", fontsize=9)
        ax.tick_params(labelsize=8)
        ax.grid(alpha=0.3)
        ax.set_title(f"{structure}  ({item['volume_cc']:.1f} cc)", fontsize=11)

    handles = [
        Line2D([0], [0], color="k", lw=2.0, label="Ground truth"),
        Line2D([0], [0], color="k", lw=2.0, ls="--", label=f"{model} prediction"),
    ]
    fig.legend(handles=handles, loc="upper right", ncol=2, fontsize=11)
    fig.suptitle(
        f"{model} — {patient_id} — dose MAE {dose_mae:.2f} Gy — mean |ΔDVH| {mean_dvh_diff:.2f}",
        fontsize=15,
    )
    return fig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="Model name, e.g. NAS_37")
    ap.add_argument("--output-dir", required=True,
                    help="Experiment output directory for this model")
    ap.add_argument("--pred-dir", default=None,
                    help="Prediction dir (default: <output-dir>/Prediction)")
    ap.add_argument("--data-dir", default=DATA_DIR)
    args = ap.parse_args()

    model = args.model
    out_dir = os.path.abspath(args.output_dir)
    pred_dir = args.pred_dir or os.path.join(out_dir, "Prediction")
    eval_dir = os.path.join(out_dir, "Evaluation")
    dvh_dir = os.path.join(out_dir, "DVH")
    data_dir = args.data_dir

    os.makedirs(eval_dir, exist_ok=True)
    os.makedirs(dvh_dir, exist_ok=True)

    per_patient = []
    per_structure = []
    all_dvh_diffs = []
    mean_curves = {s: {"gt": [], "pred": []} for s, _ in PANEL_ORDER}
    curves_npz = {"grid": GRID}

    pdf_path = os.path.join(dvh_dir, "all_patients_dvh.pdf")

    with PdfPages(pdf_path) as pdf:
        for patient_id in PATIENTS:
            gt_path = os.path.join(data_dir, patient_id)
            pred_path = os.path.join(pred_dir, patient_id)

            if not os.path.isdir(pred_path):
                print(f"[skip] missing prediction: {patient_id}")
                continue

            _, gt_dose = read_array(os.path.join(gt_path, "dose.nii.gz"))
            _, pred_dose = read_array(os.path.join(pred_path, "dose.nii.gz"))
            _, possible = read_array(os.path.join(gt_path, "possible_dose_mask.nii.gz"))

            gt_dose = gt_dose.astype(np.float64)
            pred_dose = pred_dose.astype(np.float64)
            if gt_dose.shape != pred_dose.shape:
                raise RuntimeError(f"shape mismatch for {patient_id}")

            mask_possible = possible > 0
            dose_mae = float(np.mean(np.abs(pred_dose[mask_possible] - gt_dose[mask_possible])))

            patient_data = {}
            patient_diffs = []

            for structure, mode in STRUCTS:
                struct_path = os.path.join(gt_path, structure + ".nii.gz")
                if not os.path.exists(struct_path):
                    continue

                img, struct = read_array(struct_path, sitk.sitkUInt8)
                mask = struct > 0
                if not mask.any():
                    continue
                spacing = img.GetSpacing()
                volume_cc = float(mask.sum() * np.prod(spacing) / 1000.0)

                gt_metrics = dvh_metrics(gt_dose, mask, mode, spacing)
                pr_metrics = dvh_metrics(pred_dose, mask, mode, spacing)

                for metric, gt_val in gt_metrics.items():
                    pr_val = pr_metrics[metric]
                    diff = abs(gt_val - pr_val)
                    all_dvh_diffs.append(diff)
                    patient_diffs.append(diff)
                    per_structure.append({
                        "patient": patient_id,
                        "structure": structure,
                        "mode": mode,
                        "volume_cc": volume_cc,
                        "metric": metric,
                        "gt": gt_val,
                        "pred": pr_val,
                        "abs_diff": diff,
                    })

                gt_curve = cumulative_dvh(gt_dose, mask)
                pred_curve = cumulative_dvh(pred_dose, mask)
                if gt_curve is None:
                    continue

                patient_data[structure] = {
                    "volume_cc": volume_cc,
                    "gt_curve": gt_curve,
                    "pred_curve": pred_curve,
                    "gt_metrics": gt_metrics,
                    "pred_metrics": pr_metrics,
                }
                mean_curves[structure]["gt"].append(gt_curve)
                mean_curves[structure]["pred"].append(pred_curve)
                curves_npz[f"{patient_id}|{structure}|gt"] = gt_curve.astype(np.float32)
                curves_npz[f"{patient_id}|{structure}|pred"] = pred_curve.astype(np.float32)

            mean_patient_dvh = float(np.mean(patient_diffs)) if patient_diffs else float("nan")
            per_patient.append({
                "patient": patient_id,
                "dose_mae": dose_mae,
                "n_structures": len(patient_data),
                "mean_abs_dvh_diff": mean_patient_dvh,
            })

            fig = make_patient_figure(model, patient_id, dose_mae, mean_patient_dvh,
                                      patient_data)
            fig.savefig(os.path.join(dvh_dir, f"{patient_id}_dvh.png"), dpi=120)
            pdf.savefig(fig)
            plt.close(fig)
            print(f"[done] {patient_id}: dose MAE {dose_mae:.3f} Gy, "
                  f"mean |ΔDVH| {mean_patient_dvh:.3f}")

        # Mean DVH per structure across all test patients
        fig, axes = plt.subplots(2, 5, figsize=(20, 8.5), constrained_layout=True)
        for ax, (structure, _) in zip(axes.flat, PANEL_ORDER):
            gt_list = mean_curves[structure]["gt"]
            pred_list = mean_curves[structure]["pred"]
            if not gt_list:
                ax.axis("off")
                continue
            color = COLORS[structure]
            ax.plot(GRID, np.mean(gt_list, axis=0), color=color, lw=2.2, label="GT mean")
            ax.plot(GRID, np.mean(pred_list, axis=0), color=color, lw=2.2, ls="--",
                    label="Pred mean")
            ax.set_xlim(0, 85)
            ax.set_ylim(0, 102)
            ax.set_xlabel("Dose (Gy)", fontsize=9)
            ax.set_ylabel("Volume (%)", fontsize=9)
            ax.tick_params(labelsize=8)
            ax.grid(alpha=0.3)
            ax.set_title(f"{structure}  (n={len(gt_list)})", fontsize=11)
        handles = [
            Line2D([0], [0], color="k", lw=2.2, label="GT mean"),
            Line2D([0], [0], color="k", lw=2.2, ls="--", label="Prediction mean"),
        ]
        fig.legend(handles=handles, loc="upper right", ncol=2, fontsize=11)
        fig.suptitle(f"{model} — mean DVH curves over test patients (241–340)", fontsize=15)
        mean_png = os.path.join(dvh_dir, "mean_dvh_per_structure.png")
        fig.savefig(mean_png, dpi=150)
        pdf.savefig(fig)
        plt.close(fig)

    # ------------------------- CSV outputs -------------------------
    pp_path = os.path.join(eval_dir, "per_patient_metrics.csv")
    with open(pp_path, "w") as f:
        f.write("patient,dose_mae,n_structures,mean_abs_dvh_diff\n")
        for r in per_patient:
            f.write(f"{r['patient']},{r['dose_mae']:.6f},{r['n_structures']},"
                    f"{r['mean_abs_dvh_diff']:.6f}\n")

    ps_path = os.path.join(eval_dir, "per_structure_metrics.csv")
    with open(ps_path, "w") as f:
        f.write("patient,structure,mode,volume_cc,metric,gt,pred,abs_diff\n")
        for r in per_structure:
            f.write(f"{r['patient']},{r['structure']},{r['mode']},{r['volume_cc']:.3f},"
                    f"{r['metric']},{r['gt']:.6f},{r['pred']:.6f},{r['abs_diff']:.6f}\n")

    np.savez_compressed(os.path.join(dvh_dir, "dvh_curves.npz"), **curves_npz)

    # ------------------------- summary -------------------------
    dose_scores = np.array([r["dose_mae"] for r in per_patient])
    dvh_arr = np.array(all_dvh_diffs)
    dose_mean, dose_std = float(dose_scores.mean()), float(dose_scores.std())
    dvh_mean, dvh_std = float(dvh_arr.mean()), float(dvh_arr.std())

    # per structure / metric summary
    keys = sorted({(r["structure"], r["metric"]) for r in per_structure},
                  key=lambda k: ([s for s, _ in PANEL_ORDER].index(k[0]), k[1]))
    summary_rows = []
    for structure, metric in keys:
        rows = [r for r in per_structure if r["structure"] == structure and r["metric"] == metric]
        summary_rows.append({
            "structure": structure,
            "metric": metric,
            "n": len(rows),
            "gt_mean": float(np.mean([r["gt"] for r in rows])),
            "pred_mean": float(np.mean([r["pred"] for r in rows])),
            "abs_diff_mean": float(np.mean([r["abs_diff"] for r in rows])),
        })

    lines = []
    lines.append(f"# {model} — test-set evaluation and DVH analysis\n")
    lines.append("Generated by `dvh_analysis_model.py`.\n")
    lines.append("| Item | Value |\n|---|---|")
    lines.append(f"| Test patients | 241–340 ({len(per_patient)} patients) |")
    lines.append(f"| Prediction dir | `{pred_dir}` |")
    lines.append("| Checkpoint | `best_val_evaluation_index.pkl` |")
    lines.append("| **Dose score (mean MAE)** | **{:.6f} ± {:.6f} Gy** |".format(dose_mean, dose_std))
    lines.append(f"| **DVH score (mean abs diff)** | **{dvh_mean:.6f} ± {dvh_std:.6f}** |")
    lines.append(f"| DVH metric entries | {len(dvh_arr)} |")
    lines.append("")
    lines.append("## Per-structure / per-metric summary\n")
    lines.append("| Structure | Metric | n | GT mean | Pred mean | Mean abs diff |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for r in summary_rows:
        lines.append("| {structure} | {metric} | {n} | {gt_mean:.4f} | {pred_mean:.4f} | "
                     "{abs_diff_mean:.4f} |".format(**r))
    lines.append("")
    lines.append("## Best / worst patients by dose MAE\n")
    best = sorted(per_patient, key=lambda r: r["dose_mae"])[:5]
    worst = sorted(per_patient, key=lambda r: r["dose_mae"], reverse=True)[:5]
    lines.append("| Rank | Best patient | Dose MAE (Gy) | Worst patient | Dose MAE (Gy) |")
    lines.append("|---:|---|---:|---|---:|")
    for i in range(5):
        lines.append(f"| {i+1} | {best[i]['patient']} | {best[i]['dose_mae']:.4f} | "
                     f"{worst[i]['patient']} | {worst[i]['dose_mae']:.4f} |")
    lines.append("")
    lines.append("## Files\n")
    lines.append("- `per_patient_metrics.csv` — dose MAE and mean DVH difference per patient")
    lines.append("- `per_structure_metrics.csv` — every DVH metric per patient/structure")
    lines.append("- `../DVH/pt_XXX_dvh.png` — one DVH figure per test patient (100 figures)")
    lines.append("- `../DVH/all_patients_dvh.pdf` — all figures in one multi-page PDF")
    lines.append("- `../DVH/mean_dvh_per_structure.png` — mean GT/prediction DVH per structure")
    lines.append("- `../DVH/dvh_curves.npz` — raw DVH curves (0.25 Gy grid)")
    lines.append("")
    lines.append("## Notes\n")
    lines.append(f"- Metric definitions are identical to `{model}/evaluate.py`: D1/D95/D99 for "
                 "targets, D_0.1cc/Dmean for OARs; the DVH score is the mean absolute difference "
                 "over all structure-metric entries.")
    lines.append("- The predicted and GT doses are compared on the same structure masks from the "
                 "ground-truth NIfTI files; TTA was enabled during inference.")

    md_path = os.path.join(eval_dir, "EVALUATION.md")
    with open(md_path, "w") as f:
        f.write("\n".join(lines))

    print("\n================ SUMMARY ================")
    print(f"patients: {len(per_patient)}")
    print(f"dose score (MAE): {dose_mean:.6f} ± {dose_std:.6f}")
    print(f"DVH score (MAE):  {dvh_mean:.6f} ± {dvh_std:.6f}")
    print(f"metric entries:   {len(dvh_arr)}")
    print(f"figures:          {len(per_patient)} PNG + 1 PDF")
    print(f"output:           {eval_dir}")
    print(f"                  {dvh_dir}")


if __name__ == "__main__":
    main()
