# 🧠 Multimodal RAG — Research Paper Chatbot

> Chat with any research paper. Ask questions about its text, tables, and figures — all answered by local LLMs, with zero cloud dependency.

---

## 📌 Table of Contents

- [How It Works](#-how-it-works)
- [Architecture](#-architecture)
- [Project Structure](#-project-structure)
- [Models Used](#-models-used)
- [Setup & Installation](#-setup--installation)
  - [Option A — Docker (recommended)](#-option-a--docker-recommended)
  - [Option B — Run Locally](#-option-b--run-locally)
- [Running the App](#-running-the-app)
- [API Reference](#-api-reference)
- [Tech Stack](#-tech-stack)
- [Notes](#-notes)

---

## 💡 How It Works

Most RAG systems only handle text. Research papers are full of **tables, diagrams, and figures** that carry critical information. This system handles all three.

When you upload a PDF, the pipeline does five things:

### 1 — Partition
The PDF is split into semantic chunks using `unstructured` with `hi_res` strategy. It detects and separates:
- **Text blocks** → `CompositeElement`
- **Tables** → extracted as raw HTML
- **Images** → extracted as base64-encoded PNG

### 2 — Summarise
Each chunk gets a natural-language summary using a local LLM:

| Chunk type | Model | Method |
|---|---|---|
| Text | `phi3:mini` via Ollama | LangChain summarise chain |
| Table (HTML) | `phi3:mini` via Ollama | LangChain summarise chain |
| Image | `minicpm-v` via Ollama | Vision model — describes visible content only |

### 3 — Embed & Index
Summaries are embedded using `nomic-embed-text` and stored in a **Chroma** vector store. The original raw chunks (text, HTML, image descriptions) are stored in an `InMemoryStore` keyed by UUID.

### 4 — Retrieve
At query time, a **MultiVectorRetriever** searches the vector store using the question embedding, finds the top-k matching summaries, then fetches the corresponding original chunks from the docstore.

### 5 — Generate
The retrieved chunks are assembled into a prompt and passed to `phi3:mini`, which answers **only from the provided context** — no hallucination from general knowledge.

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        PDF Upload (Flask)                        │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│              unstructured  •  hi_res strategy                    │
│                                                                  │
│   ┌─────────────┐   ┌─────────────┐   ┌──────────────────────┐  │
│   │  Text Chunks│   │   Tables    │   │  Images (base64)     │  │
│   │CompositeElem│   │ (HTML)      │   │  extracted inline    │  │
│   └──────┬──────┘   └──────┬──────┘   └──────────┬───────────┘  │
└──────────┼─────────────────┼─────────────────────┼──────────────┘
           │                 │                      │
           ▼                 ▼                      ▼
    phi3:mini           phi3:mini             minicpm-v
    (summarise)         (summarise)          (vision describe)
           │                 │                      │
           └─────────────────┼──────────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │   nomic-embed-text (Ollama)  │
              │   Embed summaries → vectors  │
              └──────────────┬───────────────┘
                             │
               ┌─────────────┴──────────────┐
               │                            │
               ▼                            ▼
       ┌───────────────┐          ┌──────────────────┐
       │  Chroma       │          │  InMemoryStore   │
       │  VectorStore  │          │  (raw originals) │
       │  (summaries)  │          │                  │
       └───────┬───────┘          └────────┬─────────┘
               │                           │
               └─────────┬─────────────────┘
                          │  MultiVectorRetriever
                          │
                          ▼
              ┌───────────────────────┐
              │  User Question        │
              │  → embed → top-k docs │
              │  → build prompt       │
              │  → phi3:mini answer   │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Flask /chat route   │
              │   → JSON response     │
              │   → UI chat bubble    │
              └───────────────────────┘
```

---

## 📁 Project Structure

```
multimodal-rag/
│
├── app.py                  # Flask app — routes for upload & chat
├── rag.py                  # RAG pipeline — pure module, no Flask
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker image definition
├── start.sh                # Container startup script (Ollama + Flask)
├── .dockerignore           # Files excluded from Docker build
│
├── templates/
│   └── index.html          # Chat UI
│
├── static/
│   ├── script.js           # Upload + chat JS
│   └── style.css           # Styles
│
├── uploads/                # PDFs saved here after upload (auto-created)
│
└── README.md
```

---

## 🤖 Models Used

All models run **locally via Ollama** — no API keys, no internet required after setup.

| Model | Role | Pull command |
|---|---|---|
| `phi3:mini` | Text & table summarisation + final answer generation | `ollama pull phi3:mini` |
| `minicpm-v` | Image / figure description (vision) | `ollama pull minicpm-v` |
| `nomic-embed-text` | Embedding summaries into vectors | `ollama pull nomic-embed-text` |

---

## ⚙️ Setup & Installation

### 🐳 Option A — Docker (recommended)

No manual setup needed. Docker handles Python, Ollama, system dependencies, and model downloads automatically.

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/) installed and running.

**1. Clone the repo**
```bash
git clone https://github.com/your-username/multimodal-rag.git
cd multimodal-rag
```

**2. Build the image**
```bash
docker build -t multimodal-rag .
```
> Takes 5–10 minutes on first build — installs Python packages, Ollama, and system dependencies.

**3. Run the container**
```bash
docker run -p 5000:5000 -v ollama-models:/root/.ollama multimodal-rag
```
> Takes another 5–15 minutes on **first** run — downloads the three Ollama models (~8 GB total). Subsequent runs are instant thanks to the volume mount.

You'll see this in the terminal when everything is ready:
```
▶ Starting Ollama server...
✅ Ollama is ready.
📦 Pulling models...
✅ All models ready.
🚀 Starting Flask app...
```

**4. Open the app**

Go to [http://localhost:5000](http://localhost:5000)

---

**Optional flags:**

```bash
# GPU support (NVIDIA — strongly recommended for minicpm-v)
docker run -p 5000:5000 --gpus all -v ollama-models:/root/.ollama multimodal-rag

# Persist uploaded PDFs across restarts
docker run -p 5000:5000 \
  -v ollama-models:/root/.ollama \
  -v $(pwd)/uploads:/app/uploads \
  multimodal-rag
```

**Useful Docker commands:**
```bash
docker ps                          # see running containers
docker stop <container-id>         # stop the app
docker logs <container-id>         # view logs if something goes wrong
docker build -t multimodal-rag .   # rebuild after code changes
```

---

### 💻 Option B — Run Locally

**Prerequisites:**
- Python 3.10+
- [Ollama](https://ollama.ai) installed and running
- Poppler

```bash
# Ubuntu / Debian
sudo apt-get install poppler-utils

# macOS
brew install poppler
```

**1. Clone the repo**
```bash
git clone https://github.com/your-username/multimodal-rag.git
cd multimodal-rag
```

**2. Install Python dependencies**
```bash
pip install -r requirements.txt
```

**3. Pull Ollama models**
```bash
ollama pull phi3:mini
ollama pull minicpm-v
ollama pull nomic-embed-text
```

**4. Start Ollama**
```bash
ollama serve
```

---

## 🚀 Running the App

**Docker:** already running after `docker run` — go to [http://localhost:5000](http://localhost:5000)

**Local:**
```bash
python app.py
```
Then open [http://localhost:5000](http://localhost:5000)

**Workflow:**
1. Click **Choose PDF** and select a research paper
2. Click **Upload PDF** — the pipeline partitions, summarises, and indexes it (1–5 minutes)
3. Once the status shows success, type your question and hit **Send**
4. Answers may take 10–30 seconds depending on your hardware

---

## 📡 API Reference

### `POST /upload`

Upload and process a PDF.

**Request:** `multipart/form-data` with field `pdf`

**Response:**
```json
{
  "status": "success",
  "message": "PDF processed successfully",
  "stats": {
    "texts": 14,
    "tables": 3,
    "images": 6
  }
}
```

---

### `POST /chat`

Ask a question about the processed PDF.

**Request:**
```json
{ "question": "What is the attention mechanism?" }
```

**Response:**
```json
{
  "status": "success",
  "answer": "The attention mechanism is a function that maps a query and a set of key-value pairs to an output..."
}
```

---

### `GET /health`

Check if the server is running and a PDF has been indexed.

**Response:**
```json
{ "status": "ok", "indexed": true }
```

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Web framework | Flask |
| PDF parsing | `unstructured` (hi_res + vision) |
| LLM inference | Ollama (local) |
| LLM orchestration | LangChain |
| Vector store | Chroma |
| Embeddings | `nomic-embed-text` |
| Text LLM | `phi3:mini` |
| Vision LLM | `minicpm-v` |
| Containerisation | Docker |

---

## 📝 Notes

- **Processing time** scales with PDF length and number of images. A 15-page paper with several figures typically takes 2–4 minutes.
- **Index is in-memory** — it is lost when the server or container restarts. Re-upload the PDF to re-index.
- **One PDF at a time** — uploading a new PDF replaces the previous index.
- **Best results** come from PDFs with selectable text rather than fully scanned images.
- **First Docker run** is slow due to model downloads (~8 GB). Use `-v ollama-models:/root/.ollama` to cache models across runs.
