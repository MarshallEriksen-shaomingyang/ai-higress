# Monorepo 迁移剩余任务清单

## 📊 当前迁移状态

### ✅ 已完成
- [x] 后端代码迁移到 `backend/` 目录
- [x] 前端代码迁移到 `fronted/` 目录
- [x] 优化方案文档编写

### ⚠️ 需要修复
- [ ] 前端目录名称拼写错误:`fronted/` → `frontend/`

### 🔨 待完成
- [ ] 创建 GitHub Actions CI/CD 配置
- [ ] 更新根目录配置文件
- [ ] 创建前端 Dockerfile
- [ ] 更新 docker-compose.yml
- [ ] 更新文档和 README

---

## 🎯 剩余任务详情

### 任务 1: 修复前端目录名称 (优先级: 🔴 高)

**问题**: 前端目录当前命名为 `fronted/`,应该是 `frontend/`

**操作步骤**:
```bash
# 使用 git mv 保留提交历史
git mv fronted frontend
git commit -m "fix: correct frontend directory name (fronted → frontend)"
```

**影响范围**:
- docker-compose.yml 中的路径引用
- 文档中的路径引用
- CI/CD 配置中的路径引用

---

### 任务 2: 创建 GitHub Actions CI/CD 配置 (优先级: 🔴 高)

#### 2.1 创建目录结构
```bash
mkdir -p .github/workflows
```

#### 2.2 创建文件列表
1. `.github/workflows/backend.yml` - 后端 CI
2. `.github/workflows/frontend.yml` - 前端 CI  
3. `.github/workflows/integration.yml` - 集成测试
4. `.github/workflows/deploy.yml` - 部署流程(可选)

#### 2.3 配置内容
所有配置内容已在 [`monorepo-optimization-plan.md`](monorepo-optimization-plan.md:237) 中提供。

---

### 任务 3: 更新根目录配置文件 (优先级: 🟡 中)

#### 3.1 更新 `.gitignore`

**当前问题**:
- 前后端忽略规则混在一起
- 缺少新目录结构的规则

**需要的更改**:
```gitignore
# ============================================
# Python (Backend)
# ============================================
backend/__pycache__/
backend/*.py[oc]
backend/.venv/
backend/.pytest_*
backend/logs/

# Backend environment
backend/.env

# ============================================
# Node.js (Frontend)  
# ============================================
frontend/node_modules/
frontend/.next/
frontend/out/
frontend/build/
frontend/.env.local
frontend/.env.*.local
frontend/*.tsbuildinfo
frontend/next-env.d.ts

# ============================================
# 旧目录(迁移后可删除)
# ============================================
# ai_higress_front/  # 已迁移
# app/               # 已迁移到 backend/
# tests/             # 已迁移到 backend/
# alembic/           # 已迁移到 backend/
```

#### 3.2 更新 `.pre-commit-config.yaml`

**需要添加**:
- 后端代码路径过滤
- 前端代码检查钩子

完整配置见 [`monorepo-optimization-plan.md`](monorepo-optimization-plan.md:370)

#### 3.3 更新 `pyproject.toml`

**需要的更改**:
```toml
[project.scripts]
# 更新入口点,指向新的后端目录
apiproxy = "backend.main:run"
```

**或者**: 在根目录保留 `main.py` 作为入口,内部导入 `backend/main.py`

---

### 任务 4: 创建前端 Dockerfile (优先级: 🟡 中)

#### 4.1 开发环境 Dockerfile

**文件**: `frontend/Dockerfile.dev`

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

#### 4.2 生产环境 Dockerfile

**文件**: `frontend/Dockerfile`

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

---

### 任务 5: 更新 docker-compose.yml (优先级: 🔴 高)

#### 5.1 需要的更改

1. **更新后端服务的构建上下文**:
```yaml
api:
  build:
    context: ./backend  # 从根目录改为 backend/
    dockerfile: Dockerfile
```

2. **更新后端服务的卷挂载**:
```yaml
volumes:
  - ./backend/logs:/app/logs
  - ./backend/app:/app/app:ro
  - ./backend/main.py:/app/main.py:ro
```

3. **添加前端服务**(可选,用于开发环境):
```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile.dev
  container_name: apiproxy-frontend
  restart: unless-stopped
  environment:
    - NEXT_PUBLIC_API_URL=http://api:8000
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
```

#### 5.2 完整的 docker-compose.yml

参考 [`monorepo-optimization-plan.md`](monorepo-optimization-plan.md:404)

---

### 任务 6: 更新文档和 README (优先级: 🟢 低)

#### 6.1 需要更新的文件

1. **根目录 README.md**
   - 更新目录结构说明
   - 更新快速开始步骤
   - 添加 Monorepo 管理指南链接

2. **后端 README** (新建 `backend/README.md`)
   - 后端开发指南
   - API 文档链接
   - 测试指南

3. **前端 README** (更新 `frontend/README.md`)
   - 前端开发指南
   - 组件文档
   - 构建和部署

#### 6.2 README 结构建议

**根目录 README.md**:
```markdown
# AI Higress - AI Gateway

## 项目结构

```
ai-higress/
├── backend/       # FastAPI 后端
├── frontend/      # Next.js 前端
├── docs/          # 项目文档
└── .github/       # CI/CD 配置
```

## 快速开始

### 使用 Docker (推荐)
...

### 本地开发
...

## 开发指南

- [后端开发指南](backend/README.md)
- [前端开发指南](frontend/README.md)
- [Monorepo 管理指南](docs/monorepo-optimization-plan.md)
- [API 文档](docs/API_Documentation.md)
```

---

## 🚀 推荐实施顺序

### 阶段 1: 紧急修复 (立即执行)
1. ✅ 修复前端目录名称:`fronted` → `frontend`
2. ✅ 更新 `.gitignore` 以适配新结构
3. ✅ 更新 `docker-compose.yml` 路径引用

### 阶段 2: CI/CD 配置 (本周内)
4. ✅ 创建 `.github/workflows/backend.yml`
5. ✅ 创建 `.github/workflows/frontend.yml`
6. ✅ 创建 `.github/workflows/integration.yml`
7. ✅ 测试 CI 流程

### 阶段 3: 前端容器化 (下周)
8. ✅ 创建 `frontend/Dockerfile.dev`
9. ✅ 创建 `frontend/Dockerfile`
10. ✅ 在 docker-compose.yml 中添加前端服务

### 阶段 4: 文档完善 (持续进行)
11. ✅ 更新根目录 README.md
12. ✅ 创建后端 README
13. ✅ 更新前端 README
14. ✅ 更新 pre-commit 配置

---

## 📋 检查清单

完成每项任务后,在此打勾:

### 目录结构
- [ ] 前端目录重命名为 `frontend/`
- [ ] 后端目录结构正确(`backend/app`, `backend/tests` 等)
- [ ] 根目录清理(移除旧的 `app/`, `tests/` 等)

### 配置文件
- [ ] `.gitignore` 已更新
- [ ] `.pre-commit-config.yaml` 已更新
- [ ] `pyproject.toml` 路径已修复
- [ ] `docker-compose.yml` 已更新

### CI/CD
- [ ] `.github/workflows/backend.yml` 已创建
- [ ] `.github/workflows/frontend.yml` 已创建
- [ ] `.github/workflows/integration.yml` 已创建
- [ ] CI 流程测试通过

### Docker
- [ ] 后端 Dockerfile 路径正确
- [ ] 前端 Dockerfile.dev 已创建
- [ ] 前端 Dockerfile 已创建
- [ ] docker-compose 服务启动正常

### 文档
- [ ] 根目录 README.md 已更新
- [ ] backend/README.md 已创建
- [ ] frontend/README.md 已更新
- [ ] API 文档链接正确

---

## 🔧 迁移命令速查

### 修复前端目录名称
```bash
git mv fronted frontend
git add -A
git commit -m "fix: rename fronted to frontend"
```

### 创建 CI/CD 目录
```bash
mkdir -p .github/workflows
```

### 测试 Docker 构建
```bash
# 测试后端构建
docker build -t apiproxy-backend:test ./backend

# 测试前端构建
docker build -t apiproxy-frontend:test ./frontend

# 测试 docker-compose
docker-compose up -d
docker-compose ps
docker-compose logs -f
docker-compose down
```

### 清理旧文件(确认迁移完成后)
```bash
# 检查是否有遗留的旧目录
ls -la app/ tests/ alembic/ scripts/

# 如果确认已迁移,可以删除(谨慎!)
# git rm -r app/ tests/ alembic/ scripts/
```

---

## ⚠️ 注意事项

### 1. Git 历史保留
- 使用 `git mv` 而不是普通的 `mv` 命令
- 这样可以保留文件的提交历史

### 2. 环境变量管理
- 后端的 `.env` 已在 `backend/.env`
- 前端需要创建 `frontend/.env.local`
- 敏感信息永远不要提交到 Git

### 3. 依赖管理
- 后端: `backend/pyproject.toml`
- 前端: `frontend/package.json`
- 两者独立管理,避免冲突

### 4. CI/CD 测试
- 推送代码前先在本地测试
- 使用 `act` 工具本地测试 GitHub Actions(可选)
  ```bash
  brew install act  # macOS
  act -l           # 列出所有工作流
  act push         # 模拟 push 事件
  ```

### 5. Docker 镜像缓存
- 首次构建可能较慢
- 使用 BuildKit 缓存加速:`DOCKER_BUILDKIT=1`
- CI 中已配置缓存(`cache-from`, `cache-to`)

---

## 🆘 故障排查

### 问题 1: Docker 构建失败

**症状**: `docker build` 报错 "COPY failed"

**解决**:
```bash
# 检查 Dockerfile 中的路径是否正确
# 确保构建上下文正确: docker build -t xxx ./backend
```

### 问题 2: CI 流程失败

**症状**: GitHub Actions 报错 "path not found"

**解决**:
```yaml
# 检查 .github/workflows/*.yml 中的 paths 配置
# 确保路径与实际目录结构匹配
paths:
  - 'backend/**'  # 正确
  - 'app/**'      # 错误(旧路径)
```

### 问题 3: docker-compose 启动失败

**症状**: 容器无法启动或退出

**解决**:
```bash
# 查看日志
docker-compose logs api
docker-compose logs frontend

# 检查环境变量
cat backend/.env
cat frontend/.env.local

# 重新构建
docker-compose build --no-cache
docker-compose up -d
```

---

## 📚 参考资源

- [Monorepo 优化方案](monorepo-optimization-plan.md)
- [Git mv 文档](https://git-scm.com/docs/git-mv)
- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [Bun 文档](https://bun.sh/docs)

---

## ✅ 完成标准

当以下条件全部满足时,迁移任务完成:

1. ✅ 目录结构符合 Monorepo 最佳实践
2. ✅ CI/CD 流程正常运行
3. ✅ Docker 服务可以正常启动
4. ✅ 所有测试通过
5. ✅ 文档已更新
6. ✅ 团队成员能够顺利开发

---

## 📞 需要帮助?

如需实施以上任务,请切换到 **Code 模式**,我可以帮你:
- 修复目录名称
- 创建所有配置文件
- 更新现有配置
- 测试 Docker 和 CI/CD

**使用方式**: 回复 "开始实施任务 X" 或 "帮我完成剩余迁移"