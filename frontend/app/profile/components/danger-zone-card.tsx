"use client";

import {
  AdaptiveCard,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/cards/adaptive-card";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n-context";

export function DangerZoneCard() {
  const { t } = useI18n();

  return (
    <AdaptiveCard showDecor={false} className="border-destructive/50">
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
    </AdaptiveCard>
  );
}
