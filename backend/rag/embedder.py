import math
import re
from collections import Counter

class TextEmbedder:
    """
    TF-IDF Vector Embedder for semantic similarity search.
    Computes term weights and cosine similarities.
    """
    def __init__(self):
        self.idf = {}
        self.vocab = set()
        self.doc_count = 0

    def tokenize(self, text):
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
        tokens = [w for w in cleaned.split() if len(w) > 1]
        return tokens

    def fit(self, texts):
        self.doc_count = len(texts)
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

    def transform(self, text):
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

    def cosine_similarity(self, vec1, vec2):
        if not vec1 or not vec2:
            return 0.0
        
        # Dot product
        intersection = set(vec1.keys()) & set(vec2.keys())
        dot = sum(vec1[k] * vec2[k] for k in intersection)
        return float(dot)
