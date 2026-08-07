from backend.rag.document_loader import DocumentLoader
from backend.rag.text_chunker import TextChunker
from backend.rag.vector_store import VectorStore
from backend.rag.reranker import RAGReranker
from backend.agents.pipeline import AgenticRAGPipeline

class RAGService:
    """
    High-level service managing RAG initialization, document indexing,
    vector store queries, and Agentic RAG pipeline execution.
    """
    def __init__(self, knowledge_base_dir="backend/knowledge_base"):
        self.loader = DocumentLoader(knowledge_base_dir)
        self.chunker = TextChunker(chunk_size=400, chunk_overlap=80)
        self.vector_store = VectorStore("backend/vector_store/vector_db.json")
        self.reranker = RAGReranker(self.vector_store)
        self.pipeline = AgenticRAGPipeline(self.reranker)

    def initialize_knowledge_base(self):
        """
        Loads knowledge base documents, chunks them, and builds persistent vector index.
        """
        documents = self.loader.load_documents()
        chunks = self.chunker.chunk_documents(documents)
        if chunks:
            self.vector_store.build_index(chunks)
            print(f"[OK] RAG Knowledge Base initialized with {len(documents)} docs ({len(chunks)} chunks).")
        else:
            print("[INFO] No knowledge base documents found to index.")

    def run_pipeline(self, gemma_output, raw_form_data=None):
        """
        Executes full 4-agent RAG pipeline.
        """
        return self.pipeline.run(gemma_output, raw_form_data)

    def direct_rag_query(self, animal_type, symptoms, severity="high"):
        """
        Runs RAG retrieval and reasoning directly for user query.
        """
        mock_gemma = {
            "animal_type": animal_type,
            "title": f"{animal_type.title()} {symptoms}",
            "symptoms": symptoms,
            "description": f"Query regarding {animal_type} showing {symptoms}",
            "severity": severity,
            "confidence": 0.90,
            "needs_vet_visit": True
        }
        return self.pipeline.run(mock_gemma)
