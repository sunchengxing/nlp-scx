# -*- coding: utf-8 -*-
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from datasets import load_dataset
from collections import Counter
from Attention import Attention
from Attention import Attention
import numpy as np
from sklearn import metrics
import os
from torch._C import dtype


# Attention全连接文本分类任务 手写 Attention模型下的参数配置
class AttentionClassifyConfig(object):
    def __init__(self):
        # 超参数配置 最大词表大小
        self.MAX_VOCABULARY_SIZE = 5000
        # 句子最大长度
        self.MAX_SEQUENCE_LENGTH = 256
        # 词向量维度大小
        self.VOCA_EMBED_DIM = 128
        # 隐藏层维度大小
        self.HIDDEN_SIZE = 256
        # 批次大小
        self.BATCH_SIZE = 64
        # 训练轮数
        self.EPOCHS = 10
        # 学习率（梯度下降的步长）
        self.LEARNING_RATE = 0.001
        # 训练的设备
        self.DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # 训练所使用的数据集
        self.DATASET_NAME = "stanfordnlp/imdb"


# Attention全连接文本分类任务手写 Attention数据集构建
class AttentionClassifyDatasets(object):
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
class AttentionClassifyBuildVocabulary(object):
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
    ds = AttentionClassifyDatasets(data, vocab, config)
    return DataLoader(
        dataset = ds,
        batch_size=config.BATCH_SIZE,
        shuffle=shuffle
    )

# Attention 文本分类模型结构：
class AttentionClassifyModel(nn.Module):
    def __init__(self, vocab, config):
        super().__init__()
        self.vocab = vocab
        self.config = config
        self.embedding = nn.Embedding(len(vocab), config.VOCA_EMBED_DIM, padding_idx= 0)
        # Attention
        # 双向Attention需要乘以2
        self.lstm = nn.LSTM(
            input_size=config.VOCA_EMBED_DIM,
            hidden_size=config.HIDDEN_SIZE,
            num_layers=1,
            batch_first=True,
            bidirectional=True )
        self.attention = Attention(config.HIDDEN_SIZE * 2)
        self.classify_layer = nn.Linear(config.HIDDEN_SIZE * 2, 2)

    def forward(self, x):
         # x-shape [bs, t] -> [bs, t, e]
         embeddings = self.embedding(x)
         # 调用Attention [bs, t, e] -> [bs, t, h]
         outs, _ = self.lstm(embeddings)
         attention_out = self.attention.forward_within_lstm(outs)
         logits = self.classify_layer(attention_out)
         return logits

class AttentionClassifyTrain(object):
    def __init__(self, config, model):
        self.config = config
        self.model = model
        self.optimizer = optim.Adam(model.parameters(), lr=config.LEARNING_RATE)
        self.criterion = nn.CrossEntropyLoss()
        self.device = config.DEVICE

    def train(self, train_loader, valid_loader):
        for epoch in range(self.config.EPOCHS):
            self.model.train()
            for batch in train_loader:
                x = batch['x'].to(self.device)
                y = batch['y'].to(self.device)
                self.optimizer.zero_grad()
                pred = self.model(x)
                loss = self.criterion(pred, y)
                loss.backward()
                self.optimizer.step()
                print(f"epoch: {epoch} loss: {loss.item()}")

            self.model.eval()
            total_loss, total_correct, total_samples = 0, 0, 0
            with torch.no_grad():
                for batch in valid_loader:
                    x = batch['x'].to(self.device)
                    y = batch['y'].to(self.device)
                    pred = self.model(x)
                    loss = self.criterion(pred, y)
                    total_loss += loss.item()
                    total_correct += (pred.argmax(dim=1) == y).sum().item()
                    total_samples += len(y)
                acc = total_correct / total_samples
                print(f"Epoch {epoch} Val Loss: {total_loss / len(valid_loader):.4f} Acc: {acc:.4f}")
                if not hasattr(self, 'best_acc') or acc > self.best_acc:
                    self.best_acc = acc
                    torch.save(self.model.state_dict(), "attention_classify_best.pt")
                    print(f"  -> saved (best val_acc: {self.best_acc:.4f})")
# if __name__ == '__main__':
#     from datasets import load_dataset
#     config = AttentionClassifyConfig()
#     dataset = load_dataset(config.DATASET_NAME)
    # print(type(dataset))
    # print(dataset)
    # print("---第一条训练样本---")
    # vocab = AttentionClassifyBuildVocabulary(config, dataset['train'])
    # vocabulary = vocab.build_vocabulary()
    # my_dataset = AttentionClassifyDatasets(dataset['train'], vocabulary, config=config)
    # print(my_dataset[0])
    # print(dataset['train'][0])
    # print("---label---")
    # print(dataset['train'][0]['label'])
    # print("---text前100字---")
    # print(dataset['train'][0]['text'][:100])
    #
    # print(f"词表大小: {len(vocabulary)}")
    # print(f"'the' 的id: {vocabulary.get('the', 1)}")
    # print(f"'zzznonsense' 的id: {vocabulary.get('zzznonsense', 1)}")

    # data_loader = build_data_loader(dataset['train'], vocabulary, config, shuffle=True)
    # batch = next(iter(data_loader))
    # print(f"batch x shape: {batch['x'].shape}")
    # print(f"batch y shape: {batch['y'].shape}")
    # model = AttentionClassifyModel(vocabulary, config)
    # batch = next(iter(data_loader))
    # out = model(batch['x'])
    # print(f"output shape: {out.shape}")  # 应该是 [64, 2]
if __name__ == '__main__':
    config = AttentionClassifyConfig()
    dataset = load_dataset(config.DATASET_NAME)

    vocab_builder = AttentionClassifyBuildVocabulary(config, dataset['train'])
    vocabulary = vocab_builder.build_vocabulary()

    # 从train里切20%做验证集
    from sklearn.model_selection import train_test_split

    split = dataset['train'].train_test_split(test_size=0.2, seed=42)
    train_data = split['train']
    val_data = split['test']
    
    train_loader = build_data_loader(train_data, vocabulary, config, shuffle=True)
    val_loader = build_data_loader(val_data, vocabulary, config, shuffle=False)

    model = AttentionClassifyModel(vocabulary, config)
    trainer = AttentionClassifyTrain(config, model)
    trainer.train(train_loader, val_loader)