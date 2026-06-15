import sys, os
from datasets import load_dataset
import torch
import re
from config import WikiTextConfig


os.environ['HF_DATASETS_OFFLINE'] = '1'   # 强制离线，不联网
class WikiTextDataset(torch.utils.data.Dataset):
    """
    WikiText数据集
    """
    def __init__(self, data, seq_len):
        self.data = data
        self.seq_len = seq_len
        self.num_windows = (len(data) - seq_len) // seq_len
        self.data = self.data[:self.num_windows * seq_len]
        self.data = self.data.reshape(-1, seq_len)
        self.num_windows = self.data.shape[0]


    def load_data(self):
        dataset = load_dataset(
            WikiTextConfig.date_set_name,
            WikiTextConfig.data_set_name_version,
            cache_dir=WikiTextConfig.cache_dataset_dir  # 指定缓存目录
        )
        return "\n".join(dataset["train"]["text"])


    def split_tokens(self, raw_text) -> list:
        """
        分词
        :param raw_text:
        :return:
        """
        tokens = re.findall(r'\w+|[^\w\s]', raw_text)
        # 分词没有"绝对正确"，只有"对任务是否合理"：
        # 拿到分词结果之后构建词表 先去重复
        vocab = set(tokens)
        # 排序
        vocab = sorted(vocab)
        # 训练的时候依赖使用word2id
        word2id = {w: i for i, w in enumerate(vocab)}
        # 推理的时候需要依赖使用id2word
        id2word = {i: w for i, w in enumerate(vocab)}
        print(f'转为字典之后的大小为{len(word2id)}')
        ids = [word2id[w] for w in tokens]
        return ids, word2id, id2word

    def __getitem__(self, idx):
        x = self.data[idx, :-1]
        y = self.data[idx, 1:]
        return x, y

    def __len__(self):
        return self.num_windows

if __name__ == '__main__':
    print('hello world')