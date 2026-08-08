import os
import json
import shutil
from typing import List, Dict, Optional

# Try to use ChromaDB for production-grade vector storage
try:
    import chromadb
    from chromadb.config import Settings
    _HAS_CHROMADB = True
except ImportError:
    _HAS_CHROMADB = False
    print("[WARNING] chromadb not installed. Falling back to JSON vector store.")
    print("[WARNING] Install with: pip install chromadb")

from backend.rag.embedder import TextEmbedder


class VectorStore:
    """
    Persistent Vector Store with ChromaDB backend.
    
    Upgraded from JSON-file storage to ChromaDB for:
    - Faster similarity search at scale
    - Built-in persistence and crash recovery
    - Efficient approximate nearest neighbor search
    - Better memory management for large knowledge bases
    
    Maintains backward-compatible API: build_index(), search().
    Falls back to JSON storage if ChromaDB is not installed.
    """
    
    COLLECTION_NAME = "kbn_knowledge_base"
    
    def __init__(self, db_path: str = "backend/vector_store/vector_db.json"):
        self.db_path = db_path
        self.embedder = TextEmbedder()
        self.chunks = []
        self.vectors = []
        self._use_chromadb = _HAS_CHROMADB
        self._collection = None
        self._chroma_client = None
        
        if self._use_chromadb:
            try:
                # Store ChromaDB alongside the old JSON path for consistency
                chroma_dir = os.path.join(os.path.dirname(db_path), "chroma_db")
                os.makedirs(chroma_dir, exist_ok=True)
                
                self._chroma_client = chromadb.PersistentClient(path=chroma_dir)
                print(f"[RAG] ChromaDB initialized at: {chroma_dir}")
            except Exception as e:
                print(f"[WARNING] ChromaDB init failed: {e}. Falling back to JSON store.")
                self._use_chromadb = False
    
    def build_index(self, chunks: List[Dict]):
        """
        Build the vector index from document chunks.
        
        Args:
            chunks: List of dicts with keys: chunk_id, source, title, content, word_count
        """
        self.chunks = chunks
        texts = [c["content"] for c in chunks]
        
        # Fit the embedder (no-op for neural, builds vocab for TF-IDF)
        self.embedder.fit(texts)
        
        if self._use_chromadb:
            self._build_chromadb_index(chunks, texts)
        else:
            self._build_json_index(chunks, texts)
    
    def _build_chromadb_index(self, chunks: List[Dict], texts: List[str]):
        """Build index using ChromaDB."""
        # Delete existing collection if any (fresh rebuild)
        try:
            self._chroma_client.delete_collection(name=self.COLLECTION_NAME)
        except Exception:
            pass
        
        self._collection = self._chroma_client.create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )
        
        # Generate embeddings in batch (much faster for neural)
        print(f"[RAG] Generating embeddings for {len(texts)} chunks...")
        
        if self.embedder._use_neural and self.embedder._model is not None:
            # Use raw numpy arrays for ChromaDB (not the dict format)
            raw_embeddings = self.embedder._model.encode(
                texts, 
                normalize_embeddings=True,
                show_progress_bar=len(texts) > 50,
                batch_size=64
            ).tolist()
        else:
            # TF-IDF: convert dict vectors to dense arrays for ChromaDB
            self.vectors = [self.embedder.transform(t) for t in texts]
            # Get all unique keys
            all_keys = sorted(set(k for v in self.vectors for k in v.keys()))
            key_to_idx = {k: i for i, k in enumerate(all_keys)}
            dim = len(all_keys)
            raw_embeddings = []
            for vec in self.vectors:
                dense = [0.0] * dim
                for k, v in vec.items():
                    dense[key_to_idx[k]] = v
                raw_embeddings.append(dense)
        
        # Add to ChromaDB in batches (ChromaDB has a batch size limit)
        batch_size = 500
        for i in range(0, len(texts), batch_size):
            batch_end = min(i + batch_size, len(texts))
            
            ids = [chunks[j]["chunk_id"] for j in range(i, batch_end)]
            documents = texts[i:batch_end]
            embeddings = raw_embeddings[i:batch_end]
            metadatas = [
                {
                    "source": chunks[j].get("source", "unknown"),
                    "title": chunks[j].get("title", ""),
                    "chunk_id": chunks[j]["chunk_id"],
                    "word_count": chunks[j].get("word_count", 0)
                }
                for j in range(i, batch_end)
            ]
            
            self._collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
        
        print(f"[RAG] ChromaDB index built: {self._collection.count()} chunks indexed.")
        
        # Also save chunks metadata to JSON for backup/compatibility
        self._save_chunks_metadata()
    
    def _build_json_index(self, chunks: List[Dict], texts: List[str]):
        """Fallback: Build index using JSON file (original implementation)."""
        self.vectors = self.embedder.embed_batch(texts)
        self._save_db()
    
    def search(self, query: str, top_k: int = 4) -> List[Dict]:
        """
        Search for most relevant chunks given a query.
        
        Args:
            query: Search query text
            top_k: Number of top results to return
            
        Returns:
            List of chunk dicts with added 'confidence' score
        """
        if self._use_chromadb:
            return self._search_chromadb(query, top_k)
        else:
            return self._search_json(query, top_k)
    
    def _search_chromadb(self, query: str, top_k: int) -> List[Dict]:
        """Search using ChromaDB."""
        # Ensure collection is loaded
        if self._collection is None:
            try:
                self._collection = self._chroma_client.get_collection(
                    name=self.COLLECTION_NAME
                )
            except Exception:
                print("[RAG] No ChromaDB collection found. Returning empty results.")
                return []
        
        if self._collection.count() == 0:
            return []
        
        # Generate query embedding
        if self.embedder._use_neural and self.embedder._model is not None:
            query_embedding = self.embedder._model.encode(
                query, normalize_embeddings=True
            ).tolist()
        else:
            query_vec = self.embedder.transform(query)
            # Convert to dense for ChromaDB
            # We need the same key mapping — load from saved metadata
            all_keys = sorted(set(k for v in self.vectors for k in v.keys()))
            if not all_keys:
                return []
            key_to_idx = {k: i for i, k in enumerate(all_keys)}
            dim = len(all_keys)
            query_embedding = [0.0] * dim
            for k, v in query_vec.items():
                if k in key_to_idx:
                    query_embedding[key_to_idx[k]] = v
        
        # Query ChromaDB
        actual_k = min(top_k, self._collection.count())
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=actual_k,
            include=["documents", "metadatas", "distances"]
        )
        
        # Convert ChromaDB results to our chunk format
        output = []
        if results and results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0
                # ChromaDB cosine distance = 1 - cosine_similarity
                confidence = round(max(0.0, 1.0 - distance), 3)
                
                if confidence > 0.05:  # Same threshold as original
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    document = results["documents"][0][i] if results["documents"] else ""
                    
                    output.append({
                        "chunk_id": chunk_id,
                        "source": metadata.get("source", "unknown"),
                        "title": metadata.get("title", ""),
                        "content": document,
                        "word_count": metadata.get("word_count", 0),
                        "confidence": confidence
                    })
        
        return output
    
    def _search_json(self, query: str, top_k: int) -> List[Dict]:
        """Fallback: Search using JSON store (original implementation)."""
        if not self.chunks:
            self._load_db()

        if not self.chunks:
            return []

        query_vec = self.embedder.transform(query)
        scores = []

        for idx, chunk_vec in enumerate(self.vectors):
            sim = self.embedder.cosine_similarity(query_vec, chunk_vec)
            scores.append((sim, idx))

        scores.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, idx in scores[:top_k]:
            if score > 0.05:
                chunk = self.chunks[idx].copy()
                chunk["confidence"] = round(float(score), 3)
                results.append(chunk)

        return results
    
    def _save_chunks_metadata(self):
        """Save chunk metadata to JSON for backup."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        data = {
            "chunks": self.chunks,
            "backend": "chromadb",
            "chunk_count": len(self.chunks)
        }
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _save_db(self):
        """Save vectors to JSON (fallback mode)."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        data = {
            "chunks": self.chunks,
            "idf": self.embedder.idf,
            "vectors": self.vectors,
            "backend": "json"
        }
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def _load_db(self):
        """Load vectors from JSON (fallback mode)."""
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
