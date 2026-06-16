import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import torch
from config import WikiTextConfig
from model.model import RNNModel

# 推理不是模型，不需要训练
class Inference(object):

    def __init__(self, model_path: str):
        """
        加载模型
        :param model_path: 模型保存路径
        """
        super(Inference, self).__init__()
        self.device = torch.device(WikiTextConfig.device)
        # 读取保存模型的时候设计的数据结构得到最终的模型数据
        checkpoint = torch.load(model_path, map_location=self.device)
        # word2id 与 id2word
        self.word2id = checkpoint['word2id']
        self.id2word = checkpoint['id2word']
        vocab_size = len(checkpoint['word2id'])
        # 然后 checkpoint 里就有 embeddings、x_linear、h_linear、output_linear、word2id、id2word。
        self.model = RNNModel(
            vocab_size=vocab_size,
            embedding_dim=WikiTextConfig.embedding_dim,
            hidden_dim=WikiTextConfig.hidden_dim
        )
        self.model.embedding.load_state_dict(checkpoint['embeddings'])
        self.model.x_linear.load_state_dict(checkpoint['x_linear'])
        self.model.h_linear.load_state_dict(checkpoint['h_linear'])
        self.model.output_linear.load_state_dict(checkpoint['output_linear'])
        self.model.to(self.device)

    def generate(self, start_word: str, n_words: int):
        """
        生成文本
        :param start_word: 开始的单词
        :param n_words: 生成的单词个数
        :return: 生成的文本
        """
        start_word_id = self.word2id[start_word]
        h_t = torch.zeros(1, WikiTextConfig.hidden_dim, device=self.device)  # bs=1
        current_id = torch.tensor([[start_word_id]], device=self.device)  # shape: (1, 1)
        generated = [start_word]
        for step in range(n_words):
            # 1. 当前词过模型，跟训练时一模一样
            x_input = self.model.embedding(current_id[:, 0])  # (1, 128)
            h_t = torch.tanh(self.model.x_linear(x_input) + self.model.h_linear(h_t))
            y_pred = self.model.output_linear(h_t)  # (1, vocab_size)

            # 2. 选出下一个词（贪心：取分数最高的）
            next_id = y_pred.argmax(dim=1).item()  # 一个数字

            # 3. 记录这个词
            generated.append(self.id2word[next_id])

            # 4. 把这个词变成下一步的输入
            current_id = torch.tensor([[next_id]], device=self.device)
        # 循环结束后返回完整结果
        return " ".join(generated)


if __name__ == '__main__':
    import os
    # 从 inference/ 目录往上一层找到项目根目录
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_path = os.path.join(project_dir, 'outputs', 'rnn_wiki-text_model_gpu.pt')
    print(f'加载模型: {model_path}')
    inference = Inference(model_path)
    text = inference.generate('The', 50)
    print(text)