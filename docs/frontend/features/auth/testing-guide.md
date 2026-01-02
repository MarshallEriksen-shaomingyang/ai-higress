# 前端认证功能测试指南

## 🎯 测试目标

验证前端认证功能的完整性，包括注册、登录、Token 刷新、登出等核心流程。

## 📋 前置条件

### 1. 启动后端服务

```bash
# 在仓库根目录确保数据库和 Redis 已启动（Docker）
cp .env.example .env
docker compose -f docker-compose.develop.yml --env-file .env up -d postgres redis

# 本地启动后端 API（开发热重载）
cd backend
uvicorn main:app --reload
```

后端应该运行在 `http://localhost:8000`

### 2. 配置前端环境变量

创建或更新 `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### 3. 启动前端服务

```bash
cd frontend
bun install
bun dev
```

前端应该运行在 `http://localhost:3000`

## 🧪 测试步骤

### 测试 1: 用户注册流程

#### 步骤：
1. 打开浏览器，访问 `http://localhost:3000/login`
2. 点击"注册"切换到注册表单
3. 填写注册信息：
   - 邮箱：`test@example.com`
   - 密码：`password123`
   - 确认密码：`password123`
4. 点击"注册"按钮

#### 预期结果：
- ✅ 表单验证通过
- ✅ 显示"注册成功"提示
- ✅ 自动登录
- ✅ 跳转到 `/dashboard/overview`
- ✅ 顶部导航栏显示用户头像/名称

#### 验证方法：
在浏览器控制台执行：
```javascript
console.log('Access Token:', localStorage.getItem('access_token'));
console.log('Cookies:', document.cookie);
```

应该看到 access_token 和 refresh_token。

---

### 测试 2: 用户登录流程

#### 步骤：
1. 如果已登录，先登出（点击用户菜单 → 退出登录）
2. 访问 `http://localhost:3000/login`
3. 填写登录信息：
   - 邮箱：`test@example.com`
   - 密码：`password123`
4. 点击"登录"按钮

#### 预期结果：
- ✅ 显示"登录成功"提示
- ✅ 跳转到 `/dashboard/overview`
- ✅ 顶部导航栏显示用户信息
- ✅ Token 存储在 localStorage 和 Cookie

---

### 测试 3: 受保护路由访问

#### 步骤：
1. 登出（如果已登录）
2. 直接访问 `http://localhost:3000/dashboard/overview`

#### 预期结果：
- ✅ 自动重定向到 `/login?redirect=/dashboard/overview`
- ✅ 登录成功后跳转回 `/dashboard/overview`

#### 步骤（已登录）：
1. 登录后访问 `http://localhost:3000/login`

#### 预期结果：
- ✅ 自动重定向到 `/dashboard/overview`

---

### 测试 4: Token 自动刷新

#### 步骤：
1. 登录系统
2. 打开浏览器开发者工具 → Network 标签
3. 手动触发刷新：在控制台执行
   ```javascript
   localStorage.removeItem('access_token');
   document.cookie = 'access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
   ```
4. 发起任何 API 请求（例如访问 dashboard 页面）

#### 预期结果：
- ✅ 第一个请求返回 401
- ✅ 自动调用 `/auth/refresh` 刷新 token
- ✅ 使用新 token 重试原请求
- ✅ 页面正常显示，无需重新登录
- ✅ Network 标签可以看到刷新请求

---

### 测试 5: 用户登出流程

#### 步骤：
1. 登录系统
2. 点击顶部导航栏的用户头像
3. 点击"退出登录"

#### 预期结果：
- ✅ 显示"已退出登录"提示
- ✅ 清除所有 token（localStorage 和 Cookie）
- ✅ 跳转到 `/login`
- ✅ 顶部导航栏显示"登录"按钮

#### 验证方法：
在浏览器控制台执行：
```javascript
console.log('Access Token:', localStorage.getItem('access_token'));
console.log('Cookies:', document.cookie);
```

---

### 测试 6: 页面刷新后状态保持

#### 步骤：
1. 登录系统
2. 访问任意页面（如 `/dashboard/providers`）
3. 按 F5 刷新页面

#### 预期结果：
- ✅ 页面刷新后仍然保持登录状态
- ✅ 用户信息正常显示
- ✅ 不需要重新登录

---

### 测试 7: 表单验证

#### 步骤（登录表单）：
1. 访问 `/login`
2. 尝试提交空表单
3. 输入无效数据：
   - 邮箱：`invalid-email`（不符合邮箱格式）
   - 密码：`12345`（少于 6 个字符）

#### 预期结果：
- ✅ 显示相应的错误提示
- ✅ 表单不会提交
- ✅ 错误信息清晰明确

#### 步骤（注册表单）：
1. 切换到注册表单
2. 测试各种无效输入：
   - 无效邮箱格式
   - 密码太短
   - 两次密码不一致

#### 预期结果：
- ✅ 所有验证规则正确触发
- ✅ 错误提示准确

---

### 测试 8: 错误处理

#### 步骤：
1. 尝试使用错误的凭据登录
   - 邮箱：`wrong@example.com`
   - 密码：`wrongpass`

#### 预期结果：
- ✅ 显示"邮箱或密码错误"提示
- ✅ 不会跳转
- ✅ 表单保持可用

#### 步骤：
2. 尝试注册已存在的邮箱

#### 预期结果：
- ✅ 显示"邮箱已被使用"提示

---

## ✅ 测试清单

完成所有测试后，确认以下功能正常：

- [ ] 用户可以成功注册
- [ ] 用户可以使用邮箱登录
- [ ] 注册后自动登录
- [ ] 登录后跳转到 dashboard
- [ ] 未登录访问受保护路由会重定向
- [ ] 登录后重定向到原页面
- [ ] 已登录访问登录页会重定向到 dashboard
- [ ] Token 过期后自动刷新
- [ ] 刷新失败后跳转登录页
- [ ] 用户可以成功登出
- [ ] 登出后清除所有 token
- [ ] 页面刷新后状态保持
- [ ] 表单验证正确工作
- [ ] 错误提示清晰友好
- [ ] 用户菜单正常显示
- [ ] 顶部导航栏状态正确

---

## 🐛 常见问题

### 问题 1: 登录后立即跳转到登录页

**原因**: Token 未正确存储在 Cookie

**解决方案**:
1. 检查浏览器是否允许 Cookie
2. 检查 `tokenManager.setAccessToken()` 是否正确调用
3. 查看浏览器控制台是否有错误

### 问题 2: 401 错误后没有自动刷新

**原因**: Axios 拦截器未正确配置

**解决方案**:
1. 检查 `frontend/http/client.ts` 的响应拦截器
2. 确认 refresh_token 存在
3. 查看 Network 标签是否有 `/auth/refresh` 请求

### 问题 3: Middleware 不工作

**原因**: Middleware 配置错误或 Cookie 未设置

**解决方案**:
1. 检查 `frontend/middleware.ts` 的 matcher 配置
2. 确认 token 存储在 Cookie 中
3. 重启开发服务器

---

## 🎉 测试完成

如果所有测试都通过，恭喜！前端认证功能已经成功集成。

下一步：
1. 部署到测试环境
2. 进行更全面的集成测试
3. 收集用户反馈
4. 优化用户体验

---

**文档版本**: 1.0.0  
**最后更新**: 2025-12-04  
**维护者**: AI Higress Team
