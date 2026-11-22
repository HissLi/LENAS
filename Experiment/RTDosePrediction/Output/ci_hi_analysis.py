#!/usr/bin/env python
"""Compute PTV conformity and homogeneity indices for one model.

Definitions
-----------
Paddick Conformity Index (CI):
    CI = (TV_PIV)^2 / (TV * PIV)
    TV     = PTV volume (voxels)
    PIV    = prescription isodose volume (all voxels with dose >= Rx)
    TV_PIV = PTV voxels receiving >= Rx
    1.0 is ideal; higher is better.

ICRU-83 Homogeneity Index (HI):
    HI = (D2 - D98) / D50
    D2  = 98th percentile dose in the PTV
    D98 = 2nd percentile dose in the PTV
    D50 = median dose in the PTV
    0 is ideal; lower is better.

Prescription doses: PTV70=70 Gy, PTV63=63 Gy, PTV56=56 Gy.
"""

import argparse
import csv
import os

import numpy as np
import SimpleITK as sitk

DATA_DIR = "/home/zihanli/project/LENAS/Data/RTDosePrediction/OpenKBP_C3D"
PATIENTS = [f"pt_{i}" for i in range(241, 341)]
PTVS = [("PTV70", 70.0), ("PTV63", 63.0), ("PTV56", 56.0)]


def read(path, dtype=None):
    img = sitk.ReadImage(path) if dtype is None else sitk.ReadImage(path, dtype)
    return sitk.GetArrayFromImage(img)


def indices(dose, mask, rx):
    vals = dose[mask > 0].astype(np.float64)
    tv = int(vals.size)
    if tv == 0:
        return None
    tv_piv = int((vals >= rx).sum())
    piv = int((dose >= rx).sum())
    coverage = tv_piv / tv
    # PIV == 0 means no voxel reaches the prescription dose: conformity is 0,
    # not undefined, so that failed coverage is not silently dropped.
    ci_paddick = (tv_piv ** 2) / (tv * piv) if piv > 0 else 0.0
    ci_rtog = piv / tv
    d2 = float(np.percentile(vals, 98))
    d98 = float(np.percentile(vals, 2))
    d50 = float(np.percentile(vals, 50))
    hi = (d2 - d98) / d50 if d50 > 0 else np.nan
    return {
        "tv": tv, "piv": piv, "tv_piv": tv_piv, "coverage": coverage,
        "ci_paddick": float(ci_paddick), "ci_rtog": float(ci_rtog),
        "d2": d2, "d98": d98, "d50": d50, "hi": float(hi),
    }


def mean_std(vals):
    arr = np.asarray([v for v in vals if np.isfinite(v)], dtype=float)
    if arr.size == 0:
        return float("nan"), float("nan"), 0
    return float(arr.mean()), float(arr.std()), int(arr.size)


def update_result_md(md_path, model, summary, n_total):
    block = []
    block.append("<!-- CI_HI_START -->")
    block.append("## Conformity and homogeneity indices (PTV)\n")
    block.append("Computed on the test patients 241–340, using the ground-truth PTV masks "
                 "and the predicted / reference dose volumes.\n")
    block.append("**Definitions**\n")
    block.append("- **Conformity Index (Paddick):** `CI = TV_PIV² / (TV × PIV)`, where "
                 "`PIV` is the prescription-isodose volume and `TV_PIV` is the PTV volume "
                 "receiving at least the prescription dose. Range 0–1, **higher is better**, "
                 "1 = ideal.")
    block.append("- **Homogeneity Index (ICRU-83):** `HI = (D2 − D98) / D50` inside the PTV. "
                 "**Lower is better**, 0 = ideal.")
    block.append("- Prescriptions: PTV70 = 70 Gy, PTV63 = 63 Gy, PTV56 = 56 Gy.")
    block.append("- If no voxel reaches the prescription dose (`PIV = 0`), CI is reported as "
                 "**0** (failed coverage) rather than undefined.")
    block.append("- PTV63/PTV56 are nested with the higher-dose targets, so their Paddick CI "
                 "is intrinsically lower: the prescription isodose volume includes the boost "
                 "region. **PTV70 is the most directly interpretable target-conformity value.**\n")
    block.append("| PTV | n | CI pred | CI GT | HI pred | HI GT |")
    block.append("|---|---:|---:|---:|---:|---:|")
    for ptv, _ in PTVS:
        pred = summary[("pred", ptv)]
        gt = summary[("gt", ptv)]
        block.append(
            f"| {ptv} | {pred['n']} | {pred['ci_mean']:.4f} ± {pred['ci_std']:.4f} | "
            f"{gt['ci_mean']:.4f} ± {gt['ci_std']:.4f} | "
            f"{pred['hi_mean']:.4f} ± {pred['hi_std']:.4f} | "
            f"{gt['hi_mean']:.4f} ± {gt['hi_std']:.4f} |")
    pred = summary[("pred", "all")]
    gt = summary[("gt", "all")]
    block.append(
        f"| **Overall** | **{n_total}** | **{pred['ci_mean']:.4f} ± {pred['ci_std']:.4f}** | "
        f"**{gt['ci_mean']:.4f} ± {gt['ci_std']:.4f}** | "
        f"**{pred['hi_mean']:.4f} ± {pred['hi_std']:.4f}** | "
        f"**{gt['hi_mean']:.4f} ± {gt['hi_std']:.4f}** |")
    block.append("")
    block.append("The per-PTV raw values (including coverage, RTOG CI, D2/D98/D50) are in "
                 "`Evaluation/ci_hi_metrics.csv`.")
    block.append("<!-- CI_HI_END -->")
    block = "\n".join(block)

    text = open(md_path).read()
    start = text.find("<!-- CI_HI_START -->")
    end = text.find("<!-- CI_HI_END -->")
    if start != -1 and end != -1:
        text = text[:start] + block + text[end + len("<!-- CI_HI_END -->"):]
    else:
        marker = "## All outputs"
        if marker in text:
            text = text.replace(marker, block + "\n\n" + marker, 1)
        else:
            text = text.rstrip() + "\n\n" + block + "\n"
    open(md_path, "w").write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--model", required=True)
    args = ap.parse_args()

    out = args.output_dir
    csv_path = os.path.join(out, "Evaluation", "ci_hi_metrics.csv")
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    rows = []
    for pid in PATIENTS:
        gt_dir = os.path.join(DATA_DIR, pid)
        pred_path = os.path.join(out, "Prediction", pid, "dose.nii.gz")
        if not os.path.exists(pred_path):
            continue
        gt_dose = read(os.path.join(gt_dir, "dose.nii.gz")).astype(np.float64)
        pred_dose = read(pred_path).astype(np.float64)

        for ptv, rx in PTVS:
            mask_path = os.path.join(gt_dir, ptv + ".nii.gz")
            if not os.path.exists(mask_path):
                continue
            mask = read(mask_path, sitk.sitkUInt8)
            if not (mask > 0).any():
                continue
            for source, dose in [("gt", gt_dose), ("pred", pred_dose)]:
                r = indices(dose, mask, rx)
                if r is None:
                    continue
                rows.append({
                    "model": args.model, "patient": pid, "ptv": ptv,
                    "prescription_gy": rx, "source": source, **r,
                })

    cols = ["model", "patient", "ptv", "prescription_gy", "source",
            "tv", "piv", "tv_piv", "coverage", "ci_paddick", "ci_rtog",
            "d2", "d98", "d50", "hi"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{r[k]:.6f}" if isinstance(r[k], float) else r[k]) for k in cols})

    # aggregate
    summary = {}
    for source in ["pred", "gt"]:
        for ptv, _ in PTVS:
            sub = [r for r in rows if r["source"] == source and r["ptv"] == ptv]
            ci_mean, ci_std, n = mean_std([r["ci_paddick"] for r in sub])
            hi_mean, hi_std, _ = mean_std([r["hi"] for r in sub])
            summary[(source, ptv)] = dict(ci_mean=ci_mean, ci_std=ci_std,
                                          hi_mean=hi_mean, hi_std=hi_std, n=n)
        sub = [r for r in rows if r["source"] == source]
        ci_mean, ci_std, n = mean_std([r["ci_paddick"] for r in sub])
        hi_mean, hi_std, _ = mean_std([r["hi"] for r in sub])
        summary[(source, "all")] = dict(ci_mean=ci_mean, ci_std=ci_std,
                                        hi_mean=hi_mean, hi_std=hi_std, n=n)

    md_path = os.path.join(out, "result.md")
    update_result_md(md_path, args.model, summary, summary[("pred", "all")]["n"])

    print(f"=== {args.model} ===")
    for source in ["pred", "gt"]:
        for ptv, _ in PTVS:
            s = summary[(source, ptv)]
            print(f"{source:4s} {ptv}: n={s['n']:3d} "
                  f"CI={s['ci_mean']:.4f}±{s['ci_std']:.4f} "
                  f"HI={s['hi_mean']:.4f}±{s['hi_std']:.4f}")
        s = summary[(source, "all")]
        print(f"{source:4s} ALL : n={s['n']:3d} "
              f"CI={s['ci_mean']:.4f}±{s['ci_std']:.4f} "
              f"HI={s['hi_mean']:.4f}±{s['hi_std']:.4f}")
    print(f"CSV: {csv_path}")
    print(f"updated: {md_path}")


if __name__ == "__main__":
    main()
