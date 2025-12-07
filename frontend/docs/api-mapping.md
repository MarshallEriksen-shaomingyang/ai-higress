# AI Higress 前端页面与API映射关系

## 页面与API映射矩阵

### 1. 首页 (/)
| 页面功能 | API端点 | 方法 | 描述 |
|---------|---------|------|------|
| 无（静态页面） | 无 | - | 首页为静态展示页面 |

### 2. 登录页面 (/login)
| 页面功能 | API端点 | 方法 | 描述 |
|---------|---------|------|------|
| 用户登录 | `/auth/login` | POST | 验证用户凭据，返回访问令牌 |
| 刷新令牌 | `/auth/refresh` | POST | 使用刷新令牌获取新的访问令牌 |

### 3. 注册页面 (/register)
| 页面功能 | API端点 | 方法 | 描述 |
|---------|---------|------|------|
| 用户注册 | `/auth/register` | POST | 创建新用户账户 |

### 4. 仪表盘概览 (/dashboard/overview)
| 页面功能 | API端点 | 方法 | 描述 |
|---------|---------|------|------|
| 获取系统状态 | `/system/status` | GET | 获取系统整体运行状态（管理员） |
| 获取提供商列表 | `/providers` | GET | 获取所有配置的提供商信息 |
| 获取逻辑模型列表 | `/logical-models` | GET | 获取所有逻辑模型信息 |
| 获取提供商指标 | `/providers/{id}/metrics` | GET | 获取特定提供商的运行指标 |
| 获取路由决策 | `/routing/decide` | POST | 模拟路由决策过程 |

### 5. 提供商管理 (/dashboard/providers)
| 页面功能 | API端点 | 方法 | 描述 |
|---------|---------|------|------|
| 获取提供商列表 | `/providers` | GET | 获取所有提供商信息 |
| 获取提供商详情 | `/providers/{id}` | GET | 获取特定提供商的详细信息 |
| 获取提供商模型 | `/providers/{id}/models` | GET | 获取提供商支持的模型列表 |
| 获取单个模型映射 | `/providers/{id}/models/{model_id}/mapping` | GET | 获取指定物理模型的别名映射配置（仅管理员或 Provider 拥有者） |
| 更新单个模型映射 | `/providers/{id}/models/{model_id}/mapping` | PUT | 更新/清除物理模型到别名的映射关系（仅管理员或 Provider 拥有者） |
| 检查提供商健康状态 | `/providers/{id}/health` | GET | 检查提供商的健康状况 |
| 获取提供商指标 | `/providers/{id}/metrics` | GET | 获取提供商的性能指标 |

### 6. 逻辑模型管理 (/dashboard/logical-models)
| 页面功能 | API端点 | 方法 | 描述 |
|---------|---------|------|------|
| 获取逻辑模型列表 | `/logical-models` | GET | 获取所有逻辑模型 |
| 获取逻辑模型详情 | `/logical-models/{id}` | GET | 获取特定逻辑模型的详细信息 |
| 获取逻辑模型上游 | `/logical-models/{id}/upstreams` | GET | 获取逻辑模型关联的上游提供商 |

### 7. API密钥管理 (/dashboard/api-keys)
| 页面功能 | API端点 | 方法 | 描述 |
|---------|---------|------|------|
| 获取用户API密钥 | `/api-keys` | GET | 获取当前用户的API密钥列表 |
| 创建API密钥 | `/api-keys` | POST | 创建新的API密钥 |
| 更新API密钥 | `/api-keys/{id}` | PUT | 更新API密钥信息 |
| 删除API密钥 | `/api-keys/{id}` | DELETE | 删除指定的API密钥 |
| 获取允许的提供商 | `/api-keys/{id}/allowed-providers` | GET | 获取API密钥允许访问的提供商 |
| 设置允许的提供商 | `/api-keys/{id}/allowed-providers` | PUT | 设置API密钥允许访问的提供商列表 |

### 8. 路由管理 (/dashboard/routing)
| 页面功能 | API端点 | 方法 | 描述 |
|---------|---------|------|------|
| 获取路由决策 | `/routing/decide` | POST | 根据条件获取路由决策 |
| 获取会话信息 | `/routing/sessions/{id}` | GET | 获取特定会话的信息 |
| 删除会话 | `/routing/sessions/{id}` | DELETE | 删除特定会话 |

### 9. 指标监控 (/dashboard/metrics)
| 页面功能 | API端点 | 方法 | 描述 |
|---------|---------|------|------|
| 获取提供商指标 | `/providers/{id}/metrics` | GET | 获取提供商的详细性能指标 |
| 获取逻辑模型指标 | 通过routing API获取 | POST | 通过路由API获取逻辑模型相关的指标 |

### 10. 系统管理 - 管理员 (/system/admin)
| 页面功能 | API端点 | 方法 | 描述 |
|---------|---------|------|------|
| 获取系统状态 | `/system/status` | GET | 获取系统整体运行状态 |
| 生成系统密钥 | `/system/secret-key/generate` | POST | 生成系统主密钥 |
| 轮换系统密钥 | `/system/secret-key/rotate` | POST | 轮换系统主密钥 |
| 初始化管理员 | `/system/admin/init` | POST | 初始化系统管理员账户 |
| 验证密钥强度 | `/system/key/validate` | POST | 验证密钥强度是否足够 |

### 11. 用户管理 - 管理员 (/system/users)
| 页面功能 | API端点 | 方法 | 描述 |
|---------|---------|------|------|
| 获取用户列表 | `/users` | GET | 获取系统用户列表 |
| 创建用户 | `/users` | POST | 创建新用户账户 |
| 更新用户信息 | `/users/{id}` | PUT | 更新用户基本信息 |
| 更新用户状态 | `/users/{id}/status` | PUT | 更新用户账户状态 |
| 获取用户API密钥 | `/api-keys` | GET | 获取特定用户的API密钥（管理员权限） |

### 12. 个人资料 (/profile)
| 页面功能 | API端点 | 方法 | 描述 |
|---------|---------|------|------|
| 获取当前用户信息 | `/auth/me` | GET | 获取当前认证用户的详细信息 |
| 更新用户信息 | `/users/{id}` | PUT | 更新当前用户的信息 |
| 修改密码 | 通过用户API实现 | PUT | 更新用户密码 |
| 获取用户API密钥 | `/api-keys` | GET | 获取当前用户的API密钥列表 |

## API使用频率分析

### 高频使用API
1. `/auth/me` - 多个页面需要验证用户信息
2. `/providers` - 仪表盘和提供商管理页面常用
3. `/logical-models` - 多个页面需要逻辑模型信息
4. `/providers/{id}/metrics` - 监控和指标页面频繁使用

### 中频使用API
1. `/providers/{id}` - 提供商详情页面
2. `/api-keys` - API密钥管理页面
3. `/routing/decide` - 路由管理页面

### 低频使用API
1. `/system/*` - 仅管理员使用
2. `/auth/login`、`/auth/register` - 仅认证流程使用
3. `/users/*` - 仅管理员管理用户时使用

## 错误处理映射

### 认证相关错误 (401)
- 影响页面: 所有需要登录的页面
- 处理方式: 重定向到登录页面，清除本地token

### 权限相关错误 (403)
- 影响页面: 系统管理页面
- 处理方式: 显示权限不足提示，返回仪表盘

### 资源不存在错误 (404)
- 影响页面: 所有详情页面
- 处理方式: 显示资源不存在提示，返回列表页面

### 服务器错误 (5xx)
- 影响页面: 所有页面
- 处理方式: 显示错误提示，提供重试选项

## 数据缓存策略

### 短期缓存（5-10分钟）
- 提供商信息
- 逻辑模型信息
- 用户基本信息

### 实时数据（不缓存）
- 提供商健康状态
- 路由决策
- 实时指标

### 长期缓存（1小时）
- 系统状态信息
- 用户权限信息
- API密钥列表

## API调用优化建议

1. **批量请求**: 对于需要多个相关数据的页面，使用并行请求
2. **条件请求**: 对于频繁请求的数据，使用条件请求（ETag）
3. **分页加载**: 对于大量数据的列表，实现分页加载
4. **延迟加载**: 对于非关键数据，实现延迟加载
5. **错误重试**: 对于临时性错误，实现自动重试机制
