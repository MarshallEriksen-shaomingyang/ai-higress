## 即将实现的新特性
    ✅- 可以为用户生成key，key配置过期时间 也可以不设置过期时间， key删除后不再能使用
    ✅ 初始化时提供管理员用户名和密码，管理员用户可以为用户配置身份是否为管理员
    - celery 任务定时检测api 提供商 和 key 的状态
    ✅ 添加厂商状态检测功能
    ✅ 添加定时开放注册的功能 开启后管理员可以设置注册时间和注册次数 默认让这些人自动is_active 变为true
    ✅ 管理员也可以设置默认可以注册成功 不过需要管理员手动激活
    - 可以自定义服务商的header
    - provider 错误率过高的报警系统
    - 模型映射 类似 可以把 claude-sonet-4.5.xx 映射到 claude-sonet-4.5
    - 提供商列表 badge 显示用户自己的提供商 和 其他用户的分享的提供商
    ✅ 系统通知落地（数据库+回执），已接入场景：
        - 共享提供商提交：提交创建、审核通过/拒绝自动通知提交者
        - API Key 巡检：过期或高错误率被禁用时通知持有用户
        - 积分自动充值：日常自动补余额成功后通知用户

### Celery 异步任务规划（细化）
1. Provider 模型刷新 & 逻辑模型同步
    - 定时拉取各 Provider `/models` 并写入 Redis（`llm:vendor:{provider_id}:models`）
    - 调用 `sync_logical_models_task` 全量/增量刷新 `LogicalModel` 到 Redis

<!-- 2. Provider 健康检查
    - 使用 `app.provider.health.check_provider_health` 定期检测厂商连通性和延迟
    - 将结果写入 Redis/DB，供路由和管理后台展示健康状态 -->
<!-- 
3. API Key 状态与过期检查
    - 扫描 DB 中已过期或即将过期的 API Key，自动标记为不可用
    - 结合调用失败统计，对异常 Key 做降权或禁用处理 -->
<!-- 
4. 定时开放注册窗口策略
    - 根据配置在指定时间段自动开启/关闭注册
    - 在开放窗口内自动将新注册用户 `is_active=True`，窗口外需要管理员手动激活 -->

<!-- 5. 指标精细聚合任务
    - 基于 `provider_routing_metrics_history` 和 `routing.metrics.aggregate_metrics`
    - 离线重算 p95/p99、error_rate 等指标并回写 DB，提高报表精度 -->

6. Metrics 历史数据归档 / 清理
    - 将早期分钟级指标按日/周聚合后持久化
    - 定期清理超出保留期的历史明细，控制表大小

<!-- 7. LogicalModel / Provider 缓存巡检
    - 定时全量调用 `sync_logical_models_task`，校正 Redis 缓存与数据库配置
    - 检测并修复缺失/脏数据的逻辑模型缓存 -->

<!-- 8. Redis 会话与 Token 维护
    - 巡检 `auth:user:{user_id}:sessions`，清理无效或损坏的会话记录
    - 根据策略限制单用户最大活跃会话数，超出时自动淘汰最老会话 -->

9. 使用量报表生成
    - 结合 `metrics_routes` 中的聚合逻辑，异步生成按用户 / API Key / Provider 的用量报表
    - 支持后台导出 CSV/JSON，前端通过任务 ID 轮询获取结果

<!-- 10. 批量权限 / 角色策略同步
    - 根据运营策略（活跃度、付费等级等）周期性调整用户角色和权限
    - 调用 `user_service` / `role_service` / `user_permission_service` 完成批量更新 -->
