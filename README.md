# APIProxy - AI Gateway

[Chinese README](README.zh.md)

APIProxy is a FastAPI-based AI gateway that exposes a single, OpenAI-compatible HTTP API on top of multiple upstream model providers. It adds routing, caching, session management, request-format adapters and cross-provider failover so your clients can talk to many LLMs through one stable endpoint.

---

## 📁 Project Structure

This project uses a **Monorepo** architecture with clear separation between backend and frontend:

```
ai-higress/
├── backend/              # FastAPI backend (AI Gateway)
│   ├── app/             # Application code
│   ├── tests/           # Backend tests
│   ├── alembic/         # Database migrations
│   ├── scripts/         # Utility scripts
│   ├── main.py          # Entry point
│   ├── Dockerfile       # Backend container
│   └── .env.example     # Backend environment template
│
├── frontend/            # Next.js frontend (Management UI)
│   ├── app/            # Next.js app directory
│   ├── components/     # React components
│   ├── http/           # API client
│   ├── lib/            # Utilities
│   ├── Dockerfile      # Production container
│   └── Dockerfile.dev  # Development container
│
├── .github/            # CI/CD workflows
│   └── workflows/
│       ├── backend.yml      # Backend CI
│       ├── frontend.yml     # Frontend CI
│       └── integration.yml  # E2E tests
│
├── docs/               # Project documentation
│   ├── monorepo-optimization-plan.md
│   └── migration-remaining-tasks.md
│
├── docker-compose.yml  # Development environment
└── README.md          # This file
```

For detailed information about the Monorepo setup, see:
- [Monorepo Optimization Plan](docs/monorepo-optimization-plan.md)
- [Development Guide](docs/migration-remaining-tasks.md)

---

## Features

- **OpenAI-compatible API**  
  Exposes `/v1/chat/completions`, `/v1/responses`, and `/models` so you can reuse existing OpenAI SDKs and tools.

- **Dynamic Multi-provider Routing**  
  - **Logical Models**: Map multiple physical provider models to a single logical model (e.g., "fast-model" -> OpenAI's `gpt-3.5-turbo`, Gemini's `gemini-pro`).
  - **Zero-Configuration Model Routing**: If a requested model is not explicitly mapped, the gateway automatically discovers which providers support it and creates a dynamic routing group on the fly.
  - **Weighted & Metrics-based Scheduling**: Distributes traffic based on configured weights and runtime performance metrics.

- **Cross-provider Failover**  
  Automatically retries requests on a different provider upon retryable errors (e.g., 429, 5xx) for both streaming and non-streaming requests.

- **Request Format Adapters**  
  - Automatically converts different request formats into a unified OpenAI-style `messages` structure.
  - Supports Gemini-style `input`, Claude-style requests, and the OpenAI Responses API (`/v1/responses`).
  - When clients call `/v1/responses`, the payload now stays in native Responses shape end-to-end: the router forwards traffic to upstream `/v1/responses` endpoints so models that have dropped `/v1/chat/completions` (e.g. `gpt-5.1-codex`) continue to work without extra adapters.
  - Handles prefixed model names (e.g., `my-provider/some-model`) for simpler routing logic.

- **Session Stickiness**  
  Binds a conversation (via `X-Session-Id` header) to the first-chosen provider to maintain context in multi-message conversations.

- **Model List Aggregation & Caching**  
  Fetches model lists from all configured providers, normalises them into an OpenAI-style `/models` response and caches them in Redis.

- **Streaming and Non-streaming Support**  
  Detects `stream` in the payload and `Accept: text/event-stream` to support both SSE streaming and plain JSON responses.

- **Session Context Storage**  
  Uses the `X-Session-Id` header to persist request/response snippets into Redis so you can inspect simple conversation history via an HTTP endpoint.

- **Flexible Configuration**  
  Upstream addresses, API keys, Redis URL, provider weights and failover behaviour are all controlled through environment variables.

- **Docker-friendly**  
  Includes a `docker-compose.yml` that starts the API gateway and Redis with a single command.

---

## Tech Stack

- Web framework: FastAPI  
- ASGI server: Uvicorn  
- HTTP client: HTTPX  
- Cache / storage: Redis  
- Config management: Pydantic Settings  
- Dependency management: uv / pip

---

## 🚀 Quick Start

APIProxy provides a robust and flexible solution for managing AI model interactions. This section guides you through setting up and running the gateway, whether for local development or larger-scale deployments. The recommended approach utilizes Docker for ease of setup and consistency across environments.

### Prerequisites

- Docker and Docker Compose  
- Git  
- Redis (containerised or external)

### 1. Run with Docker (recommended)

1. Clone the repo:

   ```bash
   git clone https://github.com/MarshallEriksen-shaomingyang/ai-higress.git
   cd APIProxy
   ```

2. Create and configure `.env`:

   ```bash
   cp .env.example .env
   ```

3. Seed providers/models in the database:

   Provider and model metadata is now stored in PostgreSQL (`providers`, `provider_api_keys`, `provider_models`). Use Alembic to create the tables, then insert rows either via the upcoming management APIs or a short bootstrap script. The snippet below creates an OpenAI provider with one API key:

   ```bash
   cd backend
   uv run python - <<'PY'
from uuid import uuid4

from app.db.session import SessionLocal
from app.models import Provider, ProviderAPIKey
from app.services.encryption import encrypt_secret

session = SessionLocal()
provider = Provider(
    id=uuid4(),
    provider_id="openai",
    name="OpenAI",
    base_url="https://api.openai.com",
    transport="http",
    provider_type="native",
    models_path="/v1/models",
    messages_path="/v1/messages",
    weight=1.0,
)
session.add(provider)
session.flush()  # ensures provider.id is available for the FK
session.add(
    ProviderAPIKey(
        provider_uuid=provider.id,
        encrypted_key=encrypt_secret("sk-your-openai-api-key"),  # never stored in plaintext
        label="default",
        max_qps=50,
    )
)
session.commit()
session.close()
PY
   ```

   Set `provider_type="aggregator"` when the upstream is a reseller or intermediary platform; keep the default `"native"` for first-party vendors.

   Repeat the process for every upstream, add `provider_models` rows when you need static model metadata, and adjust weights/QPS the same way you would have tweaked the old environment variables. The encryption helper ensures API keys are always stored as ciphertext.

   Generate and set `SECRET_KEY` (used to derive the Fernet key above and to HMAC/encrypt other identifiers):

   ```bash
   curl -X POST "http://localhost:8000/system/secret-key/generate" \
     -H "Authorization: Bearer <initial_jwt_token>" \
     -H "Content-Type: application/json" \
     -d '{"length": 64}'
   ```

   Put the generated random string into `.env` as `SECRET_KEY`.

4. 🔑 Authentication & Key Management:

   The gateway uses a redesigned key management system that separates different types of keys:

   - **System Master Key**: Used to derive encryption keys and hash sensitive data.
   - **User Authentication**: JWT-based login system for user management.
   - **API Keys**: For client applications to access AI services.
   - **Provider Keys**: For accessing external AI services (OpenAI, Claude, etc.).

   On the first startup, the gateway automatically creates a superuser and system initialization:
   
   ```bash
   # Generate and set SYSTEM_MASTER_KEY (used for encryption/hashing):
   curl -X POST "http://localhost:8000/system/secret-key/generate" \
     -H "Content-Type: application/json" \
     -d '{"length": 64}'

   # Initialize system administrator (only works if no users exist):
   curl -X POST "http://localhost:8000/system/admin/init" \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "email": "admin@example.com", "display_name": "System Administrator"}'
   
   # Log in to get JWT token for further API operations:
   curl -X POST "http://localhost:8000/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "<returned_password>"}'
   
   # Create API keys for your applications:
   curl -X POST "http://localhost:8000/users/{user_id}/api-keys" \
     -H "Authorization: Bearer <jwt_token>" \
     -H "Content-Type: application/json" \
     -d '{"name": "my-app-key", "expiry": "MONTH"}'
   ```

   For AI service access, use API keys:
   ```bash
   curl -X GET "http://localhost:8000/models" \
     -H "Authorization: Bearer <api_key>"
   ```

   See [docs/key-management.md](docs/key-management.md) for detailed information about the key management system.

5. Start the stack:

   ```bash
   docker-compose up -d
   ```

   The API will be available at `http://localhost:8000`.

6. Test it with a curl command:

   ```bash
   curl -X POST "http://localhost:8000/v1/chat/completions" \
     -H "Authorization: Bearer dGltZWxpbmU=" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "gpt-3.5-turbo",
       "messages": [{"role": "user", "content": "Hello!"}]
     }'
   ```

7. Tail logs (optional):

   ```bash
   docker-compose logs -f api
   ```

8. Stop the stack:

   ```bash
   docker-compose down
   ```

### 2. Local development

1. Clone the repo and install dependencies (Python 3.12+):

   ```bash
   git clone https://github.com/MarshallEriksen-shaomingyang/ai-higress.git
   cd ai-higress
   ```

2. **Backend setup**:

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install .
   ```

3. Configure backend `.env`:

   ```bash
   cp .env.example .env
   ```

   - Point `REDIS_URL` and `DATABASE_URL` at your local services;
   - Configure `SECRET_KEY` for hashing/encrypting sensitive identifiers;
   - On first run the service will log the autogenerated superuser password and API key—capture them from the logs, rotate them, and use `/users` + `/users/{user_id}/api-keys` for ongoing management. Every request that hits the model/chat APIs must include `Authorization: Bearer <base64(token)>`;
   - Insert/update provider rows directly in the database as described above (or by using your internal admin tooling); set retryable status codes, weights, SDK transport, etc. via the table columns instead of environment variables.

4. **Frontend setup** (optional):

   ```bash
   cd ../frontend
   bun install
   ```

   Create frontend environment file:
   ```bash
   cp .env.local.example .env.local
   # Edit .env.local and set NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

5. Start development servers:

   **Backend** (in `backend/` directory):
   ```bash
   uvicorn main:app --reload
   ```
   The API will be available at `http://localhost:8000`.

   **Frontend** (in `frontend/` directory, new terminal):
   ```bash
   bun dev
   ```
   The UI will be available at `http://localhost:3000`.

---

## Configuration

Infrastructure-level settings still live in `.env`, but provider/model metadata is persisted in the database. See `docs/configuration.md` for a full walkthrough of the new tables and scripts.

Common settings:

| Variable                           | Description                                                                                         | Default                     |
|------------------------------------|-----------------------------------------------------------------------------------------------------|-----------------------------|
| `REDIS_URL`                        | Redis connection URL                                                                                | `redis://redis:6379/0`      |
| *(per-user API keys)*             | Use `/users/{user_id}/api-keys` to mint API keys (or seed them via your ops tooling); send `Authorization: Bearer <base64(token)>` with each request | _(generated)_               |
| `MODELS_CACHE_TTL`                 | TTL for the aggregated models cache (seconds)                                                       | `300`                       |
| `MASK_AS_BROWSER`                  | When true, adds browser-like headers (User-Agent/Origin/Referer) to upstream requests              | `True`                      |
| `MASK_USER_AGENT`                  | User-Agent string to use when `MASK_AS_BROWSER` is enabled                                         | see `.env.example`          |
| `MASK_ORIGIN`                      | Optional Origin header when masking as a browser                                                    | `None`                      |
| `MASK_REFERER`                     | Optional Referer header when masking as a browser                                                   | `None`                      |
| `LOG_LEVEL`                        | Application log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)                             | `INFO`                      |
| `LOG_TIMEZONE`                     | Timezone for log timestamps (e.g. `Asia/Shanghai`); defaults to the server's local timezone         | system local timezone       |
| Variable          | Description                                                                                              | Default                                                |
|-------------------|----------------------------------------------------------------------------------------------------------|--------------------------------------------------------|
| `DATABASE_URL`    | SQLAlchemy URL for the primary Postgres instance                                                          | `postgresql+psycopg://postgres:postgres@localhost:5432/apiproxy` |
| `REDIS_URL`       | Redis connection URL                                                                                      | `redis://redis:6379/0`                                 |
| `SECRET_KEY`      | Random string used to derive Fernet/HMAC keys (generate via `bash scripts/generate_secret_key.sh`)        | `please-change-me`                                     |
| `MODELS_CACHE_TTL`| TTL for the aggregated `/models` cache (seconds)                                                          | `300`                                                  |
| `MASK_AS_BROWSER` | Whether to add browser-like headers to upstream calls                                                     | `True`                                                 |
| `MASK_USER_AGENT` | User-Agent used when `MASK_AS_BROWSER` is enabled                                                          | Chrome UA (see `.env.example`)                         |
| `MASK_ORIGIN`     | Optional Origin header when masking as a browser                                                          | `None`                                                 |
| `MASK_REFERER`    | Optional Referer header when masking as a browser                                                         | `None`                                                 |
| `LOG_LEVEL`       | Application log level                                                                                     | `INFO`                                                 |
| `LOG_TIMEZONE`    | Optional timezone for log timestamps (e.g. `Asia/Shanghai`)                                               | system local                                           |

> Provider-specific properties such as weights, transports, retryable status codes, SDK type, and static models are now stored in the `providers`, `provider_api_keys`, and `provider_models` tables. Update those rows instead of editing environment variables.

### Database & migrations

- Pydantic request/response schemas now live in `backend/app/schemas`, while `backend/app/models` contains the SQLAlchemy ORM definitions (currently `User`, `Identity`, and `Permission`).
- Configure `DATABASE_URL` (see `backend/.env.example`) to point at your Postgres instance. The provided `docker-compose.yml` already exposes a Postgres service with matching env vars.
- Run migrations via Alembic:

  ```bash
  cd backend
  # install deps / activate venv first
  alembic upgrade head
  ```

  This applies the initial migration located at `backend/alembic/versions/0001_create_auth_tables.py`, which creates the three auth tables. Subsequent schema changes should follow the same workflow.

---

## API Endpoints

### Core gateway endpoints

- `GET /health`  
  Basic health check.

- `GET /models` (auth required)  
  Returns an OpenAI-style models list aggregated from all configured providers.

- `POST /v1/chat/completions` (auth required)  
  Main chat endpoint. Supports:
  - OpenAI-style requests;  
  - Claude-style requests;  
  - Gemini-style `input` payloads (auto-converted to `messages`);  
  - Streaming and non-streaming responses;  
  - Multi-provider routing and cross-provider failover.
- `POST /v1/responses` (auth required)  
  Compatibility shim for the OpenAI Responses API. It maps `instructions`/`input`
  fields to standard chat `messages` and reuses the same routing + streaming logic.

- `GET /context/{session_id}` (auth required)  
  Returns stored conversation history for the given session id.

### Working with `/v1/responses`

- POSTing to `/v1/responses` keeps the request in OpenAI Responses format all the way to the upstream: the gateway tags the payload so the routing layer selects `/v1/responses` endpoints instead of `/v1/chat/completions`.
- Dynamic routing automatically follows suit when the client used `/v1/responses`; for statically configured logical models, point each `PhysicalModel.endpoint` to the provider's `/v1/responses` URL if the upstream requires it.
- Streaming calls are forwarded verbatim, so SDKs receive native `response.*` SSE events; `/v1/chat/completions` continues to provide OpenAI chat-style chunks.
- Use this endpoint for newer OpenAI models such as `gpt-5.1-codex`, which reject `/v1/chat/completions` entirely.

### Provider and routing endpoints

- `GET /providers`  
  List all configured providers.

- `GET /providers/{provider_id}`  
  Return configuration for a single provider.

- `GET /providers/{provider_id}/models`  
  Return (and cache) the raw models list for a provider.

- `GET /providers/{provider_id}/health`  
  Perform a lightweight health-check against the provider.

- `GET /providers/{provider_id}/metrics`  
  Return routing metrics snapshots for a provider.

- `GET /logical-models`  
  List all logical models stored in Redis.

- `GET /logical-models/{logical_model_id}`  
  Return a single logical model definition.

- `GET /logical-models/{logical_model_id}/upstreams`  
  Return the upstream physical models mapped to a logical model.

- `POST /routing/decide`  
  Compute a routing decision for a logical model, returning the selected upstream and scored candidates.

- `GET /routing/sessions/{conversation_id}`  
  Inspect the session stickiness binding for a conversation.

- `DELETE /routing/sessions/{conversation_id}`  
  Delete a session binding (cancel stickiness).

---

## Testing

The project uses `pytest` and `pytest-asyncio` for testing.

Run the full test suite:

```bash
pytest
```

Or run a specific file:

```bash
pytest tests/test_chat_greeting.py
```

---

## Contributing

Contributions are welcome. Before opening a PR:

- Add or update tests for any new endpoints, routing behaviour, or context handling;  
- Run `pytest` and ensure the suite passes locally;  
- Keep commits focused and follow the existing short, descriptive commit message style (Chinese or English is fine, e.g. `添加跨厂商故障转移` or `Add cross-provider failover`).

---

## License

This project is licensed under the MIT License. See `LICENSE` for details.
