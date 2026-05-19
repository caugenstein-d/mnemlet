"""Local embedding model via onnxruntime (all-MiniLM-L6-v2)."""

import os
from pathlib import Path
from typing import Optional

import numpy as np

MODEL_URL = "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/onnx/model.onnx"
MODEL_FILENAME = "all-MiniLM-L6-v2.onnx"
EMBEDDING_DIM = 384


class MnemletEmbedding:
    """Local embedding model using onnxruntime."""

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        self.cache_dir = cache_dir or Path.home() / ".mnemlet" / "models"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.cache_dir / MODEL_FILENAME
        self._model = None
        self._tokenizer = None
        self._ensure_model()

    def _ensure_model(self) -> None:
        """Download model if not cached."""
        if not self.model_path.exists():
            self._download_model()

    def _download_model(self) -> None:
        """Download the onnx model from Hugging Face."""
        import urllib.request

        print(f"Downloading embedding model to {self.model_path}...")
        urllib.request.urlretrieve(MODEL_URL, self.model_path)
        print("Download complete.")

    @property
    def model(self):
        """Lazy-load the onnx model."""
        if self._model is None:
            import onnxruntime as ort

            self._model = ort.InferenceSession(
                str(self.model_path),
                providers=["CPUExecutionProvider"],
            )
        return self._model

    @property
    def tokenizer(self):
        """Lazy-load the tokenizer."""
        if self._tokenizer is None:
            from tokenizers import Tokenizer

            self._tokenizer = Tokenizer.from_pretrained("bert-base-uncased")
        return self._tokenizer

    def embed(self, text: str) -> list[float]:
        """Embed a single text and return a 384-dim vector."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts using the ONNX model with mean pooling."""
        session = self.model
        tokenizer = self.tokenizer
        input_names = [inp.name for inp in session.get_inputs()]
        results = []

        for text in texts:
            encoded = tokenizer.encode(text)
            max_len = 512
            ids = encoded.ids[:max_len]
            am = encoded.attention_mask[:max_len]

            arr_input_ids = np.array([ids], dtype=np.int64)
            arr_attention_mask = np.array([am], dtype=np.int64)
            arr_token_type_ids = np.zeros((1, len(ids)), dtype=np.int64)

            feed = {}
            for name in input_names:
                if "input_ids" in name or name == "input_ids":
                    feed[name] = arr_input_ids
                elif "attention_mask" in name or name == "attention_mask":
                    feed[name] = arr_attention_mask
                elif "token_type_ids" in name or name == "token_type_ids":
                    feed[name] = arr_token_type_ids

            outputs = session.run(None, feed)
            token_embeddings = outputs[0]  # (1, seq_len, hidden_dim)

            mask = np.expand_dims(arr_attention_mask, axis=-1)
            masked = token_embeddings * mask
            summed = masked.sum(axis=1)
            counts = np.maximum(mask.sum(axis=1), 1e-9)
            mean_pooled = summed / counts

            vec = mean_pooled[0]
            norm = np.sqrt((vec * vec).sum())
            if norm > 0:
                vec = vec / norm

            results.append(vec.tolist())

        return results

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(ai * bi for ai, bi in zip(a, b))
        return max(0.0, min(1.0, dot))

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text."""
        return max(1, len(text) // 4)
