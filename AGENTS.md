# Repository Guidelines
请使用中文回答
## Project Structure & Module Organization
- `main.py`: FastAPI entrypoint and `apiproxy` script target.
- `app/`: Core gateway logic (`routes.py`, `upstream.py`, `auth.py`, `model_cache.py`, `context_store.py`, `settings.py`, `logging_config.py`).
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
- Prefer type hints and small, focused async endpoints in `app/routes.py`.
- Keep configuration in `app/settings.py`, dependency wiring in `app/deps.py`, logging in `app/logging_config.py`.
- When adding new routes, reuse existing patterns for auth, context, and upstream calls.

## 前端 UI 框架使用规范
- 当前前端技术栈：**Next.js + Tailwind CSS + shadcn/ui 风格组件库**，组件统一放在 `ai_higress_front/components/ui` 下（例如 `button.tsx`, `input.tsx`, `card.tsx`, `dialog.tsx`, `table.tsx` 等）。
- 新增或修改前端页面时，**优先复用 UI 组件库**，不要直接使用原生标签写样式（如直接写 `<button>`, `<input>`, `<select>` 并手动堆 Tailwind class）。
- 若现有 `@/components/ui` 中没有合适组件：
  - AI Agent 可以通过 **shadcn MCP** 查询/检索对应组件用法；
  - 在 `ai_higress_front` 目录下使用 **bun 命令** 安装，例如：`bunx shadcn@latest add button card dialog`（根据需要替换组件名），让组件落到 `components/ui` 后再使用。
- 如确实需要原生元素（极少数场景），也应先在 `@/components/ui` 中封装成组件，再在页面中引用，保持交互和样式的一致性。

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
- 配置 `SECRET_KEY`：请使用系统API `POST /system/secret-key/generate` 生成随机密钥并写入 `.env`，用于对敏感标识做 HMAC/加密，不会存储明文。
- Configure `SECRET_KEY`: use system API `POST /system/secret-key/generate` to generate a random secret and put it into `.env` for HMAC/encryption of sensitive identifiers (no plaintext storage).
