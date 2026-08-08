import math
import re
import numpy as np
from collections import Counter
from typing import List, Dict, Optional

# Try to use sentence-transformers for neural embeddings (massive quality upgrade)
try:
    from sentence_transformers import SentenceTransformer
    _HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    _HAS_SENTENCE_TRANSFORMERS = False
    print("[WARNING] sentence-transformers not installed. Falling back to TF-IDF embeddings.")
    print("[WARNING] Install with: pip install sentence-transformers")


class TextEmbedder:
    """
    Neural Text Embedder using sentence-transformers (all-MiniLM-L6-v2).
    
    Upgraded from TF-IDF to neural embeddings for dramatically better semantic
    understanding. Neural embeddings capture meaning, synonyms, and paraphrases,
    whereas TF-IDF only matches exact keyword overlap.
    
    Maintains backward-compatible API: fit(), transform(), cosine_similarity().
    Falls back to TF-IDF if sentence-transformers is not installed.
    """
    
    # Model name - lightweight but powerful (384-dimensional vectors)
    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    
    def __init__(self):
        self.idf = {}
        self.vocab = set()
        self.doc_count = 0
        self._model = None
        self._use_neural = _HAS_SENTENCE_TRANSFORMERS
        
        if self._use_neural:
            try:
                self._model = SentenceTransformer(self.MODEL_NAME)
                print(f"[RAG] Neural embedder loaded: {self.MODEL_NAME}")
            except Exception as e:
                print(f"[WARNING] Failed to load neural model: {e}. Falling back to TF-IDF.")
                self._use_neural = False
    
    def tokenize(self, text: str) -> List[str]:
        """Simple tokenization: lowercase, split on non-alphanumeric, filter short tokens."""
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
        tokens = [w for w in cleaned.split() if len(w) > 1]
        return tokens
    
    def fit(self, texts: List[str]):
        """
        Fit the embedder on a corpus of texts.
        
        For neural embeddings: no-op (pretrained model doesn't need fitting).
        For TF-IDF fallback: builds IDF vocabulary from the corpus.
        """
        self.doc_count = len(texts)
        
        if self._use_neural:
            # Neural model is pretrained — no fitting needed.
            # We still build a minimal IDF for serialization compatibility.
            df = Counter()
            for text in texts:
                tokens = set(self.tokenize(text))
                for t in tokens:
                    df[t] += 1
            self.idf = {
                t: math.log((1 + self.doc_count) / (1 + count)) + 1
                for t, count in df.items()
            }
            self.vocab = set(self.idf.keys())
            print(f"[RAG] Neural embedder ready. Corpus: {self.doc_count} documents.")
        else:
            # TF-IDF fallback
            df = Counter()
            for text in texts:
                tokens = set(self.tokenize(text))
                for t in tokens:
                    df[t] += 1
            self.idf = {
                t: math.log((1 + self.doc_count) / (1 + count)) + 1
                for t, count in df.items()
            }
            self.vocab = set(self.idf.keys())
    
    def transform(self, text: str):
        """
        Convert text to an embedding vector.
        
        Returns:
            - Neural mode: dict with dimension indices as keys (for compatibility)
            - TF-IDF fallback: dict with token keys and TF-IDF weights
        """
        if self._use_neural and self._model is not None:
            return self._neural_transform(text)
        else:
            return self._tfidf_transform(text)
    
    def _neural_transform(self, text: str) -> Dict:
        """Generate a neural embedding and return as a dict keyed by dimension index."""
        embedding = self._model.encode(text, normalize_embeddings=True)
        # Convert to dict format for compatibility with vector_store serialization
        vec = {str(i): float(v) for i, v in enumerate(embedding) if abs(v) > 1e-7}
        return vec
    
    def _tfidf_transform(self, text: str) -> Dict:
        """TF-IDF fallback: original implementation."""
        tokens = self.tokenize(text)
        tf = Counter(tokens)
        total_terms = max(1, len(tokens))

        vec = {}
        norm_sq = 0.0
        for term, count in tf.items():
            if term in self.idf:
                weight = (count / total_terms) * self.idf[term]
                vec[term] = weight
                norm_sq += weight * weight

        norm = math.sqrt(norm_sq)
        if norm > 0:
            vec = {k: v / norm for k, v in vec.items()}
        return vec

    def cosine_similarity(self, vec1: Dict, vec2: Dict) -> float:
        """
        Calculate cosine similarity between two embedding vectors.
        
        Works with both neural (dimension-indexed) and TF-IDF (token-indexed) vectors.
        Neural vectors are already L2-normalized, so dot product = cosine similarity.
        """
        if not vec1 or not vec2:
            return 0.0
        
        # Dot product over shared keys
        intersection = set(vec1.keys()) & set(vec2.keys())
        if not intersection:
            return 0.0
            
        dot = sum(vec1[k] * vec2[k] for k in intersection)
        
        if self._use_neural:
            # Neural embeddings are already normalized, dot product IS cosine sim
            return float(max(0.0, min(1.0, dot)))
        else:
            # TF-IDF vectors are already normalized in transform(), so dot = cosine
            return float(dot)
    
    def embed_batch(self, texts: List[str]) -> List[Dict]:
        """
        Batch embed multiple texts at once (much faster for neural embeddings).
        Falls back to sequential transform() for TF-IDF.
        """
        if self._use_neural and self._model is not None:
            embeddings = self._model.encode(texts, normalize_embeddings=True, 
                                            show_progress_bar=len(texts) > 50,
                                            batch_size=64)
            results = []
            for embedding in embeddings:
                vec = {str(i): float(v) for i, v in enumerate(embedding) if abs(v) > 1e-7}
                results.append(vec)
            return results
        else:
            return [self.transform(text) for text in texts]
