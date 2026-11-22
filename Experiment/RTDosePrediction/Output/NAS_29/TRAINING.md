# NAS_29 — training record

Auto-generated from the trainer's `log.txt` by `monitor_training.py`.

| Item | Value |
|---|---|
| Status | **finished** |
| Started | 2026-11-18 10:29:26 |
| Last update | 2026-11-18 16:26:27 |
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
SearchedNet(
  (stem0): ConvOps(
    (norm): InstanceNorm3d(16, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
    (conv): Conv3d(9, 16, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1))
  )
  (single_conv): Conv3d(16, 16, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1))
  (down_cells): ModuleList(
    (0): SearchedCell(
      (preprocess0): ConvOps(
        (norm): InstanceNorm3d(32, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
        (activation): ReLU()
        (conv): Conv3d(16, 32, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1))
      )
      (_ops): ModuleList(
        (0): IdentityOp(
          (norm): InstanceNorm3d(32, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
        )
        (1): ConvOps(
          (norm): InstanceNorm3d(32, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
          (conv): Conv3d(32, 32, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(2, 2, 2), dilation=(2, 2, 2))
        )
        (2): NoneOp(
          (norm): InstanceNorm3d(32, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
        )
        (3): ConvOps(
          (norm): InstanceNorm3d(32, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
          (depth_conv): Conv3d(32, 32, kernel_size=(3, 3, 3), stride=(2, 2, 2), padding=(1, 1, 1), groups=32)
          (point_conv): Conv3d(32, 32, kernel_size=(1, 1, 1), stride=(1, 1, 1))
        )
      )
    )
    (1): SearchedCell(
      (preprocess0): ConvOps(
        (norm): InstanceNorm3d(64, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
        (activation): ReLU()
        (conv): Conv3d(32, 64, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1))
      )
      (_ops): ModuleList(
        (0): IdentityOp(
          (norm): InstanceNorm3d(64, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
        )
        (1): ConvOps(
          (norm): InstanceNorm3d(64, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
          (conv): Conv3d(64, 64, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(2, 2, 2), dilation=(2, 2, 2))
        )
        (2): NoneOp(
          (norm): InstanceNorm3d(64, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
        )
        (3): ConvOps(
          (norm): InstanceNorm3d(64, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
          (depth_conv): Conv3d(64, 64, kernel_size=(3, 3, 3), stride=(2, 2, 2), padding=(1, 1, 1), groups=64)
          (point_conv): Conv3d(64, 64, kernel_size=(1, 1, 1), stride=(1, 1, 1))
        )
      )
    )
    (2): SearchedCell(
      (preprocess0): ConvOps(
        (norm): InstanceNorm3d(128, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
        (activation): ReLU()
        (conv): Conv3d(64, 128, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1))
      )
      (_ops): ModuleList(
        (0): IdentityOp(
          (norm): InstanceNorm3d(128, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
        )
        (1): ConvOps(
          (norm): InstanceNorm3d(128, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
          (conv): Conv3d(128, 128, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(2, 2, 2), dilation=(2, 2, 2))
        )
        (2): NoneOp(
          (norm): InstanceNorm3d(128, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
        )
        (3): ConvOps(
          (norm): InstanceNorm3d(128, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
          (depth_conv): Conv3d(128, 128, kernel_size=(3, 3, 3), stride=(2, 2, 2), padding=(1, 1, 1), groups=128)
          (point_conv): Conv3d(128, 128, kernel_size=(1, 1, 1), stride=(1, 1, 1))
        )
      )
    )
    (3): SearchedCell(
      (preprocess0): ConvOps(
        (norm): InstanceNorm3d(256, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
        (activation): ReLU()
        (conv): Conv3d(128, 256, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1))
      )
      (_ops): ModuleList(
        (0): IdentityOp(
          (norm): InstanceNorm3d(256, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
        )
        (1): ConvOps(
          (norm): InstanceNorm3d(256, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
          (conv): Conv3d(256, 256, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(2, 2, 2), dilation=(2, 2, 2))
        )
        (2): NoneOp(
          (norm): InstanceNorm3d(256, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
        )
        (3): ConvOps(
          (norm): InstanceNorm3d(256, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
          (depth_conv): Conv3d(256, 256, kernel_size=(3, 3, 3), stride=(2, 2, 2), padding=(1, 1, 1), groups=256)
          (point_conv): Conv3d(256, 256, kernel_size=(1, 1, 1), stride=(1, 1, 1))
        )
      )
    )
  )
  (up_cells): ModuleList(
    (0): SearchedCell(
      (preprocess0): ConvOps(
        (norm): InstanceNorm3d(256, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
        (activation): ReLU()
        (conv): Conv3d(512, 256, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1))
      )
      (_ops): ModuleList(
        (0-1): 2 x ConvOps(
          (norm): InstanceNorm3d(256, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
          (depth_conv): Conv3d(256, 256, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1), groups=256)
          (point_conv): Conv3d(256, 256, kernel_size=(1, 1, 1), stride=(1, 1, 1))
        )
        (2): NoneOp(
          (norm): InstanceNorm3d(256, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
        )
        (3): ConvOps(
          (norm): InstanceNorm3d(256, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
          (conv): Conv3d(256, 256, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1))
        )
      )
      (down_channel): ConvOps(
        (norm): InstanceNorm3d(128, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
        (activation): ReLU()
        (conv): Conv3d(256, 128, kernel_size=(1, 1, 1), stride=(1, 1, 1))
      )
    )
    (1): SearchedCell(
      (preprocess0): ConvOps(
        (norm): InstanceNorm3d(128, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
        (activation): ReLU()
        (conv): Conv3d(256, 128, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1))
      )
      (_ops): ModuleList(
        (0-1): 2 x ConvOps(
          (norm): InstanceNorm3d(128, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
          (depth_conv): Conv3d(128, 128, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1), groups=128)
          (point_conv): Conv3d(128, 128, kernel_size=(1, 1, 1), stride=(1, 1, 1))
        )
        (2): NoneOp(
          (norm): InstanceNorm3d(128, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
        )
        (3): ConvOps(
          (norm): InstanceNorm3d(128, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
          (conv): Conv3d(128, 128, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1))
        )
      )
      (down_channel): ConvOps(
        (norm): InstanceNorm3d(64, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
        (activation): ReLU()
        (conv): Conv3d(128, 64, kernel_size=(1, 1, 1), stride=(1, 1, 1))
      )
    )
    (2): SearchedCell(
      (preprocess0): ConvOps(
        (norm): InstanceNorm3d(64, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
        (activation): ReLU()
        (conv): Conv3d(128, 64, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1))
      )
      (_ops): ModuleList(
        (0-1): 2 x ConvOps(
          (norm): InstanceNorm3d(64, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
          (depth_conv): Conv3d(64, 64, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1), groups=64)
          (point_conv): Conv3d(64, 64, kernel_size=(1, 1, 1), stride=(1, 1, 1))
        )
        (2): NoneOp(
          (norm): InstanceNorm3d(64, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
        )
        (3): ConvOps(
          (norm): InstanceNorm3d(64, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
          (conv): Conv3d(64, 64, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1))
        )
      )
      (down_channel): ConvOps(
        (norm): InstanceNorm3d(32, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
        (activation): ReLU()
        (conv): Conv3d(64, 32, kernel_size=(1, 1, 1), stride=(1, 1, 1))
      )
    )
    (3): SearchedCell(
      (preprocess0): ConvOps(
        (norm): InstanceNorm3d(32, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
        (activation): ReLU()
        (conv): Conv3d(64, 32, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1))
      )
      (_ops): ModuleList(
        (0-1): 2 x ConvOps(
          (norm): InstanceNorm3d(32, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
          (depth_conv): Conv3d(32, 32, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1), groups=32)
          (point_conv): Conv3d(32, 32, kernel_size=(1, 1, 1), stride=(1, 1, 1))
        )
        (2): NoneOp(
          (norm): InstanceNorm3d(32, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
        )
        (3): ConvOps(
          (norm): InstanceNorm3d(32, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
          (activation): ReLU()
          (conv): Conv3d(32, 32, kernel_size=(3, 3, 3), stride=(1, 1, 1), padding=(1, 1, 1))
        )
      )
      (down_channel): ConvOps(
        (norm): InstanceNorm3d(16, eps=1e-05, momentum=0.1, affine=True, track_running_stats=False)
        (activation): ReLU()
        (conv): Conv3d(32, 16, kernel_size=(1, 1, 1), stride=(1, 1, 1))
      )
    )
  )
  (bottle): ModuleList()
  (last_conv): Sequential(
    (0): Conv3d(32, 16, kernel_size=(1, 1, 1), stride=(1, 1, 1))
    (1): Conv3d(16, 1, kernel_size=(1, 1, 1), stride=(1, 1, 1))
  )
)

TOTAL_PARAMETERS 10945409
INPUT_SHAPE (1, 9, 128, 128, 128)
OUTPUT_SHAPE (1, 1, 128, 128, 128)
```

</details>

## Training progress

<!-- TRAINING_LOG_START -->
| Epoch | Iter | Train loss (avg) | Best train loss | Val index (neg. MAE) | Val dose MAE (Gy) | End LR | Epoch time (s) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | -1 | 0.088551 | 0.088551 | -4.4756 | 4.4756 | 0.00029997 | 144.68 |
| 1 | 499 | 0.061728 | 0.061728 | -3.9404 | 3.9404 | 0.00029988 | 143.01 |
| 2 | 999 | 0.057187 | 0.057187 | -3.8758 | 3.8758 | 0.00029974 | 142.70 |
| 3 | 1499 | 0.055768 | 0.055768 | -6.0338 | 6.0338 | 0.00029954 | 143.39 |
| 4 | 1999 | 0.052867 | 0.052867 | -3.4363 | 3.4363 | 0.00029928 | 142.85 |
| 5 | 2499 | 0.051380 | 0.051380 | -3.5196 | 3.5196 | 0.00029896 | 143.21 |
| 6 | 2999 | 0.050585 | 0.050585 | -3.3994 | 3.3994 | 0.00029859 | 143.24 |
| 7 | 3499 | 0.048632 | 0.048632 | -3.3634 | 3.3634 | 0.00029815 | 144.52 |
| 8 | 3999 | 0.048747 | 0.048632 | -3.1558 | 3.1558 | 0.00029766 | 144.23 |
| 9 | 4499 | 0.047360 | 0.047360 | -3.6853 | 3.6853 | 0.00029712 | 144.70 |
| 10 | 4999 | 0.046406 | 0.046406 | -3.2192 | 3.2192 | 0.00029652 | 144.53 |
| 11 | 5499 | 0.046629 | 0.046406 | -3.1050 | 3.1050 | 0.00029586 | 143.66 |
| 12 | 5999 | 0.046042 | 0.046042 | -3.6256 | 3.6256 | 0.00029514 | 143.78 |
| 13 | 6499 | 0.045360 | 0.045360 | -3.3359 | 3.3359 | 0.00029437 | 143.15 |
| 14 | 6999 | 0.045431 | 0.045360 | -3.0709 | 3.0709 | 0.00029354 | 143.82 |
| 15 | 7499 | 0.044468 | 0.044468 | -3.2618 | 3.2618 | 0.00029266 | 144.81 |
| 16 | 7999 | 0.043904 | 0.043904 | -3.1138 | 3.1138 | 0.00029172 | 144.55 |
| 17 | 8499 | 0.044160 | 0.043904 | -3.1243 | 3.1243 | 0.00029073 | 142.41 |
| 18 | 8999 | 0.043425 | 0.043425 | -3.1402 | 3.1402 | 0.00028969 | 142.44 |
| 19 | 9499 | 0.043855 | 0.043425 | -3.1493 | 3.1493 | 0.00028859 | 142.14 |
| 20 | 9999 | 0.043013 | 0.043013 | -3.1431 | 3.1431 | 0.00028743 | 142.41 |
| 21 | 10499 | 0.042540 | 0.042540 | -2.9420 | 2.9420 | 0.00028623 | 143.69 |
| 22 | 10999 | 0.042020 | 0.042020 | -3.3767 | 3.3767 | 0.00028497 | 144.08 |
| 23 | 11499 | 0.042083 | 0.042020 | -3.1602 | 3.1602 | 0.00028366 | 143.02 |
| 24 | 11999 | 0.042228 | 0.042020 | -3.2494 | 3.2494 | 0.00028229 | 142.44 |
| 25 | 12499 | 0.041531 | 0.041531 | -3.0201 | 3.0201 | 0.00028088 | 142.90 |
| 26 | 12999 | 0.041395 | 0.041395 | -2.9614 | 2.9614 | 0.00027942 | 143.32 |
| 27 | 13499 | 0.040453 | 0.040453 | -2.8736 | 2.8736 | 0.00027790 | 143.12 |
| 28 | 13999 | 0.041123 | 0.040453 | -3.0102 | 3.0102 | 0.00027634 | 142.35 |
| 29 | 14499 | 0.040105 | 0.040105 | -2.8841 | 2.8841 | 0.00027473 | 142.77 |
| 30 | 14999 | 0.040462 | 0.040105 | -2.8275 | 2.8275 | 0.00027307 | 142.91 |
| 31 | 15499 | 0.040109 | 0.040105 | -3.0170 | 3.0170 | 0.00027136 | 142.93 |
| 32 | 15999 | 0.039894 | 0.039894 | -2.9253 | 2.9253 | 0.00026961 | 142.28 |
| 33 | 16499 | 0.039867 | 0.039867 | -3.0044 | 3.0044 | 0.00026781 | 142.13 |
| 34 | 16999 | 0.038954 | 0.038954 | -2.9670 | 2.9670 | 0.00026596 | 141.92 |
| 35 | 17499 | 0.038787 | 0.038787 | -2.8311 | 2.8311 | 0.00026407 | 142.73 |
| 36 | 17999 | 0.039289 | 0.038787 | -2.7948 | 2.7948 | 0.00026214 | 143.62 |
| 37 | 18499 | 0.038332 | 0.038332 | -2.9509 | 2.9509 | 0.00026016 | 142.32 |
| 38 | 18999 | 0.039125 | 0.038332 | -2.9385 | 2.9385 | 0.00025814 | 142.31 |
| 39 | 19499 | 0.038475 | 0.038332 | -2.8626 | 2.8626 | 0.00025608 | 142.24 |
| 40 | 19999 | 0.037926 | 0.037926 | -2.8680 | 2.8680 | 0.00025398 | 142.22 |
| 41 | 20499 | 0.038300 | 0.037926 | -2.8354 | 2.8354 | 0.00025184 | 142.52 |
| 42 | 20999 | 0.037871 | 0.037871 | -2.7612 | 2.7612 | 0.00024965 | 143.47 |
| 43 | 21499 | 0.037361 | 0.037361 | -2.8444 | 2.8444 | 0.00024743 | 142.55 |
| 44 | 21999 | 0.037456 | 0.037361 | -2.7704 | 2.7704 | 0.00024518 | 142.52 |
| 45 | 22499 | 0.036703 | 0.036703 | -2.7676 | 2.7676 | 0.00024288 | 142.24 |
| 46 | 22999 | 0.036919 | 0.036703 | -2.9166 | 2.9166 | 0.00024055 | 142.80 |
| 47 | 23499 | 0.036183 | 0.036183 | -2.7163 | 2.7163 | 0.00023819 | 142.56 |
| 48 | 23999 | 0.036407 | 0.036183 | -2.7914 | 2.7914 | 0.00023579 | 142.36 |
| 49 | 24499 | 0.036682 | 0.036183 | -2.8421 | 2.8421 | 0.00023336 | 142.48 |
| 50 | 24999 | 0.036091 | 0.036091 | -2.8106 | 2.8106 | 0.00023089 | 142.95 |
| 51 | 25499 | 0.037001 | 0.036091 | -2.8635 | 2.8635 | 0.00022840 | 142.22 |
| 52 | 25999 | 0.036100 | 0.036091 | -2.9326 | 2.9326 | 0.00022587 | 142.25 |
| 53 | 26499 | 0.035655 | 0.035655 | -2.8112 | 2.8112 | 0.00022332 | 142.87 |
| 54 | 26999 | 0.035657 | 0.035655 | -2.9801 | 2.9801 | 0.00022074 | 142.40 |
| 55 | 27499 | 0.036265 | 0.035655 | -2.8367 | 2.8367 | 0.00021813 | 142.59 |
| 56 | 27999 | 0.035603 | 0.035603 | -2.7688 | 2.7688 | 0.00021549 | 142.16 |
| 57 | 28499 | 0.034683 | 0.034683 | -2.8185 | 2.8185 | 0.00021283 | 143.01 |
| 58 | 28999 | 0.034952 | 0.034683 | -2.8096 | 2.8096 | 0.00021014 | 141.94 |
| 59 | 29499 | 0.034453 | 0.034453 | -2.8559 | 2.8559 | 0.00020743 | 141.78 |
| 60 | 29999 | 0.034817 | 0.034453 | -2.7364 | 2.7364 | 0.00020470 | 141.79 |
| 61 | 30499 | 0.035010 | 0.034453 | -2.7793 | 2.7793 | 0.00020195 | 141.69 |
| 62 | 30999 | 0.034348 | 0.034348 | -2.7031 | 2.7031 | 0.00019918 | 141.87 |
| 63 | 31499 | 0.034081 | 0.034081 | -2.7289 | 2.7289 | 0.00019639 | 142.24 |
| 64 | 31999 | 0.034353 | 0.034081 | -2.7262 | 2.7262 | 0.00019358 | 141.89 |
| 65 | 32499 | 0.034439 | 0.034081 | -2.7467 | 2.7467 | 0.00019075 | 142.02 |
| 66 | 32999 | 0.034204 | 0.034081 | -2.7819 | 2.7819 | 0.00018791 | 142.13 |
| 67 | 33499 | 0.034263 | 0.034081 | -2.7688 | 2.7688 | 0.00018506 | 141.92 |
| 68 | 33999 | 0.033460 | 0.033460 | -2.7295 | 2.7295 | 0.00018219 | 141.77 |
| 69 | 34499 | 0.033277 | 0.033277 | -2.7043 | 2.7043 | 0.00017930 | 141.83 |
| 70 | 34999 | 0.032817 | 0.032817 | -2.7275 | 2.7275 | 0.00017641 | 141.85 |
| 71 | 35499 | 0.033127 | 0.032817 | -2.7137 | 2.7137 | 0.00017351 | 141.89 |
| 72 | 35999 | 0.033238 | 0.032817 | -2.6995 | 2.6995 | 0.00017060 | 141.61 |
| 73 | 36499 | 0.033177 | 0.032817 | -2.7021 | 2.7021 | 0.00016767 | 141.44 |
| 74 | 36999 | 0.033023 | 0.032817 | -2.6966 | 2.6966 | 0.00016475 | 141.96 |
| 75 | 37499 | 0.032910 | 0.032817 | -2.7143 | 2.7143 | 0.00016181 | 141.75 |
| 76 | 37999 | 0.032787 | 0.032787 | -2.6907 | 2.6907 | 0.00015888 | 141.81 |
| 77 | 38499 | 0.032831 | 0.032787 | -2.6863 | 2.6863 | 0.00015594 | 141.83 |
| 78 | 38999 | 0.032215 | 0.032215 | -2.7016 | 2.7016 | 0.00015299 | 142.34 |
| 79 | 39499 | 0.032562 | 0.032215 | -2.7634 | 2.7634 | 0.00015005 | 141.79 |
| 80 | 39999 | 0.031726 | 0.031726 | -2.6993 | 2.6993 | 0.00014711 | 141.44 |
| 81 | 40499 | 0.032216 | 0.031726 | -2.6753 | 2.6753 | 0.00014416 | 142.43 |
| 82 | 40999 | 0.031391 | 0.031391 | -2.7119 | 2.7119 | 0.00014122 | 142.08 |
| 83 | 41499 | 0.031927 | 0.031391 | -2.7462 | 2.7462 | 0.00013829 | 141.41 |
| 84 | 41999 | 0.031397 | 0.031391 | -2.6973 | 2.6973 | 0.00013535 | 141.86 |
| 85 | 42499 | 0.031452 | 0.031391 | -2.6606 | 2.6606 | 0.00013243 | 141.61 |
| 86 | 42999 | 0.031125 | 0.031125 | -2.7077 | 2.7077 | 0.00012950 | 141.87 |
| 87 | 43499 | 0.031219 | 0.031125 | -2.7344 | 2.7344 | 0.00012659 | 141.42 |
| 88 | 43999 | 0.031115 | 0.031115 | -2.6980 | 2.6980 | 0.00012369 | 141.38 |
| 89 | 44499 | 0.031034 | 0.031034 | -2.6603 | 2.6603 | 0.00012080 | 141.97 |
| 90 | 44999 | 0.031003 | 0.031003 | -2.6842 | 2.6842 | 0.00011791 | 141.53 |
| 91 | 45499 | 0.030133 | 0.030133 | -2.6488 | 2.6488 | 0.00011504 | 141.76 |
| 92 | 45999 | 0.030280 | 0.030133 | -2.6803 | 2.6803 | 0.00011219 | 141.50 |
| 93 | 46499 | 0.029723 | 0.029723 | -2.6641 | 2.6641 | 0.00010935 | 141.75 |
| 94 | 46999 | 0.030494 | 0.029723 | -2.6609 | 2.6609 | 0.00010652 | 142.28 |
| 95 | 47499 | 0.030290 | 0.029723 | -2.6587 | 2.6587 | 0.00010371 | 141.54 |
| 96 | 47999 | 0.029709 | 0.029709 | -2.6764 | 2.6764 | 0.00010092 | 141.62 |
| 97 | 48499 | 0.029519 | 0.029519 | -2.6872 | 2.6872 | 0.00009815 | 141.60 |
| 98 | 48999 | 0.029998 | 0.029519 | -2.6913 | 2.6913 | 0.00009540 | 142.50 |
| 99 | 49499 | 0.029413 | 0.029413 | -2.7066 | 2.7066 | 0.00009267 | 142.13 |
| 100 | 49999 | 0.029556 | 0.029413 | -2.6728 | 2.6728 | 0.00008996 | 142.41 |
| 101 | 50499 | 0.029458 | 0.029413 | -2.6295 | 2.6295 | 0.00008727 | 142.49 |
| 102 | 50999 | 0.029524 | 0.029413 | -2.6827 | 2.6827 | 0.00008461 | 142.22 |
| 103 | 51499 | 0.029213 | 0.029213 | -2.6514 | 2.6514 | 0.00008197 | 142.47 |
| 104 | 51999 | 0.028716 | 0.028716 | -2.6762 | 2.6762 | 0.00007936 | 143.54 |
| 105 | 52499 | 0.029100 | 0.028716 | -2.6535 | 2.6535 | 0.00007678 | 143.57 |
| 106 | 52999 | 0.028829 | 0.028716 | -2.6478 | 2.6478 | 0.00007423 | 142.80 |
| 107 | 53499 | 0.028827 | 0.028716 | -2.6522 | 2.6522 | 0.00007170 | 142.27 |
| 108 | 53999 | 0.028886 | 0.028716 | -2.6783 | 2.6783 | 0.00006921 | 142.38 |
| 109 | 54499 | 0.028513 | 0.028513 | -2.6589 | 2.6589 | 0.00006674 | 143.09 |
| 110 | 54999 | 0.028296 | 0.028296 | -2.6397 | 2.6397 | 0.00006431 | 142.56 |
| 111 | 55499 | 0.027876 | 0.027876 | -2.6680 | 2.6680 | 0.00006191 | 142.78 |
| 112 | 55999 | 0.027935 | 0.027876 | -2.6599 | 2.6599 | 0.00005955 | 142.96 |
| 113 | 56499 | 0.027766 | 0.027766 | -2.6616 | 2.6616 | 0.00005722 | 142.83 |
| 114 | 56999 | 0.027484 | 0.027484 | -2.6337 | 2.6337 | 0.00005492 | 142.85 |
| 115 | 57499 | 0.027418 | 0.027418 | -2.6272 | 2.6272 | 0.00005267 | 142.99 |
| 116 | 57999 | 0.027711 | 0.027418 | -2.6766 | 2.6766 | 0.00005045 | 142.49 |
| 117 | 58499 | 0.027323 | 0.027323 | -2.6436 | 2.6436 | 0.00004826 | 142.27 |
| 118 | 58999 | 0.027839 | 0.027323 | -2.6440 | 2.6440 | 0.00004612 | 141.83 |
| 119 | 59499 | 0.027359 | 0.027323 | -2.6458 | 2.6458 | 0.00004402 | 143.29 |
| 120 | 59999 | 0.027018 | 0.027018 | -2.6201 | 2.6201 | 0.00004196 | 142.68 |
| 121 | 60499 | 0.027232 | 0.027018 | -2.6325 | 2.6325 | 0.00003994 | 142.47 |
| 122 | 60999 | 0.027314 | 0.027018 | -2.6485 | 2.6485 | 0.00003796 | 142.62 |
| 123 | 61499 | 0.027140 | 0.027018 | -2.6279 | 2.6279 | 0.00003603 | 142.56 |
| 124 | 61999 | 0.026916 | 0.026916 | -2.6391 | 2.6391 | 0.00003414 | 142.83 |
| 125 | 62499 | 0.026836 | 0.026836 | -2.6487 | 2.6487 | 0.00003229 | 142.25 |
| 126 | 62999 | 0.027027 | 0.026836 | -2.6347 | 2.6347 | 0.00003049 | 142.31 |
| 127 | 63499 | 0.027030 | 0.026836 | -2.6320 | 2.6320 | 0.00002874 | 142.71 |
| 128 | 63999 | 0.026814 | 0.026814 | -2.6220 | 2.6220 | 0.00002703 | 142.72 |
| 129 | 64499 | 0.026431 | 0.026431 | -2.6267 | 2.6267 | 0.00002537 | 142.68 |
| 130 | 64999 | 0.026369 | 0.026369 | -2.6380 | 2.6380 | 0.00002376 | 142.89 |
| 131 | 65499 | 0.026341 | 0.026341 | -2.6348 | 2.6348 | 0.00002220 | 142.41 |
| 132 | 65999 | 0.026536 | 0.026341 | -2.6337 | 2.6337 | 0.00002068 | 142.58 |
| 133 | 66499 | 0.026234 | 0.026234 | -2.6296 | 2.6296 | 0.00001922 | 142.82 |
| 134 | 66999 | 0.026527 | 0.026234 | -2.6332 | 2.6332 | 0.00001781 | 143.34 |
| 135 | 67499 | 0.026595 | 0.026234 | -2.6330 | 2.6330 | 0.00001644 | 142.30 |
| 136 | 67999 | 0.026210 | 0.026210 | -2.6229 | 2.6229 | 0.00001513 | 142.49 |
| 137 | 68499 | 0.025840 | 0.025840 | -2.6226 | 2.6226 | 0.00001387 | 142.80 |
| 138 | 68999 | 0.026036 | 0.025840 | -2.6311 | 2.6311 | 0.00001267 | 143.09 |
| 139 | 69499 | 0.026023 | 0.025840 | -2.6357 | 2.6357 | 0.00001151 | 143.31 |
| 140 | 69999 | 0.026232 | 0.025840 | -2.6354 | 2.6354 | 0.00001041 | 143.41 |
| 141 | 70499 | 0.025670 | 0.025670 | -2.6321 | 2.6321 | 0.00000937 | 146.25 |
| 142 | 70999 | 0.025646 | 0.025646 | -2.6232 | 2.6232 | 0.00000838 | 143.07 |
| 143 | 71499 | 0.025623 | 0.025623 | -2.6357 | 2.6357 | 0.00000744 | 143.41 |
| 144 | 71999 | 0.026153 | 0.025623 | -2.6304 | 2.6304 | 0.00000656 | 143.55 |
| 145 | 72499 | 0.026386 | 0.025623 | -2.6376 | 2.6376 | 0.00000573 | 146.44 |
| 146 | 72999 | 0.025624 | 0.025623 | -2.6290 | 2.6290 | 0.00000496 | 146.82 |
| 147 | 73499 | 0.025769 | 0.025623 | -2.6299 | 2.6299 | 0.00000424 | 146.74 |
| 148 | 73999 | 0.025598 | 0.025598 | -2.6315 | 2.6315 | 0.00000358 | 144.96 |
| 149 | 74499 | 0.025559 | 0.025559 | -2.6307 | 2.6307 | 0.00000298 | 145.49 |
| 150 | 74999 | 0.025965 | 0.025559 | -2.6305 | 2.6305 | 0.00000244 | 146.19 |
| 151 | 75499 | 0.025535 | 0.025535 | -2.6307 | 2.6307 | 0.00000195 | 145.11 |
| 152 | 75999 | 0.025327 | 0.025327 | -2.6280 | 2.6280 | 0.00000151 | 145.91 |
| 153 | 76499 | 0.025744 | 0.025327 | -2.6255 | 2.6255 | 0.00000114 | 146.88 |
| 154 | 76999 | 0.025672 | 0.025327 | -2.6262 | 2.6262 | 0.00000082 | 143.97 |
| 155 | 77499 | 0.025961 | 0.025327 | -2.6246 | 2.6246 | 0.00000056 | 144.99 |
| 156 | 77999 | 0.025527 | 0.025327 | -2.6260 | 2.6260 | 0.00000036 | 145.68 |
| 157 | 78499 | 0.025840 | 0.025327 | -2.6258 | 2.6258 | 0.00000022 | 144.44 |
| 158 | 78999 | 0.025781 | 0.025327 | -2.6258 | 2.6258 | 0.00000013 | 145.68 |
| 159 | 79499 | 0.025256 | 0.025256 | -2.6258 | 2.6258 | 0.00000010 | 145.64 |

### Epoch-0 iteration losses (logged every 10 iterations)

| Iteration | Moving train loss |
|---:|---:|
| 0 | 0.415600 |
| 10 | 0.401170 |
| 20 | 0.379410 |
| 30 | 0.356200 |
| 40 | 0.333550 |
| 50 | 0.313360 |
| 60 | 0.294130 |
| 70 | 0.275900 |
| 80 | 0.259710 |
| 90 | 0.245790 |
| 100 | 0.231340 |
| 110 | 0.218330 |
| 120 | 0.206310 |
| 130 | 0.194750 |
| 140 | 0.185160 |
| 150 | 0.176070 |
| 160 | 0.167010 |
| 170 | 0.159600 |
| 180 | 0.152200 |
| 190 | 0.144900 |
| 200 | 0.138460 |
| 210 | 0.133280 |
| 220 | 0.128940 |
| 230 | 0.124800 |
| 240 | 0.122650 |
| 250 | 0.118180 |
| 260 | 0.113470 |
| 270 | 0.109310 |
| 280 | 0.106010 |
| 290 | 0.103070 |
| 300 | 0.100840 |
| 310 | 0.097580 |
| 320 | 0.094670 |
| 330 | 0.091420 |
| 340 | 0.089460 |
| 350 | 0.086940 |
| 360 | 0.085500 |
| 370 | 0.083250 |
| 380 | 0.081750 |
| 390 | 0.080640 |
| 400 | 0.079870 |
| 410 | 0.078720 |
| 420 | 0.078990 |
| 430 | 0.078750 |
| 440 | 0.078500 |
| 450 | 0.077860 |
| 460 | 0.077150 |
| 470 | 0.076090 |
| 480 | 0.074380 |
| 490 | 0.073600 |

_Parsed 160 epoch(s); status: finished_

<!-- TRAINING_LOG_END -->

---

## Held-out test result (patients 241–340)

| Item | Value |
|---|---|
| Command | `python test.py --GPU_id 0` |
| Checkpoint | `best_val_evaluation_index.pkl` |
| Test patients | 241–340 (100 patients) |
| Test-time augmentation | enabled, 4 flips averaged |
| **Dose score (MAE)** | **2.555265** |
| **DVH score (MAE)** | **1.662817** |
| Predictions | `Output/NAS_29/Prediction/<pt>/dose.nii.gz` (100/100) |
| Test log | `Output/NAS_29/test_stdout.log` |

Comparison:

| Model | Dose MAE | DVH MAE |
|---|---:|---:|
| **NAS_29 (this retrained run)** | **2.5553** | **1.6628** |
| NAS_29 (repository's original `nas_test.log`) | 2.5226 | 1.6002 |
| LENAS / KDA-Net single (paper) | 2.565 | 1.737 |
| U-NAS single (paper) | 2.597 | 1.803 |
| U-NAS ensemble, 5 models (paper) | 2.357 | 1.465 |

The retrained single model beats the paper's single-model numbers; the small gap to the
repository's original NAS_29 log is consistent with run-to-run variance (the training
code sets no random seed).
