import type { Language } from "../i18n-context";

export const profileTranslations: Record<Language, Record<string, string>> = {
  en: {
    // Page header
    "profile.subtitle": "Manage your account settings and preferences",

    // Profile info section
    "profile.info_title": "Profile Information",
    "profile.info_description": "Update your personal details",
    "profile.edit_button": "Edit Profile",
    "profile.change_avatar": "Change Avatar",
    "profile.full_name": "Full Name",
    "profile.email": "Email",
    "profile.role_label": "Role",
    "profile.role_no_roles": "No roles",
    "profile.account_created": "Account Created",
    "profile.update_success": "Profile updated successfully",
    "profile.update_avatar_success": "Avatar updated successfully",

    // Security section
    "profile.security_title": "Security",
    "profile.security_description": "Manage your password and security settings",
    "profile.current_password": "Current Password",
    "profile.new_password": "New Password",
    "profile.confirm_password": "Confirm New Password",
    "profile.update_password": "Update Password",
    "profile.updating_password": "Updating...",
    "profile.password_required": "Please enter the new password",
    "profile.password_mismatch": "New password and confirmation do not match",
    "profile.password_update_success": "Password updated successfully",

    // Preferences section
    "profile.preferences_title": "Preferences",
    "profile.preferences_description": "Customize your experience",
    "profile.email_notifications_title": "Email Notifications",
    "profile.email_notifications_description":
      "Receive email updates about system events",
    "profile.configure_button": "Configure",
    "profile.language_region_title": "Language & Region",
    "profile.language_english": "English (US)",
    "profile.language_chinese": "Simplified Chinese",
    "profile.change_language_button": "Change",

    // Danger zone
    "profile.danger_zone_title": "Danger Zone",
    "profile.danger_zone_description": "Irreversible actions",
    "profile.delete_account_title": "Delete Account",
    "profile.delete_account_description":
      "Permanently delete your account and all associated data (not yet implemented)",
    "profile.delete_account_button": "Delete Account",
  },
  zh: {
    // Page header
    "profile.subtitle": "管理你的账户设置和偏好",

    // Profile info section
    "profile.info_title": "个人资料",
    "profile.info_description": "更新你的个人信息",
    "profile.edit_button": "编辑资料",
    "profile.change_avatar": "更换头像",
    "profile.full_name": "姓名",
    "profile.email": "邮箱",
    "profile.role_label": "角色",
    "profile.role_no_roles": "暂无角色",
    "profile.account_created": "创建时间",
    "profile.update_success": "个人资料已更新",
    "profile.update_avatar_success": "头像已更新",

    // Security section
    "profile.security_title": "安全设置",
    "profile.security_description": "管理登录密码和安全相关设置",
    "profile.current_password": "当前密码",
    "profile.new_password": "新密码",
    "profile.confirm_password": "确认新密码",
    "profile.update_password": "更新密码",
    "profile.updating_password": "更新中...",
    "profile.password_required": "请输入新密码",
    "profile.password_mismatch": "两次输入的密码不一致",
    "profile.password_update_success": "密码更新成功",

    // Preferences section
    "profile.preferences_title": "偏好设置",
    "profile.preferences_description": "配置你的使用体验",
    "profile.email_notifications_title": "邮件通知",
    "profile.email_notifications_description": "接收系统事件的邮件通知",
    "profile.configure_button": "配置",
    "profile.language_region_title": "语言与区域",
    "profile.language_english": "English (US)",
    "profile.language_chinese": "简体中文",
    "profile.change_language_button": "更改",

    // Danger zone
    "profile.danger_zone_title": "危险区域",
    "profile.danger_zone_description": "包含不可逆操作",
    "profile.delete_account_title": "删除账户",
    "profile.delete_account_description":
      "永久删除你的账户及相关数据（暂未开放）",
    "profile.delete_account_button": "删除账户",
  },
};
