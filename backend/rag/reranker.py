class RAGReranker:
    """
    Handles Multi-Query expansion, Top-K retrieval reranking,
    confidence score normalization, and source citation formatting.
    """
    def __init__(self, vector_store):
        self.vector_store = vector_store

    def rewrite_queries(self, animal_type, symptoms, severity):
        """
        Generate expanded multi-query variations to maximize recall across SOPs.
        """
        queries = [
            f"{animal_type} {symptoms} {severity} symptoms management treatment isolation",
            f"{animal_type} disease outbreak SOP isolation protocol Karnataka",
            f"{symptoms} biosecurity guidelines vaccination schedule"
        ]
        return queries

    def retrieve_and_rerank(self, animal_type, symptoms, severity, top_k=4):
        queries = self.rewrite_queries(animal_type, symptoms, severity)
        
        seen_chunks = {}
        for q in queries:
            results = self.vector_store.search(q, top_k=top_k)
            for r in results:
                cid = r["chunk_id"]
                if cid not in seen_chunks or r["confidence"] > seen_chunks[cid]["confidence"]:
                    seen_chunks[cid] = r

        all_chunks = list(seen_chunks.values())
        
        # Rerank: boost chunks matching animal_type or specific symptoms in title/content
        for chunk in all_chunks:
            boost = 0.0
            content_lower = (chunk["title"] + " " + chunk["content"]).lower()
            if animal_type.lower() in content_lower:
                boost += 0.15
            for sym in symptoms.lower().split():
                if len(sym) > 3 and sym in content_lower:
                    boost += 0.05
            
            chunk["confidence"] = round(min(0.98, chunk["confidence"] + boost), 3)

        all_chunks.sort(key=lambda x: x["confidence"], reverse=True)
        return all_chunks[:top_k]
