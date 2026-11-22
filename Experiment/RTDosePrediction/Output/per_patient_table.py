#!/usr/bin/env python
"""Append a 100-patient score table to result.md.

Columns: dose MAE, mean DVH difference, and prediction CI/HI for PTV70/63/56.
Reads Evaluation/per_patient_metrics.csv and Evaluation/ci_hi_metrics.csv.
"""
import argparse
import csv
import os

import numpy as np

PATIENTS = [f"pt_{i}" for i in range(241, 341)]
PTVS = ["PTV70", "PTV63", "PTV56"]


def load_per_patient(out_dir):
    path = os.path.join(out_dir, "Evaluation", "per_patient_metrics.csv")
    return {r["patient"]: r for r in csv.DictReader(open(path))}


def load_ci_hi(out_dir):
    path = os.path.join(out_dir, "Evaluation", "ci_hi_metrics.csv")
    rows = {}
    for r in csv.DictReader(open(path)):
        if r["source"] == "pred":
            rows[(r["patient"], r["ptv"])] = r
    return rows


def build_block(out_dir):
    pp = load_per_patient(out_dir)
    ci = load_ci_hi(out_dir)

    lines = []
    lines.append("<!-- PER_PATIENT_START -->")
    lines.append("## Per-patient test scores (100 patients)\n")
    lines.append("Dose = MAE within `possible_dose_mask` (Gy); DVH = mean absolute "
                 "difference over all structure-metric entries; CI = Paddick; "
                 "HI = ICRU-83. PTV70 is present for all 100 patients; PTV63/PTV56 are "
                 "shown where delineated (`—` otherwise).\n")
    lines.append("| Patient | Dose MAE (Gy) | DVH MAE | CI PTV70 | HI PTV70 | "
                 "CI PTV63 | HI PTV63 | CI PTV56 | HI PTV56 |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

    ci_values = {p: [] for p in PTVS}
    hi_values = {p: [] for p in PTVS}
    doses, dvhs = [], []

    for pid in PATIENTS:
        row = pp[pid]
        dose = float(row["dose_mae"])
        dvh = float(row["mean_abs_dvh_diff"])
        doses.append(dose)
        dvhs.append(dvh)
        cells = [pid, f"{dose:.4f}", f"{dvh:.4f}"]
        for ptv in PTVS:
            r = ci.get((pid, ptv))
            if r is None:
                cells += ["—", "—"]
            else:
                c = float(r["ci_paddick"])
                h = float(r["hi"])
                ci_values[ptv].append(c)
                hi_values[ptv].append(h)
                cells += [f"{c:.4f}", f"{h:.4f}"]
        lines.append("| " + " | ".join(cells) + " |")

    mean_cells = ["**Mean**", f"{np.mean(doses):.4f}", f"{np.mean(dvhs):.4f}"]
    for ptv in PTVS:
        mean_cells += [
            f"{np.mean(ci_values[ptv]):.4f}" if ci_values[ptv] else "—",
            f"{np.mean(hi_values[ptv]):.4f}" if hi_values[ptv] else "—",
        ]
    lines.append("| " + " | ".join(mean_cells) + " |")
    lines.append("")
    lines.append("Mean CI/HI for PTV63/PTV56 are over the patients where the structure is "
                 "delineated. Because PTV63/PTV56 are nested with higher-dose targets, their "
                 "Paddick CI is intrinsically lower; PTV70 is the primary conformity value.")
    lines.append("The Mean row is the unweighted average over the 100 patients; the official "
                 "DVH score in the test-set table above averages over all 1,783 "
                 "structure-metric entries, so it can differ slightly from the mean of the "
                 "per-patient DVH column.")
    lines.append("<!-- PER_PATIENT_END -->")
    return "\n".join(lines)


def update_md(md_path, block):
    text = open(md_path).read()
    start_marker = "<!-- PER_PATIENT_START -->"
    end_marker = "<!-- PER_PATIENT_END -->"
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start != -1 and end != -1:
        text = text[:start] + block + text[end + len(end_marker):]
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
    args = ap.parse_args()
    md = os.path.join(args.output_dir, "result.md")
    block = build_block(args.output_dir)
    update_md(md, block)
    print(f"updated {md}")


if __name__ == "__main__":
    main()
