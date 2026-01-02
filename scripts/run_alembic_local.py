from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.settings import settings

# Construct a direct connection string for Alembic offline generation if env vars are missing.
# But here we just want to ensure we can connect.
# We will just patch os.environ for the duration of this command if running locally.

def run_alembic_with_local_db():
    import subprocess
    
    env = os.environ.copy()
    env["POSTGRES_HOST"] = "127.0.0.1"
    env["POSTGRES_PORT"] = "5432"
    env["POSTGRES_USER"] = "postgres"
    env["POSTGRES_PASSWORD"] = "postgres"
    env["POSTGRES_DB"] = "ai_gateway"
    
    cmd = ["/data/AI-Higress-Gateway/backend/.venv/bin/alembic", "revision", "--autogenerate", "-m", "add_kb_global_embedding_model"]
    
    subprocess.run(cmd, env=env, cwd="backend", check=True)

if __name__ == "__main__":
    run_alembic_with_local_db()
