import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import torch
from collections import Counter
from config import WikiTextConfig
from dataset.datasets import WikiTextDataset
from model.model import RNNModel
from train.train import train


def prepare_data(config: WikiTextConfig):
    """
    数据预处理：加载 → 分词 → 低频过滤 → 构建词表 → reshape
    返回 x, y, word2id, id2word
    """
    # 1. 创建 dataset 实例（先用空数据，后面赋值）
    dataset = WikiTextDataset(torch.tensor([0]), config.seq_length)

    # 2. 加载原始文本
    raw_text = dataset.load_data()

    # 3. 分词
    tokens = re_tokenize(raw_text)

    # 4. 低频词过滤（词频 < 5 替换为 <unk>）
    token_freq = Counter(tokens)
    UNK_TOKEN = "<unk>"
    filtered_tokens = []
    for t in tokens:
        if token_freq[t] < 5:
            filtered_tokens.append(UNK_TOKEN)
        else:
            filtered_tokens.append(t)

    # 5. 构建词表
    vocab = sorted(set(filtered_tokens))
    word2id = {w: i for i, w in enumerate(vocab)}
    id2word = {i: w for i, w in enumerate(vocab)}
    print(f'词表大小: {len(vocab)}')

    # 6. 转 ids → tensor → reshape 成 (bs, -1)
    ids = [word2id[w] for w in filtered_tokens]
    data = torch.tensor(ids)
    bs = config.batch_size
    n_tokens = (len(data) // bs) * bs
    data = data[:n_tokens].reshape(bs, -1)

    # 7. 错位切片得到 x 和 y
    x = data[:, :-1]
    y = data[:, 1:]
    print(f'数据形状: x={x.shape}, y={y.shape}')

    return x, y, word2id, id2word


def re_tokenize(raw_text: str) -> list:
    """正则分词：英文按单词+标点切分"""
    import re
    return re.findall(r'\w+|[^\w\s]', raw_text)


def main():
    # 1. 加载配置
    config = WikiTextConfig()
    print(f'配置: epochs={config.num_epochs}, lr={config.learning_rate}, device={config.device}')

    # 2. 数据预处理
    x, y, word2id, id2word = prepare_data(config)
    vocab_size = len(word2id)

    # 3. 创建模型
    model = RNNModel(
        vocab_size=vocab_size,
        embedding_dim=config.embedding_dim,
        hidden_dim=config.hidden_dim
    )
    print(f'模型参数量: {sum(p.numel() for p in model.parameters()):,}')

    # 4. 训练
    train(model, x, y, config)

    # 5. 保存词表（推理时需要）
    torch.save({
        'word2id': word2id,
        'id2word': id2word,
    }, 'vocab.pt')
    print('词表已保存到 vocab.pt')


if __name__ == '__main__':
    main()
