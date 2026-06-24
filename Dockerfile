FROM python:3.11-slim

# ── System dependencies ───────────────────────────────────────────────────────
# poppler-utils  → pdf2image (used by unstructured hi_res)
# libgl1         → OpenCV dependency pulled in by unstructured
# curl           → used to install Ollama
# zstd           → required by Ollama installer
RUN apt-get update && apt-get install -y \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    curl \
    zstd \
    && rm -rf /var/lib/apt/lists/*

# ── Install Ollama ────────────────────────────────────────────────────────────
RUN curl -fsSL https://ollama.ai/install.sh | sh

# ── Python dependencies ───────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy project files ────────────────────────────────────────────────────────
COPY . .

# Create uploads folder
RUN mkdir -p uploads

# ── Startup script ────────────────────────────────────────────────────────────
COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 5000
EXPOSE 11434

CMD ["/start.sh"]