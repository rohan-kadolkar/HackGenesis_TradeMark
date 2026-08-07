class TextChunker:
    """
    Chunks documents into overlapping text windows with metadata tags.
    """
    def __init__(self, chunk_size=400, chunk_overlap=80):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_documents(self, documents):
        chunks = []
        chunk_id = 0

        for doc in documents:
            content = doc["content"]
            source = doc["source"]
            title = doc["title"]
            
            words = content.split()
            if not words:
                continue

            i = 0
            while i < len(words):
                chunk_words = words[i:i + self.chunk_size]
                chunk_text = " ".join(chunk_words)
                
                chunk_id += 1
                chunks.append({
                    "chunk_id": f"chunk_{chunk_id}",
                    "source": source,
                    "title": title,
                    "content": chunk_text,
                    "word_count": len(chunk_words)
                })

                if i + self.chunk_size >= len(words):
                    break
                i += (self.chunk_size - self.chunk_overlap)

        return chunks
