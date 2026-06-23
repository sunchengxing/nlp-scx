# -*- coding: utf-8 -*-
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from datasets import load_dataset
from collections import Counter
from PositionalEncoding import PositionalEncoding


# Transformer全连接文本分类任务 手写 Transformer模型下的参数配置
class TransformerClassifyConfig(object):
    def __init__(self):
        # 超参数配置 最大词表大小
        self.MAX_VOCABULARY_SIZE = 20000
        # 句子最大长度
        self.MAX_SEQUENCE_LENGTH = 256
        # 词向量维度大小
        self.VOCA_EMBED_DIM = 128
        # 隐藏层维度大小
        self.HIDDEN_SIZE = 256
        # 批次大小
        self.BATCH_SIZE = 64
        # 训练轮数
        self.EPOCHS = 3
        # 学习率（梯度下降的步长）
        self.LEARNING_RATE = 0.001
        # 训练的设备
        self.DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # 训练所使用的数据集
        self.DATASET_NAME = "stanfordnlp/imdb"
        # Transformer参数配置（超参数配置）
        # 模型的维度
        self.D_MODEL = 128
        # 多头注意力的头数  # 必须能整除 D_MODEL
        self.NUM_HEADS = 4
        # 编码器层数
        self.NUM_LAYERS = 2


# Transformer全连接文本分类任务手写 Transformer数据集构建
class TransformerClassifyDatasets(object):
    def __init__(self, data, vocab, config):
        """
        data  huggingface数据集
        vocab 词表大小
        config 配置
        """
        self.data = data
        self.vocab = vocab
        self.config = config
        pass

    def __getitem__(self, item):
        """
        获取数据集的item
        :param item:
        :return: 返回第item个文本的向量
        """
        item_ = self.data[item]
        # 1. 取出原始文本和标签
        train_data_text, train_data_label = item_['text'], item_['label']
        # 2. 文本转小写，按空格分词（简单tokenize） 做tokenizer
        train_text_item_tokens = train_data_text.lower().split(" ")
        # 3. 每个词用 word2id 查 id，查不到的词用 <UNK> id=1
        tokens_ids_ = [self.vocab.get(token, 1) for token in train_text_item_tokens]
        # 4. 截断：超过 MAX_SEQ_LEN 的截掉
        tokens_ids_ = tokens_ids_[ : self.config.MAX_SEQUENCE_LENGTH]
        # 5. 补齐：不足 MAX_SEQ_LEN 的补 <PAD> id=0
        tokens_ids_ = tokens_ids_ + [0] * (self.config.MAX_SEQUENCE_LENGTH - len(tokens_ids_))
        # 6. 转成 tensor 返回 {'x': LongTensor, 'y': LongTensor}
        return {'x' : torch.LongTensor(tokens_ids_), 'y' : torch.tensor(train_data_label, dtype=torch.long)}

    def __len__(self):
        """
        获取数据集的长度
        :return:
        """
        return len(self.data)


# 构建词表
class TransformerClassifyBuildVocabulary(object):
    def __init__(self,config, train_data):
        self.config = config
        self.train_data = train_data

    def build_vocabulary(self):
        """
        构建词表
        :return:
        """
        counter = Counter()
        train_data = self.train_data
        for data in train_data:
            tokens = data['text'].lower().split(" ")
            counter.update(tokens)

        vocab = {'<PAD>' : 0, '<UNK>' : 1}
        for token, _ in counter.most_common(self.config.MAX_VOCABULARY_SIZE - 2):
            vocab[token] = len(vocab)
        return vocab

    def __len__(self):
        return len(self.train_data)


# 无状态函数可以直接使用模块化构建不需要单独写一个类
def build_data_loader(data, vocab, config,  shuffle):
    ds = TransformerClassifyDatasets(data, vocab, config)
    return DataLoader(
        dataset = ds,
        batch_size=config.BATCH_SIZE,
        shuffle=shuffle
    )

# Transformer 文本分类模型结构：
class TransformerClassifyModel(nn.Module):
    def __init__(self, vocab, config):
        super().__init__()
        self.embedding = nn.Embedding(len(vocab), config.D_MODEL, padding_idx=0)
        self.pe = PositionalEncoding(config.D_MODEL)
        self.encoder = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=config.D_MODEL,
                nhead=config.NUM_HEADS,
                batch_first=True
            ),
            num_layers=config.NUM_LAYERS
        )
        self.classify = nn.Linear(config.D_MODEL, 2)
        self.dropout = nn.Dropout(0.3)

    def forward(self, x):
        # x shape: [batch, seq_len]

        # 1. Embedding → [batch, seq_len, d_model]
        x = self.embedding(x)

        # 2. PE → [batch, seq_len, d_model]
        x = self.pe(x)

        # 3. Encoder → [batch, seq_len, d_model]
        x = self.encoder(x)

        # 4. mean pooling：把 seq_len 维度平均掉 → [batch, d_model]
        x = x.mean(dim=1)

        # 5. dropout + Linear → [batch, 2]
        x = self.dropout(x)
        x = self.classify(x)
        return x

class TransformerClassifyTrain(object):
    def __init__(self, config, model):
        self.config = config
        self.model = model
        self.optimizer = optim.Adam(model.parameters(), lr=config.LEARNING_RATE)
        self.criterion = nn.CrossEntropyLoss()
        self.device = config.DEVICE

    def evaluate(self, model, loader):
        model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for batch in loader:
                x = batch['x'].to(self.device)
                y = batch['y'].to(self.device)
                pred = model(x).argmax(dim=1)
                correct += (pred == y).sum().item()
                total += y.size(0)
        return correct / total

    def train(self, model, train_loader, val_loader, config):
        for epoch in range(config.EPOCHS):  # epoch 循环
            model.train()
            total_loss = 0  # 每轮重置
            for batch in train_loader:
                x = batch['x'].to(self.device)
                y = batch['y'].to(self.device)
                self.optimizer.zero_grad()
                out = model(x)
                loss = self.criterion(out, y)
                loss.backward()
                self.optimizer.step()
                total_loss += loss.item()

            acc = self.evaluate(model, val_loader)  # 每轮结束验证
            print(f"Epoch {epoch + 1} | loss: {total_loss / len(train_loader):.4f} | val_acc: {acc:.4f}")
            if not hasattr(self, 'best_acc') or acc > self.best_acc:
                self.best_acc = acc
                torch.save(model.state_dict(), "transformer_classify_best.pt")
                print(f"  -> saved (best val_acc: {self.best_acc:.4f})")


if __name__ == '__main__':
    config = TransformerClassifyConfig()
    dataset = load_dataset(config.DATASET_NAME)

    vocab_builder = TransformerClassifyBuildVocabulary(config, dataset['train'])
    vocabulary = vocab_builder.build_vocabulary()

    # 从train里切20%做验证集
    from sklearn.model_selection import train_test_split

    split = dataset['train'].train_test_split(test_size=0.2, seed=42)
    train_data = split['train']
    val_data = split['test']
    
    train_loader = build_data_loader(train_data, vocabulary, config, shuffle=True)
    val_loader = build_data_loader(val_data, vocabulary, config, shuffle=False)
    test_loader = build_data_loader(dataset['test'], vocabulary, config, shuffle=False)

    model = TransformerClassifyModel(vocabulary, config)
    model.to(config.DEVICE)
    trainer = TransformerClassifyTrain(config, model)
    trainer.train(model, train_loader, val_loader, config)

    # 加载最优权重，跑测试集
    model.load_state_dict(torch.load("transformer_classify_best.pt", map_location=config.DEVICE))
    test_acc = trainer.evaluate(model, test_loader)
    print(f"\nTest Acc: {test_acc:.4f}")