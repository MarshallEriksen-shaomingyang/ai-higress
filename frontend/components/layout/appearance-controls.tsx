"use client";

import { useEffect, useState } from "react";
import { Languages } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { useI18n } from "@/lib/i18n-context";
import { cn } from "@/lib/utils";

type Variant = "topnav" | "rail";

export function AppearanceControls({
  variant = "topnav",
  className,
}: {
  variant?: Variant;
  className?: string;
}) {
  const { language, setLanguage, t } = useI18n();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isRail = variant === "rail";
  const languageLabel =
    language === "en" ? t("common.language.zh_short") : t("common.language.en_short");

  const languageButton = (
    <Button
      variant="ghost"
      size={isRail ? "icon" : "icon"}
      onClick={() => setLanguage(language === "en" ? "zh" : "en")}
      aria-label={t("common.switch_language")}
      title={t("common.switch_language")}
      className={cn(isRail ? "h-10 w-10 rounded-xl" : "h-9 w-9", !mounted && "opacity-50")}
      disabled={!mounted}
    >
      {isRail ? <Languages className="h-5 w-5" /> : <span className="text-sm font-medium">{languageLabel}</span>}
    </Button>
  );

  return (
    <div className={cn(isRail ? "flex flex-col items-center gap-1.5" : "flex items-center gap-2", className)}>
      <ThemeSwitcher align={isRail ? "start" : "end"} />
      {isRail ? (
        <Tooltip>
          <TooltipTrigger asChild>{languageButton}</TooltipTrigger>
          <TooltipContent side="right" sideOffset={8}>
            {t("common.switch_language")}
          </TooltipContent>
        </Tooltip>
      ) : (
        languageButton
      )}
    </div>
  );
}

