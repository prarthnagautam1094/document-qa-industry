# Base image pinned to 3.12 rather than the exact local interpreter
# (3.14, brand new at the time of writing) — 3.12 has mature prebuilt
# manylinux wheels for every dependency here (chromadb's hnswlib,
# sentence-transformers' torch, psycopg2-binary), so the build stays
# fast and reproducible instead of falling back to a from-source compile
# for a dependency that hasn't shipped a 3.14 wheel yet.
FROM python:3.12-slim

WORKDIR /app

# Copy only the dependency manifest first so `pip install` is a cached
# layer that's skipped on every rebuild that only changes application
# code, not dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

# No --reload: on this project's dev machine, uvicorn/watchfiles'
# --reload spawns its worker under the wrong Python environment, which
# silently breaks Supabase auth verification (every request 401s with no
# error logged) — see services/auth_service.py and the project history.
# A container image is a production-shaped artifact regardless, so
# --reload has no place here even where that specific bug doesn't apply.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
