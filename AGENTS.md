# Repository Guidelines
请使用中文回答
## Project Structure & Module Organization
- `main.py`: FastAPI entrypoint and `apiproxy` script target.
- `service/`: Core gateway logic (`routes.py`, `upstream.py`, `auth.py`, `model_cache.py`, `context_store.py`, `settings.py`, `logging_config.py`).
- `tests/`: Pytest suite (async and sync tests), mirror new features here.
- `scripts/`: Helper scripts (e.g. `scripts/list_models.py`).
- `docs/`: Design notes (model routing, session context) that should stay in sync with code changes.

## Build, Run & Test Commands
- Create env & install: `python -m venv .venv && source .venv/bin/activate && pip install .`
- Local dev server: `apiproxy` or `uvicorn main:app --reload`.
- Docker stack (app + Redis): `docker-compose up -d` / `docker-compose down`.
- Run tests: `pytest` (or `pytest tests/test_chat_greeting.py` for a single file).

## Coding Style & Naming Conventions
- Python 3.12, PEP 8, 4-space indentation, `snake_case` for functions/variables, `PascalCase` for classes.
- Prefer type hints and small, focused async endpoints in `service/routes.py`.
- Keep configuration in `service/settings.py`, dependency wiring in `service/deps.py`, logging in `service/logging_config.py`.
- When adding new routes, reuse existing patterns for auth, context, and upstream calls.

## Testing Guidelines
- Use `pytest` and `pytest-asyncio` for async tests (`@pytest.mark.asyncio`).
- Place tests under `tests/` with names like `test_<feature>.py` and `test_<case>()`.
- Add or update tests for every new endpoint, caching rule, or context behavior.
- Human developers: run `pytest` and ensure green before opening a PR.
- AI agents (Codex/LLM helpers): **must not run tests themselves**. Instead:
  - write/update tests as needed;
  - tell the user exactly which test commands to run (e.g. `pytest`, or `pytest tests/test_chat_greeting.py`);
  - ask the user to run the tests and report the result back into the conversation.

## Commit & Pull Request Guidelines
- Existing history uses short, descriptive messages (often in Chinese). Follow that style; e.g., `添加模型缓存错误处理` or `Refine session logging`.
- Keep commits focused; group related changes (code + tests + docs).
- PRs should include: purpose, high-level changes, impacted endpoints, and test summary (`pytest`, manual curl examples if behavior changed).

## Spec & Agent Workflow (.specify)
- `.specify/memory/constitution.md`: Project principles that govern code quality, testing, UX, performance, and security. Read it before large refactors or process changes.
- `.specify/templates/*.md`: Templates for specs, plans, tasks, and agent files. Update these when you change the standard development workflow.
- `.specify/scripts/bash/create-new-feature.sh`: Scaffolds a numbered feature spec and branch name. Example: `bash .specify/scripts/bash/create-new-feature.sh 'Add rate limiting' --short-name rate-limit`.
- `.specify/scripts/bash/setup-plan.sh`: Creates an implementation plan from the template for the current feature branch.

## Security & Automation
- Secrets scanning is enforced via pre-commit (`detect-secrets` with `.secrets.baseline`).
- Run `pre-commit install` once, then `pre-commit run --all-files` before pushing.
- Never commit real API keys or `.env` contents; update the baseline only to reflect intentional, non-sensitive values.
