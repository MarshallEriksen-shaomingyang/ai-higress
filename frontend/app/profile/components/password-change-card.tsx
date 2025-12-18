"use client";

import { useState } from "react";
import {
  AdaptiveCard,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/cards/adaptive-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Lock } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import { toast } from "sonner";
import { useAuthStore } from "@/lib/stores/auth-store";
import { userService } from "@/http/user";
import { ErrorHandler } from "@/lib/errors";

export function PasswordChangeCard() {
  const { t } = useI18n();
  const authUser = useAuthStore((state) => state.user);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isUpdatingPassword, setIsUpdatingPassword] = useState(false);

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

  if (!authUser) return null;

  return (
    <AdaptiveCard showDecor={false}>
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
    </AdaptiveCard>
  );
}
