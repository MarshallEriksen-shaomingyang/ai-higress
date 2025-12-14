# 逻辑模型 Cache-Aside 模式

## 问题背景

之前的实现中，`/logical-models` 接口直接从 Redis 读取数据，但 Provider 和 ProviderModel 的创建/更新操作只写入数据库，不会自动同步到 Redis。这导致：

1. 新创建的 Provider 不会出现在 `/logical-models` 列表中
2. 更新 Provider 后，逻辑模型信息不会更新
3. 需要手动触发同步或重启服务才能看到变化

## 解决方案：Cache-Aside 模式

采用经典的 Cache-Aside（旁路缓存）模式：

### 读取流程

```
GET /logical-models
    ↓
尝试从 Redis 读取
    ↓
缓存命中？
    ├─ 是 → 直接返回
    └─ 否 → 从数据库聚合
            ↓
        写入 Redis
            ↓
        返回结果
```

### 写入流程

```
创建/更新 Provider
    ↓
写入数据库
    ↓
失效 Redis 缓存（删除所有 llm:logical:* 键）
    ↓
返回成功
```

下次读取时会自动从数据库回源并重建缓存。

## 实现细节

### 1. 读取接口改造

修改了以下接口，添加数据库回源逻辑和用户权限过滤：

- `GET /logical-models` - 列出当前用户可访问的逻辑模型
- `GET /logical-models/{logical_model_id}` - 获取单个逻辑模型（仅包含可访问的上游）
- `GET /logical-models/{logical_model_id}/upstreams` - 获取逻辑模型的上游列表（仅包含可访问的上游）

**权限规则：**

用户只能看到以下 Provider 的模型：
- 公开 Provider（`visibility=public` 且 `owner_id=NULL`）
- 自己创建的 Provider（`owner_id=当前用户`）
- 被授权访问的受限 Provider（`visibility=restricted` 且在授权列表中）
- 超级管理员可以看到所有 Provider

**实现代码示例：**

```python
@router.get("/logical-models", response_model=LogicalModelsResponse)
async def list_logical_models_endpoint(
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> LogicalModelsResponse:
    # 尝试从 Redis 读取全量数据
    models = await list_logical_models(redis)
    
    # 缓存未命中，从数据库回源
    if not models:
        logger.info("Logical models cache miss, falling back to database")
        from app.services.logical_model_sync import sync_logical_models
        
        try:
            models = await sync_logical_models(redis, session=db)
            logger.info("Synced %d logical models from database to Redis", len(models))
        except Exception:
            logger.exception("Failed to sync logical models from database")
            models = []
    
    # 根据用户权限过滤逻辑模型
    accessible_provider_ids = get_accessible_provider_ids(db, UUID(current_user.id))
    
    filtered_models: list[LogicalModel] = []
    for model in models:
        # 过滤出用户可访问的上游
        accessible_upstreams = [
            upstream for upstream in model.upstreams
            if upstream.provider_id in accessible_provider_ids
        ]
        
        # 如果该逻辑模型至少有一个可访问的上游，则包含它
        if accessible_upstreams:
            filtered_models.append(
                model.model_copy(update={"upstreams": accessible_upstreams})
            )
    
    return LogicalModelsResponse(models=filtered_models, total=len(filtered_models))
```

### 2. 缓存失效函数

在 `app/storage/redis_service.py` 中添加：

```python
async def invalidate_logical_models_cache(redis: Redis) -> int:
    """
    清空所有逻辑模型缓存，用于 Provider 创建/更新后触发缓存失效。
    
    返回删除的键数量。
    """
    pattern = LOGICAL_MODEL_KEY_TEMPLATE.format(logical_model="*")
    keys = await redis.keys(pattern)
    if not keys:
        return 0
    return int(await redis.delete(*keys))
```

### 3. 写入接口改造

在以下接口中添加缓存失效调用：

**私有 Provider 管理：**
- `POST /users/{user_id}/private-providers` - 创建私有 Provider
- `PUT /users/{user_id}/private-providers/{provider_id}` - 更新私有 Provider

**管理员 Provider 管理：**
- `PUT /admin/providers/{provider_id}/visibility` - 更新可见性
- `PUT /admin/providers/{provider_id}/probe-config` - 更新探针配置

**实现代码示例：**

```python
@router.post("/users/{user_id}/private-providers")
async def create_private_provider_endpoint(
    user_id: UUID,
    payload: UserProviderCreateRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: AuthenticatedUser = Depends(require_jwt_token),
) -> UserProviderResponse:
    # ... 创建 Provider 的业务逻辑 ...
    
    # 失效逻辑模型缓存
    try:
        from app.storage.redis_service import invalidate_logical_models_cache
        deleted = await invalidate_logical_models_cache(redis)
        logger.info("Invalidated %d logical model cache keys", deleted)
    except Exception:
        logger.exception("Failed to invalidate logical models cache")
    
    return UserProviderResponse.model_validate(provider)
```

## 优势

1. **自动同步**：无需手动触发同步，创建/更新后自动生效
2. **高可用**：Redis 故障时自动降级到数据库
3. **简单可靠**：经典的缓存模式，易于理解和维护
4. **性能优化**：大部分请求命中缓存，只有缓存失效后才查数据库
5. **权限隔离**：用户只能看到自己有权限访问的 Provider 和模型

## 注意事项

1. **缓存失效粒度**：当前实现是全量失效（删除所有逻辑模型缓存），如果逻辑模型数量很大，可以考虑改为增量失效
2. **并发问题**：多个请求同时缓存未命中时，可能会重复从数据库聚合，可以考虑加分布式锁优化
3. **一致性窗口**：从失效缓存到下次读取之间，存在短暂的不一致窗口，但对于这个场景是可接受的
4. **权限过滤性能**：每次请求都需要查询用户权限并过滤结果，如果用户量很大，可以考虑将用户权限也缓存到 Redis

## 测试

运行测试验证 Cache-Aside 模式：

```bash
pytest backend/tests/api/test_logical_models_cache_aside.py -v
```

## 相关文件

- `backend/app/api/logical_model_routes.py` - 逻辑模型读取接口
- `backend/app/api/v1/private_provider_routes.py` - 私有 Provider 管理接口
- `backend/app/api/v1/admin_provider_routes.py` - 管理员 Provider 管理接口
- `backend/app/storage/redis_service.py` - Redis 缓存服务
- `backend/app/services/logical_model_sync.py` - 逻辑模型同步服务
