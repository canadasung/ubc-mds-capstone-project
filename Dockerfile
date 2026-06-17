# Dockerfile for the FastAPI backend on a Hugging Face Docker Space.
#
# Build context = the Space repo root, which must contain (at minimum):
#   Dockerfile  requirements.txt  README.md  backend_api/  scripts/  data/sample/
#
# The routers add the project root to sys.path and read data/sample/*.csv, so
# backend_api/, scripts/, and data/ all have to be present (see backend_api/routers/*.py).

FROM python:3.12-slim

# HF Spaces run the container as uid 1000; create a matching user.
RUN useradd -m -u 1000 user

WORKDIR /app

# Install deps first so this layer is cached across code changes.
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the (subset) repo.
COPY --chown=user . .

USER user

# HF's default app port.
EXPOSE 7860
CMD ["uvicorn", "backend_api.main:app", "--host", "0.0.0.0", "--port", "7860"]
