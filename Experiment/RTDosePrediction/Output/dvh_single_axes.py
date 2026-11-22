#!/usr/bin/env python
"""Regenerate DVH figures with all structures overlaid in one axes.

Reads the existing Evaluation/per_patient_metrics.csv and DVH/dvh_curves.npz,
backs up the old grid-style DVH folder, then writes:
  DVH/pt_XXX_dvh.png        (one axes, all structures, GT solid / pred dashed)
  DVH/all_patients_dvh.pdf  (mean page + 100 patient pages)
  DVH/mean_dvh_all_structures.png
  DVH/mean_dvh_per_structure.png  (same content; keeps old links valid)
"""

import argparse
import csv
import os
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D

STRUCTS = ["PTV70", "PTV63", "PTV56", "Brainstem", "SpinalCord",
           "RightParotid", "LeftParotid", "Esophagus", "Larynx", "Mandible"]

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

PATIENTS = [f"pt_{i}" for i in range(241, 341)]


def load_metrics(out_dir):
    path = os.path.join(out_dir, "Evaluation", "per_patient_metrics.csv")
    rows = {}
    for r in csv.DictReader(open(path)):
        rows[r["patient"]] = (float(r["dose_mae"]), float(r["mean_abs_dvh_diff"]))
    return rows


def style_axes(ax):
    ax.set_xlim(0, 85)
    ax.set_ylim(0, 102)
    ax.set_xlabel("Dose (Gy)", fontsize=11)
    ax.set_ylabel("Volume (%)", fontsize=11)
    ax.grid(alpha=0.3)


def add_legends(fig, model, struct_handles):
    style_handles = [
        Line2D([0], [0], color="k", lw=2.2, label="Ground truth"),
        Line2D([0], [0], color="k", lw=2.2, ls="--", label=f"{model} prediction"),
    ]
    axes = fig.axes[0]
    axes.legend(handles=style_handles, loc="upper right", fontsize=10)
    fig.legend(handles=struct_handles, loc="center left", bbox_to_anchor=(0.84, 0.5),
               fontsize=9, title="Structures", ncol=1)


def patient_figure(model, pid, data, grid, dose_mae, mean_dvh):
    fig, ax = plt.subplots(figsize=(13, 7.5))
    handles = []
    for s in STRUCTS:
        kg, kp = f"{pid}|{s}|gt", f"{pid}|{s}|pred"
        if kg not in data:
            continue
        color = COLORS[s]
        ax.plot(grid, data[kg], color=color, lw=2.0)
        ax.plot(grid, data[kp], color=color, lw=2.0, ls="--")
        handles.append(Line2D([0], [0], color=color, lw=2.5, label=s))

    style_axes(ax)
    ax.set_title(f"{model} — {pid} — dose MAE {dose_mae:.2f} Gy — mean |ΔDVH| {mean_dvh:.2f}",
                 fontsize=13)
    add_legends(fig, model, handles)
    fig.subplots_adjust(left=0.07, right=0.83, top=0.90, bottom=0.10)
    return fig


def mean_figure(model, data, grid):
    fig, ax = plt.subplots(figsize=(13, 7.5))
    handles = []
    for s in STRUCTS:
        gt_list, pred_list = [], []
        for pid in PATIENTS:
            kg, kp = f"{pid}|{s}|gt", f"{pid}|{s}|pred"
            if kg in data:
                gt_list.append(data[kg])
                pred_list.append(data[kp])
        if not gt_list:
            continue
        color = COLORS[s]
        ax.plot(grid, np.mean(gt_list, axis=0), color=color, lw=2.2)
        ax.plot(grid, np.mean(pred_list, axis=0), color=color, lw=2.2, ls="--")
        handles.append(Line2D([0], [0], color=color, lw=2.5,
                              label=f"{s} (n={len(gt_list)})"))

    style_axes(ax)
    ax.set_title(f"{model} — mean DVH over test patients 241–340", fontsize=13)
    add_legends(fig, model, handles)
    fig.subplots_adjust(left=0.07, right=0.83, top=0.90, bottom=0.10)
    return fig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--model", required=True)
    args = ap.parse_args()

    out = args.output_dir
    dvh_dir = os.path.join(out, "DVH")
    backup = os.path.join(out, "DVH_grid_style")

    if os.path.isdir(dvh_dir) and not os.path.isdir(backup):
        shutil.copytree(dvh_dir, backup)
        print(f"backed up old DVH folder -> {backup}")

    os.makedirs(dvh_dir, exist_ok=True)
    with np.load(os.path.join(dvh_dir, "dvh_curves.npz")) as z:
        data = {k: z[k] for k in z.files}
    grid = data["grid"]
    metrics = load_metrics(out)

    pdf_path = os.path.join(dvh_dir, "all_patients_dvh.pdf")
    with PdfPages(pdf_path) as pdf:
        # mean summary page first
        fig = mean_figure(args.model, data, grid)
        fig.savefig(os.path.join(dvh_dir, "mean_dvh_all_structures.png"),
                    dpi=150, bbox_inches="tight")
        # keep the old filename valid for result.md links
        fig.savefig(os.path.join(dvh_dir, "mean_dvh_per_structure.png"),
                    dpi=150, bbox_inches="tight")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        for i, pid in enumerate(PATIENTS, 1):
            if pid not in metrics:
                continue
            dose_mae, mean_dvh = metrics[pid]
            fig = patient_figure(args.model, pid, data, grid, dose_mae, mean_dvh)
            fig.savefig(os.path.join(dvh_dir, f"{pid}_dvh.png"),
                        dpi=150, bbox_inches="tight")
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
            if i % 10 == 0:
                print(f"[{args.model}] {i}/100 patients")

    print(f"[{args.model}] done -> {dvh_dir}")


if __name__ == "__main__":
    main()
