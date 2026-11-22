#!/usr/bin/env python
"""Keep TRAINING.md in sync with the NetworkTrainer log for NAS_29."""
import argparse
import datetime as dt
import os
import re
import time

HEADER = """# NAS_29 — training record

Auto-generated from the trainer's `log.txt` by `monitor_training.py`.

| Item | Value |
|---|---|
| Status | **{status}** |
| Started | {started} |
| Last update | {updated} |
| Command | `python train.py --batch_size 2 --list_GPU_ids 0 --max_iter 80000` |
| Working dir | `/home/zihanli/project/LENAS/RTDosePrediction/NAS_29` |
| Output dir | `/home/zihanli/project/LENAS/Experiment/RTDosePrediction/Output/NAS_29` |
| GPU | NVIDIA RTX PRO 5000 72GB, GPU 0 |
| Environment | conda `lenas` (Python 3.11.18, torch 2.8.0+cu128) |

## Configuration

| Item | Value |
|---|---|
| Model | `SearchedNet` (U-NAS searched architecture NAS_29) |
| Genotype file | `best_genotype.pkl` |
| Parameters | 10,945,409 (≈10.9 M) |
| Input | 9 channels, 128×128×128 (PTV70/63/56 composite, 7 OARs, CT) |
| Output | 1 channel, 128×128×128 normalized dose (×70 Gy at inference) |
| Batch size | **2** (validation batch 1) |
| Iterations | **80,000** (`max_iter`) |
| Iterations / epoch | 500 (`train_num_samples_per_epoch = batch_size × 500 = 1000` samples) |
| Epochs | **160** |
| DataLoader workers | 4 |
| Training loss | masked L1 (`nn.L1Loss`, mean) on `dose / 70`, restricted to `possible_dose_mask > 0` |
| Validation metric | dose MAE on patients **201–240** (`online_evaluation`), reported as negative mean; higher is better |
| Train patients | 1–200 |
| Test patients | 241–340 |
| Checkpoints | `latest.pkl`, `best_train_loss.pkl`, `best_val_evaluation_index.pkl` |

## Optimizer and scheduler

| Item | Value |
|---|---|
| Optimizer | **Adam**, one parameter group (all 10.9 M parameters) |
| Learning rate | **3e-4** |
| Weight decay | **3e-5 effective** (train.py passes 1e-4, but the single-group Adam branch in `network_trainer.py` hard-codes 3e-5) |
| Betas | (0.9, 0.999) |
| Epsilon | 1e-8 |
| AMSGrad | True (the trainer always enables it for Adam) |
| LR scheduler | `CosineAnnealingLR` |
| `T_max` | 80,000 (max_iter) |
| `eta_min` | 1e-7 |
| LR update | every iteration (`lr_scheduler_update_on_iter = True`) |
| Loss EMA factor | `eps_train_loss = 0.01` (moving train-loss display only) |

## Model structure

Genotype (`NAS_29/geno.py`):

```
Genotype(down=[(0.35017598, 'identity'), (0.24430475, 'dil_conv'),
               (0.21760184764862062, 'none'), (0.2582529366016388, 'down_dep_conv')],
         up=[(0.25242656, 'dep_conv'), (0.2862034, 'dep_conv'),
             (0.20971298217773438, 'none'), (0.2050437331199646, 'up_interpolate')])
```

Full layer dump (`model_structure.txt`):

<details>
<summary>Click to expand the full <code>print(model)</code> output</summary>

```
{model_structure}
```

</details>

## Training progress

<!-- TRAINING_LOG_START -->
<!-- TRAINING_LOG_END -->
"""


def parse_log(path):
    epochs = []
    iters = []
    cur = None
    if not os.path.exists(path):
        return epochs, iters

    with open(path, errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            m = re.match(r"Epoch: (\d+), iter: (-?\d+)", line)
            if m:
                if cur is not None:
                    epochs.append(cur)
                cur = {"epoch": int(m.group(1)), "iter": int(m.group(2))}
                continue
            if cur is None:
                continue
            for key, pat in [
                ("begin_lr", r"Begin lr is ([0-9.eE+\-]+)"),
                ("train_loss", r"Average train loss is\s+([0-9.eE+\-]+)"),
                ("best_train", r"Average train loss is\s+[0-9.eE+\-]+,\s+best is\s+([0-9.eE+\-]+)"),
                ("val_index", r"Average val evaluation index is\s+([0-9.eE+\-]+)"),
                ("best_val", r"Average val evaluation index is\s+[0-9.eE+\-]+,\s+best is\s+([0-9.eE+\-]+)"),
                ("train_time", r"Train use time\s+([0-9.eE+\-]+)"),
                ("val_time", r"Val use time\s+([0-9.eE+\-]+)"),
                ("total_time", r"Total use time\s+([0-9.eE+\-]+)"),
                ("end_lr", r"End lr is ([0-9.eE+\-]+)"),
            ]:
                mm = re.search(pat, line)
                if mm and key not in cur:
                    cur[key] = mm.group(1)
            mm = re.search(r"Iter\s+(\d+)\s+([0-9.eE+\-]+)", line)
            if mm:
                iters.append((int(mm.group(1)), float(mm.group(2))))
    if cur is not None:
        epochs.append(cur)
    return epochs, iters


def fmt(v, nd=6):
    if v is None:
        return "—"
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return str(v)


def build_progress(epochs, iters, status):
    out = []
    if not epochs:
        out.append("_Waiting for the first epoch to finish (500 iterations)…_\n")
        out.append("Live log: `tail -f log.txt` in the output directory.\n")
        return "\n".join(out)

    out.append("| Epoch | Iter | Train loss (avg) | Best train loss | Val index (neg. MAE) | Val dose MAE (Gy) | End LR | Epoch time (s) |")
    out.append("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for e in epochs:
        val_mae = "—"
        if e.get("val_index") is not None:
            try:
                val_mae = f"{-float(e['val_index']):.4f}"
            except (TypeError, ValueError):
                pass
        out.append(
            "| {ep} | {it} | {tl} | {bt} | {vi} | {vm} | {lr} | {tt} |".format(
                ep=e["epoch"], it=e["iter"],
                tl=fmt(e.get("train_loss")), bt=fmt(e.get("best_train")),
                vi=fmt(e.get("val_index"), 4), vm=val_mae,
                lr=fmt(e.get("end_lr"), 8), tt=fmt(e.get("total_time"), 2),
            )
        )

    if iters:
        out.append("\n### Epoch-0 iteration losses (logged every 10 iterations)\n")
        out.append("| Iteration | Moving train loss |")
        out.append("|---:|---:|")
        for it, loss in iters:
            out.append(f"| {it} | {loss:.6f} |")

    out.append("")
    out.append(f"_Parsed {len(epochs)} epoch(s); status: {status}_")
    return "\n".join(out)


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--interval", type=float, default=60.0)
    ap.add_argument("--once", action="store_true", help="update once and exit")
    args = ap.parse_args()

    out_dir = args.output_dir
    log_path = os.path.join(out_dir, "log.txt")
    stdout_path = os.path.join(out_dir, "train_stdout.log")
    pid_path = os.path.join(out_dir, "train.pid")
    md_path = os.path.join(out_dir, "TRAINING.md")
    struct_path = os.path.join(out_dir, "model_structure.txt")

    started = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    model_structure = ""
    if os.path.exists(struct_path):
        with open(struct_path, errors="replace") as f:
            model_structure = f.read().strip()

    while True:
        epochs, iters = parse_log(log_path)
        pid = None
        if os.path.exists(pid_path):
            try:
                pid = int(open(pid_path).read().strip())
            except ValueError:
                pid = None
        running = pid is not None and pid_alive(pid)
        done = False
        if os.path.exists(log_path):
            with open(log_path, errors="replace") as f:
                done = "# Done !" in f.read()
        if done:
            status = "finished"
        elif running:
            status = "running"
        else:
            status = "stopped / failed"

        progress = build_progress(epochs, iters, status)
        if status == "stopped / failed" and os.path.exists(stdout_path):
            tail = "".join(open(stdout_path, errors="replace").readlines()[-25:])
            progress += "\n\n### Last stdout lines\n\n```\n" + tail.rstrip() + "\n```\n"

        md = HEADER.format(
            status=status, started=started,
            updated=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            model_structure=model_structure,
        ).replace("<!-- TRAINING_LOG_START -->", "<!-- TRAINING_LOG_START -->\n" + progress + "\n")
        tmp = md_path + ".tmp"
        with open(tmp, "w") as f:
            f.write(md)
        os.replace(tmp, md_path)

        if args.once or done or not running:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
