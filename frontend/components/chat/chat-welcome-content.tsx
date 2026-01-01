"use client";

import { Sparkles, MessageSquare, Image as ImageIcon, Zap } from "lucide-react";

import { useI18n } from "@/lib/i18n-context";
import { cn } from "@/lib/utils";

export function ChatWelcomeContent({ className }: { className?: string } = {}) {
  const { t } = useI18n();

  const featureCards = [
    {
      icon: MessageSquare,
      title: t("chat.welcome.feature_chat_title"),
      description: t("chat.welcome.feature_chat_desc"),
    },
    {
      icon: ImageIcon,
      title: t("chat.welcome.feature_image_title"),
      description: t("chat.welcome.feature_image_desc"),
    },
    {
      icon: Zap,
      title: t("chat.welcome.feature_fast_title"),
      description: t("chat.welcome.feature_fast_desc"),
    },
  ];

  return (
    <div className={cn("w-full max-w-4xl mx-auto px-6 py-12 space-y-12", className)}>
      <div className="text-center space-y-6">
        <div className="flex justify-center">
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-3xl blur-2xl" />
            <div className="relative rounded-3xl bg-gradient-to-br from-blue-500 to-purple-600 p-6">
              <Sparkles className="h-16 w-16 text-white" />
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <h1 className="text-4xl font-light tracking-tight">
            {t("chat.welcome.main_title")}
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            {t("chat.welcome.main_description")}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {featureCards.map((feature) => {
          const Icon = feature.icon;
          return (
            <div
              key={feature.title}
              className="group relative rounded-2xl border border-border/50 bg-card/50 p-6 transition-all hover:border-border hover:bg-card/80 hover:shadow-lg"
            >
              <div className="space-y-3">
                <div className="inline-flex rounded-xl bg-primary/10 p-3">
                  <Icon className="h-6 w-6 text-primary" />
                </div>
                <h3 className="text-lg font-medium">{feature.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {feature.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>

    </div>
  );
}

