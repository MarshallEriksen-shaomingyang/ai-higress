// 导出所有HTTP服务和类型
export { httpClient, type AxiosRequestConfig, type AxiosResponse, type AxiosError } from './client';
export { authService, type LoginRequest, type RegisterRequest, type AuthResponse, type UserInfo } from './auth';
export { userService, type CreateUserRequest, type UpdateUserRequest, type UpdateUserStatusRequest } from './user';
export { apiKeyService, type CreateApiKeyRequest, type UpdateApiKeyRequest, type ApiKey, type AllowedProviders } from './api-key';
export {
  providerService,
  type Provider,
  type Model,
  type HealthStatus,
  type ProviderMetrics,
  type MetricsResponse
} from './provider';
export {
  logicalModelService,
  type LogicalModel,
  type UpstreamModel,
  type UpstreamsResponse
} from './logical-model';
export {
  routingService,
  type RoutingDecisionRequest,
  type RoutingDecisionResponse,
  type CandidateInfo,
  type SessionInfo
} from './routing';
export {
  systemService,
  type GenerateSecretKeyRequest,
  type GenerateSecretKeyResponse,
  type InitAdminRequest,
  type InitAdminResponse,
  type ValidateKeyRequest,
  type ValidateKeyResponse,
  type SystemStatusResponse,
  type CacheSegment,
  type CacheClearResponse,
  type ProviderLimits,
  type UpdateProviderLimitsRequest
} from './system';
export {
  adminService,
  type Permission,
  type Role,
  type CreateRoleRequest,
  type UpdateRoleRequest,
  type RolePermissionsResponse,
  type SetRolePermissionsRequest
} from './admin';
export {
  creditService,
  type CreditAccount,
  type CreditTransaction,
  type TopupRequest,
  type TransactionQueryParams
} from './credit';
export {
  providerKeyService,
  type ProviderKey,
  type CreateProviderKeyRequest,
  type UpdateProviderKeyRequest
} from './provider-keys';
