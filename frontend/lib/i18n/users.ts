import type { Language } from "../i18n-context";

export const usersTranslations: Record<Language, Record<string, string>> = {
  en: {
    // Users page
    "users.title": "User Management",
    "users.subtitle": "Manage user accounts and permissions",
    "users.add_user": "Add User",
    "users.table_column_name": "Name",
    "users.table_column_email": "Email",
    "users.table_column_roles": "Roles",
    "users.table_column_status": "Status",
    "users.table_column_last_login": "Last Login",
    "users.manage_roles": "Manage Roles",
    "users.roles_dialog_title": "Manage User Roles",
    "users.roles_dialog_desc": "Assign roles to this user",
    "users.select_roles": "Select roles for this user",
  },
  zh: {
    // Users page
    "users.title": "用户管理",
    "users.subtitle": "管理用户账户和权限",
    "users.add_user": "添加用户",
    "users.table_column_name": "姓名",
    "users.table_column_email": "邮箱",
    "users.table_column_roles": "角色",
    "users.table_column_status": "状态",
    "users.table_column_last_login": "最后登录",
    "users.manage_roles": "管理角色",
    "users.roles_dialog_title": "管理用户角色",
    "users.roles_dialog_desc": "为该用户分配角色",
    "users.select_roles": "为该用户选择角色",
  },
};
