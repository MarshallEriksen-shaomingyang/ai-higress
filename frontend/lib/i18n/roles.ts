import type { Language } from "../i18n-context";

export const rolesTranslations: Record<Language, Record<string, string>> = {
  en: {
    // Roles page
    "roles.title": "Roles & Permissions",
    "roles.subtitle": "Manage system roles and their access permissions",
    "roles.add_role": "Add Role",
    "roles.create_dialog_title": "Create New Role",
    "roles.edit_dialog_title": "Edit Role",
    "roles.permissions_dialog_title": "Manage Permissions",
    "roles.label_role_name": "Role Name",
    "roles.label_role_code": "Role Code",
    "roles.label_role_desc": "Description",
    "roles.table_column_name": "Name",
    "roles.table_column_code": "Code",
    "roles.table_column_description": "Description",
    "roles.delete_confirm": "Are you sure you want to delete this role?",
    "roles.permissions_save": "Save Permissions",
    "roles.permissions_desc": "Select the permissions for this role",
  },
  zh: {
    // Roles page
    "roles.title": "角色与权限",
    "roles.subtitle": "管理系统角色及其访问权限",
    "roles.add_role": "添加角色",
    "roles.create_dialog_title": "创建新角色",
    "roles.edit_dialog_title": "编辑角色",
    "roles.permissions_dialog_title": "管理权限",
    "roles.label_role_name": "角色名称",
    "roles.label_role_code": "角色编码",
    "roles.label_role_desc": "描述",
    "roles.table_column_name": "名称",
    "roles.table_column_code": "编码",
    "roles.table_column_description": "描述",
    "roles.delete_confirm": "确定要删除该角色吗？",
    "roles.permissions_save": "保存权限",
    "roles.permissions_desc": "为该角色选择权限",
  },
};
