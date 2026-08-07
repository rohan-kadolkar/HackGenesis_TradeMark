import os
import glob

class DocumentLoader:
    """
    Loads text, markdown, pdf, docx documents from knowledge base directory.
    """
    def __init__(self, knowledge_base_dir="backend/knowledge_base"):
        self.knowledge_base_dir = knowledge_base_dir

    def load_documents(self):
        docs = []
        if not os.path.exists(self.knowledge_base_dir):
            os.makedirs(self.knowledge_base_dir, exist_ok=True)
            return docs

        pattern = os.path.join(self.knowledge_base_dir, "**/*.*")
        files = glob.glob(pattern, recursive=True)

        for file_path in files:
            ext = os.path.splitext(file_path)[1].lower()
            rel_path = os.path.relpath(file_path, self.knowledge_base_dir)
            doc_title = os.path.basename(file_path).replace("_", " ").replace("-", " ").title()

            content = ""
            if ext in [".txt", ".md"]:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
            elif ext == ".pdf":
                try:
                    # PDF extraction fallback or pypdf
                    import pypdf
                    reader = pypdf.PdfReader(file_path)
                    content = "\n".join([page.extract_text() or "" for page in reader.pages])
                except ImportError:
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                    except Exception:
                        pass
                except Exception as e:
                    print(f"Error reading PDF {file_path}: {e}")
            elif ext == ".docx":
                try:
                    import docx
                    doc = docx.Document(file_path)
                    content = "\n".join([p.text for p in doc.paragraphs])
                except Exception as e:
                    print(f"Error reading DOCX {file_path}: {e}")

            if content.strip():
                docs.append({
                    "source": rel_path,
                    "title": doc_title,
                    "content": content.strip(),
                    "file_type": ext[1:]
                })

        return docs
