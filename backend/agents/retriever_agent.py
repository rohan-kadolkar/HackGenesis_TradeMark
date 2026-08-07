class RetrieverAgent:
    """
    Agent 2: Retriever Agent
    Executes multi-query semantic retrieval against the vector store.
    """
    def __init__(self, reranker):
        self.reranker = reranker

    def execute(self, animal_type, symptoms, severity, top_k=4):
        retrieved_chunks = self.reranker.retrieve_and_rerank(
            animal_type=animal_type,
            symptoms=symptoms,
            severity=severity,
            top_k=top_k
        )

        formatted_context = []
        for chunk in retrieved_chunks:
            formatted_context.append({
                "source": chunk.get("source", "Knowledge Base"),
                "title": chunk.get("title", "SOP Guideline"),
                "content": chunk.get("content", ""),
                "confidence": chunk.get("confidence", 0.85)
            })

        return formatted_context
