# APIProxy - AI Gateway

[Chinese README](README.zh.md)

APIProxy is a FastAPI-based AI gateway that exposes a single, OpenAI-compatible HTTP API on top of multiple upstream model providers. It adds routing, caching, session management, request-format adapters and cross-provider failover so your clients can talk to many LLMs through one stable endpoint.

---

## Features

- OpenAI-compatible API  
  Exposes `/v1/chat/completions` and `/models` so you can reuse existing OpenAI SDKs and tools.

- Multi-provider routing with logical models  
  Configure multiple providers via environment variables, map them into logical models stored in Redis, and let the gateway choose the best upstream based on weights and runtime metrics.

- Cross-provider failover (non-streaming and streaming)  
  - Non-streaming: when the selected provider returns a retryable error (e.g. 429, 5xx) or a transport error, the gateway automatically falls back to the next candidate provider.  
  - Streaming: if an upstream fails before any bytes have been sent, the gateway retries on the next provider; once output has started, a structured SSE error event is sent to the client instead.  
  - Retryable HTTP status codes are configurable per provider via `LLM_PROVIDER_{id}_RETRYABLE_STATUS_CODES`, with sensible defaults for `openai`, `gemini` and `claude/anthropic` (429, 500, 502, 503, 504).

- Request format adapters  
  Automatically detects and adapts different request shapes, such as Gemini-style `input` lists, into the OpenAI-style `messages` format expected by upstream chat APIs.

- Model list aggregation and caching  
  Fetches model lists from all configured providers, normalises them into an OpenAI-style `/models` response and caches them in Redis.

- Session context storage  
  Uses the `X-Session-Id` header to persist request/response snippets into Redis so you can inspect simple conversation history via an HTTP endpoint.

- Streaming and non-streaming support  
  Detects `stream` in the payload and `Accept: text/event-stream` to support both SSE streaming and plain JSON responses.

- Flexible configuration  
  Upstream addresses, API keys, Redis URL, provider weights and failover behaviour are all controlled through environment variables.

- Docker-friendly  
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

## Quick Start

Docker is the easiest way to run APIProxy locally or in production.

### Prerequisites

- Docker and Docker Compose  
- Git  
- Redis (containerised or external)

### 1. Run with Docker (recommended)

1. Clone the repo:

   ```bash
   git clone <https://github.com/MarshallEriksen-shaomingyang/ai-higress.git>
   cd APIProxy
   ```

2. Create and configure `.env`:

   ```bash
   cp .env.example .env
   ```

   - Set `REDIS_URL` to point to your Redis instance;  
   - Configure `APIPROXY_AUTH_TOKEN` as the gateway API token (clients must send its Base64-encoded form in `Authorization` headers; use `uv run scripts/encode_token.py <token>` to generate the encoded value);  
   - Configure `LLM_PROVIDERS` and `LLM_PROVIDER_{id}_*` for each provider;  
   - Optionally configure cross-provider failover per provider:

     ```env
     LLM_PROVIDER_openai_RETRYABLE_STATUS_CODES=429,500,502-504
     LLM_PROVIDER_gemini_RETRYABLE_STATUS_CODES=429,500,502,503,504
     LLM_PROVIDER_claude_RETRYABLE_STATUS_CODES=429,500,502,503,504
     ```

     See `docs/configuration.md` for a full description.

3. Start the stack:

   ```bash
   docker-compose up -d
   ```

   The API will be available at `http://localhost:8000`.

4. Tail logs (optional):

   ```bash
   docker-compose logs -f api
   ```

5. Stop the stack:

   ```bash
   docker-compose down
   ```

### 2. Local development

1. Clone the repo and install dependencies (Python 3.12+):

   ```bash
   git clone <https://github.com/MarshallEriksen-shaomingyang/ai-higress.git>
   cd APIProxy
   python -m venv .venv
   source .venv/bin/activate
   pip install .
   ```

2. Configure `.env`:

   ```bash
   cp .env.example .env
   ```

   - Point `REDIS_URL` at your local Redis;  
   - Configure `APIPROXY_AUTH_TOKEN` as the gateway API token (clients must send its Base64-encoded form; generate it via `uv run scripts/encode_token.py <token>`);  
   - Set up `LLM_PROVIDERS` and `LLM_PROVIDER_{id}_*`;  
   - Optionally override retryable status codes per provider with `LLM_PROVIDER_{id}_RETRYABLE_STATUS_CODES`.

3. Start the dev server:

   ```bash
   apiproxy
   # or
   uvicorn main:app --reload
   ```

   The API will be available at `http://localhost:8000`.

---

## Configuration

APIProxy is configured entirely via environment variables, typically loaded from `.env`. For full details see `.env.example` and `docs/configuration.md`.

Common settings:

| Variable                           | Description                                                                                         | Default                     |
|------------------------------------|-----------------------------------------------------------------------------------------------------|-----------------------------|
| `REDIS_URL`                        | Redis connection URL                                                                                | `redis://redis:6379/0`      |
| `APIPROXY_AUTH_TOKEN`              | Gateway API token; clients must send `Authorization: Bearer <base64(APIPROXY_AUTH_TOKEN)>` (generate via `uv run scripts/encode_token.py <token>`) | `timeline`                  |
| `MODELS_CACHE_TTL`                 | TTL for the aggregated models cache (seconds)                                                       | `300`                       |
| `MASK_AS_BROWSER`                  | When true, adds browser-like headers (User-Agent/Origin/Referer) to upstream requests              | `True`                      |
| `MASK_USER_AGENT`                  | User-Agent string to use when `MASK_AS_BROWSER` is enabled                                         | see `.env.example`          |
| `MASK_ORIGIN`                      | Optional Origin header when masking as a browser                                                    | `None`                      |
| `MASK_REFERER`                     | Optional Referer header when masking as a browser                                                   | `None`                      |
| `LLM_PROVIDERS`                    | Comma-separated provider ids, e.g. `openai,gemini,claude`                                           | `None`                      |
| `LLM_PROVIDER_{id}_NAME`           | Human-readable provider name                                                                        | required                    |
| `LLM_PROVIDER_{id}_BASE_URL`       | Provider API base URL                                                                               | required                    |
| `LLM_PROVIDER_{id}_API_KEY`        | API key / token for this provider                                                                   | required                    |
| `LLM_PROVIDER_{id}_MODELS_PATH`    | Path for listing models (relative to `BASE_URL`)                                                    | `/v1/models`                |
| `LLM_PROVIDER_{id}_WEIGHT`         | Base routing weight used by the scheduler                                                           | `1.0`                       |
| `LLM_PROVIDER_{id}_REGION`         | Optional region label such as `global` or `us-east`                                                 | `None`                      |
| `LLM_PROVIDER_{id}_MAX_QPS`        | Provider-level QPS limit                                                                            | `None`                      |
| `LLM_PROVIDER_{id}_RETRYABLE_STATUS_CODES` | Comma-separated HTTP status codes or ranges (e.g. `429,500,502-504`) treated as retryable. When unset, built-in defaults apply for `openai`, `gemini`, and `claude/anthropic` (`[429,500,502,503,504]`); otherwise a generic rule of 429 and 5xx is used. | `None` (fall back to defaults) |

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

- `GET /context/{session_id}` (auth required)  
  Returns stored conversation history for the given session id.

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

Note: by repository convention, AI agents (Codex/LLM helpers) do not run tests themselves; human developers should run the commands above and confirm the results.

---

## Contributing

Contributions are welcome. Before opening a PR:

- Add or update tests for any new endpoints, routing behaviour, or context handling;  
- Run `pytest` and ensure the suite passes locally;  
- Keep commits focused and follow the existing short, descriptive commit message style (Chinese or English is fine, e.g. `添加跨厂商故障转移` or `Add cross-provider failover`).

---

## License

This project is licensed under the MIT License. See `LICENSE` for details.
