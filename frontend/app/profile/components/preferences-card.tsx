"use client";

import {
  AdaptiveCard,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/cards/adaptive-card";
import { Button } from "@/components/ui/button";
import { Bell, Globe } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";

export function PreferencesCard() {
  const { t, language } = useI18n();

  const languageLabel =
    language === "zh"
      ? t("profile.language_chinese")
      : t("profile.language_english");

  return (
    <AdaptiveCard showDecor={false}>
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
    </AdaptiveCard>
  );
}
