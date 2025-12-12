# FastAPI 安全加固指南

本文档介绍 AI Gateway 项目针对自动化扫描攻击的安全防护措施和最佳实践。

## 目录

1. [当前安全措施](#当前安全措施)
2. [自动化扫描攻击类型](#自动化扫描攻击类型)
3. [安全中间件](#安全中间件)
4. [部署层面防护](#部署层面防护)
5. [监控和告警](#监控和告警)
6. [安全配置清单](#安全配置清单)

## 当前安全措施

### 1. 应用层安全

#### 认证机制 (`app/auth.py`)
- **API Key 认证**：支持 Bearer Token 和 X-API-Key 两种方式
- **密钥哈希存储**：使用 HMAC 哈希，不存储明文密钥
- **Redis 缓存**：认证结果缓存，减少数据库查询
- **密钥过期**：支持密钥过期时间和用户状态检查

#### 安全中间件 (`app/middleware/`)

##### SecurityHeadersMiddleware
添加安全响应头，防护常见 Web 攻击：

```python
# 使用示例
app.add_middleware(
    SecurityHeadersMiddleware,
    enable_hsts=True,  # 生产环境启用 HTTPS 强制
    hsts_max_age=31536000,
)
```

**防护的攻击类型**：
- MIME 类型嗅探攻击（X-Content-Type-Options）
- 点击劫持（X-Frame-Options）
- XSS 攻击（Content-Security-Policy）
- 信息泄露（Referrer-Policy）

##### RateLimitMiddleware
限流中间件，防止暴力破解和 DDoS 攻击：

```python
# 使用示例
app.add_middleware(
    RateLimitMiddleware,
    redis_client=redis_client,  # 生产环境使用 Redis
    default_max_requests=100,
    default_window_seconds=60,
    path_limits={
        "/auth/login": (5, 60),  # 登录：每分钟 5 次
        "/auth/register": (3, 300),  # 注册：每 5 分钟 3 次
        "/v1/chat/completions": (60, 60),  # API：每分钟 60 次
    },
)
```

**特性**：
- 基于 IP 的滑动窗口限流
- 支持路径级别的自定义限流规则
- 内存或 Redis 存储（分布式部署）
- 自动添加 X-RateLimit-* 响应头

##### RequestValidatorMiddleware
请求验证中间件，检测并阻止恶意请求：

```python
# 使用示例
app.add_middleware(
    RequestValidatorMiddleware,
    enable_sql_injection_check=True,
    enable_xss_check=True,
    enable_path_traversal_check=True,
    enable_command_injection_check=True,
    enable_user_agent_check=True,
    log_suspicious_requests=True,
    # 生产环境建议开启请求体扫描；当前默认关闭以避免大包体/文件上传误判
    inspect_body=False,
    inspect_body_max_length=None,  # 可选：设置上限后超出直接拒绝；默认不限制
    ban_ip_on_detection=True,  # 命中恶意规则后自动封禁来源 IP
    ban_ttl_seconds=900,  # 封禁 15 分钟（结合 Redis 可跨实例共享）
    allowed_ips={"10.0.0.9"},  # 可选：对可信 IP / 健康检查放行
    allowed_path_prefixes={"/health"},  # 可选：对特定路径放行
)
```

**检测的攻击模式**：
- SQL 注入（UNION SELECT, DROP TABLE 等）
- XSS 攻击（<script>, javascript: 等）
- 路径遍历（../, %2e%2e/ 等）
- 命令注入（;, |, $() 等）
- 扫描工具识别（sqlmap, nikto, nmap 等）

**封禁与取证建议**：
- 短期封禁：使用内存或 Redis 存储，命中规则后直接写入封禁名单（带 TTL），可快速阻断重复攻击 IP；
- 长期追踪：若需要审计或拉黑高风险来源，可将命中记录追加到数据库/日志管道，由离线任务决定是否写入持久化黑名单表；
- 业务白名单：为健康检查、可信代理等来源 IP 或路径预留白名单，避免因规则误伤产生全局封禁；
- DoS 防护：如果担心大包体 DoS，可按需配置 `inspect_body_max_length`，仅解析文本类 Content-Type；默认不做体积限制。
- 全局开关：可通过环境变量 `ENABLE_SECURITY_MIDDLEWARE` 显式控制安全中间件栈（true 强制开启，false 关闭；默认跟随 `APP_ENV=production`）。

### 2. 容器化安全

#### Docker 配置（`docker-compose.develop.yml` / `docker-compose-deploy.yml`）
- **网络隔离**：独立的 bridge 网络（172.20.0.0/24）
- **端口绑定**：数据库和 Redis 仅绑定到 127.0.0.1
- **健康检查**：所有服务配置健康检查
- **最小权限**：使用非 root 用户运行（建议）

#### Dockerfile 最佳实践
```dockerfile
# 使用官方基础镜像
FROM python:3.12-slim

# 创建非 root 用户
RUN useradd -m -u 1000 appuser

# 设置工作目录权限
WORKDIR /app
RUN chown appuser:appuser /app

# 切换到非 root 用户
USER appuser

# 其他配置...
```

## 自动化扫描攻击类型

### 1. 端口扫描
**攻击方式**：使用 nmap、masscan 等工具扫描开放端口

**防护措施**：
- 使用防火墙限制入站流量
- 仅开放必要端口（80/443）
- 使用云服务商的安全组规则

### 2. 路径爆破
**攻击方式**：尝试访问常见路径（/admin, /.env, /api/docs）

**防护措施**：
- RequestValidatorMiddleware 检测路径遍历
- 禁用或保护 /docs 和 /redoc 端点（生产环境）
- 使用非标准路径命名

### 3. SQL 注入
**攻击方式**：在 URL 参数或请求体中注入 SQL 代码

**防护措施**：
- RequestValidatorMiddleware 检测 SQL 注入模式
- 使用 SQLAlchemy ORM（参数化查询）
- 输入验证和清理

### 4. 暴力破解
**攻击方式**：尝试大量密码组合

**防护措施**：
- RateLimitMiddleware 限制登录频率
- 账户锁定机制（多次失败后）
- 强密码策略
- 双因素认证（2FA）

### 5. DDoS 攻击
**攻击方式**：大量请求耗尽服务器资源

**防护措施**：
- RateLimitMiddleware 全局限流
- 使用 CDN（Cloudflare, AWS CloudFront）
- 负载均衡和自动扩展
- 连接数限制

### 6. 漏洞扫描
**攻击方式**：使用自动化工具扫描已知 CVE 漏洞

**防护措施**：
- 定期更新依赖包
- 使用 `pip-audit` 或 `safety` 检查漏洞
- 订阅安全公告
- 及时打补丁

## 安全中间件

### 中间件执行顺序

FastAPI 中间件按照**添加顺序的逆序**执行：

```python
# 添加顺序（代码中）
app.add_middleware(SecurityHeadersMiddleware)  # 3. 最后执行（响应阶段）
app.add_middleware(RateLimitMiddleware)        # 2. 第二执行
app.add_middleware(RequestValidatorMiddleware) # 1. 最先执行（请求阶段）
app.add_middleware(CORSMiddleware)             # 0. CORS 处理

# 实际执行顺序（请求 -> 响应）
# 请求阶段：CORS -> RequestValidator -> RateLimit -> SecurityHeaders -> 业务逻辑
# 响应阶段：业务逻辑 -> SecurityHeaders -> RateLimit -> RequestValidator -> CORS
```

### 生产环境配置

#### 启用 Redis 限流

```python
from app.deps import get_redis

# 在 create_app() 中
redis_client = get_redis()

app.add_middleware(
    RateLimitMiddleware,
    redis_client=redis_client,  # 使用 Redis 实现分布式限流
    default_max_requests=100,
    default_window_seconds=60,
)
```

#### 启用 HSTS

```python
app.add_middleware(
    SecurityHeadersMiddleware,
    enable_hsts=True,  # 生产环境启用
    hsts_max_age=31536000,  # 1 年
)
```

#### 自定义限流规则

```python
path_limits = {
    # 认证相关
    "/auth/login": (5, 60),
    "/auth/register": (3, 300),
    "/auth/refresh": (10, 60),
    
    # API 端点
    "/v1/chat/completions": (60, 60),
    "/v1/models": (30, 60),
    
    # 管理端点
    "/admin": (20, 60),
}
```

## 部署层面防护

### 1. 反向代理（Nginx）

```nginx
# /etc/nginx/sites-available/ai-gateway

# 限制请求大小
client_max_body_size 10M;

# 限制请求速率
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=1r/s;

server {
    listen 80;
    server_name api.example.com;
    
    # 强制 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;
    
    # SSL 配置
    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # 隐藏版本信息
    server_tokens off;
    
    # 安全头（额外保护）
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # 限制请求方法
    if ($request_method !~ ^(GET|POST|PUT|DELETE|OPTIONS)$) {
        return 405;
    }
    
    # 阻止常见扫描路径
    location ~ /\. {
        deny all;
        return 404;
    }
    
    location ~ \.(env|git|svn|htaccess)$ {
        deny all;
        return 404;
    }
    
    # API 端点限流
    location /v1/ {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # 登录端点严格限流
    location /auth/login {
        limit_req zone=login_limit burst=3 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    # 禁用生产环境文档
    location ~ ^/(docs|redoc|openapi.json) {
        deny all;
        return 404;
    }
}
```

### 2. 防火墙规则（UFW）

```bash
# 默认策略
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 允许 SSH（限制 IP）
sudo ufw allow from 203.0.113.0/24 to any port 22

# 允许 HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 启用防火墙
sudo ufw enable
```

### 3. Fail2Ban 配置

```ini
# /etc/fail2ban/jail.local

[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
logpath = /var/log/nginx/error.log
maxretry = 3
bantime = 7200

[ai-gateway-auth]
enabled = true
filter = ai-gateway-auth
logpath = /var/log/ai-gateway/app.log
maxretry = 5
bantime = 3600
```

```ini
# /etc/fail2ban/filter.d/ai-gateway-auth.conf

[Definition]
failregex = ^.*Blocked suspicious request.*IP: <HOST>.*$
            ^.*Invalid API token.*from <HOST>.*$
            ^.*rate_limit_exceeded.*IP: <HOST>.*$
ignoreregex =
```

### 4. 云服务商安全组

#### AWS Security Group
```bash
# 仅允许 HTTPS 流量
aws ec2 authorize-security-group-ingress \
    --group-id sg-xxxxx \
    --protocol tcp \
    --port 443 \
    --cidr 0.0.0.0/0

# 允许特定 IP 的 SSH
aws ec2 authorize-security-group-ingress \
    --group-id sg-xxxxx \
    --protocol tcp \
    --port 22 \
    --cidr 203.0.113.0/24
```

#### 阿里云安全组规则
- 入方向：仅开放 80/443 端口
- 出方向：允许所有
- 优先级：1（最高）

### 5. CDN 和 WAF

#### Cloudflare 配置
- **DDoS 防护**：自动启用
- **WAF 规则**：
  - 阻止已知恶意 IP
  - SQL 注入防护
  - XSS 防护
  - 速率限制
- **Bot 管理**：
  - 挑战可疑流量
  - 阻止已知扫描工具
- **缓存规则**：
  - 静态资源缓存
  - API 响应不缓存

#### AWS WAF 规则
```json
{
  "Name": "RateLimitRule",
  "Priority": 1,
  "Statement": {
    "RateBasedStatement": {
      "Limit": 2000,
      "AggregateKeyType": "IP"
    }
  },
  "Action": {
    "Block": {}
  }
}
```

## 监控和告警

### 1. 日志监控

#### 应用日志
```python
# app/logging_config.py 已配置结构化日志

# 关键事件记录
logger.warning(
    "Blocked suspicious request: %s | IP: %s | Path: %s",
    reason, client_ip, path
)

logger.error(
    "Rate limit exceeded: IP=%s Path=%s",
    client_ip, path
)
```

#### 日志聚合（ELK Stack）
```yaml
# filebeat.yml
filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /var/log/ai-gateway/*.log
    json.keys_under_root: true
    json.add_error_key: true

output.elasticsearch:
  hosts: ["localhost:9200"]
  index: "ai-gateway-%{+yyyy.MM.dd}"
```

### 2. 指标监控（Prometheus）

```python
# 添加 Prometheus 指标
from prometheus_client import Counter, Histogram

# 请求计数
request_count = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# 限流计数
rate_limit_exceeded = Counter(
    'rate_limit_exceeded_total',
    'Total rate limit exceeded',
    ['endpoint', 'ip']
)

# 可疑请求计数
suspicious_requests = Counter(
    'suspicious_requests_total',
    'Total suspicious requests blocked',
    ['reason', 'ip']
)
```

### 3. 告警规则

#### Prometheus AlertManager
```yaml
groups:
  - name: security_alerts
    rules:
      # 高频率限流告警
      - alert: HighRateLimitExceeded
        expr: rate(rate_limit_exceeded_total[5m]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High rate limit exceeded rate"
          description: "Rate limit exceeded {{ $value }} times/sec"
      
      # 可疑请求告警
      - alert: SuspiciousRequestsDetected
        expr: rate(suspicious_requests_total[5m]) > 5
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Suspicious requests detected"
          description: "{{ $value }} suspicious requests/sec"
      
      # 认证失败告警
      - alert: HighAuthFailureRate
        expr: rate(auth_failures_total[5m]) > 20
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High authentication failure rate"
```

### 4. 实时监控面板

#### Grafana Dashboard
- **请求统计**：QPS、响应时间、错误率
- **安全事件**：限流次数、可疑请求、认证失败
- **资源使用**：CPU、内存、网络
- **地理分布**：请求来源国家/地区

## 安全配置清单

### 开发环境
- [ ] 启用基础安全中间件
- [ ] 配置合理的限流规则
- [ ] 启用请求日志
- [ ] 使用 .env 管理敏感配置
- [ ] 定期更新依赖包

### 测试环境
- [ ] 所有开发环境配置
- [ ] 启用 HTTPS（自签名证书）
- [ ] 配置 Fail2Ban
- [ ] 模拟攻击测试
- [ ] 压力测试

### 生产环境
- [ ] 所有测试环境配置
- [ ] 启用 HSTS
- [ ] 使用 Redis 分布式限流
- [ ] 配置 Nginx 反向代理
- [ ] 启用 WAF（Cloudflare/AWS WAF）
- [ ] 配置 CDN
- [ ] 禁用 /docs 和 /redoc
- [ ] 配置防火墙规则
- [ ] 启用 Fail2Ban
- [ ] 配置日志聚合（ELK）
- [ ] 配置监控告警（Prometheus + Grafana）
- [ ] 定期安全审计
- [ ] 备份和灾难恢复计划
- [ ] 使用非 root 用户运行
- [ ] 最小权限原则
- [ ] 定期漏洞扫描

### 持续安全
- [ ] 每周检查依赖包更新
- [ ] 每月安全审计
- [ ] 每季度渗透测试
- [ ] 订阅安全公告
- [ ] 制定应急响应计划
- [ ] 定期备份和恢复演练

## 常见问题

### Q: 如何测试限流是否生效？

```bash
# 使用 ab (Apache Bench) 测试
ab -n 100 -c 10 http://localhost:8000/v1/models

# 使用 curl 循环测试
for i in {1..20}; do
  curl -H "Authorization: Bearer xxx" \
       http://localhost:8000/auth/login
  sleep 0.1
done
```

### Q: 如何查看被阻止的请求？

```bash
# 查看应用日志
tail -f /var/log/ai-gateway/app.log | grep "Blocked suspicious"

# 查看 Nginx 日志
tail -f /var/log/nginx/error.log | grep "limiting requests"
```

### Q: 如何临时禁用某个中间件？

```python
# 在 create_app() 中注释掉对应的 add_middleware 调用
# app.add_middleware(RequestValidatorMiddleware, ...)
```

### Q: 生产环境如何配置 Redis 限流？

```python
# 在 create_app() 中
from app.deps import get_redis

async def get_redis_for_middleware():
    return get_redis()

# 注意：中间件初始化时需要同步获取 Redis 客户端
# 建议在应用启动时初始化
redis_client = get_redis()

app.add_middleware(
    RateLimitMiddleware,
    redis_client=redis_client,
    # ...其他配置
)
```

## 参考资源

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Nginx Security](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Cloudflare WAF](https://www.cloudflare.com/waf/)
- [AWS WAF](https://aws.amazon.com/waf/)
- [Fail2Ban Documentation](https://www.fail2ban.org/)
