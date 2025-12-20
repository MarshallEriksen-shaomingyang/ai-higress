# syntax=docker/dockerfile:1
FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System dependencies for building uvicorn[standard] extras (uvloop, httptools)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        python3-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies based on pyproject.toml
COPY pyproject.toml ./
RUN python - <<'PY'
import pathlib
import tomllib

pyproject = tomllib.loads(pathlib.Path('pyproject.toml').read_text())
deps = pyproject.get('project', {}).get('dependencies', [])
pathlib.Path('requirements.txt').write_text('\n'.join(deps))
PY
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && rm -f requirements.txt

# Copy application source
COPY . .

ENV PORT=8000 \
    REDIS_URL=redis://redis:6379/0

EXPOSE 8000


# Set up the entrypoint script
RUN chmod +x ./entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
