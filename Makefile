.PHONY: help sync-env dev-backend dev-frontend dev docker-up docker-down clean
.PHONY: build-bridge-dist

help: ## 显示帮助信息
	@echo "AI-Higress-Gateway 开发命令"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

sync-env: ## 同步前端环境变量
	@echo "同步环境变量..."
	@bash scripts/sync-frontend-env.sh

dev-backend: ## 启动后端开发服务器
	@echo "启动后端..."
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: sync-env ## 启动前端开发服务器（自动同步环境变量）
	@echo "启动前端..."
	cd frontend && bun run dev

dev: ## 同时启动前后端（需要两个终端）
	@echo "请在两个终端分别运行:"
	@echo "  终端1: make dev-backend"
	@echo "  终端2: make dev-frontend"

docker-up: ## 启动 Docker 开发栈
	@echo "启动 Docker 开发栈..."
	IMAGE_TAG=latest docker compose -f docker-compose.develop.yml --env-file .env up -d

docker-down: ## 停止 Docker 开发栈
	@echo "停止 Docker 开发栈..."
	docker compose -f docker-compose.develop.yml down

docker-logs: ## 查看 Docker 日志
	docker compose -f docker-compose.develop.yml logs -f

clean: ## 清理临时文件
	@echo "清理临时文件..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/.next
	rm -rf frontend/node_modules/.cache
	@echo "清理完成"

build-bridge-dist: ## 构建 Go Bridge 发布包（Linux/macOS/Windows）
	@bash scripts/build-bridge-dist.sh

install-backend: ## 安装后端依赖
	@echo "安装后端依赖..."
	cd backend && pip install -e .

install-frontend: ## 安装前端依赖
	@echo "安装前端依赖..."
	cd frontend && bun install

install: install-backend install-frontend ## 安装所有依赖

test-backend: ## 运行后端测试
	@echo "运行后端测试..."
	cd backend && pytest

lint-backend: ## 检查后端代码风格
	@echo "检查后端代码..."
	cd backend && ruff check .

format-backend: ## 格式化后端代码
	@echo "格式化后端代码..."
	cd backend && ruff format .
