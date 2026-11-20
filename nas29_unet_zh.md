# NAS_29 与 Unet — 数据集划分与训练配置

本文是 `nas29_unet.md` 的中文版本。代码、路径、字段名和 `file:line` 引用保持英文，便于直接定位源码。

本文件记录仓库中已运行的两个模型的数据集划分及全部训练/推理配置：

| 模型 | 状态 | 输出目录 |
|---|---|---|
| **NAS_29** | 已于 2026-11-18 16:25:51 完成；测试 dose 2.555265 / DVH 1.662817 | `Experiment/RTDosePrediction/Output/NAS_29` |
| **Unet** | 已于 2026-11-19 19:33 完成；测试 dose 2.653749 / DVH 1.808596 | `Experiment/RTDosePrediction/Output/Unet` |

两者使用相同的 OpenKBP 数据流程、损失函数、优化器、学习率调度器和验证协议。区别在于模型结构（搜索得到的 NAS 架构 vs 标准 3D U-Net）以及 `test.py` 中默认的 TTA 开关。

以下路径均相对于 `/home/zihanli/project/LENAS`。

---

## 1. 数据集划分

两个模型均使用 OpenKBP 官方划分：

| 划分 | 患者 | 数量 | 作用 |
|---|---|---:|---|
| 训练集（Train） | `pt_1` … `pt_200` | 200 | 参数优化 |
| 验证集（Validation） | `pt_201` … `pt_240` | 40 | 选择 checkpoint / 在线评估 |
| 测试集（Test） | `pt_241` … `pt_340` | 100 | 仅最终评估 |

### 1.1 划分代码位置

**训练数据加载器** — `RTDosePrediction/DataLoader/dataloader_OpenKBP_C3D.py:122-124`：

```python
self.list_case_id = {
    'train': ['.../OpenKBP_C3D/pt_' + str(i) for i in range(1, 201)],
    'val':   ['.../OpenKBP_C3D/pt_' + str(i) for i in range(201, 241)],
}[phase]
```

两个模型的导入与调用位置：

| 模型 | 导入位置 | `get_loader` 调用位置 |
|---|---|---|
| NAS_29 | `RTDosePrediction/NAS_29/train.py:9` | `RTDosePrediction/NAS_29/train.py:60-66` |
| Unet | `RTDosePrediction/Unet/train.py:9` | `RTDosePrediction/Unet/train.py:47-53` |

**训练期间的验证集** — 患者 201–240：

| 模型 | 代码位置 |
|---|---|
| NAS_29 | `RTDosePrediction/NAS_29/online_evaluation.py:8` |
| Unet | `RTDosePrediction/Unet/online_evaluation.py:8` |

```python
list_patient_dirs = ['.../OpenKBP_C3D/pt_' + str(i) for i in range(201, 241)]
```

验证函数在 `NAS_29/train.py:71` / `Unet/train.py:59` 处绑定。
注意：数据加载器也会构造一个用于 201–240 的 `val_loader`，但 `NetworkTrainer.val()`
实际只调用 `online_evaluation`（`NetworkTrainer/network_trainer.py:266-277`），
因此 `val_loader` 不会被迭代使用。

**测试集** — 患者 241–340：

| 模型 | 代码位置 |
|---|---|
| NAS_29 | `RTDosePrediction/NAS_29/test.py:184` |
| Unet | `RTDosePrediction/Unet/test.py:175` |

```python
list_patient_dirs = ['.../OpenKBP_C3D/pt_' + str(i) for i in range(241, 341)]
```

### 1.2 为什么磁盘上没有单独的划分文件夹

`RTDosePrediction/DataPrepare/prepare_OpenKBP_C3D.py:47-50` 会把
`provided-data/{train-pats,validation-pats,test-pats}` 展平到同一个目录：

```python
list_patient_dirs = []
for sub_dir in ['train-pats', 'validation-pats', 'test-pats']:
    for patient_id in os.listdir(source_dir + '/' + sub_dir):
        list_patient_dirs.append(source_dir + '/' + sub_dir + '/' + patient_id)
```

全部 340 位患者都存放在 `Data/RTDosePrediction/OpenKBP_C3D/pt_<id>/` 下。
因此，数据划分**仅由 1.1 节中的患者 ID 范围决定**；由于各集合 ID 不重叠，
只要不修改这些范围，就不会发生数据泄漏。

---

## 2. 输入数据与预处理

两个模型完全一致。代码：`RTDosePrediction/DataLoader/dataloader_OpenKBP_C3D.py`。

| 项目 | 内容 | 代码位置 |
|---|---|---|
| 读取文件 | `CT`、`dose`、`possible_dose_mask`、`PTV70/63/56`、7 个 OAR | `:17-50` |
| 缺失结构 | 用全 0 体积补齐 | `:43-48` |
| 输入通道数 | **9** = PTV 复合通道 + 7 个 OAR 掩码 + CT | `:53-67` |
| PTV 复合 | `70/70·PTV70 + 63/70·PTV63 + 56/70·PTV56` | `:55-57` |
| CT 归一化 | 裁剪到 `[-1024, 1500]`，除以 1000 | `:69-72` |
| 剂量标签 | `dose / 70` | `:74-75` |
| 损失掩码 | `possible_dose_mask` | `:77-82` |
| 训练数据增强 | 翻转 p=0.8（轴 0、2）、绕 z 轴旋转 p=0.3、平移 p=0.8（最大位移 20） | `:86-107` |
| 验证变换 | 仅转为 tensor | `:110-112` |
| Dataset / DataLoader | 每 epoch 1000 个样本、batch 2、shuffle、4 个 worker | `:115-155` |

`pre_processing` 返回 `[input, dose/70, possible_dose_mask]`，因此每个样本为
`9×128×128×128`、`1×128×128×128`、`1×128×128×128`。

---

## 3. 模型

| 项目 | NAS_29 | Unet |
|---|---|---|
| 类名 | `SearchedNet` | `Model`（`BaseUNet`） |
| 参数量 | **10,945,409**（43.8 MB） | **6,471,713**（25.9 MB） |
| 输入 / 输出 | 9×128³ → 1×128³ | 9×128³ → 1×128³ |
| 构造位置 | `NAS_29/train.py:41-47` | `Unet/train.py:34-36` |
| 定义位置 | `NAS_29/searched.py:97-147` | `Unet/model.py:147-160` |
| Genotype | `NAS_29/geno.py:4` | 无 |

**NAS_29** 先从 genotype 文件读取搜索得到的 cell 结构，再构建 U-NAS 网络：

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

Genotype（`NAS_29/geno.py:4`）：

```text
down: identity, dil_conv, none, down_dep_conv
up:   dep_conv, dep_conv, none, up_interpolate
```

网络结构：`stem0` ConvOps 9→16、一个 3×3×3 卷积 16→16、4 个 down cell、4 个 up cell、
每个 cell 4 个 node、输出卷积 32→16→1（`NAS_29/searched.py:110-147`）。

**Unet** 是固定的 3D U-Net，包含 5 个编码/解码阶段：

```python
# Unet/train.py:34-36
trainer.setting.network = Model(in_ch=9, out_ch=1,
                                list_ch_A=[-1, 16, 32, 64, 128, 256],
                                list_ch_B=[-1, 32, 64, 128, 256, 512])
```

`Model.forward` 返回单个 tensor（`Unet/model.py:156-160`）；`BaseUNet` 位于
`Unet/model.py:136-144`，`Encoder` 位于 `Unet/model.py:36-67`，`Decoder` 位于
`Unet/model.py:70-129`。

---

## 4. 训练配置

| 配置 | NAS_29 | Unet | 代码位置 |
|---|---|---|---|
| Project 名称 | `NAS_29` | `Unet` | `NAS_29/train.py:33`；`Unet/train.py:30` |
| 输出目录 | `Output/NAS_29` | `Output/Unet` | `NAS_29/train.py:34`；`Unet/train.py:31` |
| Batch size | 2 | 2 | `NAS_29/train.py:23-24`；`Unet/train.py:20-21` |
| GPU ids | `[0]` | `[0]` | `NAS_29/train.py:25-26`；`Unet/train.py:22-23` |
| `max_iter` | 80,000 | 80,000 | `NAS_29/train.py:27-28,58`；`Unet/train.py:24-25,44` |
| 每 epoch 样本数 | `batch_size × 500 = 1000` | 相同 | `NAS_29/train.py:60-66`；`Unet/train.py:47-53` |
| **每 epoch 迭代数** | **500** | **500** | 同上 |
| **Epoch 数** | **160** | **160** | 80,000 / 500 |
| `max_epoch` | 99999999（未使用） | 相同 | `NetworkTrainer/network_trainer.py:21-22` |
| `save_per_epoch` | 99999999（未使用） | 相同 | `NetworkTrainer/network_trainer.py:26` |
| `eps_train_loss` | 0.01 | 0.01 | `NAS_29/train.py:68`；`Unet/train.py:56` |
| 学习率更新 | 每次迭代更新 | 每次迭代更新 | `NAS_29/train.py:69`；`Unet/train.py:57` |
| 损失函数 | `Loss()` | `Loss()` | `NAS_29/train.py:70`；`Unet/train.py:58` |
| 验证函数 | `online_evaluation` | `online_evaluation` | `NAS_29/train.py:71`；`Unet/train.py:59` |
| 设备 | `cuda:0` | `cuda:0` | `NetworkTrainer/network_trainer.py:95-108` |
| wandb | 离线，project `VNet` | 离线，project `VNet` | `NetworkTrainer/network_trainer.py:9-11,92` |

定义“每 epoch 500 次迭代”的加载器调用：

```python
# NAS_29/train.py:60-66（Unet/train.py:47-53 除名称外完全相同）
trainer.setting.train_loader, trainer.setting.val_loader = get_loader(
    train_bs=args.batch_size,                 # 2
    val_bs=1,
    train_num_samples_per_epoch=args.batch_size * 500,   # 1000 个样本
    val_num_samples_per_epoch=1,
    num_works=4)
```

训练停止由 `max_iter` 判断，而不是 `max_epoch`
（`NetworkTrainer/network_trainer.py:226-230,287`）：

```python
if (self.setting.max_iter is not None) and (self.log.iter >= self.setting.max_iter - 1):
    break
self.log.iter += 1
```

`log.iter` 从 −1 开始（`NetworkTrainer/network_trainer.py:51`），因此循环实际执行
第 0 … 79,999 次迭代，共 **80,000 次优化器 step**。

Checkpoint（`NetworkTrainer/network_trainer.py:346-363`）：

| 文件 | 写入时机 |
|---|---|
| `latest.pkl` | 每个 epoch |
| `best_train_loss.pkl` | 平均训练损失改善时 |
| `best_val_evaluation_index.pkl` | 验证指标改善时 |

NAS_29 的 checkpoint 约 168 MB；Unet 的 checkpoint 约 99 MB。

---

## 5. 损失函数

两个目录中的文件完全相同：
`NAS_29/loss.py:5-21` 与 `Unet/loss.py:5-21`（md5 相同）。

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

- 损失 = 归一化剂量上的**平均绝对误差（MAE）**，且仅在
  `possible_dose_mask > 0` 的体素上计算。
- 标签归一化 `dose / 70`：`DataLoader/dataloader_OpenKBP_C3D.py:75`。
- 预测值仅在推理/评估时乘以 70
  （`NAS_29/test.py:138`；`Unet/test.py:137`）。

---

## 6. 优化器与学习率调度器

### 6.1 训练脚本传入的内容

```python
# NAS_29/train.py:73-86
trainer.set_optimizer(optimizer_type='Adam',
                      args={'lr': 3e-4, 'weight_decay': 1e-4})
trainer.set_lr_scheduler(lr_scheduler_type='cosine',
                         args={'T_max': args.max_iter,   # 80000
                               'eta_min': 1e-7,
                               'last_epoch': -1})
```

Unet 的代码块完全相同，位于 `Unet/train.py:61-74`。

### 6.2 实际构造的内容

`NetworkTrainer/network_trainer.py:110-128`：

```python
if optimizer_type == 'Adam':
    if hasattr(self.setting.network, 'decoder') and hasattr(self.setting.network, 'encoder'):
        # 两个参数组，分别使用 lr_encoder / lr_decoder
        ...
    else:
        self.setting.optimizer = optim.Adam(self.setting.network.parameters(),
                                            lr=args['lr'],
                                            weight_decay=3e-5,
                                            betas=(0.9, 0.999),
                                            eps=1e-08,
                                            amsgrad=True)
```

`SearchedNet` 和 Unet 的 `Model` 顶层都没有 `.encoder`/`.decoder` 属性，
因此两者都走**单参数组**分支。

| 项目 | 两个模型的实际值 |
|---|---|
| 优化器 | Adam，1 个参数组（全部参数） |
| 学习率 | **3e-4** |
| Weight decay | **3e-5** —— `train.py` 传入的是 1e-4，但该分支硬编码为 3e-5 |
| Betas | (0.9, 0.999) |
| Epsilon | 1e-8 |
| AMSGrad | True |

若要让 `train.py` 传入的 1e-4 生效，需要把
`NetworkTrainer/network_trainer.py:125` 改为
`weight_decay=args['weight_decay']`。

调度器构造（`NetworkTrainer/network_trainer.py:138-144`）：

```python
self.setting.lr_scheduler = optim.lr_scheduler.CosineAnnealingLR(
    self.setting.optimizer,
    T_max=args['T_max'],        # 80000
    eta_min=args['eta_min'],    # 1e-7
    last_epoch=args['last_epoch'])
```

由于 `lr_scheduler_update_on_iter=True`，调度器在每次迭代后更新
（`NetworkTrainer/network_trainer.py:158-163,250`）。

---

## 7. 训练期间验证

两个模型都使用 `online_evaluation`，在患者 **201–240** 上验证，且不做 TTA。

| 项目 | 代码位置 |
|---|---|
| NAS_29 验证函数 | `NAS_29/online_evaluation.py:7-47` |
| Unet 验证函数 | `Unet/online_evaluation.py:7-47` |
| 每个 epoch 调用一次 | `NetworkTrainer/network_trainer.py:266-277,299-301` |

```python
# NAS_29/online_evaluation.py:8；Unet/online_evaluation.py:8
list_patient_dirs = ['.../OpenKBP_C3D/pt_' + str(i) for i in range(201, 241)]

# :31-33
prediction_B[np.logical_or(possible_dose_mask < 1, prediction_B < 0)] = 0
Dose_score = 70. * get_3D_Dose_dif(prediction_B.squeeze(0),
                                   gt_dose.squeeze(0),
                                   possible_dose_mask.squeeze(0))

# :47
return - np.mean(list_Dose_score)      # 越大越好
```

指标为 `possible_dose_mask > 0` 区域内的剂量 MAE（Gy）；当该负均值指标改善时，
训练器保存 `best_val_evaluation_index.pkl`。

---

## 8. 测试 / 推理 / 评估

| 项目 | NAS_29 | Unet |
|---|---|---|
| Checkpoint | `Output/NAS_29/best_val_evaluation_index.pkl`（`NAS_29/test.py:156`） | `Output/Unet/best_val_evaluation_index.pkl`（`Unet/test.py:155`） |
| 测试患者 | 241–340（`NAS_29/test.py:184`） | 241–340（`Unet/test.py:175`） |
| 代码中的 TTA 默认值 | **True**（`NAS_29/test.py:157`） | **False**（`Unet/test.py:156`） |
| 本次实际使用的 TTA | 默认 True | 通过 `Output/Unet/run_pipeline.sh` 显式传入 `--TTA True` |
| TTA 模式 | `[[], ['Z'], ['W'], ['Z','W']]`（`NAS_29/test.py:129-134`） | 相同（`Unet/test.py:128-133`） |
| 后处理 | 掩码外和负值置零，再乘 70（`NAS_29/test.py:136-138`） | 相同（`Unet/test.py:135-137`） |
| 预测文件 | `Prediction/<pt>/dose.nii.gz`（`NAS_29/test.py:140-146`） | 相同（`Unet/test.py:139-145`） |
| 指标代码 | `NAS_29/evaluate.py:11-48,51-99` | `Unet/evaluate.py:11-48,60-150`（额外接受 `list_patient_ids`） |

指标定义（两个 `evaluate.py` 相同）：

- **Dose score** = `possible_dose_mask > 0` 区域内预测与 GT 的 MAE
  （`NAS_29/evaluate.py:11-17`；`Unet/evaluate.py:11-17`）。
- **DVH score** = 所有“结构-指标”组合的绝对差的平均值：
  - 靶区：`D1`、`D95`、`D99`（`evaluate.py:20-30` / `:29-39`）；
  - OAR：`D_0.1cc`、`mean`（`evaluate.py:32-44` / `:41-53`）；
  - 结构：Brainstem、SpinalCord、RightParotid、LeftParotid、Esophagus、Larynx、
    Mandible、PTV70、PTV63、PTV56。

Unet 的 `evaluate.py` 还会额外打印 MSE 和各结构诊断信息，但返回的仍是相同的两个均值
（`Unet/evaluate.py:150`）。

---

## 9. 其他配置说明

1. **没有设置随机种子。** 数据集中的 `random.shuffle`
   （`DataLoader/dataloader_OpenKBP_C3D.py:126`）、数据增强中的 Python `random`
   以及 cuDNN 算法选择都会使训练结果不可完全复现。
2. **`eps_train_loss = 0.01`** 只是用于显示移动平均训练损失的 EMA 系数
   （`NetworkTrainer/network_trainer.py:165-170`），不是损失阈值。
3. **`max_epoch` / `save_per_epoch` 都是 99999999**；真正生效的停止条件是
   `max_iter=80000`。
4. **数据加载器的 `val_loader` 未被使用**；验证由 201–240 上的
   `online_evaluation` 完成。
5. **wandb 被强制设为离线模式**：`WANDB_MODE=offline`
   （`NetworkTrainer/network_trainer.py:9-11`）。
6. **Unet/train.py 在启动时会用 graphviz 画图**
   （`Unet/train.py:38-41`），因此 `PATH` 中必须有 `dot`。NAS_29 中对应代码块
   已被注释（`NAS_29/train.py:17-18,49-54`）。
7. **路径全部硬编码**为 `/home/zihanli/project/LENAS`（原为 `YOUR_ROOT`）。
8. **Unet 的 `Model` 是标准 3D U-Net**，使用 `InstanceNorm3d`、ReLU、三线性上采样和
   1×1 输出卷积；NAS_29 的 `SearchedNet` 使用 `best_genotype.pkl` 中保存的搜索
   `SearchedCell` 结构。

---

## 10. 命令

NAS_29：

```bash
cd RTDosePrediction/NAS_29
python geno.py                       # 生成 best_genotype.pkl
python train.py --batch_size 2 --list_GPU_ids 0 --max_iter 80000
python test.py --GPU_id 0
```

Unet：

```bash
cd RTDosePrediction/Unet
python train.py --batch_size 2 --list_GPU_ids 0 --max_iter 80000
python test.py --GPU_id 0 --TTA True
```

本次使用的 Unet 完整流水线（训练 → 推理 → 评估 → DVH 可视化）：

```bash
bash Experiment/RTDosePrediction/Output/Unet/run_pipeline.sh
```
