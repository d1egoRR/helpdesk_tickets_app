import argparse
import errno
import hashlib
import logging
import shutil
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from helpdesk.config import Settings, get_settings

logger = logging.getLogger(__name__)

DEFAULT_DOCS_GLOB = "**/*.md"
DEFAULT_ENCODING = "utf-8"
DEFAULT_TEXT_SEPARATORS: tuple[str, ...] = ("\n\n", "\n", ".", "!", "?", ",", " ", "")
DOC_ID_LENGTH = 8
CONTENT_PREVIEW_LENGTH = 200
DEFAULT_SAMPLE_QUERIES: tuple[str, ...] = (
    "¿Cómo reseteo mi contraseña?",
    "¿Cuál es el tamaño máximo para subir archivos?",
    "Error 500 página blanca qué hacer",
)


class ChromaVectorStoreSetup:
    """One-time setup utility for indexing Markdown helpdesk documents into ChromaDB."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.docs_path = self.settings.docs_path
        self.chroma_path = self.settings.chromadb_path
        self.collection_name = self.settings.chroma_collection_name
        self.embeddings = self._build_embeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.rag_chunk_size,
            chunk_overlap=self.settings.rag_chunk_overlap,
            length_function=len,
            separators=list(DEFAULT_TEXT_SEPARATORS),
        )

    def load_documents(self) -> list[Document]:
        """Load Markdown documents from the configured docs directory and enrich metadata."""
        if not self.docs_path.exists() or not self.docs_path.is_dir():
            raise FileNotFoundError(f"Documents directory not found: {self.docs_path}")

        logger.info(f"Loading Markdown documents from {self.docs_path}")
        loader = DirectoryLoader(
            str(self.docs_path),
            glob=DEFAULT_DOCS_GLOB,
            loader_cls=TextLoader,
            loader_kwargs={"encoding": DEFAULT_ENCODING},
        )
        documents = loader.load()

        for document in documents:
            filename = self._extract_filename(document)
            document.metadata.update(
                {
                    "filename": filename,
                    "doc_type": self._get_doc_type(filename),
                    "doc_id": self._generate_doc_id(document.page_content),
                }
            )

        logger.info(f"Loaded {len(documents)} documents")
        return documents

    def split_documents(self, documents: list[Document]) -> list[Document]:
        """Split loaded documents into overlapping chunks and attach chunk metadata."""
        logger.info(f"Splitting {len(documents)} documents into chunks")
        chunks = self.text_splitter.split_documents(documents)

        for index, chunk in enumerate(chunks):
            chunk.metadata.update(
                {
                    "chunk_id": index,
                    "chunk_size": len(chunk.page_content),
                }
            )

        logger.info(f"Created {len(chunks)} chunks")
        return chunks

    def create_vectorstore(self, documents: list[Document]) -> Chroma:
        """Delete any existing ChromaDB store and create a fresh persisted vector store."""
        if not documents:
            raise ValueError("Cannot create vector store from an empty document list")

        logger.info(f"Creating ChromaDB vector store at {self.chroma_path}")
        self._clear_vectorstore_directory()

        vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            persist_directory=str(self.chroma_path),
            collection_name=self.collection_name,
        )

        logger.info(
            f"Vector store created at {self.chroma_path} "
            f"(collection={self.collection_name}, vectors={len(documents)})"
        )
        return vectorstore

    def load_existing_vectorstore(self) -> Chroma:
        """Load and return an existing persisted ChromaDB vector store."""
        if not self._has_existing_vectorstore():
            raise FileNotFoundError(f"Vector store not found at {self.chroma_path}")

        logger.info(
            f"Loading existing ChromaDB vector store from {self.chroma_path} "
            f"(collection={self.collection_name})"
        )
        return Chroma(
            persist_directory=str(self.chroma_path),
            embedding_function=self.embeddings,
            collection_name=self.collection_name,
        )

    def setup_rag_system(self, force_rebuild: bool = False) -> Chroma | None:
        """Return an existing vector store or build it from docs when missing or forced."""
        logger.info(f"Starting RAG vector store setup (force_rebuild={force_rebuild})")

        if self._has_existing_vectorstore() and not force_rebuild:
            logger.info("Existing vector store found; reusing persisted database")
            return self.load_existing_vectorstore()

        documents = self.load_documents()
        if not documents:
            logger.warning(f"No Markdown documents found in {self.docs_path}")
            return None

        chunks = self.split_documents(documents)
        vectorstore = self.create_vectorstore(chunks)
        logger.info("RAG vector store setup completed successfully")
        return vectorstore

    def test_search(
        self,
        vectorstore: Chroma,
        query: str,
        k: int | None = None,
    ) -> list[Document]:
        """Run a similarity search against the vector store and log matched chunks."""
        top_k = k if k is not None else self.settings.rag_search_k
        logger.info(f"Running test search: query={query!r}, k={top_k}")

        results = vectorstore.similarity_search(query, k=top_k)

        for rank, document in enumerate(results, start=1):
            preview = document.page_content[:CONTENT_PREVIEW_LENGTH].replace("\n", " ")
            logger.info(
                f"Result {rank} | "
                f"doc_type={document.metadata.get('doc_type', 'unknown')} | "
                f"filename={document.metadata.get('filename', 'unknown')} | "
                f"doc_id={document.metadata.get('doc_id', 'unknown')} | "
                f"chunk_id={document.metadata.get('chunk_id', 'unknown')} | "
                f"preview={preview}..."
            )

        return results

    def _build_embeddings(self) -> OpenAIEmbeddings:
        """Validate embedding settings and create the OpenAIEmbeddings client."""
        api_key = self.settings.openai_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            raise ValueError("OPENAI_API_KEY must be configured in the environment")

        embeddings_model = self.settings.embeddings_model.strip()
        if not embeddings_model:
            raise ValueError("EMBEDDINGS_MODEL must be configured in the environment")

        return OpenAIEmbeddings(
            model=embeddings_model,
            api_key=api_key,
        )

    def _extract_filename(self, document: Document) -> str:
        """Extract the filename stem from the document source metadata."""
        source = document.metadata.get("source")
        if not source:
            return "unknown"
        return Path(str(source)).stem

    def _get_doc_type(self, filename: str) -> str:
        """Determine the document type using configured filename keyword rules."""
        normalized_name = filename.lower()

        for doc_type, keywords in self.settings.rag_doc_type_rules.items():
            if any(keyword.lower() in normalized_name for keyword in keywords):
                return doc_type

        return self.settings.rag_default_doc_type

    def _generate_doc_id(self, content: str) -> str:
        """Generate a deterministic short identifier from document content."""
        return hashlib.sha256(content.encode(DEFAULT_ENCODING)).hexdigest()[:DOC_ID_LENGTH]

    def _has_existing_vectorstore(self) -> bool:
        """Check whether a non-empty persisted ChromaDB directory exists."""
        return (
            self.chroma_path.exists()
            and self.chroma_path.is_dir()
            and any(self.chroma_path.iterdir())
        )

    def _clear_vectorstore_directory(self) -> None:
        """Remove the persisted ChromaDB directory or its contents when mounted."""
        if not self.chroma_path.exists():
            return

        try:
            shutil.rmtree(self.chroma_path)
        except OSError as exc:
            if exc.errno != errno.EBUSY:
                raise
            for entry in self.chroma_path.iterdir():
                if entry.is_dir() and not entry.is_symlink():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()


def main() -> None:
    """Execute one-time ChromaDB vector store setup and run sample search queries."""
    parser = argparse.ArgumentParser(
        description="Build or load the helpdesk ChromaDB vector store and run sample searches."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force rebuilding the ChromaDB vector store even if it already exists.",
    )
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Custom test search query (can be specified multiple times).",
    )
    args = parser.parse_args()

    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    setup = ChromaVectorStoreSetup(settings=settings)
    vectorstore = setup.setup_rag_system(force_rebuild=args.force)
    if vectorstore is None:
        logger.warning("Skipping test searches because no vector store was created")
        return

    queries = args.queries or list(DEFAULT_SAMPLE_QUERIES)
    for query in queries:
        setup.test_search(vectorstore, query=query)


if __name__ == "__main__":
    main()
