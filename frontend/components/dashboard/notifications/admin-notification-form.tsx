"use client";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Checkbox } from "@/components/ui/checkbox";
import { useI18n } from "@/lib/i18n-context";
import { toast } from "sonner";
import { useErrorDisplay } from "@/lib/errors";
import { useCreateNotification } from "@/lib/swr/use-notifications";
import { useAdminUsers } from "@/lib/swr/use-admin-users";
import { useAllRoles } from "@/lib/swr/use-user-roles";
import type { NotificationLevel, NotificationTargetType } from "@/lib/api-types";
import { useMemo, useState } from "react";

interface AdminNotificationFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

interface FormData {
  title: string;
  content: string;
  level: NotificationLevel;
  target_type: NotificationTargetType;
  target_user_ids: string[];
  target_role_codes: string[];
  link_url?: string;
}

interface FormErrors {
  title?: string;
  content?: string;
  target_user_ids?: string;
  target_role_codes?: string;
  link_url?: string;
}

export function AdminNotificationForm({
  open,
  onOpenChange,
  onSuccess
}: AdminNotificationFormProps) {
  const { t } = useI18n();
  const { showError } = useErrorDisplay();
  const { createNotification, submitting, isSuperUser } = useCreateNotification();
  const { users, loading: loadingUsers } = useAdminUsers();
  const { roles, loading: loadingRoles } = useAllRoles();
  
  const [formData, setFormData] = useState<FormData>({
    title: '',
    content: '',
    level: 'info',
    target_type: 'all',
    target_user_ids: [],
    target_role_codes: [],
    link_url: '',
  });
  const [userSearch, setUserSearch] = useState("");
  const [userPopoverOpen, setUserPopoverOpen] = useState(false);
  const [rolePopoverOpen, setRolePopoverOpen] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});

  // 如果不是超级管理员，不渲染组件
  if (!isSuperUser) {
    return null;
  }

  // 验证表单
  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};
    
    if (!formData.title.trim()) {
      newErrors.title = t("notifications.form.titleRequired");
    } else if (formData.title.length > 100) {
      newErrors.title = t("notifications.form.titleTooLong");
    }
    
    if (!formData.content.trim()) {
      newErrors.content = t("notifications.form.contentRequired");
    } else if (formData.content.length > 500) {
      newErrors.content = t("notifications.form.contentTooLong");
    }

    if (formData.target_type === 'users') {
      if (!formData.target_user_ids.length) {
        newErrors.target_user_ids = t("notifications.form.userIdsRequired");
      }
    }

    if (formData.target_type === 'roles') {
      if (!formData.target_role_codes.length) {
        newErrors.target_role_codes = t("notifications.form.rolesRequired");
      }
    }

    if (formData.link_url && formData.link_url.trim()) {
      try {
        new URL(formData.link_url);
      } catch {
        newErrors.link_url = t("notifications.form.invalidUrl");
      }
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // 处理提交
  const handleSubmit = async () => {
    if (!validateForm()) return;
    
    try {
      const payload: any = {
        title: formData.title.trim(),
        content: formData.content.trim(),
        level: formData.level,
        target_type: formData.target_type,
      };

      if (formData.target_type === 'users' && formData.target_user_ids.length) {
        payload.target_user_ids = formData.target_user_ids;
      }

      if (formData.target_type === 'roles' && formData.target_role_codes.length) {
        payload.target_role_codes = formData.target_role_codes;
      }

      if (formData.link_url?.trim()) {
        payload.link_url = formData.link_url.trim();
      }

      await createNotification(payload);
      
      toast.success(t("notifications.form.createSuccess"));
      
      // 重置表单
      setFormData({
        title: '',
        content: '',
        level: 'info',
        target_type: 'all',
        target_user_ids: [],
        target_role_codes: [],
        link_url: '',
      });
      setErrors({});
      
      // 关闭对话框
      onOpenChange(false);
      
      // 调用成功回调
      onSuccess?.();
    } catch (error) {
      showError(error, { context: t("notifications.form.createError") });
    }
  };

  // 处理对话框关闭
  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen && !submitting) {
      // 重置表单
      setFormData({
        title: '',
        content: '',
        level: 'info',
        target_type: 'all',
        target_user_ids: [],
        target_role_codes: [],
        link_url: '',
      });
      setErrors({});
    }
    onOpenChange(newOpen);
  };

  const updateField = <K extends keyof FormData>(field: K, value: FormData[K]) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field as keyof FormErrors]) {
      setErrors(prev => ({ ...prev, [field]: undefined }));
    }
  };

  const filteredUsers = useMemo(() => {
    const keyword = userSearch.trim().toLowerCase();
    if (!keyword) return users;
    return users.filter(user =>
      user.username.toLowerCase().includes(keyword) ||
      (user.email ?? "").toLowerCase().includes(keyword)
    );
  }, [users, userSearch]);

  const toggleUser = (userId: string) => {
    setFormData(prev => {
      const exists = prev.target_user_ids.includes(userId);
      const next = exists
        ? prev.target_user_ids.filter(id => id !== userId)
        : [...prev.target_user_ids, userId];
      return { ...prev, target_user_ids: next };
    });
    if (errors.target_user_ids) {
      setErrors(prev => ({ ...prev, target_user_ids: undefined }));
    }
  };

  const toggleRole = (roleCode: string) => {
    setFormData(prev => {
      const exists = prev.target_role_codes.includes(roleCode);
      const next = exists
        ? prev.target_role_codes.filter(code => code !== roleCode)
        : [...prev.target_role_codes, roleCode];
      return { ...prev, target_role_codes: next };
    });
    if (errors.target_role_codes) {
      setErrors(prev => ({ ...prev, target_role_codes: undefined }));
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>{t("notifications.form.createTitle")}</DialogTitle>
          <DialogDescription>
            {t("notifications.form.createDescription")}
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4 py-4 max-h-[60vh] overflow-y-auto">
          {/* 标题 */}
          <div className="space-y-2">
            <Label htmlFor="title">
              {t("notifications.form.title")} <span className="text-destructive">*</span>
            </Label>
            <Input
              id="title"
              placeholder={t("notifications.form.titlePlaceholder")}
              value={formData.title}
              onChange={(e) => updateField('title', e.target.value)}
              disabled={submitting}
              maxLength={100}
              className={errors.title ? 'border-destructive' : ''}
            />
            {errors.title && (
              <p className="text-sm text-destructive">{errors.title}</p>
            )}
            <p className="text-xs text-muted-foreground">
              {formData.title.length} / 100
            </p>
          </div>

          {/* 内容 */}
          <div className="space-y-2">
            <Label htmlFor="content">
              {t("notifications.form.content")} <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="content"
              placeholder={t("notifications.form.contentPlaceholder")}
              value={formData.content}
              onChange={(e) => updateField('content', e.target.value)}
              disabled={submitting}
              rows={4}
              maxLength={500}
              className={errors.content ? 'border-destructive' : ''}
            />
            {errors.content && (
              <p className="text-sm text-destructive">{errors.content}</p>
            )}
            <p className="text-xs text-muted-foreground">
              {formData.content.length} / 500
            </p>
          </div>

          {/* 等级 */}
          <div className="space-y-2">
            <Label htmlFor="level">{t("notifications.form.level")}</Label>
            <Select
              value={formData.level}
              onValueChange={(value) => updateField('level', value as NotificationLevel)}
              disabled={submitting}
            >
              <SelectTrigger id="level">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="info">{t("notifications.level.info")}</SelectItem>
                <SelectItem value="success">{t("notifications.level.success")}</SelectItem>
                <SelectItem value="warning">{t("notifications.level.warning")}</SelectItem>
                <SelectItem value="error">{t("notifications.level.error")}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* 目标受众 */}
          <div className="space-y-2">
            <Label htmlFor="target_type">{t("notifications.form.targetType")}</Label>
            <Select
              value={formData.target_type}
              onValueChange={(value) => updateField('target_type', value as NotificationTargetType)}
              disabled={submitting}
            >
              <SelectTrigger id="target_type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("notifications.targetType.all")}</SelectItem>
                <SelectItem value="users">{t("notifications.targetType.users")}</SelectItem>
                <SelectItem value="roles">{t("notifications.targetType.roles")}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* 指定用户（仅当 target_type 为 users 时显示） */}
          {formData.target_type === 'users' && (
            <div className="space-y-2">
              <Label>
                {t("notifications.form.targetUserIds")} <span className="text-destructive">*</span>
              </Label>
              <Popover open={userPopoverOpen} onOpenChange={setUserPopoverOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={userPopoverOpen}
                    className={errors.target_user_ids ? "justify-between border-destructive" : "justify-between"}
                    disabled={submitting}
                  >
                    {formData.target_user_ids.length > 0
                      ? `${t("notifications.form.selectUsers")} (${formData.target_user_ids.length})`
                      : t("notifications.form.selectUsers")}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[480px] p-3" align="start">
                  <div className="space-y-3">
                    <Input
                      placeholder={t("notifications.form.searchUser")}
                      value={userSearch}
                      onChange={(e) => setUserSearch(e.target.value)}
                      disabled={loadingUsers}
                    />
                    <ScrollArea className="h-64 pr-2">
                      {loadingUsers ? (
                        <p className="text-sm text-muted-foreground py-2">{t("common.loading")}</p>
                      ) : filteredUsers.length === 0 ? (
                        <p className="text-sm text-muted-foreground py-2">{t("notifications.form.noUsers")}</p>
                      ) : (
                        <div className="space-y-2">
                          {filteredUsers.map((user) => (
                            <label
                              key={user.id}
                              className="flex items-start gap-3 rounded-md px-2 py-2 hover:bg-muted/50"
                            >
                              <Checkbox
                                checked={formData.target_user_ids.includes(user.id)}
                                onCheckedChange={() => toggleUser(user.id)}
                              />
                              <div className="flex flex-col text-sm leading-tight">
                                <span className="font-medium">{user.username}</span>
                                {user.email && (
                                  <span className="text-muted-foreground text-xs">{user.email}</span>
                                )}
                              </div>
                            </label>
                          ))}
                        </div>
                      )}
                    </ScrollArea>
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>
                        {t("notifications.form.selectedCount").replace("{count}", formData.target_user_ids.length.toString())}
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => updateField("target_user_ids", [])}
                        disabled={!formData.target_user_ids.length}
                      >
                        {t("notifications.form.clearSelection")}
                      </Button>
                    </div>
                  </div>
                </PopoverContent>
              </Popover>
              {errors.target_user_ids && (
                <p className="text-sm text-destructive">{errors.target_user_ids}</p>
              )}
              <p className="text-xs text-muted-foreground">
                {t("notifications.form.targetUserIdsHint")}
              </p>
            </div>
          )}

          {/* 指定角色（仅当 target_type 为 roles 时显示） */}
          {formData.target_type === 'roles' && (
            <div className="space-y-2">
              <Label>
                {t("notifications.form.targetRoleCodes")} <span className="text-destructive">*</span>
              </Label>
              <Popover open={rolePopoverOpen} onOpenChange={setRolePopoverOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={rolePopoverOpen}
                    className={errors.target_role_codes ? "justify-between border-destructive" : "justify-between"}
                    disabled={submitting}
                  >
                    {formData.target_role_codes.length > 0
                      ? `${t("notifications.form.selectRoles")} (${formData.target_role_codes.length})`
                      : t("notifications.form.selectRoles")}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[480px] p-3" align="start">
                  <ScrollArea className="h-64 pr-2">
                    {loadingRoles ? (
                      <p className="text-sm text-muted-foreground py-2">{t("common.loading")}</p>
                    ) : roles.length === 0 ? (
                      <p className="text-sm text-muted-foreground py-2">{t("notifications.form.noRoles")}</p>
                    ) : (
                      <div className="space-y-2">
                        {roles.map((role) => (
                          <label
                            key={role.code}
                            className="flex items-start gap-3 rounded-md px-2 py-2 hover:bg-muted/50"
                          >
                            <Checkbox
                              checked={formData.target_role_codes.includes(role.code)}
                              onCheckedChange={() => toggleRole(role.code)}
                            />
                            <div className="flex flex-col text-sm leading-tight">
                              <span className="font-medium">{role.name}</span>
                              <span className="text-muted-foreground text-xs">{role.code}</span>
                            </div>
                          </label>
                        ))}
                      </div>
                    )}
                  </ScrollArea>
                  <div className="flex items-center justify-between text-xs text-muted-foreground pt-2">
                    <span>
                      {t("notifications.form.selectedCount").replace("{count}", formData.target_role_codes.length.toString())}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => updateField("target_role_codes", [])}
                      disabled={!formData.target_role_codes.length}
                    >
                      {t("notifications.form.clearSelection")}
                    </Button>
                  </div>
                </PopoverContent>
              </Popover>
              {errors.target_role_codes && (
                <p className="text-sm text-destructive">{errors.target_role_codes}</p>
              )}
            </div>
          )}

          {/* 链接 URL（可选） */}
          <div className="space-y-2">
            <Label htmlFor="link_url">{t("notifications.form.linkUrl")}</Label>
            <Input
              id="link_url"
              type="url"
              placeholder={t("notifications.form.linkUrlPlaceholder")}
              value={formData.link_url}
              onChange={(e) => updateField('link_url', e.target.value)}
              disabled={submitting}
              className={errors.link_url ? 'border-destructive' : ''}
            />
            {errors.link_url && (
              <p className="text-sm text-destructive">{errors.link_url}</p>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={submitting}
          >
            {t("common.cancel")}
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={submitting}
          >
            {submitting ? t("notifications.form.creating") : t("notifications.form.create")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
