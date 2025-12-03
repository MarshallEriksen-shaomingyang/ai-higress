# Monorepo 优化方案

## 📋 优化目标

1. **清晰的目录结构** - 前后端职责分离,便于独立开发和维护
2. **高效的 CI/CD** - 智能触发,避免不必要的构建
3. **统一的代码规范** - 前后端共享配置,保持一致性
4. **简化的部署流程** - Docker 配置优化,支持独立或联合部署

---

## 🗂️ 优化后的目录结构

### 建议结构(保持向后兼容)

```
ai-higress/
├── backend/                    # 后端代码(从根目录迁移)
│   ├── app/                   # FastAPI 应用
│   ├── tests/                 # 后端测试
│   ├── alembic/               # 数据库迁移
│   ├── scripts/               # 后端脚本
│   ├── main.py                # 入口文件
│   ├── pyproject.toml         # Python 依赖
│   ├── Dockerfile             # 后端镜像
│   └── .env.example           # 后端环境变量模板
│
├── frontend/                   # 前端代码(重命名 ai_higress_front)
│   ├── app/                   # Next.js 应用
│   ├── components/            # React 组件
│   ├── http/                  # API 客户端
│   ├── lib/                   # 工具函数
│   ├── public/                # 静态资源
│   ├── package.json           # Node.js 依赖
│   ├── Dockerfile             # 前端镜像(可选)
│   └── .env.local.example     # 前端环境变量模板
│
├── shared/                     # 共享资源
│   ├── api-types/             # API 类型定义(TypeScript + Python)
│   │   ├── __init__.py        # Python 类型定义
│   │   └── index.ts           # TypeScript 类型定义
│   └── docs/                  # API 契约文档
│
├── .github/                    # CI/CD 配置
│   └── workflows/
│       ├── backend-ci.yml     # 后端 CI
│       ├── frontend-ci.yml    # 前端 CI
│       ├── integration.yml    # 集成测试
│       └── deploy.yml         # 部署流程
│
├── docs/                       # 项目文档
│   ├── backend/               # 后端文档
│   ├── frontend/              # 前端文档
│   ├── api-contract.md        # API 契约
│   └── development-guide.md   # 开发指南
│
├── docker-compose.yml          # 开发环境编排
├── docker-compose.prod.yml     # 生产环境编排
├── .gitignore                  # Git 忽略规则
├── .pre-commit-config.yaml     # Git hooks
├── README.md                   # 项目介绍
└── MONOREPO.md                 # Monorepo 管理指南
```

### 兼容性方案(推荐)

考虑到迁移成本,建议采用**渐进式优化**:

```
ai-higress/
├── app/                        # 后端代码(保持现状)
├── tests/                      # 后端测试(保持现状)
├── alembic/                    # 数据库迁移(保持现状)
├── scripts/                    # 后端脚本(保持现状)
├── main.py                     # 后端入口(保持现状)
├── pyproject.toml              # Python 依赖(保持现状)
│
├── frontend/                   # 前端代码(重命名 ai_higress_front)
│   ├── app/
│   ├── components/
│   └── package.json
│
├── .github/                    # 新增 CI/CD 配置
│   └── workflows/
│       ├── backend.yml
│       ├── frontend.yml
│       └── integration.yml
│
├── docs/                       # 文档目录(优化)
│   ├── backend/
│   ├── frontend/
│   └── monorepo-guide.md
│
├── docker-compose.yml          # 保持现状
├── Dockerfile                  # 后端镜像(保持现状)
├── .gitignore                  # 优化配置
└── README.md                   # 更新文档
```

---

## 🔧 关键配置优化

### 1. .gitignore 优化

```gitignore
# ============================================
# Python (Backend)
# ============================================
__pycache__/
*.py[oc]
build/
dist/
wheels/
*.egg-info

# Virtual environments
.venv/
.uv-*
.pytest_*

# Backend logs
logs/
*.log

# Backend environment
.env

# ============================================
# Node.js (Frontend)
# ============================================

# Dependencies
frontend/node_modules/
frontend/.pnp/
frontend/.yarn/

# Build outputs
frontend/.next/
frontend/out/
frontend/build/

# Frontend environment
frontend/.env.local
frontend/.env.*.local

# Misc
frontend/.DS_Store
frontend/*.tsbuildinfo
frontend/next-env.d.ts

# ============================================
# IDE & Tools
# ============================================
.vscode/
.idea/
.serena/
.codebuddy/
specs/
.specs/

# ============================================
# Project-specific
# ============================================
CODEBUDDY.md
ai_higress/  # 旧前端目录(迁移后可删除)
```

### 2. GitHub Actions CI/CD 配置

#### backend.yml - 后端 CI

```yaml
name: Backend CI

on:
  push:
    branches: [main, develop]
    paths:
      - 'app/**'
      - 'tests/**'
      - 'alembic/**'
      - 'scripts/**'
      - 'main.py'
      - 'pyproject.toml'
      - 'Dockerfile'
      - '.github/workflows/backend.yml'
  pull_request:
    branches: [main, develop]
    paths:
      - 'app/**'
      - 'tests/**'
      - 'alembic/**'
      - 'scripts/**'
      - 'main.py'
      - 'pyproject.toml'
      - 'Dockerfile'

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: apiproxy_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install .
      
      - name: Run linting (Ruff)
        run: |
          ruff check app/ tests/
          ruff format --check app/ tests/
      
      - name: Run tests
        env:
          DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/apiproxy_test
          REDIS_URL: redis://localhost:6379/0
          SECRET_KEY: test-secret-key-for-ci
        run: |
          pytest --cov=app --cov-report=xml --cov-report=term
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          flags: backend
          name: backend-coverage

  docker-build:
    runs-on: ubuntu-latest
    needs: lint-and-test
    if: github.event_name == 'push'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Build Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile
          push: false
          tags: apiproxy-api:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

#### frontend.yml - 前端 CI

```yaml
name: Frontend CI

on:
  push:
    branches: [main, develop]
    paths:
      - 'frontend/**'
      - '.github/workflows/frontend.yml'
  pull_request:
    branches: [main, develop]
    paths:
      - 'frontend/**'

jobs:
  lint-and-build:
    runs-on: ubuntu-latest
    
    defaults:
      run:
        working-directory: frontend
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Bun
        uses: oven-sh/setup-bun@v1
        with:
          bun-version: latest
      
      - name: Install dependencies
        run: bun install --frozen-lockfile
      
      - name: Run linting
        run: bun run lint
      
      - name: Type checking
        run: bunx tsc --noEmit
      
      - name: Build
        run: bun run build
        env:
          NEXT_PUBLIC_API_URL: http://localhost:8000
      
      - name: Upload build artifacts
        if: github.event_name == 'push'
        uses: actions/upload-artifact@v4
        with:
          name: frontend-build-${{ github.sha }}
          path: frontend/.next
          retention-days: 7

  docker-build:
    runs-on: ubuntu-latest
    needs: lint-and-build
    if: github.event_name == 'push'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Build Docker image
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          file: ./frontend/Dockerfile
          push: false
          tags: apiproxy-frontend:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

#### integration.yml - 集成测试

```yaml
name: Integration Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Create .env file
        run: |
          cp .env.example .env
          echo "POSTGRES_PASSWORD=test123" >> .env
          echo "REDIS_PASSWORD=test123" >> .env
          echo "SECRET_KEY=test-secret-key" >> .env
      
      - name: Start services
        run: docker-compose up -d
      
      - name: Wait for services
        run: |
          timeout 60 bash -c 'until curl -f http://localhost:8000/health; do sleep 2; done'
      
      - name: Run integration tests
        run: |
          # 测试后端 API
          curl -f http://localhost:8000/models -H "Authorization: Bearer test-token"
          
          # 测试前端可访问性(如果有前端服务)
          # curl -f http://localhost:3000
      
      - name: Collect logs
        if: failure()
        run: |
          docker-compose logs api > api-logs.txt
          docker-compose logs postgres > postgres-logs.txt
          docker-compose logs redis > redis-logs.txt
      
      - name: Upload logs
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: integration-logs
          path: '*-logs.txt'
      
      - name: Cleanup
        if: always()
        run: docker-compose down -v
```

### 3. Docker 配置优化

#### docker-compose.yml (开发环境)

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: apiproxy-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:?POSTGRES_USER not set}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD not set}
      POSTGRES_DB: ${POSTGRES_DB:?POSTGRES_DB not set}
    ports:
      - "127.0.0.1:35432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - apiproxy-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: apiproxy-redis
    restart: unless-stopped
    ports:
      - "127.0.0.1:16379:6379"
    volumes:
      - redis-data:/data
      - ./redis/redis.conf:/usr/local/etc/redis/redis.conf:ro
    environment:
      REDIS_PASSWORD: ${REDIS_PASSWORD:?REDIS_PASSWORD not set}
    command:
      - sh
      - -c
      - |
        redis-server /usr/local/etc/redis/redis.conf --requirepass "$${REDIS_PASSWORD}"
    networks:
      - apiproxy-net
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  api:
    build:
      context: .
      dockerfile: Dockerfile
    image: apiproxy-api:latest
    container_name: apiproxy-api
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
      # 开发模式:挂载源代码实现热重载
      - ./app:/app/app:ro
      - ./main.py:/app/main.py:ro
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8000:8000"
    networks:
      - apiproxy-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    # 开发模式:启用热重载
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  # 前端服务(可选,用于开发环境)
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    container_name: apiproxy-frontend
    restart: unless-stopped
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    volumes:
      - ./frontend:/app:cached
      - /app/node_modules
      - /app/.next
    ports:
      - "3000:3000"
    networks:
      - apiproxy-net
    depends_on:
      - api

volumes:
  postgres-data:
  redis-data:

networks:
  apiproxy-net:
    driver: bridge
```

#### frontend/Dockerfile.dev (前端开发镜像)

```dockerfile
FROM oven/bun:1-alpine AS base

WORKDIR /app

# Install dependencies
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

# Copy source
COPY . .

EXPOSE 3000

CMD ["bun", "run", "dev"]
```

#### frontend/Dockerfile (前端生产镜像)

```dockerfile
FROM oven/bun:1-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile --production=false

# Copy source and build
COPY . .
RUN bun run build

# Production image
FROM oven/bun:1-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Copy built files
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000

CMD ["bun", "run", "start"]
```

### 4. Pre-commit 配置优化

```yaml
repos:
  # Python 代码检查
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
        args: [--fix]
        files: ^(app|tests|scripts)/.*\.py$
      - id: ruff-format
        files: ^(app|tests|scripts)/.*\.py$

  # 密钥检测
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']

  # 前端代码检查
  - repo: local
    hooks:
      - id: frontend-lint
        name: Frontend ESLint
        entry: bash -c 'cd frontend && bun run lint'
        language: system
        files: ^frontend/.*\.(ts|tsx|js|jsx)$
        pass_filenames: false

  # 通用检查
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
        exclude: ^\.github/workflows/
      - id: check-json
      - id: check-merge-conflict
      - id: check-added-large-files
        args: ['--maxkb=1000']
```

---

## 📚 前后端协作规范

### API 契约管理

1. **类型定义同步**
   - 后端修改 Pydantic schema 后,自动生成 TypeScript 类型
   - 使用工具:`openapi-typescript` 或 `quicktype`

   ```bash
   # 生成 TypeScript 类型
   curl http://localhost:8000/openapi.json | \
     bunx openapi-typescript -o frontend/lib/api-types.ts
   ```

2. **API 文档维护**
   - FastAPI 自动生成 OpenAPI 文档:`http://localhost:8000/docs`
   - 前端基于 OpenAPI spec 生成 API 客户端

3. **版本管理**
   - API 使用语义化版本:`v1`, `v2`
   - 前端通过环境变量指定 API 版本

### 开发流程

1. **功能开发**
   ```bash
   # 创建功能分支
   git checkout -b feature/user-management
   
   # 后端开发
   cd .
   source .venv/bin/activate
   uvicorn main:app --reload
   
   # 前端开发(新终端)
   cd frontend
   bun dev
   ```

2. **提交代码**
   ```bash
   # Pre-commit 自动检查
   git add .
   git commit -m "feat: add user management"
   
   # Push 触发 CI
   git push origin feature/user-management
   ```

3. **代码审查**
   - 后端 PR:至少一名后端开发者 review
   - 前端 PR:至少一名前端开发者 review
   - 全栈 PR:前后端各一名开发者 review

---

## 🚀 迁移步骤

### 阶段 1:重命名前端目录(无破坏性)

```bash
# 1. 重命名前端目录
git mv ai_higress_front frontend

# 2. 更新 docker-compose.yml 中的路径
# 将 ai_higress_front/ 改为 frontend/

# 3. 更新 .gitignore
# 将 ai_higress/ 改为 frontend/ 相关规则

# 4. 提交变更
git add -A
git commit -m "refactor: rename frontend directory"
```

### 阶段 2:添加 CI/CD 配置

```bash
# 1. 创建 .github/workflows/ 目录
mkdir -p .github/workflows

# 2. 添加 CI 配置文件
# (复制上述 backend.yml, frontend.yml, integration.yml)

# 3. 测试 CI 流程
git push origin main
```

### 阶段 3:优化配置文件

```bash
# 1. 更新 .gitignore
# 2. 更新 .pre-commit-config.yaml
# 3. 添加前端 Dockerfile

git add -A
git commit -m "chore: optimize monorepo configuration"
```

### 阶段 4:文档更新

```bash
# 1. 更新 README.md
# 2. 创建 docs/monorepo-guide.md
# 3. 更新前端 README.md

git add -A
git commit -m "docs: update monorepo documentation"
```

---

## 📖 最佳实践

### 1. 依赖管理

- **后端**:使用 `pyproject.toml` 管理依赖,优先使用 `uv` 或 `pip`
- **前端**:使用 `package.json` 管理依赖,优先使用 `bun`
- **版本锁定**:后端 `requirements.txt`,前端 `bun.lock`

### 2. 环境变量

- **后端**:`.env` 文件,通过 Pydantic Settings 加载
- **前端**:`.env.local` 文件,只有 `NEXT_PUBLIC_*` 前缀的变量会暴露到浏览器
- **敏感信息**:永远不要提交到 Git,使用 CI secrets

### 3. 测试策略

- **后端**:
  - 单元测试:`pytest tests/`
  - 集成测试:`pytest tests/integration/`
  - 覆盖率目标:80%+

- **前端**:
  - 组件测试:Jest + React Testing Library
  - E2E 测试:Playwright(可选)
  - 类型检查:`tsc --noEmit`

### 4. 代码规范

- **后端**:
  - Linter: Ruff
  - Formatter: Ruff format
  - 类型检查: Python type hints

- **前端**:
  - Linter: ESLint
  - Formatter: Prettier(内置于 ESLint)
  - 类型检查: TypeScript strict mode

### 5. Git 工作流

- **分支策略**:
  - `main`: 生产分支,受保护
  - `develop`: 开发分支
  - `feature/*`: 功能分支
  - `fix/*`: 修复分支

- **提交规范**:
  ```
  feat: 新功能
  fix: 修复 bug
  docs: 文档更新
  style: 代码格式调整
  refactor: 重构
  test: 测试相关
  chore: 构建/工具配置
  ```

---

## 🔍 常见问题

### Q1: 为什么不直接拆分成两个仓库?

**A:** 对于当前规模的项目,Monorepo 的优势更明显:
- 版本同步简单(前后端 API 变更在同一 commit)
- 开发效率高(一次 PR 完成全栈功能)
- 部署简单(docker-compose 一键启动)

### Q2: CI 会不会很慢?

**A:** 不会。通过 `paths` 过滤器,只有相关代码变更才会触发对应的 CI:
- 只改后端代码 → 只运行后端 CI
- 只改前端代码 → 只运行前端 CI
- 两者都改 → 两个 CI 并行运行

### Q3: 如何共享类型定义?

**A:** 两种方案:
1. **自动生成**(推荐):后端 OpenAPI → TypeScript 类型
2. **手动维护**:`shared/api-types/` 目录

### Q4: 前端如何调用本地后端 API?

**A:** 在前端 `.env.local` 中配置:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Q5: 何时考虑拆分仓库?

**A:** 当满足以下条件时:
- 团队规模 > 10 人,前后端分组明确
- 前后端发布节奏完全独立
- 需要严格的权限隔离

---

## 📝 总结

通过本次优化,项目将获得:

✅ **更清晰的结构** - 前后端职责分离,易于维护
✅ **更高效的 CI** - 智能触发,节省时间和资源
✅ **更好的协作** - 统一规范,减少沟通成本
✅ **更简单的部署** - Docker 配置优化,支持多种场景

同时保持了 Monorepo 的核心优势:

🎯 **版本同步** - 前后端 API 变更一次完成
🎯 **开发效率** - 一个 PR 搞定全栈功能
🎯 **代码复用** - 类型定义、工具函数共享
🎯 **简化管理** - 一个仓库,一套流程

---

## 🔗 相关资源

- [Monorepo 最佳实践](https://monorepo.tools/)
- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [Next.js 环境变量](https://nextjs.org/docs/app/building-your-application/configuring/environment-variables)
- [FastAPI 项目结构](https://fastapi.tiangolo.com/tutorial/bigger-applications/)