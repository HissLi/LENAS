# NAS_29 vs Unet — dataset split and training configuration

This file records the dataset split and all training/inference configuration for the two
models that have been run in this repository:

| Model | Status | Output directory |
|---|---|---|
| **NAS_29** | finished 2026-11-18 16:25:51; test dose 2.555265 / DVH 1.662817 | `Experiment/RTDosePrediction/Output/NAS_29` |
| **Unet** | finished 2026-11-19 19:33; test dose 2.653749 / DVH 1.808596 | `Experiment/RTDosePrediction/Output/Unet` |

They share the same OpenKBP data pipeline, loss, optimizer, scheduler and validation
protocol. The differences are the model architecture (searched vs standard 3D U-Net) and
the default TTA flag in `test.py`.

All paths below are relative to `/home/zihanli/project/LENAS`.

---

## 1. Dataset split

Both models use the official OpenKBP split:

| Split | Patients | Count | Role |
|---|---|---:|---|
| Train | `pt_1` … `pt_200` | 200 | optimization |
| Validation | `pt_201` … `pt_240` | 40 | checkpoint selection / online evaluation |
| Test | `pt_241` … `pt_340` | 100 | final evaluation only |

### 1.1 Where the split is defined

**Training loader** — `RTDosePrediction/DataLoader/dataloader_OpenKBP_C3D.py:122-124`:

```python
self.list_case_id = {
    'train': ['.../OpenKBP_C3D/pt_' + str(i) for i in range(1, 201)],
    'val':   ['.../OpenKBP_C3D/pt_' + str(i) for i in range(201, 241)],
}[phase]
```

The loader is imported and called identically:

| Model | Import | Loader call |
|---|---|---|
| NAS_29 | `RTDosePrediction/NAS_29/train.py:9` | `RTDosePrediction/NAS_29/train.py:60-66` |
| Unet | `RTDosePrediction/Unet/train.py:9` | `RTDosePrediction/Unet/train.py:47-53` |

**Validation during training** — patients 201–240:

| Model | Code position |
|---|---|
| NAS_29 | `RTDosePrediction/NAS_29/online_evaluation.py:8` |
| Unet | `RTDosePrediction/Unet/online_evaluation.py:8` |

```python
list_patient_dirs = ['.../OpenKBP_C3D/pt_' + str(i) for i in range(201, 241)]
```

The validation function is wired in at `NAS_29/train.py:71` / `Unet/train.py:59`.
Note: the loader also constructs a `val_loader` for 201–240, but `NetworkTrainer.val()`
calls only `online_evaluation` (`NetworkTrainer/network_trainer.py:266-277`), so the
`val_loader` is not iterated.

**Test split** — patients 241–340:

| Model | Code position |
|---|---|
| NAS_29 | `RTDosePrediction/NAS_29/test.py:184` |
| Unet | `RTDosePrediction/Unet/test.py:175` |

```python
list_patient_dirs = ['.../OpenKBP_C3D/pt_' + str(i) for i in range(241, 341)]
```

### 1.2 Why there is no split folder on disk

`RTDosePrediction/DataPrepare/prepare_OpenKBP_C3D.py:47-50` flattens
`provided-data/{train-pats,validation-pats,test-pats}` into one directory:

```python
list_patient_dirs = []
for sub_dir in ['train-pats', 'validation-pats', 'test-pats']:
    for patient_id in os.listdir(source_dir + '/' + sub_dir):
        list_patient_dirs.append(source_dir + '/' + sub_dir + '/' + patient_id)
```

All 340 patients are stored under `Data/RTDosePrediction/OpenKBP_C3D/pt_<id>/`. The split
is enforced **only by the ID ranges** in sections 1.1; IDs are disjoint, so there is no
leakage as long as those ranges are not changed.

---

## 2. Input data and preprocessing

Identical for both models. Code: `RTDosePrediction/DataLoader/dataloader_OpenKBP_C3D.py`.

| Item | Value | Code position |
|---|---|---|
| Files read | `CT`, `dose`, `possible_dose_mask`, `PTV70/63/56`, 7 OARs | `:17-50` |
| Missing structure | filled with zeros | `:43-48` |
| Input channels | **9** = PTV composite + 7 OAR masks + CT | `:53-67` |
| PTV composite | `70/70·PTV70 + 63/70·PTV63 + 56/70·PTV56` | `:55-57` |
| CT normalization | clip to `[-1024, 1500]`, divide by 1000 | `:69-72` |
| Dose target | `dose / 70` | `:74-75` |
| Loss mask | `possible_dose_mask` | `:77-82` |
| Training augmentation | flips p=0.8 (axes 0,2), z-rotation p=0.3, translation p=0.8, max shift 20 | `:86-107` |
| Validation transform | tensor conversion only | `:110-112` |
| Dataset / DataLoader | 1000 samples per epoch, batch 2, shuffle, 4 workers | `:115-155` |

The output of `pre_processing` is `[input, dose/70, possible_dose_mask]`, so each sample
is `9×128×128×128`, `1×128×128×128`, `1×128×128×128`.

---

## 3. Model

| Item | NAS_29 | Unet |
|---|---|---|
| Class | `SearchedNet` | `Model` (`BaseUNet`) |
| Parameters | **10,945,409** (43.8 MB) | **6,471,713** (25.9 MB) |
| Input / output | 9×128³ → 1×128³ | 9×128³ → 1×128³ |
| Construction | `NAS_29/train.py:41-47` | `Unet/train.py:34-36` |
| Definition | `NAS_29/searched.py:97-147` | `Unet/model.py:147-160` |
| Genotype | `NAS_29/geno.py:4` | none |

**NAS_29** loads the searched cell genotype and builds the U-NAS network:

```python
# NAS_29/train.py:37-47
geno_file = 'best_genotype.pkl'
with open(geno_file, 'rb') as f:
    gene = eval(pickle.load(f)[0])

trainer.setting.network = SearchedNet(in_channels=9,
                                      init_n_kernels=16,
                                      out_channels=1,
                                      depth=4,
                                      n_nodes=4,
                                      channel_change=True,
                                      gene=gene)
```

Genotype (`NAS_29/geno.py:4`):

```text
down: identity, dil_conv, none, down_dep_conv
up:   dep_conv, dep_conv, none, up_interpolate
```

Architecture: `stem0` ConvOps 9→16, one 3×3×3 conv 16→16, 4 down cells, 4 up cells,
4 nodes per cell, output conv 32→16→1 (`NAS_29/searched.py:110-147`).

**Unet** is a fixed 3D U-Net with five encoder/decoder stages:

```python
# Unet/train.py:34-36
trainer.setting.network = Model(in_ch=9, out_ch=1,
                                list_ch_A=[-1, 16, 32, 64, 128, 256],
                                list_ch_B=[-1, 32, 64, 128, 256, 512])
```

`Model.forward` returns a single tensor (`Unet/model.py:156-160`); `BaseUNet` is at
`Unet/model.py:136-144`, `Encoder` at `Unet/model.py:36-67`, `Decoder` at
`Unet/model.py:70-129`.

---

## 4. Training configuration

| Setting | NAS_29 | Unet | Code position |
|---|---|---|---|
| Project name | `NAS_29` | `Unet` | `NAS_29/train.py:33`; `Unet/train.py:30` |
| Output dir | `Output/NAS_29` | `Output/Unet` | `NAS_29/train.py:34`; `Unet/train.py:31` |
| Batch size | 2 | 2 | `NAS_29/train.py:23-24`; `Unet/train.py:20-21` |
| GPU ids | `[0]` | `[0]` | `NAS_29/train.py:25-26`; `Unet/train.py:22-23` |
| `max_iter` | 80,000 | 80,000 | `NAS_29/train.py:27-28,58`; `Unet/train.py:24-25,44` |
| Samples / epoch | `batch_size × 500 = 1000` | same | `NAS_29/train.py:60-66`; `Unet/train.py:47-53` |
| **Iterations / epoch** | **500** | **500** | same as above |
| **Epochs** | **160** | **160** | 80,000 / 500 |
| `max_epoch` | 99999999 (unused) | same | `NetworkTrainer/network_trainer.py:21-22` |
| `save_per_epoch` | 99999999 (unused) | same | `NetworkTrainer/network_trainer.py:26` |
| `eps_train_loss` | 0.01 | 0.01 | `NAS_29/train.py:68`; `Unet/train.py:56` |
| LR update | every iteration | every iteration | `NAS_29/train.py:69`; `Unet/train.py:57` |
| Loss | `Loss()` | `Loss()` | `NAS_29/train.py:70`; `Unet/train.py:58` |
| Validation function | `online_evaluation` | `online_evaluation` | `NAS_29/train.py:71`; `Unet/train.py:59` |
| Device | `cuda:0` | `cuda:0` | `NetworkTrainer/network_trainer.py:95-108` |
| wandb | offline, project `VNet` | offline, project `VNet` | `NetworkTrainer/network_trainer.py:9-11,92` |

The loader call that defines the 500-iteration epoch:

```python
# NAS_29/train.py:60-66  (Unet/train.py:47-53 is identical apart from names)
trainer.setting.train_loader, trainer.setting.val_loader = get_loader(
    train_bs=args.batch_size,                 # 2
    val_bs=1,
    train_num_samples_per_epoch=args.batch_size * 500,   # 1000 samples
    val_num_samples_per_epoch=1,
    num_works=4)
```

The stopping rule is the `max_iter` check, not `max_epoch`
(`NetworkTrainer/network_trainer.py:226-230,287`):

```python
if (self.setting.max_iter is not None) and (self.log.iter >= self.setting.max_iter - 1):
    break
self.log.iter += 1
```

`log.iter` starts at −1 (`NetworkTrainer/network_trainer.py:51`), so the loop executes
iterations 0 … 79,999 = exactly 80,000 optimizer steps.

Checkpoints (`NetworkTrainer/network_trainer.py:346-363`):

| File | When written |
|---|---|
| `latest.pkl` | every epoch |
| `best_train_loss.pkl` | when average train loss improves |
| `best_val_evaluation_index.pkl` | when validation index improves |

NAS_29 checkpoints are ~168 MB; Unet checkpoints are ~99 MB.

---

## 5. Loss

Identical file in both directories:
`NAS_29/loss.py:5-21` and `Unet/loss.py:5-21` (same md5).

```python
class Loss(nn.Module):
    def __init__(self):
        super().__init__()
        self.L1_loss_func = nn.L1Loss(reduction='mean')

    def forward(self, pred, gt):
        pred_A = pred
        gt_dose = gt[0]                    # dose / 70
        possible_dose_mask = gt[1]

        pred_A = pred_A[possible_dose_mask > 0]
        gt_dose = gt_dose[possible_dose_mask > 0]

        return self.L1_loss_func(pred_A, gt_dose)
```

- Loss = **mean absolute error** on normalized dose, restricted to
  `possible_dose_mask > 0`.
- Target normalization `dose / 70`: `DataLoader/dataloader_OpenKBP_C3D.py:75`.
- Predictions are multiplied by 70 only at inference/evaluation
  (`NAS_29/test.py:138`; `Unet/test.py:137`).

---

## 6. Optimizer and learning-rate scheduler

### 6.1 What the training scripts request

```python
# NAS_29/train.py:73-86
trainer.set_optimizer(optimizer_type='Adam',
                      args={'lr': 3e-4, 'weight_decay': 1e-4})
trainer.set_lr_scheduler(lr_scheduler_type='cosine',
                         args={'T_max': args.max_iter,   # 80000
                               'eta_min': 1e-7,
                               'last_epoch': -1})
```

Unet's block is identical at `Unet/train.py:61-74`.

### 6.2 What is actually constructed

`NetworkTrainer/network_trainer.py:110-128`:

```python
if optimizer_type == 'Adam':
    if hasattr(self.setting.network, 'decoder') and hasattr(self.setting.network, 'encoder'):
        # two parameter groups, lr_encoder / lr_decoder
        ...
    else:
        self.setting.optimizer = optim.Adam(self.setting.network.parameters(),
                                            lr=args['lr'],
                                            weight_decay=3e-5,
                                            betas=(0.9, 0.999),
                                            eps=1e-08,
                                            amsgrad=True)
```

Neither `SearchedNet` nor Unet's `Model` exposes `.encoder`/`.decoder` attributes on the
top-level module, so both take the **single-parameter-group** branch.

| Item | Effective value (both models) |
|---|---|
| Optimizer | Adam, 1 parameter group (all parameters) |
| Learning rate | **3e-4** |
| Weight decay | **3e-5** — `train.py` passes 1e-4, but this branch hard-codes 3e-5 |
| Betas | (0.9, 0.999) |
| Epsilon | 1e-8 |
| AMSGrad | True |

To make `train.py`'s 1e-4 effective, change `NetworkTrainer/network_trainer.py:125` to
`weight_decay=args['weight_decay']`.

Scheduler construction (`NetworkTrainer/network_trainer.py:138-144`):

```python
self.setting.lr_scheduler = optim.lr_scheduler.CosineAnnealingLR(
    self.setting.optimizer,
    T_max=args['T_max'],        # 80000
    eta_min=args['eta_min'],    # 1e-7
    last_epoch=args['last_epoch'])
```

Because `lr_scheduler_update_on_iter=True`, the scheduler steps after every iteration
(`NetworkTrainer/network_trainer.py:158-163,250`).

---

## 7. Validation during training

Both models use `online_evaluation` on patients **201–240**, with no TTA.

| Item | Code position |
|---|---|
| NAS_29 validation function | `NAS_29/online_evaluation.py:7-47` |
| Unet validation function | `Unet/online_evaluation.py:7-47` |
| Called every epoch | `NetworkTrainer/network_trainer.py:266-277,299-301` |

```python
# NAS_29/online_evaluation.py:8; Unet/online_evaluation.py:8
list_patient_dirs = ['.../OpenKBP_C3D/pt_' + str(i) for i in range(201, 241)]

# :31-33
prediction_B[np.logical_or(possible_dose_mask < 1, prediction_B < 0)] = 0
Dose_score = 70. * get_3D_Dose_dif(prediction_B.squeeze(0),
                                   gt_dose.squeeze(0),
                                   possible_dose_mask.squeeze(0))

# :47
return - np.mean(list_Dose_score)      # higher is better
```

The metric is dose MAE in Gy over `possible_dose_mask > 0`; the trainer saves
`best_val_evaluation_index.pkl` when this negative-mean index improves.

---

## 8. Test / inference / evaluation

| Item | NAS_29 | Unet |
|---|---|---|
| Checkpoint | `Output/NAS_29/best_val_evaluation_index.pkl` (`NAS_29/test.py:156`) | `Output/Unet/best_val_evaluation_index.pkl` (`Unet/test.py:155`) |
| Test patients | 241–340 (`NAS_29/test.py:184`) | 241–340 (`Unet/test.py:175`) |
| TTA default in code | **True** (`NAS_29/test.py:157`) | **False** (`Unet/test.py:156`) |
| TTA used in our run | default True | explicit `--TTA True` via `Output/Unet/run_pipeline.sh` |
| TTA modes | `[[], ['Z'], ['W'], ['Z','W']]` (`NAS_29/test.py:129-134`) | same (`Unet/test.py:128-133`) |
| Post-processing | zero outside mask/negatives, ×70 (`NAS_29/test.py:136-138`) | same (`Unet/test.py:135-137`) |
| Prediction file | `Prediction/<pt>/dose.nii.gz` (`NAS_29/test.py:140-146`) | same (`Unet/test.py:139-145`) |
| Metric code | `NAS_29/evaluate.py:11-48,51-99` | `Unet/evaluate.py:11-48,60-150` (also accepts `list_patient_ids`) |

Metric definitions (identical in both `evaluate.py` files):

- **Dose score** = MAE between prediction and GT over `possible_dose_mask > 0`
  (`NAS_29/evaluate.py:11-17`; `Unet/evaluate.py:11-17`).
- **DVH score** = mean absolute difference over all structure-metric entries:
  - targets: `D1`, `D95`, `D99` (`evaluate.py:20-30` / `:29-39`);
  - OARs: `D_0.1cc`, `mean` (`evaluate.py:32-44` / `:41-53`);
  - structures: Brainstem, SpinalCord, RightParotid, LeftParotid, Esophagus, Larynx,
    Mandible, PTV70, PTV63, PTV56.

The Unet `evaluate.py` additionally prints MSE/per-structure diagnostics but returns the
same two mean values (`Unet/evaluate.py:150`).

---

## 9. Other configuration notes

1. **No random seed is set.** `random.shuffle` in the dataset
   (`DataLoader/dataloader_OpenKBP_C3D.py:126`), Python `random` in augmentation, and
   cuDNN algorithm selection make runs non-deterministic.
2. **`eps_train_loss = 0.01`** is only the EMA factor for the displayed moving train loss
   (`NetworkTrainer/network_trainer.py:165-170`), not a loss threshold.
3. **`max_epoch` / `save_per_epoch` are 99999999**; `max_iter=80000` is the active stop.
4. **The loader's `val_loader` is unused**; validation is `online_evaluation` on 201–240.
5. **wandb is forced offline** via `WANDB_MODE=offline`
   (`NetworkTrainer/network_trainer.py:9-11`).
6. **Unet/train.py renders a graphviz diagram** at startup
   (`Unet/train.py:38-41`), so `dot` must be on `PATH`. NAS_29's equivalent block is
   commented out (`NAS_29/train.py:17-18,49-54`).
7. **Paths are hardcoded** to `/home/zihanli/project/LENAS` (originally `YOUR_ROOT`).
8. **Unet's `Model` is a standard 3D U-Net** with `InstanceNorm3d`, ReLU, trilinear
   upsampling and 1×1 output conv; NAS_29's `SearchedNet` uses the searched
   `SearchedCell` operations stored in `best_genotype.pkl`.

---

## 10. Commands

NAS_29:

```bash
cd RTDosePrediction/NAS_29
python geno.py                       # writes best_genotype.pkl
python train.py --batch_size 2 --list_GPU_ids 0 --max_iter 80000
python test.py --GPU_id 0
```

Unet:

```bash
cd RTDosePrediction/Unet
python train.py --batch_size 2 --list_GPU_ids 0 --max_iter 80000
python test.py --GPU_id 0 --TTA True
```

The Unet pipeline used here chains training, inference, evaluation and DVH visualization:

```bash
bash Experiment/RTDosePrediction/Output/Unet/run_pipeline.sh
```
