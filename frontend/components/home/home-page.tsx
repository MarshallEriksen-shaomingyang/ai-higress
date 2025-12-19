"use client";

import Link from "next/link";
import { useMemo } from "react";
import { toast } from "sonner";
import { ArrowRight, Zap, Shield, BarChart3, Network, Cpu, Key, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AdaptiveCard, CardContent } from "@/components/cards/adaptive-card";
import { useI18n } from "@/lib/i18n-context";
import { useGatewayConfig } from "@/lib/swr";
import { useAuthStore } from "@/lib/stores/auth-store";
import { DASHBOARD_PATH, DOCS_URL, GITHUB_URL } from "./home-links";
import { TypewriterSuffixes } from "./typewriter-suffixes";

export function HomePage() {
  const { t } = useI18n();
  const { isAuthenticated } = useAuthStore();
  const { config, loading: configLoading } = useGatewayConfig(isAuthenticated);

  const envBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const resolvedBaseUrl = config?.api_base_url?.trim() || envBaseUrl;
  const displayBaseUrl = configLoading && !config ? "…" : resolvedBaseUrl;

  const features = useMemo(
    () => [
      {
        icon: Network,
        title: t("home.feature.smart_routing.title"),
        description: t("home.feature.smart_routing.description"),
      },
      {
        icon: Cpu,
        title: t("home.feature.multi_model.title"),
        description: t("home.feature.multi_model.description"),
      },
      {
        icon: Zap,
        title: t("home.feature.high_performance.title"),
        description: t("home.feature.high_performance.description"),
      },
      {
        icon: Shield,
        title: t("home.feature.secure_reliable.title"),
        description: t("home.feature.secure_reliable.description"),
      },
      {
        icon: BarChart3,
        title: t("home.feature.real_time_monitoring.title"),
        description: t("home.feature.real_time_monitoring.description"),
      },
      {
        icon: Key,
        title: t("home.feature.unified_interface.title"),
        description: t("home.feature.unified_interface.description"),
      },
    ],
    [t],
  );

  const apiSuffixes = useMemo(
    () => [
      {
        path: "/v1/chat/completions",
        description: t("home.api_card.suffix.chat"),
      },
      {
        path: "/v1/responses",
        description: t("home.api_card.suffix.responses"),
      },
      {
        path: "/models",
        description: t("home.api_card.suffix.models"),
      },
      {
        path: "/v1/messages",
        description: t("home.api_card.suffix.messages"),
      },
    ],
    [t],
  );

  const handleCopyBaseUrl = async () => {
    try {
      if (navigator?.clipboard) {
        await navigator.clipboard.writeText(resolvedBaseUrl);
      } else {
        const textArea = document.createElement("textarea");
        textArea.value = resolvedBaseUrl;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand("copy");
        document.body.removeChild(textArea);
      }
      toast.success(t("home.api_card.copy_success"));
    } catch (error) {
      toast.error(t("home.api_card.copy_failed"));
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Hero Section */}
      <section className="container mx-auto px-6 pt-20 pb-16 max-w-6xl">
        <div className="text-center space-y-6">
          <h1 className="text-5xl md:text-6xl font-bold tracking-tight">
            {t("app.title")}
          </h1>
          <p className="text-xl md:text-2xl text-muted-foreground max-w-3xl mx-auto">
            {t("home.tagline")}
          </p>
          <p className="text-base md:text-lg text-muted-foreground max-w-2xl mx-auto">
            {t("home.description")}
          </p>
          <div className="flex gap-4 justify-center pt-4">
            <Link href={DASHBOARD_PATH}>
              <Button size="lg" className="gap-2">
                {t("home.btn_enter_console")}
                <ArrowRight className="w-4 h-4" />
              </Button>
            </Link>
            <Link href="/login">
              <Button variant="outline" size="lg">
                {t("home.btn_get_started")}
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* API Access */}
      <section className="container mx-auto px-6 pb-12 max-w-5xl">
        <AdaptiveCard className="border bg-muted/30">
          <CardContent className="p-6 space-y-6">
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground uppercase tracking-wide">
                {t("home.api_card.title")}
              </p>
              <h2 className="text-2xl font-semibold">{t("home.api_card.subtitle")}</h2>
              <p className="text-sm text-muted-foreground">
                {t("home.api_card.description")}
              </p>
            </div>
            <div className="grid gap-6 lg:grid-cols-2">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium">{t("home.api_card.base_label")}</p>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="gap-2"
                    onClick={handleCopyBaseUrl}
                    aria-label={t("home.api_card.copy")}
                  >
                    <Copy className="h-4 w-4" />
                    {t("home.api_card.copy")}
                  </Button>
                </div>
                <code className="block rounded border bg-background px-4 py-3 font-mono text-sm break-all">
                  {displayBaseUrl}
                </code>
              </div>
              <div className="space-y-3">
                <p className="text-sm font-medium">{t("home.api_card.suffix_label")}</p>
                <div className="flex flex-wrap items-center gap-2">
                  <TypewriterSuffixes suffixes={apiSuffixes} />
                </div>
              </div>
            </div>
          </CardContent>
        </AdaptiveCard>
      </section>

      {/* Features Grid */}
      <section className="container mx-auto px-6 py-16 max-w-6xl">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold mb-4">{t("home.features_title")}</h2>
          <p className="text-muted-foreground">
            {t("home.features_subtitle")}
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, index) => (
            <AdaptiveCard key={index} className="border hover:shadow-lg transition-shadow">
              <CardContent className="pt-6">
                <div className="flex flex-col items-start space-y-3">
                  <div className="p-2 bg-muted rounded">
                    <feature.icon className="w-6 h-6" />
                  </div>
                  <h3 className="text-lg font-semibold">{feature.title}</h3>
                  <p className="text-sm text-muted-foreground">
                    {feature.description}
                  </p>
                </div>
              </CardContent>
            </AdaptiveCard>
          ))}
        </div>
      </section>

      {/* Use Cases */}
      <section className="container mx-auto px-6 py-16 max-w-6xl">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold mb-4">{t("home.use_cases_title")}</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <AdaptiveCard>
            <CardContent className="pt-6">
              <h3 className="text-xl font-semibold mb-3">{t("home.use_case.enterprise.title")}</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>{t("home.use_case.enterprise.item1")}</li>
                <li>{t("home.use_case.enterprise.item2")}</li>
                <li>{t("home.use_case.enterprise.item3")}</li>
                <li>{t("home.use_case.enterprise.item4")}</li>
              </ul>
            </CardContent>
          </AdaptiveCard>
          <AdaptiveCard>
            <CardContent className="pt-6">
              <h3 className="text-xl font-semibold mb-3">{t("home.use_case.developer.title")}</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>{t("home.use_case.developer.item1")}</li>
                <li>{t("home.use_case.developer.item2")}</li>
                <li>{t("home.use_case.developer.item3")}</li>
                <li>{t("home.use_case.developer.item4")}</li>
              </ul>
            </CardContent>
          </AdaptiveCard>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t mt-16">
        <div className="container mx-auto px-6 py-8 max-w-6xl">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-sm text-muted-foreground">
              {t("home.footer_copyright")}
            </p>
            <div className="flex gap-6 text-sm text-muted-foreground">
              <Link href={DASHBOARD_PATH} className="hover:text-foreground transition-colors">
                {t("home.footer_console")}
              </Link>
              <Link
                href={DOCS_URL}
                className="hover:text-foreground transition-colors"
                target="_blank"
                rel="noreferrer"
              >
                {t("home.footer_docs")}
              </Link>
              <Link
                href={GITHUB_URL}
                className="hover:text-foreground transition-colors"
                target="_blank"
                rel="noreferrer"
              >
                {t("home.footer_github")}
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
