# NAS models — what they are and how they differ

This document explains the NAS model family in `RTDosePrediction/` and compares all 25
searched models `NAS_18`–`NAS_42` using the repository's genotypes, parameter counts and
recorded `nas_test.log` results.

All paths are relative to `/home/zihanli/project/LENAS`.

---

## 1. Taxonomy: what counts as a “NAS model”

| Category | Directories | Description |
|---|---|---|
| **Searched single models** | `NAS_18` … `NAS_42` (25) | Architectures found by U-NAS; the main “NAS models” |
| **Manual NAS models** | `manual_1` … `manual_6` (6) | Hand-designed cell variants in the same `SearchedNet` framework (paper appendix) |
| **NAS search framework** | `U-NAS/` | Differentiable NAS code that searches for cell genotypes |
| **NAS distillation model** | `KD/` | KDA-Net: distils an ensemble of NAS teachers into one student |

The U-NAS ensemble uses four of the searched models as teachers:
`NAS_28`, `NAS_20`, `NAS_27`, `NAS_37` (`KD/pre_models.py:10`).

---

## 2. What all NAS_18–NAS_42 share

They are **not 25 different algorithms**; they are 25 genotypes in the same training
framework.

| Shared item | Evidence |
|---|---|
| `prim_ops.py`, `genotype.py`, `loss.py`, `online_evaluation.py`, `helper.py` | byte-identical across all 25 directories |
| `searched.py` | identical except `NAS_23` (whitespace only) |
| `train.py` | differs only in `project_name` / `output_dir` |
| `test.py` | differs only in model name/path; all evaluate patients 241–340 |
| `evaluate.py` | identical except `NAS_18` (extra MSE diagnostics; same returned metrics) |
| Model constructor | all use `SearchedNet(in_channels=9, init_n_kernels=16, out_channels=1, depth=4, n_nodes=4, channel_change=True, gene=...)` |
| Training config | batch 2, 80,000 iterations, 500 iters/epoch, 160 epochs, Adam 3e-4, cosine to 1e-7, masked L1 |
| Validation / test | validation 201–240, test 241–340 |
| Data pipeline | same 9-channel input, same augmentation, same `dose/70` target |

Code positions:

- Genotype: `RTDosePrediction/NAS_x/geno.py:4`
- Model construction: `RTDosePrediction/NAS_x/train.py:41-47`
- `SearchedNet`: `RTDosePrediction/NAS_x/searched.py:97-147`
- `SearchedCell`: `RTDosePrediction/NAS_x/searched.py:10-63`
- Operation definitions: `RTDosePrediction/NAS_x/prim_ops.py:6-24`
- Training config: `RTDosePrediction/NAS_x/train.py:23-28,60-86`
- Optimizer/scheduler: `NetworkTrainer/network_trainer.py:110-144`
- Validation: `RTDosePrediction/NAS_x/online_evaluation.py:8`
- Test split: `RTDosePrediction/NAS_x/test.py:184`

Only one file is genuinely different: `NAS_28` has an extra `evaluate2.py`.

---

## 3. What actually differs: the genotype

Each `geno.py` stores four operations for the 4 down cells and four for the 4 up cells:

```python
Genotype(down=[(weight, 'op'), ...], up=[(weight, 'op'), ...])
```

The weights are search-time architecture parameters. At model-build time, only the
operation names matter. They determine the topology inside every cell, and therefore the
parameter count and the model's behaviour.

### Operation glossary

| Operation | Implementation (`prim_ops.py:6-24`) | Effect |
|---|---|---|
| `identity` | `IdentityOp` | pass-through |
| `none` | `NoneOp` → `x.mul(0.)` | dropped branch (zero) |
| `dil_conv` | `ConvOps(..., dilation=2)` | dilated 3×3×3 conv |
| `conv` | `ConvOps(...)` | standard 3×3×3 conv |
| `dep_conv` | `ConvOps(..., depthwised=True)` | depthwise conv |
| `se_conv` | `SEConvOp` | squeeze-and-excitation conv |
| `down_dep_conv` | `ConvOps(..., stride=2, depthwised=True)` | depthwise stride-2 downsample |
| `down_dil_conv` | `ConvOps(..., stride=2, dilation=2)` | dilated stride-2 downsample |
| `down_conv` | `ConvOps(..., stride=2)` | stride-2 convolution |
| `max_pool` / `avg_pool` | `PoolingOp` | 2×2×2 pooling |
| `up_interpolate` | `ConvOps(..., interpolate=True)` | conv + trilinear ×2 upsample |
| `up_se_conv` | `SEConvOp(..., stride=2, transposed=True)` | transposed SE conv |
| `up_dep_conv` | depthwise transposed conv | upsampling |
| `up_conv` | transposed conv | upsampling |
| `up_dil_conv` | dilated transposed conv | upsampling (unstable — see below) |

---

## 4. Full comparison of NAS_18–NAS_42

Scores are from the repository's `nas_test.log` files; **lower is better**.
`—` = no recorded log.

| Model | Params | Down-cell ops | Up-cell ops | Dose | DVH | Notes |
|---|---:|---|---|---:|---:|---|
| **NAS_29** | 10.95M | identity, dil_conv, none, down_dep_conv | dep_conv, dep_conv, none, up_interpolate | **2.5226** | **1.6002** | Best recorded single model |
| NAS_37 | 13.20M | dep_conv, conv, identity, down_dil_conv | dep_conv, se_conv, none, up_interpolate | 2.5658 | 1.6497 | KD ensemble teacher |
| NAS_42 | 10.95M | conv, dep_conv, identity, down_dep_conv | se_conv, dep_conv, identity, up_se_conv | 2.5506 | 1.6613 | |
| NAS_35 | 8.39M | dep_conv, identity, identity, max_pool | se_conv, se_conv, identity, up_conv | 2.5412 | 1.6937 | Smallest models |
| NAS_26 | 13.10M | se_conv, dep_conv, none, down_dil_conv | conv, se_conv, none, up_interpolate | 2.6108 | 1.7025 | |
| NAS_27 | 8.60M | dep_conv, se_conv, none, down_conv | se_conv, dep_conv, none, up_dep_conv | 2.5755 | 1.7110 | KD ensemble teacher |
| NAS_28* | 13.09M | dep_conv, dil_conv, identity, down_dil_conv | se_conv, identity, none, up_interpolate | 2.5617 | 1.7141 | Log on patients 1–240; KD teacher |
| NAS_22 | 10.85M | conv, dep_conv, identity, max_pool | se_conv, dep_conv, identity, up_se_conv | 2.5576 | 1.7167 | |
| NAS_34 | 12.99M | se_conv, conv, identity, down_dil_conv | se_conv, identity, identity, up_interpolate | 2.5834 | 1.7273 | |
| NAS_24 | 8.60M | dep_conv, se_conv, none, down_dep_conv | se_conv, dep_conv, identity, up_interpolate | 2.6084 | 1.7312 | Identical genotype to NAS_23 |
| NAS_30 | 8.60M | se_conv, dep_conv, none, down_dep_conv | dil_conv, se_conv, identity, up_dep_conv | 2.5615 | 1.7323 | |
| NAS_20 | 13.10M | dep_conv, conv, identity, down_dil_conv | se_conv, se_conv, none, up_interpolate | 2.5636 | 1.7436 | KD ensemble teacher |
| NAS_23 | 8.60M | dep_conv, se_conv, none, down_dep_conv | se_conv, dep_conv, identity, up_interpolate | 2.6264 | 1.7579 | Identical genotype to NAS_24 |
| NAS_40 | 10.74M | dep_conv, dil_conv, identity, max_pool | se_conv, se_conv, none, up_interpolate | 2.5807 | 1.7652 | |
| NAS_31 | 8.50M | dep_conv, se_conv, none, down_dep_conv | se_conv, se_conv, none, up_interpolate | 2.5788 | 1.7673 | |
| NAS_41 | 10.84M | se_conv, dep_conv, identity, max_pool | dil_conv, conv, none, up_dep_conv | 2.6566 | 1.7695 | |
| NAS_39 | 8.39M | conv, identity, identity, avg_pool | se_conv, se_conv, identity, up_dep_conv | 2.6778 | 1.7696 | Smallest models |
| NAS_36 | 12.99M | se_conv, conv, none, down_dil_conv | se_conv, se_conv, none, up_interpolate | 2.5867 | 1.7916 | |
| NAS_19 | 20.04M | dil_conv, dil_conv, identity, down_dil_conv | conv, conv, none, up_conv | 2.5626 | 1.8032 | Largest model |
| NAS_38 | 15.55M | conv, dil_conv, identity, down_dep_conv | conv, dep_conv, identity, up_dil_conv | 9.1574 | 14.7340 | **Failed run** |
| NAS_21 | 13.30M | dep_conv, dil_conv, none, down_dep_conv | dep_conv, conv, none, up_dil_conv | 9.2373 | 15.2944 | **Failed run** |
| NAS_32 | 13.20M | dep_conv, se_conv, none, down_dep_conv | dil_conv, dil_conv, none, up_dil_conv | 9.4192 | 15.3867 | **Failed run** |
| NAS_33 | 10.74M | identity, se_conv, identity, down_dep_conv | conv, identity, identity, up_dil_conv | 10.5544 | 15.7626 | **Failed run** |
| NAS_25 | 13.10M | conv, se_conv, none, down_dil_conv | dep_conv, se_conv, identity, up_dil_conv | 10.5550 | 16.3541 | **Failed run** |
| NAS_18 | 8.49M | dep_conv, se_conv, none, max_pool | se_conv, dep_conv, identity, up_interpolate | — | — | No `nas_test.log` |

\* `NAS_28`'s log was produced on patients 1–240, so its score is **not comparable** with
the other models (which used 241–340).

---

## 5. Patterns and interpretation

### 5.1 The final up operation is the strongest predictor of success

| Final up op | Models | DVH range |
|---|---|---|
| `up_interpolate` | NAS_18, 20, 23, 24, 26, 28, 29, 31, 34, 36, 37, 40 | **1.60–1.79** |
| `up_se_conv` | NAS_22, 42 | 1.66–1.72 |
| `up_dep_conv` | NAS_27, 30, 39, 41 | 1.71–1.77 |
| `up_conv` | NAS_19, 35 | 1.69–1.80 |
| **`up_dil_conv`** | **NAS_21, 25, 32, 33, 38** | **14.73–16.35 (all failed)** |

The five `up_dil_conv` models are exactly the five degenerate runs. The dilated transposed
convolution upsampler is unstable under this training recipe.

### 5.2 Parameter count is not correlated with accuracy

- Smallest: `NAS_35` and `NAS_39` at **8.39 M**; both perform reasonably (DVH 1.69 / 1.77).
- Largest: `NAS_19` at **20.04 M**; DVH 1.80, worse than the 10.95 M NAS_29.
- The best model, `NAS_29`, is mid-sized at **10.95 M**.

Op types drive the parameter count: `conv`/`dil_conv` add parameters; `identity`, `none`,
pooling, depthwise and SE operations reduce them.

### 5.3 NAS_23 and NAS_24 are the same architecture

They have identical genotypes and identical 8.60 M parameter counts, yet their recorded
scores differ (DVH 1.7579 vs 1.7312). The training code sets no random seed, so this is
run-to-run variance, not an architectural difference.

### 5.4 Best single model vs ensemble teachers

- **Best recorded single model:** `NAS_29` (DVH **1.6002**, dose **2.5226**).
- **Ensemble teachers:** `NAS_28`, `NAS_20`, `NAS_27`, `NAS_37` — chosen for the U-NAS
  ensemble (`KD/pre_models.py:10`), not simply as the four highest single scores.
- **Our retrained NAS_29:** dose **2.5553**, DVH **1.6628** on test 241–340 — slightly
  different from the original log because training is non-deterministic.

---

## 6. Practical recommendations

| Goal | Recommendation |
|---|---|
| Best single model to train | **NAS_29** (`up_interpolate`, best recorded DVH) |
| Best overall DVH curve | U-NAS ensemble using `NAS_28`, `NAS_20`, `NAS_27`, `NAS_37` |
| Avoid | Any genotype ending in `up_dil_conv` |
| Reproducibility | Add a random seed before training; otherwise expect run-to-run variation |
| Compare fairly | Use the same test split (241–340) and the same TTA setting |

---

## 7. Caveats on the recorded scores

1. The scores in the table are from the repository's existing `nas_test.log` files, not
   from retraining all 25 models under one new protocol.
2. `NAS_18` has no log; `NAS_28`'s log is on patients 1–240; the others are on 241–340.
3. The original logs were produced by the authors' runs; the training code has no random
   seed, so a retrained model can differ (as our NAS_29 run shows).
4. The DVH score is the mean absolute difference over all structure-metric entries
   (D1/D95/D99 for PTVs; D_0.1cc/mean for OARs); lower is better.
5. Only the genotype changes between the 25 models — the training code, data pipeline,
   loss, optimizer and validation protocol are the same.
