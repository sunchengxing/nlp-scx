"""
LSTM 语言模型推理 - 文本生成
"""
import torch
import re

# ============ 加载模型 ============
model_path = 'lstm_wiki-text_model.pt'  # 改成你的模型路径
device = torch.device('cpu')

print(f'加载模型: {model_path}')
checkpoint = torch.load(model_path, map_location=device)
word2id = checkpoint['word2id']
id2word = checkpoint['id2word']
vocab_size = len(word2id)
print(f'词表大小: {vocab_size}')

# ============ 重建 LSTM 模型 ============
embedding = torch.nn.Embedding(vocab_size, 128).to(device)
# 输入门
input_gate_x = torch.nn.Linear(128, 256).to(device)
input_gate_h = torch.nn.Linear(256, 256).to(device)
# 遗忘门
forget_gate_x = torch.nn.Linear(128, 256).to(device)
forget_gate_h = torch.nn.Linear(256, 256).to(device)
# 候选记忆
candidate_x = torch.nn.Linear(128, 256).to(device)
candidate_h = torch.nn.Linear(256, 256).to(device)
# 输出门
output_gate_x = torch.nn.Linear(128, 256).to(device)
output_gate_h = torch.nn.Linear(256, 256).to(device)
# 最终输出
output_linear = torch.nn.Linear(256, vocab_size).to(device)

# 加载参数
embedding.load_state_dict(checkpoint['embedding'])
input_gate_x.load_state_dict(checkpoint['input_gate_x'])
input_gate_h.load_state_dict(checkpoint['input_gate_h'])
forget_gate_x.load_state_dict(checkpoint['forget_gate_x'])
forget_gate_h.load_state_dict(checkpoint['forget_gate_h'])
candidate_x.load_state_dict(checkpoint['candidate_x'])
candidate_h.load_state_dict(checkpoint['candidate_h'])
output_gate_x.load_state_dict(checkpoint['output_gate_x'])
output_gate_h.load_state_dict(checkpoint['output_gate_h'])
output_linear.load_state_dict(checkpoint['output_linear'])
print('模型加载完成')

# ============ 生成函数 ============
def generate(start_word, n_words, method='greedy', temperature=1.0, top_k=0):
    """
    生成文本
    :param start_word: 起始词
    :param n_words: 生成词数
    :param method: 'greedy' 贪心 | 'sample' 采样
    :param temperature: 采样温度（越高越随机）
    :param top_k: top-k 采样（0=不限制）
    """
    if start_word not in word2id:
        # 尝试正则分词后取第一个词
        tokens = re.findall(r'\w+|[^\w\s]', start_word)
        if tokens and tokens[0] in word2id:
            start_word = tokens[0]
        else:
            print(f'词 "{start_word}" 不在词表中，可用词: {list(word2id.keys())[:20]}...')
            return

    current_id = torch.tensor([[word2id[start_word]]], device=device)
    h_t = torch.zeros(1, 256, device=device)
    c_t = torch.zeros(1, 256, device=device)
    generated = [start_word]

    for step in range(n_words):
        x_input = embedding(current_id[:, 0])
        i = torch.sigmoid(input_gate_x(x_input) + input_gate_h(h_t))
        f = torch.sigmoid(forget_gate_x(x_input) + forget_gate_h(h_t))
        g = torch.tanh(candidate_x(x_input) + candidate_h(h_t))
        o = torch.sigmoid(output_gate_x(x_input) + output_gate_h(h_t))
        c_t = f * c_t + i * g
        h_t = o * torch.tanh(c_t)
        y_pred = output_linear(h_t)

        if method == 'greedy':
            next_id = y_pred.argmax(dim=1).item()
        else:  # sample
            logits = y_pred[0] / temperature
            if top_k > 0:
                top_values, top_ids = logits.topk(top_k)
                logits = torch.full_like(logits, float('-inf'))
                logits[top_ids] = top_values
            probs = torch.softmax(logits, dim=0)
            next_id = torch.multinomial(probs, 1).item()

        generated.append(id2word[next_id])
        current_id = torch.tensor([[next_id]], device=device)

    return " ".join(generated)


# ============ 测试生成 ============
print('\n' + '='*60)
print('LSTM 模型文本生成测试')
print('='*60)

test_words = ['The', 'In', 'He', 'It', 'They']

print('\n--- 贪心生成（确定性）---')
for word in test_words:
    text = generate(word, 30, method='greedy')
    if text:
        print(f'\n[{word}] → {text}')

print('\n--- 采样生成（随机性，temperature=0.8）---')
for word in test_words:
    text = generate(word, 30, method='sample', temperature=0.8)
    if text:
        print(f'\n[{word}] → {text}')

print('\n--- Top-K 采样（top_k=5，temperature=0.8）---')
for word in test_words:
    text = generate(word, 30, method='sample', temperature=0.8, top_k=5)
    if text:
        print(f'\n[{word}] → {text}')
