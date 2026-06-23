import torch


class Config:
    # 数据配置
    DATASET_NAME =  "Salesforce/wikitext"
    DATASET_VERSION = "wikitext-2-raw-v1"
    MAX_VOCABULARY_SIZE = 20000
    SEQ_LEN = 128

    # 模型配置
    EMBED_DIM = 128
    HIDDEN_SIZE = 256
    NUM_LAYERS = 2
    DROPOUT = 0.3

    # 训练
    BATCH_SIZE = 64
    EPOCH = 10
    LEARNING_RATE = 0.001
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    # 生成
    MAX_GEN_LEN = 100
    TOP_K = 5
    TEMPERATURE = 1.0
