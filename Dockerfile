# Local / portable runtime. Azure App Service uses its own Oryx build —
# this file is NOT part of that pipeline.
#
# Build context is the repo root:  docker build -t amebot .
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Deploy dependency set (kept identical to the Azure lockfile) ...
COPY Backend/requirements.txt ./Backend/requirements.txt
RUN pip install -r Backend/requirements.txt
# ... plus slowapi, so the container gets rate limiting without touching
# Backend/requirements.txt (the Azure lockfile).
RUN pip install "slowapi>=0.1.9"

COPY Backend/ ./Backend/
COPY frontend/ ./frontend/

WORKDIR /app/Backend
EXPOSE 8000

# On first boot with valid Azure keys, the app builds the FAISS index from
# Backend/data/amenify_manual.json (the index itself is not baked into the image).
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
