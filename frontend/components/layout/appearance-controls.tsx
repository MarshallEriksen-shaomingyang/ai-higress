"use client";

import { useEffect, useState } from "react";
import { Languages, User } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

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
  const pathname = usePathname();
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
      size="icon"
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
      {isRail && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              asChild
              variant="ghost"
              size="icon"
              className={cn(
                "h-10 w-10 rounded-xl",
                pathname.startsWith("/profile") && "bg-accent text-accent-foreground"
              )}
            >
              <Link href="/profile" aria-label={t("nav.my_profile")}>
                <User className="h-5 w-5" />
              </Link>
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right" sideOffset={8}>
            {t("nav.my_profile")}
          </TooltipContent>
        </Tooltip>
      )}
    </div>
  );
}

