多提供商网关配置指南
====================

本文档说明如何通过环境变量配置 APIProxy，使其以「多提供商 + 逻辑模型 + 智能路由」模式工作。

所有配置都来自 `.env` 文件（或 Docker Compose 的 `env_file`），模板见仓库根目录的 `.env.example`。

> 鉴权提示：在 `.env` 中设置 `APIPROXY_AUTH_TOKEN`，客户端需要在请求头里发送它的 Base64 编码：
> `Authorization: Bearer <base64(APIPROXY_AUTH_TOKEN)>`。可以运行
> `uv run scripts/encode_token.py <token>` 来快速生成编码结果。


1. 基本步骤
-----------

1. 复制模板：

   ```bash
   cp .env.example .env
   ```

2. 根据部署方式修改 Redis 地址：

   - Docker Compose 默认：

     ```env
     REDIS_URL=redis://redis:6379/0
     ```

   - 本地开发（本机跑 Redis）：

     ```env
     REDIS_URL=redis://localhost:6379/0
     ```

3. 在 `.env` 中配置多提供商信息（详见下文），然后：

   - Docker：
     ```bash
     docker-compose up -d
     ```
   - 本地：
     ```bash
     uv run uvicorn main:app --reload
     # 或
     uv run apiproxy
     ```


2. 多提供商环境变量约定
----------------------

多提供商配置完全通过环境变量进行，约定如下：

```env
# 所有提供商 ID，逗号分隔
LLM_PROVIDERS=openai,azure,local

# OpenAI 提供商
LLM_PROVIDER_openai_NAME=OpenAI
LLM_PROVIDER_openai_BASE_URL=https://api.openai.com
LLM_PROVIDER_openai_API_KEY=sk-your-openai-api-key
LLM_PROVIDER_openai_MODELS_PATH=/v1/models
LLM_PROVIDER_openai_WEIGHT=3
LLM_PROVIDER_openai_REGION=global
LLM_PROVIDER_openai_COST_INPUT=0.003
LLM_PROVIDER_openai_COST_OUTPUT=0.006
LLM_PROVIDER_openai_MAX_QPS=50

# Azure OpenAI 提供商
LLM_PROVIDER_azure_NAME=Azure OpenAI
LLM_PROVIDER_azure_BASE_URL=https://your-resource.openai.azure.com
LLM_PROVIDER_azure_API_KEY=your-azure-api-key
LLM_PROVIDER_azure_MODELS_PATH=/openai/models
LLM_PROVIDER_azure_WEIGHT=2
LLM_PROVIDER_azure_REGION=us-east
LLM_PROVIDER_azure_COST_INPUT=0.0025
LLM_PROVIDER_azure_COST_OUTPUT=0.005
LLM_PROVIDER_azure_MAX_QPS=100

# 本地模型（可选）
LLM_PROVIDER_local_NAME=Local Model
LLM_PROVIDER_local_BASE_URL=http://localhost:8080
LLM_PROVIDER_local_API_KEY=not-required
LLM_PROVIDER_local_MODELS_PATH=/v1/models
LLM_PROVIDER_local_WEIGHT=1
LLM_PROVIDER_local_REGION=local
```

约定说明：

- `LLM_PROVIDERS`：给出所有提供商的「ID」，例如 `openai,azure,local`。
- **重要：`LLM_PROVIDERS` 中的每个 id，必须和下面环境变量前缀中的 `{id}` 一一对应。**  
  例如：

  ```env
  LLM_PROVIDERS=a4f

  # 对应的配置前缀必须是 LLM_PROVIDER_a4f_*
  LLM_PROVIDER_a4f_NAME=a4f
  LLM_PROVIDER_a4f_BASE_URL=https://api.a4f.co
  LLM_PROVIDER_a4f_API_KEY=xxx
  ```

  如果写成：

  ```env
  LLM_PROVIDERS=a4f
  LLM_PROVIDER_openai_NAME=a4f
  ```

  则 `a4f` 这个 provider 会被视为「缺少配置」而被静默跳过，最终网关认为没有任何 provider。

- 对于每个 `{id}`，使用前缀 `LLM_PROVIDER_{id}_` 配置该提供商：
  - 必填：
    - `LLM_PROVIDER_{id}_NAME`：显示名称；
    - `LLM_PROVIDER_{id}_BASE_URL`：API 基础地址，例如 `https://api.openai.com`；
    - `LLM_PROVIDER_{id}_API_KEY`：访问该提供商所需的密钥或 token。
  - 可选：
    - `LLM_PROVIDER_{id}_MODELS_PATH`：模型列表路径，默认 `/v1/models`；
    - `LLM_PROVIDER_{id}_WEIGHT`：基础权重（影响路由倾向，默认 1.0）；
    - `LLM_PROVIDER_{id}_REGION`：区域标签（如 `global`、`us-east` 等），可用于按区域就近路由；
    - `LLM_PROVIDER_{id}_COST_INPUT` / `COST_OUTPUT`：用于成本敏感调度策略；
    - `LLM_PROVIDER_{id}_MAX_QPS`：该提供商允许的最大 QPS。

配置完成后，网关会在启动时自动：

1. 从 `LLM_PROVIDERS` + `LLM_PROVIDER_*` 中解析可用提供商（缺少必填字段的会被跳过并记录 warning）。
2. 调用每个提供商的 `BASE_URL + MODELS_PATH` 获取模型列表，并写入 Redis：

   ```text
   llm:vendor:{provider_id}:models -> 标准化后的模型列表 JSON
   ```


3. 验证配置是否生效
-------------------

启动服务后，可以用以下接口检查配置是否正确：

1. 查看提供商列表：

   ```bash
   curl -X GET "http://localhost:8000/providers" \
     -H "Authorization: Bearer <base64(APIPROXY_AUTH_TOKEN)>"
   ```

   返回中应包含你在 `LLM_PROVIDERS` 中配置的各个 `id`。

2. 查看某个提供商的模型：

   ```bash
   curl -X GET "http://localhost:8000/providers/openai/models" \
     -H "Authorization: Bearer <base64(APIPROXY_AUTH_TOKEN)>"
   ```

   如果能看到模型列表，说明：
   - `BASE_URL` / `MODELS_PATH` / `API_KEY` 配置正确；
   - Redis 写入也正常（该列表会缓存到 Redis 中）。

3. （可选）检查健康状态：

   ```bash
   curl -X GET "http://localhost:8000/providers/openai/health" \
     -H "Authorization: Bearer <base64(APIPROXY_AUTH_TOKEN)>"
   ```


4. 逻辑模型与路由相关配置
-------------------------

逻辑模型本身的数据目前存储在 Redis 中，按 `llm:logical:{logical_model}` 键保存，格式遵守
`service/models/logical_model.py` 的 `LogicalModel` 结构。配置方式通常有两种：

1. 通过脚本/管理工具写入 LogicalModel：

   - 例如编写一个管理脚本，从代码中构造 `LogicalModel` 实例，然后通过
     `service/storage/redis_service.set_logical_model()` 写入 Redis。

2. 手工写入（开发环境调试时）：

   - 先在代码里构造一个 LogicalModel 并 `print(json.dumps(model.model_dump()))`，
     再用 `redis-cli` 手工 `SET llm:logical:gpt-4 '...json...'`。

配置好逻辑模型后，可以用以下接口验证：

```bash
# 列出所有逻辑模型
curl -X GET "http://localhost:8000/logical-models" \
  -H "Authorization: Bearer <base64(APIPROXY_AUTH_TOKEN)>"

# 查看某个逻辑模型
curl -X GET "http://localhost:8000/logical-models/gpt-4" \
  -H "Authorization: Bearer <base64(APIPROXY_AUTH_TOKEN)>"

# 查看逻辑模型的上游列表
curl -X GET "http://localhost:8000/logical-models/gpt-4/upstreams" \
  -H "Authorization: Bearer <base64(APIPROXY_AUTH_TOKEN)>"
```


5. 路由策略与会话粘连
---------------------

当逻辑模型和运行时指标都就绪后，可以使用 `/routing/decide` 接口检查路由决策：

```bash
curl -X POST "http://localhost:8000/routing/decide" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <base64(APIPROXY_AUTH_TOKEN)>" \
  -d '{
    "logical_model": "gpt-4",
    "strategy": "latency_first",
    "conversation_id": "conv_123",
    "preferred_region": "us-east",
    "exclude_providers": ["local"]
  }'
```

- `strategy` 可选值：
  - `latency_first`
  - `cost_first`
  - `reliability_first`
  - `balanced`（默认）
- `conversation_id` 提供会话粘连能力；绑定关系可通过：

  ```bash
  curl -X GET "http://localhost:8000/routing/sessions/conv_123" \
    -H "Authorization: Bearer <base64(APIPROXY_AUTH_TOKEN)>"
  ```

  查看，删除粘连用：

  ```bash
  curl -X DELETE "http://localhost:8000/routing/sessions/conv_123" \
    -H "Authorization: Bearer <base64(APIPROXY_AUTH_TOKEN)>"
  ```


6. 小结
-------

- 所有多提供商配置均通过 `.env` 中的：
  - `REDIS_URL`
  - `LLM_PROVIDERS`
  - `LLM_PROVIDER_{id}_*`
- 模型发现、逻辑模型映射和路由决策可以通过 `/providers`、`/logical-models`、
  `/routing/decide` 等接口逐步验证。
- 推荐以 `.env.example` 为基础，在不同环境中维护不同的 `.env` 文件，
  保持配置与代码解耦。 
