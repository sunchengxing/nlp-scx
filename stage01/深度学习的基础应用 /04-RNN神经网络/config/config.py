from dataclasses import dataclass

@dataclass
class WikiTextConfig:
    date_set_name : str = "Salesforce/wikitext"
    data_set_name_version : str = "wikitext-2-raw-v1"
    batch_size : int = 75
    seq_length : int = 20
    num_epochs : int = 10
    embedding_dim : int = 128
    hidden_dim : int = 256
    learning_rate : float = 0.01
    device : str = "cpu"
    model_save_path : str = "wikitext-rnn.pt"
    cache_dataset_dir : str = "/Users/scx/.cache/huggingface/datasets"
