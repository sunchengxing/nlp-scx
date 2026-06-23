import json

import split_tokens as st
import pandas as pd
import os


class vocab_tool:

    def build_vocab(self,train_csv: str, token2ids_path: str, label2ids_path: str) -> tuple[dict[str, int], dict[str, int]]:
        df = pd.read_csv(train_csv, sep="\t", header=None, names=["text", "label"])

        token2cnt, label2cnt, text_lens = {}, {}, []
        for _, row in df.iterrows():
            text, label = row["text"].strip(), row["label"].strip()
            tokens = st.SplitTokensTools(text)
            for t in tokens:
                token2cnt[t] = token2cnt.get(t, 0) + 1
            label2cnt[label] = label2cnt.get(label, 0) + 1
            text_lens.append(len(tokens))

        print(f"总Token数量: {len(token2cnt)}")
        print(f"总标签数量: {len(label2cnt)}  {label2cnt}")

        # 可视化 token 频次分布（只看出现 <10 次的）
        # _plot_distribution([v for v in token2cnt.values() if v < 10], "Token Count Distribution", "Token Count")
        # _plot_distribution(text_lens, "Text Length Distribution", "Text Length")

        # 过滤低频 token 构建词典
        token2ids = {"<PAD>": 0, "<UNK>": 1}
        for token, cnt in token2cnt.items():
            if cnt >= 3:
                token2ids[token] = len(token2ids)

        label2ids = {label: idx for idx, label in enumerate(label2cnt)}

        self.save_json(token2ids_path, token2ids)
        self.save_json(label2ids_path, label2ids)
        return token2ids, label2ids

    def save_json(json_file, obj):
        os.makedirs(os.path.dirname(json_file), exist_ok=True)
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)

    def load_json(json_file):
        with open(json_file, "r", encoding="utf-8") as f:
            return json.load(f)