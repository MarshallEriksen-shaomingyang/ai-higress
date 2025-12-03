# 测试文件说明

## 当前测试状态

1. **API密钥测试**
   - `test_api_key_routes.py` 测试API密钥的CRUD操作
   - 这些功能现在已移至JWT认证的路由中 (`app/api/v2/api_key_routes.py`)
   - 测试需要更新或重构

2. **认证测试**
   - `test_auth.py` 测试用户认证功能
   - 这些测试应该与新JWT系统兼容

## 需要更新的测试

1. 拆分API密钥测试为两个部分：
   - 客户端API密钥认证测试（访问AI服务）
   - API密钥管理测试（JWT认证的路由）

2. 为新的JWT认证路由添加测试：
   - `/auth/login`
   - `/auth/register`
   - `/auth/refresh`
   - `/users/{user_id}/api-keys`
   - `/providers/{provider_id}/keys`
   - `/system/*`

## 测试运行

运行所有测试：
```bash
pytest tests/
```

运行特定测试：
```bash
pytest tests/test_auth.py
```