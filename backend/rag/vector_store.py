import os
import json
from backend.rag.embedder import TextEmbedder

class VectorStore:
    """
    Persistent Vector Store using TF-IDF Embeddings and Cosine Similarity.
    Persists indexed vector store to backend/vector_store/vector_db.json.
    """
    def __init__(self, db_path="backend/vector_store/vector_db.json"):
        self.db_path = db_path
        self.embedder = TextEmbedder()
        self.chunks = []
        self.vectors = []

    def build_index(self, chunks):
        self.chunks = chunks
        texts = [c["content"] for c in chunks]
        
        self.embedder.fit(texts)
        self.vectors = [self.embedder.transform(t) for t in texts]

        self._save_db()

    def search(self, query, top_k=4):
        if not self.chunks:
            self._load_db()

        if not self.chunks:
            return []

        query_vec = self.embedder.transform(query)
        scores = []

        for idx, chunk_vec in enumerate(self.vectors):
            sim = self.embedder.cosine_similarity(query_vec, chunk_vec)
            # Add small boost if key words match in title/content
            scores.append((sim, idx))

        scores.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, idx in scores[:top_k]:
            if score > 0.05:
                chunk = self.chunks[idx].copy()
                chunk["confidence"] = round(float(score), 3)
                results.append(chunk)

        return results

    def _save_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        data = {
            "chunks": self.chunks,
            "idf": self.embedder.idf,
            "vectors": self.vectors
        }
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def _load_db(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.chunks = data.get("chunks", [])
                    self.embedder.idf = data.get("idf", {})
                    self.embedder.doc_count = len(self.chunks)
                    self.vectors = data.get("vectors", [])
            except Exception as e:
                print(f"Error loading vector db: {e}")
