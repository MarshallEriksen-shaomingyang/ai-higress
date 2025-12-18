"use client";

import { useEffect, useState } from "react";
import {
  AdaptiveCard,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/cards/adaptive-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { User, Mail } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import { toast } from "sonner";
import { useAuthStore } from "@/lib/stores/auth-store";
import { userService } from "@/http/user";
import { ErrorHandler } from "@/lib/errors";
import { AvatarUpload } from "./avatar-upload";

export function ProfileInfoCard() {
  const { t, language } = useI18n();
  const authUser = useAuthStore((state) => state.user);
  const setAuthUser = useAuthStore((state) => state.setUser);

  const [isEditing, setIsEditing] = useState(false);
  const [profileForm, setProfileForm] = useState({
    display_name: "",
    email: "",
  });
  const [isSavingProfile, setIsSavingProfile] = useState(false);

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

  if (!authUser) return null;

  const formattedCreatedAt =
    authUser.created_at &&
    new Intl.DateTimeFormat(language === "zh" ? "zh-CN" : "en-US", {
      year: "numeric",
      month: "long",
      day: "2-digit",
    }).format(new Date(authUser.created_at));

  const profileRolesLabel =
    authUser.role_codes && authUser.role_codes.length > 0
      ? authUser.role_codes.join(", ")
      : t("profile.role_no_roles");

  return (
    <AdaptiveCard showDecor={false}>
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
        <AvatarUpload isEditing={isEditing} />

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
    </AdaptiveCard>
  );
}
