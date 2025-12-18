import { httpClient } from './client';
import type { UserInfo } from '@/lib/api-types';

// 权限定义
export interface Permission {
    id: string;
    code: string;
    description: string;
    created_at: string;
    updated_at: string;
}

// 角色定义
export interface Role {
    id: string;
    code: string;
    name: string;
    description?: string;
    created_at: string;
    updated_at: string;
}

// 创建角色请求
export interface CreateRoleRequest {
    code: string;
    name: string;
    description?: string;
}

// 更新角色请求
export interface UpdateRoleRequest {
    name?: string;
    description?: string;
}

// 角色权限响应
export interface RolePermissionsResponse {
    role_id: string;
    role_code: string;
    permission_codes: string[];
}

// 设置角色权限请求
export interface SetRolePermissionsRequest {
    permission_codes: string[];
}

// Admin API 服务
export const adminService = {
    // 获取所有权限定义
    getPermissions: async (): Promise<Permission[]> => {
        const response = await httpClient.get('/admin/permissions');
        return response.data;
    },

    // 获取所有角色
    getRoles: async (): Promise<Role[]> => {
        const response = await httpClient.get('/admin/roles');
        return response.data;
    },

    // 创建角色
    createRole: async (data: CreateRoleRequest): Promise<Role> => {
        const response = await httpClient.post('/admin/roles', data);
        return response.data;
    },

    // 更新角色
    updateRole: async (roleId: string, data: UpdateRoleRequest): Promise<Role> => {
        const response = await httpClient.put(`/admin/roles/${roleId}`, data);
        return response.data;
    },

    // 删除角色
    deleteRole: async (roleId: string): Promise<void> => {
        await httpClient.delete(`/admin/roles/${roleId}`);
    },

    // 获取角色的权限
    getRolePermissions: async (roleId: string): Promise<RolePermissionsResponse> => {
        const response = await httpClient.get(`/admin/roles/${roleId}/permissions`);
        return response.data;
    },

    // 设置角色的权限
    setRolePermissions: async (roleId: string, data: SetRolePermissionsRequest): Promise<RolePermissionsResponse> => {
        const response = await httpClient.put(`/admin/roles/${roleId}/permissions`, data);
        return response.data;
    },

    // 获取用户的角色
    getUserRoles: async (userId: string): Promise<Role[]> => {
        const response = await httpClient.get(`/admin/users/${userId}/roles`);
        return response.data;
    },

    // 设置用户的角色
    setUserRoles: async (userId: string, roleIds: string[]): Promise<Role[]> => {
        const response = await httpClient.put(`/admin/users/${userId}/roles`, { role_ids: roleIds });
        return response.data;
    },

    // 获取所有用户（管理员）
    getAllUsers: async (): Promise<UserInfo[]> => {
        const response = await httpClient.get('/admin/users');
        return response.data;
    },

    // 获取用户权限
    getUserPermissions: async (userId: string): Promise<import('@/lib/api-types').UserPermission[]> => {
        const response = await httpClient.get(`/admin/users/${userId}/permissions`);
        return response.data;
    },

    // 授予/更新用户权限
    grantUserPermission: async (
        userId: string,
        data: import('@/lib/api-types').GrantPermissionRequest
    ): Promise<import('@/lib/api-types').UserPermission> => {
        const response = await httpClient.post(`/admin/users/${userId}/permissions`, data);
        return response.data;
    },

    // 撤销用户权限
    revokeUserPermission: async (userId: string, permissionId: string): Promise<void> => {
        await httpClient.delete(`/admin/users/${userId}/permissions/${permissionId}`);
    },
};
