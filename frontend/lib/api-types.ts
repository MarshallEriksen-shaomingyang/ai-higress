// API 类型定义文件
// 此文件包含所有与后端 API 交互的 TypeScript 类型定义

// ============= 认证相关 =============
export interface UserInfo {
  id: string;
  username: string;
  email: string;
  display_name: string | null;
  avatar: string | null;
  is_active: boolean;
  is_superuser: boolean;
  role_codes?: string[];
  permission_flags?: Array<{
    key: string;
    value: boolean;
  }>;
  created_at: string;
  updated_at: string;
}

// ============= API 密钥相关 =============
export interface ApiKey {
  id: string;
  user_id: string;
  name: string;
  key_prefix: string;
  expiry_type: 'week' | 'month' | 'year' | 'never';
  expires_at: string | null;
  created_at: string;
  updated_at: string;
  has_provider_restrictions: boolean;
  allowed_provider_ids: string[];
  token?: string; // 仅在创建时返回
}

export interface CreateApiKeyRequest {
  name: string;
  expiry?: 'week' | 'month' | 'year' | 'never';
  allowed_provider_ids?: string[];
}

export interface UpdateApiKeyRequest {
  name?: string;
  expiry?: 'week' | 'month' | 'year' | 'never';
  allowed_provider_ids?: string[];
}

// ============= 积分相关 =============
export interface CreditAccount {
  id: string;
  user_id: string;
  balance: number;
  daily_limit: number | null;
  status: 'active' | 'suspended';
  created_at: string;
  updated_at: string;
}

export interface CreditTransaction {
  id: string;
  account_id: string;
  user_id: string;
  api_key_id: string | null;
  amount: number;
  reason: 'usage' | 'topup' | 'refund' | 'adjustment';
  description: string | null;
  model_name: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  created_at: string;
}

export interface TopupRequest {
  amount: number;
  description?: string;
}

export interface TransactionQueryParams {
  limit?: number;
  offset?: number;
  start_date?: string;
  end_date?: string;
}

// ============= 厂商密钥相关 =============
export interface ProviderKey {
  id: string;
  provider_id: string;
  label: string;
  key_prefix?: string;  // 前端显示用，后端不返回完整密钥
  weight: number;
  max_qps: number | null;
  status: 'active' | 'inactive';
  created_at: string;
  updated_at: string | null;
}

export interface CreateProviderKeyRequest {
  key: string;
  label: string;
  weight?: number;
  max_qps?: number;
  status?: 'active' | 'inactive';
}

export interface UpdateProviderKeyRequest {
  key?: string;
  label?: string;
  weight?: number;
  max_qps?: number;
  status?: 'active' | 'inactive';
}
