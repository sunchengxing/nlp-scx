# 技术方案 · 基于股吧数据的情感分析

> 版本：v2.0（新增路线C）
> 日期：2026-06-16

---

## 一、技术路线总览

本项目采用**三路线对比**策略，同一任务、同一数据、三种训练方式：

```
路线A：手写 Transformer（从零训练）     路线C：手写 Transformer（预训练+微调）     路线B：预训练 BERT 微调
┌──────────────────────┐         ┌──────────────────────┐         ┌──────────────────────┐
│ 手写 Transformer 编码器 │         │ 手写 Transformer 编码器 │         │ chinese-bert-wwm-ext  │
│ 随机初始化              │         │ 在大语料上 MLM 预训练   │         │ 加载预训练权重         │
│ HF 股吧数据训练         │         │ HF 股吧数据微调        │         │ HF 股吧数据微调        │
│ 同一套评估指标          │         │ 同一套评估指标          │         │ 同一套评估指标          │
└──────────────────────┘         └──────────────────────┘         └──────────────────────┘
            ↓                              ↓                              ↓
            └────────────────── 三路线对比结论 ───────────────────┘
```

### 1.1 为什么做三条路线

| | 路线A（从零训练） | 路线C（自预训练+微调） | 路线B（BERT 微调） |
|---|---|---|---|
| 架构 | 手写 Transformer | 手写 Transformer | 预训练 BERT |
| 预训练 | ❌ 无 | ✅ 自己在大语料上训 | ✅ 现成预训练权重 |
| 验证什么 | 基线（最差） | **预训练的价值（关键对照）** | 工业标准（最好） |

**核心对比：**
- **A vs C** → 同架构，有无预训练的差距 = **预训练的价值**
- **C vs B** → 同流程（预训练+微调），自训 vs 现成预训练 = **模型规模和语料规模的价值**
- **A vs B** → 最差 vs 最好 = **全部差距**

---

## 二、公共部分（两条路线共用）

### 2.1 数据流

```
HF 数据集加载
    ↓
数据清洗（去纯表情、纯标点、重复帖、广告）
    ↓
标签分布统计 + 抽样校验
    ↓
划分 train / validation / test
    ↓
┌─────────────────┐    ┌─────────────────┐
│ 路线A: 手写字词分词 │    │ 路线B: BERT Tokenizer │
│ 构建词表 + padding │    │ subword 分词 + padding │
└─────────────────┘    └─────────────────┘
```

### 2.2 数据源

| 数据 | 用途 | 来源 |
|------|------|------|
| HF baseline (8,520条标题+标签) | 训练 + 验证 | `HikasaHana/eastmoney_guba_title` |
| HF test (2,130条) | 测试集 | 同上 |
| 本地帖子 (743条) | 验证 + 舆情 | MySQL scx_guba_post |

### 2.3 数据划分

| 划分 | 来源 | 数量 |
|------|------|------|
| train | HF train 的 90% | ~7,668 |
| validation | HF train 的 10% | ~852 |
| test | HF test | 2,130 |
| 本地验证 | MySQL scx_guba_post | 743 |

### 2.4 评估指标（统一标准）

| 指标 | 说明 | 目标 |
|------|------|------|
| Accuracy | 整体准确率 | ≥ 70% |
| F1-macro | 三分类均衡 F1 | ≥ 0.65 |
| Precision(negative) | 看空精确率 | ≥ 0.70 |
| Recall(negative) | 看空召回率 | ≥ 0.65 |
| Confusion Matrix | 误判模式分析 | 必须 |

---

## 三、路线A：手写 Transformer

### 3.1 模型架构

```
Input (batch, seq_len)
  ↓
Embedding + Positional Encoding        ← 手写位置编码
  ↓
Multi-Head Self-Attention              ← 手写 Q/K/V + Scaled Dot-Product
  ↓
Add & Layer Norm                       ← 手写残差连接 + 层归一化
  ↓
Feed-Forward Network                   ← 2 层 MLP
  ↓
Add & Layer Norm
  ↓
... × N 层                             ← 堆叠 2 层（数据量小，不宜太深）
  ↓
Global Average Pooling                 ← 聚合序列表示
  ↓
Linear(hidden, 3)                      ← 三分类输出
  ↓
Softmax → 看多/看空/中性
```

### 3.2 模型配置

| 参数 | 值 | 说明 |
|------|-----|------|
| d_model | 128 | 数据量小，不需要太大 |
| n_heads | 4 | 多头注意力头数 |
| n_layers | 2 | 堆叠层数 |
| d_ff | 512 | FFN 中间维度 |
| max_len | 64 | 最大序列长度 |
| vocab_size | ~8,000 | 字级别词表（中文按字切分） |
| dropout | 0.3 | 防过拟合 |

### 3.3 分词策略

中文按**字级别**分词，不依赖外部 tokenizer：

```python
# "下周看涨" → ['下', '周', '看', '涨']
chars = list(text)
```

原因：
- 字级别词表小（~8,000），数据量 8,520 条够用
- 词级别需要分词器，且词表大（3万+），数据不够训
- 和 BERT 的 subword 分词形成对比

### 3.4 训练配置

| 参数 | 值 |
|------|-----|
| optimizer | Adam (lr=0.001) |
| scheduler | CosineAnnealingLR |
| epochs | 30 |
| batch_size | 32 |
| gradient clipping | 1.0 |
| early stopping | patience=5 |

### 3.5 预期效果

⚠️ **数据量严重不足，预期效果较差。**

Transformer 从零训练需要**百万级**数据，8,520 条远远不够。这是有意为之——**亲身验证数据量不足时从零训练的局限性。**

---

## 四、路线B：预训练 BERT 微调

### 4.1 模型架构

```
Input (batch, seq_len)
  ↓
chinese-bert-wwm-ext (预训练权重)       ← 冻结或微调
  ↓ [CLS] token 表示
Linear(768, 3)                          ← 只训练分类头
  ↓
Softmax → 看多/看空/中性
```

### 4.2 模型选择

| 优先级 | 模型 | 参数量 | 说明 |
|--------|------|--------|------|
| ⭐⭐⭐ | `hfl/chinese-bert-wwm-ext` | ~110M | 中文全词掩码，金融文本基础好 |
| ⭐⭐ | `bert-base-chinese` | ~110M | 官方中文 BERT |
| ⭐ | `yiyanghkust/finbert-tone` | ~110M | 金融领域专用（如有中文版） |

### 4.3 Tokenizer

使用 BERT 配套 tokenizer（WordPiece subword 分词）：

```python
from transformers import BertTokenizer
tokenizer = BertTokenizer.from_pretrained('hfl/chinese-bert-wwm-ext')
# "下周看涨" → ['下', '周', '看', '涨']  ← 中文基本一字一 token
```

### 4.4 训练配置

| 参数 | 值 | 说明 |
|------|-----|------|
| optimizer | AdamW (lr=2e-5) | 微调用小学习率 |
| scheduler | linear warmup + decay | 标准 BERT 微调策略 |
| epochs | 3-5 | 微调不宜过多，容易过拟合 |
| batch_size | 16 | 显存允许可调 32 |
| weight_decay | 0.01 | 正则化 |
| early stopping | patience=2 | 小数据集容易过拟合 |
| max_length | 64 | 根据标题长度分布确定 |

### 4.5 训练框架

使用 HuggingFace Trainer：

```python
from transformers import Trainer, TrainingArguments

training_args = TrainingArguments(
    output_dir='./results',
    num_train_epochs=5,
    per_device_train_batch_size=16,
    learning_rate=2e-5,
    weight_decay=0.01,
    evaluation_strategy='epoch',
    save_strategy='epoch',
    load_best_model_at_end=True,
    metric_for_best_model='f1_macro',
)
```

### 4.6 预期效果

- F1-macro: 0.75-0.85（参考同类任务基线）
- 训练时间: Colab T4 约 10-20 分钟

---

## 五、路线C：手写 Transformer 预训练 + 微调

### 5.1 核心思路

路线C 和路线A 用**完全相同的 Transformer 架构**，但增加一个预训练阶段：

```
阶段1：在大语料上做 MLM 预训练（学习通用中文语义）
    ↓ 保存预训练权重
阶段2：在股吧数据上微调（学习金融情感规则）
```

### 5.2 预训练任务：Masked Language Model (MLM)

和 BERT 一样的预训练方式——随机遮住 15% 的字，让模型预测被遮住的字：

```
原始:   "下周看涨，继续持有"
遮盖:   "下[MASK]看[MASK]，继续[MASK]有"
目标:   模型预测 [MASK]=周, 涨, 持

损失:   CrossEntropy(预测, 被遮住的真实字)
```

**为什么 MLM 能学到语义？**

模型要猜被遮住的字，就必须理解上下文：
- "下.getMonth看涨" → 必须理解"下周"是时间词
- "暴跌好" → 必须理解"暴跌"和"好"的语义关系
- 学习过程中，Transformer 的 self-attention 自然学会了词与词之间的关联

### 5.3 预训练语料

| 语料 | 大小 | 来源 | 推荐度 |
|------|------|------|--------|
| 中文 Wikipedia | ~1G 文本 | HuggingFace `wikimedia/wikipedia` | ⭐⭐⭐ |
| 新闻资讯 | 数G | 公开中文新闻数据集 | ⭐⭐ |
| BERT 原始中文语料 | ~3G | 中文维基+新闻+百科 | ⭐⭐⭐ |

**推荐先用中文 Wikipedia**——获取简单，质量高，足够验证预训练的效果。

### 5.4 预训练配置

| 参数 | 值 | 说明 |
|------|-----|------|
| 模型 | 路线A 同款 Transformer | d_model=128, 2层, 4头 |
| 预训练任务 | MLM (mask 15%) | 和 BERT 一样的遮盖比例 |
| 预训练数据 | 中文 Wikipedia (~1G) | 百万级句子 |
| 预训练 epochs | 10-20 | Colab T4 约 2-4 小时 |
| batch_size | 64 | 预训练用大 batch |
| optimizer | Adam (lr=1e-4) | 预训练学习率稍大 |
| max_len | 128 | 预训练用稍长序列 |

### 5.5 微调配置

| 参数 | 值 | 说明 |
|------|-----|------|
| 加载权重 | 预训练阶段的 checkpoint | 只加载 Transformer 编码器权重 |
| 微调 epochs | 5-10 | 比路线A 少，因为已经有好的初始化 |
| optimizer | Adam (lr=5e-4) | 微调学习率比预训练小 |
| batch_size | 32 | 和路线A 一致 |
| early stopping | patience=5 | 和路线A 一致 |

### 5.6 预期效果

- 应该**显著优于路线A**（预训练赋予了通用中文能力）
- 可能**不如路线B**（模型规模和语料规模都不如 BERT）
- F1-macro 预估: 0.55-0.70

---

## 六、三路线对比实验设计

### 5.1 控制变量

| 控制项 | 说明 |
|--------|------|
| 数据集 | 完全相同的 train/val/test 划分 |
| 评估指标 | 完全相同的指标计算方式 |
| 测试集 | 完全相同的 2,130 条测试数据 |
| 本地验证 | 完全相同的 743 条帖子标题 |

### 5.2 实验变量

| 变量 | 路线A | 路线B |
|------|-------|-------|
| 模型架构 | 手写 Transformer | 预训练 BERT |
| 参数初始化 | 随机初始化 | 预训练权重 |
| 分词方式 | 字级别手写 | BERT Tokenizer |
| 训练轮次 | 30 | 3-5 |
| 训练框架 | 手写 PyTorch 循环 | HuggingFace Trainer |

### 5.3 对比维度

| 维度 | 要回答的问题 |
|------|-------------|
| 准确率 | 微调比从零训练高多少？ |
| 训练效率 | 达到相近效果需要多少轮/时间？ |
| 数据依赖 | 数据量不足时各自的退化程度？ |
| 错误模式 | 两者的混淆矩阵差异是什么？ |

---

## 六、三路线对比实验设计

### 6.1 控制变量

| 控制项 | 说明 |
|--------|------|
| 数据集 | 完全相同的 train/val/test 划分 |
| 评估指标 | 完全相同的指标计算方式 |
| 测试集 | 完全相同的 2,130 条测试数据 |
| 本地验证 | 完全相同的 743 条帖子标题 |

### 6.2 实验变量

| 变量 | 路线A | 路线C | 路线B |
|------|-------|-------|-------|
| 模型架构 | 手写 Transformer | 手写 Transformer | 预训练 BERT |
| 参数初始化 | 随机初始化 | **预训练权重** | 预训练权重 |
| 预训练语料 | ❌ 无 | 中文 Wikipedia | 百G级语料（BERT自带） |
| 模型参数量 | ~2M | ~2M | ~110M |
| 微调轮次 | 30 | 5-10 | 3-5 |

### 6.3 对比维度

| 对比 | 要回答的问题 | 预期结论 |
|------|-------------|---------|
| **A vs C** | 同架构，预训练有多大帮助？ | C 显著优于 A |
| **C vs B** | 自预训练 vs 工业预训练的差距？ | B 优于 C（规模碾压） |
| **A vs B** | 最差 vs 最好的全量差距？ | 差距最大 |

### 6.4 预期结果

| 指标 | 路线A | 路线C | 路线B |
|------|-------|-------|-------|
| Accuracy | 45-55% | 60-70% | 75-85% |
| F1-macro | 0.30-0.45 | 0.55-0.70 | 0.75-0.85 |
| 训练时间(Colab) | 5-10min | 2-4h(预训练)+5min(微调) | 10-20min |

---

## 七、工程结构

```
08-基于股吧数据的情感分析与舆情分析预演/
├── docs/
│   ├── PRD-情感分析与舆情分析.md
│   └── technical-plan.md              ← 本文档
├── config/
│   ├── __init__.py
│   └── config.py                      ← 超参数配置（含路线A和B的参数）
├── dataset/
│   ├── __init__.py
│   └── datasets.py                    ← HF 数据加载 + 数据清洗 + 本地 DB 读取
├── model/
│   ├── __init__.py
│   ├── transformer_model.py           ← 路线A/C: 手写 Transformer（含 MLM 头）
│   └── bert_model.py                  ← 路线B: BERT 微调封装
├── train/
│   ├── __init__.py
│   ├── pretrain_transformer.py        ← 路线C 预训练（MLM）
│   ├── train_transformer.py           ← 路线A/C 分类训练逻辑
│   └── train_bert.py                  ← 路线B 训练逻辑（Trainer）
├── evaluate/
│   ├── __init__.py
│   └── metrics.py                     ← 统一评估指标计算
├── inference/
│   ├── __init__.py
│   └── predict.py                     ← 批量预测 + 本地帖子推理
├── analysis/
│   ├── __init__.py
│   └── sentiment.py                   ← 加权舆情计算
├── main.py                            ← 入口文件
└── script/
    ├── train_transformer_colab.py     ← 路线A 单文件（Colab用）
    ├── pretrain_transformer_colab.py  ← 路线C 预训练单文件（Colab用）
    └── train_bert_colab.py            ← 路线B 单文件（Colab用）
```

---

## 八、执行计划

| 步骤 | 内容 | 交付物 |
|------|------|--------|
| 1 | HF 数据集加载 + EDA | 数据分布报告 |
| 2 | 数据清洗 + 划分 | 清洗后数据 |
| 3 | 路线A：手写 Transformer 从零训练 | 模型 + 评估结果 |
| 4 | 路线C：手写 Transformer 预训练 + 微调 | 预训练权重 + 微调模型 + 评估结果 |
| 5 | 路线B：BERT 微调 | 模型 + 评估结果 |
| 6 | 三路线对比分析 | 对比报告 |
| 7 | 本地帖子验证 + 舆情指标 | 舆情分析报告 |

---

## 九、风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| 路线A 效果很差 | 正常预期，本身就是对照组 | 不用担心，差才是有价值的对比 |
| 路线C 预训练耗时 | Colab 可能断线 | 分多次跑，保存 checkpoint |
| 路线C 预训练效果不够 | 小模型+小语料不如 BERT | 正常，这是规模差异，不是失败 |
| HF 标注质量存疑 | 三条路线都受影响 | 抽样 50 条校验 |
| 数据量少，BERT 也过拟合 | 路线B 效果打折 | 早停 + weight_decay + 数据增强 |
| 本地帖子领域不同 | 验证效果打折 | 作为参考，不作为主要评判依据 |
| Colab 断线 | 训练中断 | 保存 checkpoint + Google Drive |
