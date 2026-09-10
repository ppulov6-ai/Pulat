"""Local multilingual E5 embeddings from the official ONNX export.

Model rules (prefixes, masked mean pooling, L2, at most 512 tokens):
https://huggingface.co/intfloat/multilingual-e5-small#usage

Nothing is downloaded or loaded at import/construction time. The model directory
must contain model.onnx and tokenizer.json from intfloat/multilingual-e5-small.
"""
from __future__ import annotations

from pathlib import Path
from threading import RLock

import numpy as np



class LocalE5Embeddings:
    """Retrieval: query uses ``query: ``, documents use ``passage: ``.

    For RAGAS AnswerRelevancy use ``as_query_embeddings()``: its original and
    generated questions both need the symmetric ``query: `` prefix.
    """

    model = "intfloat/multilingual-e5-small"

    def __init__(self, model_dir: str | Path, batch_size: int = 8, n_threads: int = 4):
        if batch_size < 1 or n_threads < 1:
            raise ValueError("batch_size and n_threads must be positive")
        self.model_dir = Path(model_dir).expanduser().resolve()
        self.batch_size = batch_size
        self.n_threads = n_threads
        self._session = None
        self._tokenizer = None
        self._lock = RLock()

    def _ensure_loaded(self) -> None:
        with self._lock:
            if self._session is not None:
                return
            from tokenizers import Tokenizer
            import onnxruntime as ort

            model_file = self.model_dir / "model.onnx"
            tokenizer_file = self.model_dir / "tokenizer.json"
            for file in (model_file, tokenizer_file):
                if not file.is_file():
                    raise FileNotFoundError(f"Required local model file not found: {file}")
            tokenizer = Tokenizer.from_file(str(tokenizer_file))
            pad_token = "<pad>"
            pad_id = tokenizer.token_to_id(pad_token)
            if pad_id is None:
                pad_token = "[PAD]"
                pad_id = tokenizer.token_to_id(pad_token)
            if pad_id is None:
                raise ValueError("Tokenizer has no supported padding token")
            tokenizer.enable_truncation(max_length=512, direction="right")
            tokenizer.enable_padding(pad_id=pad_id, pad_token=pad_token, direction="right")

            options = ort.SessionOptions()
            options.intra_op_num_threads = self.n_threads
            options.inter_op_num_threads = 1
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            session = ort.InferenceSession(
                str(model_file), sess_options=options, providers=["CPUExecutionProvider"]
            )
            supported = {"input_ids", "attention_mask", "token_type_ids"}
            unexpected = {item.name for item in session.get_inputs()} - supported
            if unexpected:
                raise ValueError(f"Unsupported ONNX inputs: {sorted(unexpected)}")
            output_names = {item.name for item in session.get_outputs()}
            if "last_hidden_state" not in output_names:
                raise ValueError("ONNX export must expose last_hidden_state for mean pooling")
            self._tokenizer = tokenizer
            self._session = session

    def _embed(self, texts: list[str], prefix: str) -> list[list[float]]:
        if not texts:
            return []
        if any(not isinstance(text, str) for text in texts):
            raise TypeError("All embedding inputs must be strings")
        self._ensure_loaded()
        vectors = []
        # LangChain's asynchronous methods may call this object from threads.
        with self._lock:
            for start in range(0, len(texts), self.batch_size):
                batch = [prefix + text for text in texts[start:start + self.batch_size]]
                encoded = self._tokenizer.encode_batch(batch, add_special_tokens=True)
                arrays = {
                    "input_ids": np.asarray([item.ids for item in encoded], dtype=np.int64),
                    "attention_mask": np.asarray(
                        [item.attention_mask for item in encoded], dtype=np.int64
                    ),
                    "token_type_ids": np.asarray(
                        [item.type_ids for item in encoded], dtype=np.int64
                    ),
                }
                feed = {}
                for item in self._session.get_inputs():
                    if item.type not in {"tensor(int64)", "tensor(int32)"}:
                        raise ValueError(f"Unsupported ONNX input type: {item.type}")
                    dtype = np.int32 if item.type == "tensor(int32)" else np.int64
                    feed[item.name] = arrays[item.name].astype(dtype, copy=False)
                hidden = self._session.run(["last_hidden_state"], feed)[0]
                mask = arrays["attention_mask"].astype(np.float32)
                if hidden.ndim != 3 or hidden.shape[:2] != mask.shape:
                    raise ValueError(f"Unexpected token embedding shape: {hidden.shape}")
                # The official example includes all non-padding tokens, including
                # special tokens, in the masked arithmetic mean.
                hidden = np.asarray(hidden, dtype=np.float32)
                hidden = np.where(mask[..., None].astype(bool), hidden, 0.0)
                pooled = hidden.sum(axis=1) / mask.sum(axis=1, keepdims=True)
                norms = np.linalg.norm(pooled, axis=1, keepdims=True)
                if not np.isfinite(pooled).all() or np.any(norms <= 0):
                    raise ValueError("ONNX model produced invalid embedding vectors")
                vectors.extend((pooled / norms).tolist())
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "query: ")[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "passage: ")

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "query: ")

    def as_query_embeddings(self) -> QuerySimilarityEmbeddings:
        """Share this model/session with a symmetric similarity adapter."""
        return QuerySimilarityEmbeddings(self)


class QuerySimilarityEmbeddings:
    """RAGAS adapter: original and generated questions use identical prefixes."""

    model = "intfloat/multilingual-e5-small"

    def __init__(self, encoder: LocalE5Embeddings):
        self.encoder = encoder

    def embed_query(self, text: str) -> list[float]:
        return self.encoder.embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.encoder.embed_queries(texts)
