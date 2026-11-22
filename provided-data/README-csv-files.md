# OpenKBP patient CSV files

Reference for the CSV files inside each patient folder:

- Training: `train-pats/pt_1` – `pt_200` (200 patients)
- Validation: `validation-pats/pt_201` – `pt_240` (40 patients)
- Test: `test-pats/pt_241` – `pt_340` (100 patients, same file types)

There are exactly **14 possible CSV file types** per patient folder. All files for a patient share the same
**128 × 128 × 128 voxel grid**, so the same flat index refers to the same voxel across files. The train and
validation files have identical formats and meanings; only their role in the pipeline differs.

## File reference

| CSV file | Format | Meaning | Role in a **train** patient | Role in a **validation** patient | Present (train / val) |
|---|---|---|---|---|---|
| `ct.csv` | sparse `index, intensity` | CT scan on the patient's 128³ grid; the anatomy image | **Model input** used to fit the network | **Model input** at inference | 200/200 / 40/40 |
| `dose.csv` | sparse `index, dose_Gy` | Reference dose from the treatment plan (ground truth) | **Training target** — the `Y` in the MAE loss | **Evaluation ground truth** only; never fed to the model | 200/200 / 40/40 |
| `possible_dose_mask.csv` | sparse index list (empty value column) | Voxels where dose may be non-zero; dose is 0 everywhere else | Loaded during training, but **not used in the loss** | Masks prediction to 0 outside; **denominator of the dose score** | 200/200 / 40/40 |
| `voxel_dimensions.csv` | 3 plain numbers (x, y, z in mm) | Physical voxel size | Loaded; **not used by the network** | Used only for the volume conversion in `D_0.1cc` | 200/200 / 40/40 |
| `Brainstem.csv` | sparse index list | Binary OAR mask | Input channel; reference DVH metric source | Input channel; DVH computed for reference & prediction | 182/200 / 35/40 |
| `SpinalCord.csv` | sparse index list | Binary OAR mask | Input channel; reference DVH metric source | Input channel; DVH computed for reference & prediction | 188/200 / 38/40 |
| `LeftParotid.csv` | sparse index list | Binary OAR mask (salivary gland) | Input channel; reference DVH metric source | Input channel; DVH computed for reference & prediction | 193/200 / 38/40 |
| `RightParotid.csv` | sparse index list | Binary OAR mask (salivary gland) | Input channel; reference DVH metric source | Input channel; DVH computed for reference & prediction | 192/200 / 40/40 |
| `Esophagus.csv` | sparse index list | Binary OAR mask | Input channel; reference DVH metric source | Input channel; DVH computed for reference & prediction | 81/200 / 17/40 |
| `Larynx.csv` | sparse index list | Binary OAR mask | Input channel; reference DVH metric source | Input channel; DVH computed for reference & prediction | 100/200 / 22/40 |
| `Mandible.csv` | sparse index list | Binary OAR mask (jawbone) | Input channel; reference DVH metric source | Input channel; DVH computed for reference & prediction | 136/200 / 28/40 |
| `PTV56.csv` | sparse index list | Target volume prescribed **56 Gy** | Input channel; reference DVH metric source | Input channel; DVH computed for reference & prediction | 178/200 / 38/40 |
| `PTV63.csv` | sparse index list | Target volume prescribed **63 Gy** | Input channel; reference DVH metric source | Input channel; DVH computed for reference & prediction | 91/200 / 26/40 |
| `PTV70.csv` | sparse index list | Target volume prescribed **70 Gy** (boost) | Input channel; reference DVH metric source | Input channel; DVH computed for reference & prediction | 200/200 / 40/40 |

## Notes

- **Train vs. validation is a role difference, not a format difference.**
  - In training, `dose.csv` is the supervision: `train_on_batch([ct, masks], dose)`.
  - In validation, `dose.csv` is used only by `DoseEvaluator` to compute reference DVH values and the dose
    score. The model sees only `ct.csv` + structure masks at prediction time.
  - The validation split is a genuine hold-out: `main.py` trains only on `train-pats`.
- **All files use the same 128³ grid for a given patient.** The data are stored sparsely:
  - `ct.csv` / `dose.csv`: `index, value` (CT intensity / Gy)
  - `possible_dose_mask.csv` and all ROI masks: `index,` with an empty value column — listed means
    "inside", absent means "outside"
  - `voxel_dimensions.csv`: the only non-sparse file — 3 numbers.
- **Missing ROI files are expected.** The structure was not contoured for that patient; the DataLoader fills
  that channel with zeros, and the evaluator skips that ROI's DVH metrics. `PTV70` is the only target
  present for all 340 patients.
- **`possible_dose_mask` is not a target or an organ** — it is the dose domain: every voxel outside it has
  dose exactly 0, which is why it is used to mask predictions and as the dose-score denominator.
- **Units:** dose in Gy, voxel spacing in mm, CT intensities as stored (the data description recommends
  clipping to 0–4095), voxel dimensions vary per patient.
- The `unraveled_indices.csv` mentioned in the data description is not shipped with this data.

## Reconstruction

```python
import numpy as np
import pandas as pd

def load_patient_file(path):
    """Reconstruct a 128x128x128 array from one patient CSV."""
    df = pd.read_csv(path, index_col=0)
    arr = np.zeros(128**3)
    if df["data"].isna().all():          # mask: index list only
        arr = arr.astype(bool)
        arr[df.index.values] = True
    else:                                 # CT or dose: sparse values
        arr[df.index.values] = df["data"].values
    return arr.reshape(128, 128, 128)
```
