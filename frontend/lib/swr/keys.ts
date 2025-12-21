/**
 * 统一管理 SWR key，避免在各处硬编码 path。
 * 约定：key 只负责缓存标识，不负责拼装完整业务参数（复杂查询可在领域 hook 内构造）。
 */
export const swrKeys = {
  adminUsers: () => "/admin/users",
  adminRoles: () => "/admin/roles",
  adminPermissions: () => "/admin/permissions",
  adminEvals: () => "/admin/evals",
  adminEval: (evalId: string) => `/admin/evals/${evalId}`,
  adminUserRoles: (userId: string) => `/admin/users/${userId}/roles`,
  adminUserPermissions: (userId: string) => `/admin/users/${userId}/permissions`,
  providerSubmissionsMe: () => "/providers/submissions/me",
};
