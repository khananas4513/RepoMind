import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-small-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


_MODEL = None


def get_model():
    global _MODEL
    if _MODEL is None:                      # load once, reuse for every repo
        _MODEL = SentenceTransformer(MODEL_NAME)
    return _MODEL


class CodeIndex:
    def __init__(self):
        self.model = get_model()
        self.index = None
        self.chunks = []

    @staticmethod
    def _doc_text(c) -> str:
        # Contextual header: the model sees WHERE the code lives and what it is.
        return f"File: {c.path}\n{c.kind}: {c.symbol}\n{c.text}"

    def build(self, chunks):
        self.chunks = chunks
        vecs = self.model.encode(
            [self._doc_text(c) for c in chunks],
            batch_size=32, normalize_embeddings=True, show_progress_bar=True,
        )
        vecs = np.asarray(vecs, dtype="float32")
        self.index = faiss.IndexFlatIP(vecs.shape[1])   # inner product == cosine (normalized)
        self.index.add(vecs)

    def search(self, query: str, k: int = 5):
        q = self.model.encode([QUERY_PREFIX + query], normalize_embeddings=True)
        scores, ids = self.index.search(np.asarray(q, dtype="float32"), k)
        return [(float(s), self.chunks[i]) for s, i in zip(scores[0], ids[0]) if i != -1]