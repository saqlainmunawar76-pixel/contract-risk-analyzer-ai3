# AI-Powered Contract & Legal Document Risk Analyzer
# TEYZIX CORE Internship Task 3 (AI-3) — Docker Deployment (Bonus Feature)

FROM python:3.11-slim

# System dependency: tesseract-ocr binary required by pytesseract for
# OCR fallback on scanned PDF pages.
RUN apt-get update && \
    apt-get install -y --no-install-recommends tesseract-ocr curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persist the SQLite database and uploaded sample contracts outside the
# container layer so data survives container restarts when this path is
# mounted as a volume (see docker-compose.yml).
RUN mkdir -p /app/data

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
