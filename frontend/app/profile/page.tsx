"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { User, Mail, Lock, Bell, Globe } from "lucide-react";
import { SessionCard } from "./components/session-card";
import {
  RevokeSessionDialog,
  RevokeAllSessionsDialog,
} from "./components/revoke-session-dialog";
import { useSessions, useRevokeSession } from "@/lib/swr/use-sessions";
import { useI18n } from "@/lib/i18n-context";
import { toast } from "sonner";
import type { SessionResponse } from "@/lib/api-types";
import { useAuthStore } from "@/lib/stores/auth-store";
import { userService } from "@/http/user";
import { ErrorHandler } from "@/lib/errors";

export default function ProfilePage() {
  const { t, language } = useI18n();

  // Auth state
  const authUser = useAuthStore((state) => state.user);
  const isAuthLoading = useAuthStore((state) => state.isLoading);
  const setAuthUser = useAuthStore((state) => state.setUser);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Profile editing state
  const [isEditing, setIsEditing] = useState(false);
  const [profileForm, setProfileForm] = useState({
    display_name: "",
    email: "",
  });
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isUploadingAvatar, setIsUploadingAvatar] = useState(false);

  // Password change state
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isUpdatingPassword, setIsUpdatingPassword] = useState(false);

  // Session management
  const { sessions, loading, refresh } = useSessions();
  const { revokeSession, revokeOtherSessions } = useRevokeSession();
  const [selectedSession, setSelectedSession] = useState<SessionResponse | null>(
    null,
  );
  const [showRevokeDialog, setShowRevokeDialog] = useState(false);
  const [showRevokeAllDialog, setShowRevokeAllDialog] = useState(false);
  const [isRevoking, setIsRevoking] = useState(false);

  const otherSessionsCount = sessions.filter((s) => !s.is_current).length;

  // 初始化表单为当前用户信息
  useEffect(() => {
    if (authUser) {
      setProfileForm({
        display_name: authUser.display_name ?? "",
        email: authUser.email,
      });
    }
  }, [authUser]);

  const handleProfileInputChange = (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const { name, value } = e.target;
    setProfileForm((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleAvatarButtonClick = () => {
    if (!isEditing) return;
    fileInputRef.current?.click();
  };

  const handleAvatarFileChange = async (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    if (!authUser) return;

    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploadingAvatar(true);
    try {
      const updated = await userService.uploadAvatar(file);
      setAuthUser(updated);
      toast.success(t("profile.update_avatar_success"));
    } catch (error) {
      const normalized = ErrorHandler.normalize(error);
      const message = ErrorHandler.getUserMessage(normalized, t);
      toast.error(message);
    } finally {
      setIsUploadingAvatar(false);
      // 允许用户选择同一个文件时也能再次触发 onChange
      e.target.value = "";
    }
  };

  const handleRevoke = (sessionId: string) => {
    const session = sessions.find((s) => s.session_id === sessionId);
    if (session) {
      setSelectedSession(session);
      setShowRevokeDialog(true);
    }
  };

  const handleConfirmRevoke = async () => {
    if (!selectedSession) return;

    setIsRevoking(true);
    try {
      await revokeSession(selectedSession.session_id);
      toast.success(t("sessions.revoke_success"));
      setShowRevokeDialog(false);
      refresh();
    } catch (error) {
      toast.error(t("sessions.revoke_error"));
    } finally {
      setIsRevoking(false);
    }
  };

  const handleRevokeAll = async () => {
    setIsRevoking(true);
    try {
      await revokeOtherSessions();
      toast.success(t("sessions.revoke_all_success"));
      setShowRevokeAllDialog(false);
      refresh();
    } catch (error) {
      toast.error(t("sessions.revoke_all_error"));
    } finally {
      setIsRevoking(false);
    }
  };

  const formattedCreatedAt =
    authUser?.created_at &&
    new Intl.DateTimeFormat(language === "zh" ? "zh-CN" : "en-US", {
      year: "numeric",
      month: "long",
      day: "2-digit",
    }).format(new Date(authUser.created_at));

  const profileRolesLabel =
    authUser?.role_codes && authUser.role_codes.length > 0
      ? authUser.role_codes.join(", ")
      : t("profile.role_no_roles");

  const languageLabel =
    language === "zh"
      ? t("profile.language_chinese")
      : t("profile.language_english");

  const handleSaveProfile = async () => {
    if (!authUser) return;

    setIsSavingProfile(true);
    try {
      const payload: { display_name?: string; email?: string } = {};
      if (profileForm.display_name !== authUser.display_name) {
        payload.display_name = profileForm.display_name || undefined;
      }
      if (profileForm.email !== authUser.email) {
        payload.email = profileForm.email;
      }

      if (!payload.display_name && !payload.email) {
        setIsEditing(false);
        return;
      }

      const updated = await userService.updateUser(authUser.id, payload);
      setAuthUser(updated);
      toast.success(t("profile.update_success"));
      setIsEditing(false);
    } catch (error) {
      const normalized = ErrorHandler.normalize(error);
      const message = ErrorHandler.getUserMessage(normalized, t);
      toast.error(message);
    } finally {
      setIsSavingProfile(false);
    }
  };

  const handleUpdatePassword = async () => {
    if (!authUser) return;

    if (!newPassword || !confirmPassword) {
      toast.error(t("profile.password_required"));
      return;
    }

    if (newPassword !== confirmPassword) {
      toast.error(t("profile.password_mismatch"));
      return;
    }

    setIsUpdatingPassword(true);
    try {
      await userService.updateUser(authUser.id, {
        password: newPassword,
      });
      toast.success(t("profile.password_update_success"));
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error) {
      const normalized = ErrorHandler.normalize(error);
      const message = ErrorHandler.getUserMessage(normalized, t);
      toast.error(message);
    } finally {
      setIsUpdatingPassword(false);
    }
  };

  if (isAuthLoading) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <p className="text-muted-foreground">
          {t("common.loading") || "Loading..."}
        </p>
      </div>
    );
  }

  if (!authUser) {
    return (
      <div className="max-w-4xl mx-auto p-6 space-y-4">
        <h1 className="text-3xl font-bold mb-2">{t("nav.my_profile")}</h1>
        <p className="text-muted-foreground">{t("errors.unauthorized")}</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold mb-2">{t("nav.my_profile")}</h1>
        <p className="text-muted-foreground">{t("profile.subtitle")}</p>
      </div>

      {/* Profile Information */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t("profile.info_title")}</CardTitle>
              <CardDescription>{t("profile.info_description")}</CardDescription>
            </div>
            <Button
              variant={isEditing ? "outline" : "default"}
              onClick={() => setIsEditing((prev) => !prev)}
              disabled={isSavingProfile}
            >
              {isEditing ? t("common.cancel") : t("profile.edit_button")}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center space-x-4">
            <div className="h-20 w-20 rounded-full bg-muted flex items-center justify-center overflow-hidden">
              {authUser.avatar ? (
                // 使用原生 img 避免对 Next.js Image 做额外域名配置
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={authUser.avatar}
                  alt={authUser.display_name || authUser.email}
                  className="h-full w-full object-cover"
                />
              ) : (
                <User className="w-10 h-10 text-foreground" />
              )}
            </div>
            {isEditing && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleAvatarButtonClick}
                  disabled={isUploadingAvatar}
                >
                  {t("profile.change_avatar")}
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleAvatarFileChange}
                />
              </>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium flex items-center">
                <User className="w-4 h-4 mr-2 text-muted-foreground" />
                {t("profile.full_name")}
              </label>
              <Input
                name="display_name"
                value={profileForm.display_name}
                disabled={!isEditing}
                onChange={handleProfileInputChange}
                placeholder={authUser.email}
                className={!isEditing ? "bg-muted" : ""}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium flex items-center">
                <Mail className="w-4 h-4 mr-2 text-muted-foreground" />
                {t("profile.email")}
              </label>
              <Input
                name="email"
                type="email"
                value={profileForm.email}
                disabled={!isEditing}
                onChange={handleProfileInputChange}
                className={!isEditing ? "bg-muted" : ""}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">
                {t("profile.role_label")}
              </label>
              <Input value={profileRolesLabel} disabled className="bg-muted" />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">
                {t("profile.account_created")}
              </label>
              <Input
                value={formattedCreatedAt || "-"}
                disabled
                className="bg-muted"
              />
            </div>
          </div>

          {isEditing && (
            <div className="flex justify-end space-x-2 pt-4">
              <Button
                variant="outline"
                onClick={() => {
                  setIsEditing(false);
                  setProfileForm({
                    display_name: authUser.display_name ?? "",
                    email: authUser.email,
                  });
                }}
                disabled={isSavingProfile}
              >
                {t("common.cancel")}
              </Button>
              <Button onClick={handleSaveProfile} disabled={isSavingProfile}>
                {isSavingProfile ? t("common.saving") : t("common.save")}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Security */}
      <Card>
        <CardHeader>
          <CardTitle>{t("profile.security_title")}</CardTitle>
          <CardDescription>
            {t("profile.security_description")}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium flex items-center">
              <Lock className="w-4 h-4 mr-2 text-muted-foreground" />
              {t("profile.current_password")}
            </label>
            <Input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">
              {t("profile.new_password")}
            </label>
            <Input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">
              {t("profile.confirm_password")}
            </label>
            <Input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          <div className="flex justify-end pt-4">
            <Button
              onClick={handleUpdatePassword}
              disabled={isUpdatingPassword}
            >
              {isUpdatingPassword
                ? t("profile.updating_password")
                : t("profile.update_password")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Active Sessions */}
      <Card>
        <CardHeader>
          <CardTitle>{t("sessions.title")}</CardTitle>
          <CardDescription>{t("sessions.description")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading ? (
            <div className="text-center py-8 text-muted-foreground">
              {t("common.loading") || "Loading..."}
            </div>
          ) : sessions.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {t("sessions.no_sessions")}
            </div>
          ) : (
            <>
              {sessions.map((session) => (
                <SessionCard
                  key={session.session_id}
                  session={session}
                  onRevoke={handleRevoke}
                />
              ))}

              {otherSessionsCount > 0 && (
                <div className="pt-4 border-t">
                  <Button
                    variant="outline"
                    className="w-full text-destructive hover:text-destructive hover:bg-destructive/10"
                    onClick={() => setShowRevokeAllDialog(true)}
                  >
                    {t("sessions.revoke_all_other_sessions")} (
                    {otherSessionsCount})
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Preferences */}
      <Card>
        <CardHeader>
          <CardTitle>{t("profile.preferences_title")}</CardTitle>
          <CardDescription>
            {t("profile.preferences_description")}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Bell className="w-5 h-5 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">
                  {t("profile.email_notifications_title")}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("profile.email_notifications_description")}
                </p>
              </div>
            </div>
            <Button variant="outline" size="sm" disabled>
              {t("profile.configure_button")}
            </Button>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Globe className="w-5 h-5 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">
                  {t("profile.language_region_title")}
                </p>
                <p className="text-xs text-muted-foreground">{languageLabel}</p>
              </div>
            </div>
            <Button variant="outline" size="sm" disabled>
              {t("profile.change_language_button")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Danger Zone */}
      <Card className="border-destructive/50">
        <CardHeader>
          <CardTitle className="text-destructive">
            {t("profile.danger_zone_title")}
          </CardTitle>
          <CardDescription>
            {t("profile.danger_zone_description")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">
                {t("profile.delete_account_title")}
              </p>
              <p className="text-xs text-muted-foreground">
                {t("profile.delete_account_description")}
              </p>
            </div>
            <Button variant="destructive" size="sm" disabled>
              {t("profile.delete_account_button")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Dialogs */}
      <RevokeSessionDialog
        open={showRevokeDialog}
        onOpenChange={setShowRevokeDialog}
        session={selectedSession}
        onConfirm={handleConfirmRevoke}
        isRevoking={isRevoking}
      />

      <RevokeAllSessionsDialog
        open={showRevokeAllDialog}
        onOpenChange={setShowRevokeAllDialog}
        sessionCount={otherSessionsCount}
        onConfirm={handleRevokeAll}
        isRevoking={isRevoking}
      />
    </div>
  );
}
