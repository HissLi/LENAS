# NAS_29 — dataset split, configuration, and source code

This file records the exact split and configuration of the **currently running NAS_29
training job** (PID `633545`, started 2026-11-18 10:04:48), together with the code that
implements each item. Line numbers refer to the current working tree.

Live, auto-updated progress (loss, validation score, LR, epoch time) is in:

- `/home/zihanli/project/LENAS/Experiment/RTDosePrediction/Output/NAS_29/TRAINING.md`
- raw trainer log: `/home/zihanli/project/LENAS/Experiment/RTDosePrediction/Output/NAS_29/log.txt`

---

## 0. Current run snapshot

| Item | Value |
|---|---|
| PID | 633545 |
| Started | 2026-11-18 10:04:48 |
| Progress at 10:29 | epoch 10, iter 4999 / 80000 |
| Last epoch average train loss | 0.04736 |
| Last validation index | −3.6853 (mean dose MAE 3.6853 Gy) |
| Best validation index so far | −3.1558 (mean dose MAE 3.1558 Gy) |
| GPU | RTX PRO 5000 72GB, GPU 0 |

These are early-epoch numbers. Checkpoint selection is on the validation split
(201–240); the final test split (241–340) is never touched during training.

---

## 1. Dataset split

### 1.1 Official OpenKBP partition

| Split | Patients | Count | Role |
|---|---|---:|---|
| Train | `pt_1` … `pt_200` | 200 | optimization |
| Validation | `pt_201` … `pt_240` | 40 | checkpoint selection / online evaluation |
| Test | `pt_241` … `pt_340` | 100 | final evaluation only |

Raw source: `/home/zihanli/project/LENAS/provided-data/{train-pats,validation-pats,test-pats}`.

Verified live: the running job's `log.txt` lists exactly `pt_201:` … `pt_240:` during validation.

### 1.2 Where the split is enforced

**Training split** — `RTDosePrediction/DataLoader/dataloader_OpenKBP_C3D.py:122-124`:

```python
self.list_case_id = {
    'train': ['/home/zihanli/project/LENAS/Data/RTDosePrediction/OpenKBP_C3D/pt_' + str(i)
              for i in range(1, 201)],
    'val':   ['/home/zihanli/project/LENAS/Data/RTDosePrediction/OpenKBP_C3D/pt_' + str(i)
              for i in range(201, 241)],
}[phase]
```

NAS_29 imports this loader at `NAS_29/train.py:9` and calls it at `NAS_29/train.py:60-66`.

**Validation split used during training** — `NAS_29/online_evaluation.py:8`:

```python
list_patient_dirs = ['/home/zihanli/project/LENAS/Data/RTDosePrediction/OpenKBP_C3D/pt_' + str(i)
                     for i in range(201, 241)]
```

It is wired in at `NAS_29/train.py:71`:

```python
trainer.setting.online_evaluation_function_val = online_evaluation
```

> The loader also constructs a `val_loader` for 201–240, but `NetworkTrainer.val()`
> never iterates it; validation is performed entirely by `online_evaluation`
> (`NetworkTrainer/network_trainer.py:266-277`). Both use the same 201–240 range.

**Test split** — `NAS_29/test.py:184`:

```python
list_patient_dirs = ['/home/zihanli/project/LENAS/Data/RTDosePrediction/OpenKBP_C3D/pt_' + str(i)
                     for i in range(241, 341)]
```

### 1.3 Why there is no split directory on disk

`DataPrepare/prepare_OpenKBP_C3D.py:47-50` flattens the three raw folders into one
directory:

```python
list_patient_dirs = []
for sub_dir in ['train-pats', 'validation-pats', 'test-pats']:
    for patient_id in os.listdir(source_dir + '/' + sub_dir):
        list_patient_dirs.append(source_dir + '/' + sub_dir + '/' + patient_id)
```

All 340 patients are written to `Data/RTDosePrediction/OpenKBP_C3D/pt_<id>/`. The split
is therefore enforced **only by the patient-ID ranges above**. Do not move or rename
patient folders, or the split will silently change.

---

## 2. Data loading and preprocessing

### 2.1 Files read per patient

`DataLoader/dataloader_OpenKBP_C3D.py:17-50`

| File | dtype | Use |
|---|---|---|
| `CT.nii.gz` | int16 | input channel |
| `dose.nii.gz` | float32 | target, divided by 70 |
| `possible_dose_mask.nii.gz` | uint8 | loss mask / output mask |
| `PTV70/63/56.nii.gz` | uint8 | target mask channels |
| `Brainstem`, `SpinalCord`, `RightParotid`, `LeftParotid`, `Esophagus`, `Larynx`, `Mandible` | uint8 | OAR channels |

Missing structures are replaced by zero volumes (`dataloader_OpenKBP_C3D.py:43-48`).

### 2.2 Input construction / normalization

`DataLoader/dataloader_OpenKBP_C3D.py:53-83`:

```python
# 9-channel input
PTVs = 70.0/70. * PTV70 + 63.0/70. * PTV63 + 56.0/70. * PTV56
OAR_all = concatenate([Brainstem, SpinalCord, RightParotid, LeftParotid,
                       Esophagus, Larynx, Mandible], axis=0)
CT = clip(CT, -1024, 1500) / 1000.
dose = dose / 70.
possible_dose_mask = possible_dose_mask

list_images = [concatenate((PTVs, OAR_all, CT), axis=0),   # input, 9×128×128×128
               dose,                                        # target
               possible_dose_mask]                          # mask
```

### 2.3 Training augmentation

`DataLoader/dataloader_OpenKBP_C3D.py:86-107`:

```python
random_flip_3d(list_images, list_axis=(0, 2), p=0.8)
random_rotate_around_z_axis(list_images, list_angles=(0,40,80,...,320),
                            list_interp=(cv2.INTER_NEAREST,)*3, p=0.3)
random_translate(list_images, roi_mask=list_images[2][0], p=0.8,
                 max_shift=20, list_pad_value=[0,0,0])
to_tensor(list_images)
```

Validation uses only `to_tensor` (`dataloader_OpenKBP_C3D.py:110-112`).

### 2.4 Dataset sampling and epoch definition

`DataLoader/dataloader_OpenKBP_C3D.py:115-155`:

```python
class MyDataset(data.Dataset):
    def __init__(self, num_samples_per_epoch, phase):
        ...
        random.shuffle(self.list_case_id)      # shuffled once per dataset construction
        self.sum_case = len(self.list_case_id)

    def __getitem__(self, index_):
        if index_ > self.sum_case - 1:         # wrap around
            index_ = index_ - (index_ // self.sum_case) * self.sum_case
        ...
    def __len__(self):
        return self.num_samples_per_epoch

train_loader = DataLoader(train_dataset, batch_size=train_bs, shuffle=True,
                          num_workers=num_works, pin_memory=False)
```

`NAS_29/train.py:60-66`:

```python
get_loader(train_bs=args.batch_size,          # 2
           val_bs=1,
           train_num_samples_per_epoch=args.batch_size * 500,   # 1000 samples
           val_num_samples_per_epoch=1,
           num_works=4)
```

Therefore:

- 1 epoch = **1000 samples / batch 2 = 500 iterations**.
- Each "epoch" cycles over the 200 training patients about **5 times** (1000 / 200).
- 80,000 iterations = **160 epochs**.

---

## 3. Model configuration

### 3.1 Genotype

`NAS_29/geno.py:3-6`:

```python
a = ("Genotype(down=[(0.35017598, 'identity'), (0.24430475, 'dil_conv'),
                     (0.21760184764862062, 'none'), (0.2582529366016388, 'down_dep_conv')],
       up=[(0.25242656, 'dep_conv'), (0.2862034, 'dep_conv'),
           (0.20971298217773438, 'none'), (0.2050437331199646, 'up_interpolate')])", 1)
```

### 3.2 Network construction

`NAS_29/train.py:37-47` (identical in `NAS_29/test.py:165-175`):

```python
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

`SearchedNet` is defined at `NAS_29/searched.py:97-99`; its stem and cell construction
begins at `NAS_29/searched.py:110-135`.

### 3.3 Verified shape and size

| Item | Value |
|---|---|
| Parameters | **10,945,409** (≈10.9 M; 43.782 MB in float32) |
| Input | `(1, 9, 128, 128, 128)` |
| Output | `(1, 1, 128, 128, 128)` normalized dose (×70 Gy at inference) |
| Encoder | `stem0` ConvOps 9→16, one 3×3×3 conv 16→16 |
| Body | 4 down cells (`depth=4`), 4 up cells, 4 nodes per cell |
| Head | output conv `32→16→1` (1×1×1) |

Full layer dump: `/home/zihanli/project/LENAS/Experiment/RTDosePrediction/Output/NAS_29/model_structure.txt`
(also embedded in `TRAINING.md`).

---

## 4. Training-loop settings

`NAS_29/train.py:22-35, 58-91`:

| Setting | Value | Code |
|---|---|---|
| `project_name` | `NAS_29` | `train.py:33` |
| `output_dir` | `/home/zihanli/project/LENAS/Experiment/RTDosePrediction/Output/NAS_29` | `train.py:34` |
| GPU ids | `[0]` (single GPU; no `DataParallel`) | `train.py:25-26`, `network_trainer.py:95-108` |
| Batch size | 2 | `train.py:23-24` |
| `max_iter` | 80,000 | `train.py:27-28, 58` |
| `max_epoch` | 99999999 (unused; `max_iter` stops training) | `network_trainer.py:21-22, 287` |
| `save_per_epoch` | 99999999 (unused; checkpoints saved every epoch) | `network_trainer.py:26, 309-317` |
| `eps_train_loss` | 0.01 (EMA factor for the displayed moving loss only) | `train.py:68`, `network_trainer.py:165-170` |
| `lr_scheduler_update_on_iter` | True (LR steps every iteration) | `train.py:69` |
| Training loss | `Loss()` | `train.py:70` |
| Validation function | `online_evaluation` | `train.py:71` |
| Device | `cuda:0` | `network_trainer.py:95-108` |
| wandb | offline (`WANDB_MODE=offline`), project name `VNet` | `network_trainer.py:9-11, 92` |

Iteration stopping rule — `NetworkTrainer/network_trainer.py:226-230, 287`:

```python
for batch_idx, list_loader_output in enumerate(self.setting.train_loader):
    if (self.setting.max_iter is not None) and (self.log.iter >= self.setting.max_iter - 1):
        break
    self.log.iter += 1
```

`log.iter` starts at −1 (`network_trainer.py:51`), so the loop runs iterations
0 … 79,999 = exactly 80,000 optimizer steps.

---

## 5. Loss function

`NAS_29/loss.py:5-21`:

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

        L1_loss = self.L1_loss_func(pred_A, gt_dose)
        return L1_loss
```

- Loss = **mean absolute error** between predicted and reference normalized dose,
  restricted to voxels where `possible_dose_mask > 0`.
- Target is `dose / 70` (section 2.2); predictions are multiplied by 70 only at
  inference/evaluation.
- No additional regularization term in the loss.

---

## 6. Optimizer and learning-rate scheduler

### 6.1 What `train.py` requests

`NAS_29/train.py:73-86`:

```python
trainer.set_optimizer(optimizer_type='Adam',
                      args={'lr': 3e-4, 'weight_decay': 1e-4})

trainer.set_lr_scheduler(lr_scheduler_type='cosine',
                         args={'T_max': args.max_iter,   # 80000
                               'eta_min': 1e-7,
                               'last_epoch': -1})
```

### 6.2 What is actually constructed

`NetworkTrainer/network_trainer.py:110-128`:

```python
def set_optimizer(self, optimizer_type, args):
    if optimizer_type == 'Adam':
        if hasattr(self.setting.network, 'decoder') and hasattr(self.setting.network, 'encoder'):
            # two groups, lr_encoder / lr_decoder
            ...
        else:
            self.setting.optimizer = optim.Adam(self.setting.network.parameters(),
                                                lr=args['lr'],
                                                weight_decay=3e-5,
                                                betas=(0.9, 0.999),
                                                eps=1e-08,
                                                amsgrad=True)
```

`SearchedNet` has **no** `encoder`/`decoder` attributes, so NAS_29 takes the single-group
branch. The effective configuration is:

| Item | Effective value |
|---|---|
| Optimizer | **Adam**, 1 parameter group (all 10,945,409 parameters) |
| Learning rate | **3e-4** |
| Weight decay | **3e-5** ← `train.py` passes 1e-4, but this branch hard-codes 3e-5 |
| Betas | (0.9, 0.999) |
| Epsilon | 1e-8 |
| AMSGrad | True |

> This is a real discrepancy in the upstream code, not a transcription mistake. If you
> want 1e-4 weight decay, edit `NetworkTrainer/network_trainer.py:125` to
> `weight_decay=args['weight_decay']`.

### 6.3 Scheduler

`NetworkTrainer/network_trainer.py:138-144`:

```python
elif lr_scheduler_type == 'cosine':
    self.setting.lr_scheduler_type = 'cosine'
    self.setting.lr_scheduler = optim.lr_scheduler.CosineAnnealingLR(
        self.setting.optimizer,
        T_max=args['T_max'],        # 80000
        eta_min=args['eta_min'],    # 1e-7
        last_epoch=args['last_epoch'])
```

Because `lr_scheduler_update_on_iter=True`, `update_lr()` is called after every
iteration (`network_trainer.py:158-163, 250`):

```python
def update_lr(self):
    if self.setting.lr_scheduler_type == 'ReduceLROnPlateau':
        self.setting.lr_scheduler.step(self.log.moving_train_loss)
    else:
        self.setting.lr_scheduler.step()
```

So the LR follows a cosine curve from 3e-4 down to 1e-7 over the 80,000 iterations.

---

## 7. Validation during training

`NAS_29/online_evaluation.py:7-47`:

```python
list_patient_dirs = [... pt_' + str(i) for i in range(201, 241)]

with torch.no_grad():
    trainer.setting.network.eval()
    for patient_dir in list_patient_dirs:
        dict_images = read_data(patient_dir)
        list_images = pre_processing(dict_images)
        input_, gt_dose, possible_dose_mask = list_images[0], list_images[1], list_images[2]

        [input_] = val_transform([input_])
        input_ = input_.unsqueeze(0).to(trainer.setting.device)
        prediction_B = trainer.setting.network(input_)
        prediction_B = np.array(prediction_B.cpu().data[0, :, :, :, :])

        prediction_B[np.logical_or(possible_dose_mask < 1, prediction_B < 0)] = 0
        Dose_score = 70. * get_3D_Dose_dif(prediction_B.squeeze(0),
                                           gt_dose.squeeze(0),
                                           possible_dose_mask.squeeze(0))
        list_Dose_score.append(Dose_score)

return - np.mean(list_Dose_score)       # higher is better
```

- Validation patients: **201–240** (40 patients).
- No test-time augmentation during validation.
- Dose error is the MAE over `possible_dose_mask > 0`, in Gy.
- The returned index is the **negative mean dose MAE**; the trainer saves
  `best_val_evaluation_index.pkl` when this index improves
  (`network_trainer.py:171-183`).

Validation frequency: once per epoch, i.e. every 500 iterations
(`train()` then `val()` in `NetworkTrainer.run`, `network_trainer.py:299-301`).

---

## 8. Checkpoints, logging, and wandb

`NetworkTrainer/network_trainer.py:346-363`:

```python
ckpt = {
    'network_state_dict': ...,
    'lr_scheduler_state_dict': ...,
    'optimizer_state_dict': ...,
    'log': self.log,
}
torch.save(ckpt, self.setting.output_dir + '/' + status + '.pkl')
```

| File | When written |
|---|---|
| `latest.pkl` | every epoch |
| `best_train_loss.pkl` | when average train loss improves |
| `best_val_evaluation_index.pkl` | when validation index improves |
| `log.txt` | continuously (one block per epoch) |
| `wandb/` | offline run directory |

The final test/evaluation uses `best_val_evaluation_index.pkl`
(`NAS_29/test.py:156`). Checkpoints are ~168 MB each (model + optimizer + scheduler + log).

---

## 9. Test / evaluation configuration

`NAS_29/test.py:149-193`:

| Setting | Value | Code |
|---|---|---|
| GPU | `--GPU_id 0` | `test.py:154` |
| Checkpoint | `Output/NAS_29/best_val_evaluation_index.pkl` | `test.py:156` |
| TTA | default **True** | `test.py:157` |
| Test patients | **241–340** | `test.py:184` |
| Test-time flips | `[[], ['Z'], ['W'], ['Z','W']]` (4 predictions averaged) | `test.py:129-134`, `test.py:96-111` |
| Post-processing | zero outside `possible_dose_mask`, zero negatives, ×70 | `test.py:136-138` |
| Output | `Output/NAS_29/Prediction/<pt>/dose.nii.gz` | `test.py:140-146` |

Metrics (`NAS_29/evaluate.py`):

- **Dose score** — MAE between predicted and GT dose over `possible_dose_mask > 0`
  (`evaluate.py:11-17`).
- **DVH score** — mean absolute error over:
  - target metrics: `D1`, `D95`, `D99` (`evaluate.py:20-30`),
  - OAR metrics: `D_0.1_cc`, `mean` (`evaluate.py:32-44`),
  computed per structure for `Brainstem`, `SpinalCord`, `RightParotid`, `LeftParotid`,
  `Esophagus`, `Larynx`, `Mandible`, `PTV70`, `PTV63`, `PTV56`
  (`evaluate.py:51-...`).

Evaluation command:

```bash
cd /home/zihanli/project/LENAS/RTDosePrediction/NAS_29
python test.py --GPU_id 0
```

---

## 10. Reproducibility notes and caveats

1. **No random seed is set.** `random.shuffle` (`dataloader_OpenKBP_C3D.py:126`),
   Python `random` in the augmentations, and cuDNN's default algorithm selection make
   runs non-deterministic unless you add seeds / `torch.backends.cudnn.deterministic`.
2. **Split is ID-range based** (section 1.3). The prepared directory is flat and
   contains all 340 patients.
3. **Effective weight decay is 3e-5**, not the 1e-4 passed by `train.py` (section 6.2).
4. **`max_epoch` and `save_per_epoch` are left at 99999999**; `max_iter=80000` is the
   active stopping criterion.
5. **The loader's `val_loader` is unused.** Validation is `online_evaluation` on
   201–240; both use the same patients.
6. **`wandb` is forced offline** via `WANDB_MODE=offline` in
   `NetworkTrainer/network_trainer.py:9-11`. Override with `WANDB_MODE=online` if you
   want cloud logging.

---

## 11. Commands used for this run

```bash
conda activate lenas

cd /home/zihanli/project/LENAS/RTDosePrediction/NAS_29
python geno.py                       # writes best_genotype.pkl

python train.py --batch_size 2 --list_GPU_ids 0 --max_iter 80000
```

Monitor / control:

```bash
cd /home/zihanli/project/LENAS/Experiment/RTDosePrediction/Output/NAS_29
tail -f log.txt
tail -f train_stdout.log
cat TRAINING.md
kill $(cat train.pid)
```
