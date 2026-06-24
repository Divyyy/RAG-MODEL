import uuid
import logging

import ollama
from unstructured.partition.pdf import partition_pdf
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.documents import Document
from langchain_core.stores import InMemoryStore
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_classic.retrievers import MultiVectorRetriever

logger = logging.getLogger(__name__)

# Module-level state
_retriever = None
_chain = None


# Helpers 

def _get_images_base64(chunks):
    images_b64 = []
    for chunk in chunks:
        if "CompositeElement" in str(type(chunk)):
            for el in chunk.metadata.orig_elements or []:
                if "Image" in str(type(el)):
                    images_b64.append(el.metadata.image_base64)
    return images_b64


def _summarize_image(img_b64: str) -> str:
    response = ollama.chat(
        model="minicpm-v",
        messages=[
            {
                "role": "user",
                "content": (
                    "Describe ONLY what is visible in this figure.\n\n"
                    "Output:\n\nFigure Number:\nTitle:\n\nText Labels:\n- ...\n\n"
                    "Blocks:\n- ...\n\nArrows:\n- ...\n\nTables:\n- ...\n\n"
                    "Equations:\n- ...\n\n"
                    "Do NOT explain concepts, infer architecture, speculate, "
                    "or use words like likely/probably/typically/suggests. "
                    "Only transcribe and describe visible content."
                ),
                "images": [img_b64],
            }
        ],
    )
    return response["message"]["content"]


def _build_prompt(data):
    docs = data["context"]
    # Extract plain text — docs can be Document objects or raw strings
    parts = []
    for doc in docs:
        if hasattr(doc, "page_content"):
            parts.append(doc.page_content)
        else:
            parts.append(str(doc))
    context = "\n\n".join(parts)

    prompt = ChatPromptTemplate.from_template(
        "You are a helpful assistant.\n\n"
        "Answer ONLY from the provided context.\n\n"
        "Context:\n{context}\n\n"
        "Question:\n{question}"
    )
    return prompt.invoke({"context": context, "question": data["question"]})


def _build_retriever_and_chain():
    vectorstore = Chroma(
        collection_name="multi_modal_rag",
        embedding_function=OllamaEmbeddings(model="nomic-embed-text"),
    )
    store = InMemoryStore()
    id_key = "doc_id"

    ret = MultiVectorRetriever(
        vectorstore=vectorstore,
        docstore=store,
        id_key=id_key,
    )

    ch = (
        {"context": ret, "question": RunnablePassthrough()}
        | RunnableLambda(_build_prompt)
        | ChatOllama(model="phi3:mini")
        | StrOutputParser()
    )

    return ret, ch, id_key


# Public API (which flask app.py calls) 

def process_pdf(pdf_path: str) -> dict:
    """
    Partition a PDF, summarise all text/table/image chunks,
    and build the vector index. Call this once per PDF before querying.
    Returns {"texts": int, "tables": int, "images": int}
    """
    global _retriever, _chain

    logger.info(f"Partitioning PDF: {pdf_path}")
    chunks = partition_pdf(
        filename=pdf_path,
        infer_table_structure=True,
        strategy="hi_res",
        extract_image_block_types=["Image"],
        extract_image_block_to_payload=True,
        chunking_strategy="by_title",
        max_characters=10000,
        combine_text_under_n_chars=2000,
        new_after_n_chars=6000,
    )

    tables = [c for c in chunks if "Table" in str(type(c))]
    texts  = [c for c in chunks if "CompositeElement" in str(type(c))]
    images = _get_images_base64(chunks)

    logger.info(f"Found {len(texts)} text chunks, {len(tables)} tables, {len(images)} images")

    summarize_chain = (
        {"text": lambda x: x}
        | ChatPromptTemplate.from_template(
            "You are an assistant tasked with summarizing tables and text. "
            "Give a concise summary of the table or text. "
            "Respond only with the summary.\n{text}"
        )
        | ChatOllama(model="phi3:mini")
        | StrOutputParser()
    )

    logger.info("Summarising texts...")
    text_summaries = summarize_chain.batch(texts, {"max_concurrency": 2})

    tables_html = [t.metadata.text_as_html for t in tables]
    logger.info("Summarising tables...")
    table_summaries = summarize_chain.batch(tables_html, {"max_concurrency": 2})

    logger.info("Summarising images...")
    image_summaries = [_summarize_image(img) for img in images]

    _retriever, _chain, id_key = _build_retriever_and_chain()

    # Index texts
    docs_ids = [str(uuid.uuid4()) for _ in texts]
    _retriever.vectorstore.add_documents([
        Document(page_content=s, metadata={id_key: docs_ids[i]})
        for i, s in enumerate(text_summaries)
    ])
    _retriever.docstore.mset(list(zip(docs_ids, texts)))

    # Index tables
    table_ids = [str(uuid.uuid4()) for _ in tables]
    _retriever.vectorstore.add_documents([
        Document(page_content=s, metadata={id_key: table_ids[i]})
        for i, s in enumerate(table_summaries)
    ])
    _retriever.docstore.mset(list(zip(table_ids, tables_html)))

    # Index images
    image_ids = [str(uuid.uuid4()) for _ in images]
    _retriever.vectorstore.add_documents([
        Document(page_content=s, metadata={id_key: image_ids[i]})
        for i, s in enumerate(image_summaries)
    ])
    _retriever.docstore.mset(list(zip(image_ids, image_summaries)))

    logger.info("Indexing complete.")
    return {"texts": len(texts), "tables": len(tables), "images": len(images)}


def query(question: str) -> str:
    """Run a question through the RAG chain. process_pdf() must be called first."""
    if _chain is None:
        raise RuntimeError("No PDF processed yet. Upload a PDF first.")
    result = _chain.invoke(question)
    if isinstance(result, dict):
        return result.get("output", result.get("answer", str(result)))
    return str(result) if result else "No answer found."


def is_ready() -> bool:
    """Return True if a PDF has been indexed and the chain is ready."""
    return _chain is not None