"use client";

import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Loader2, Shield } from "lucide-react";

import { useAuth } from "@/components/providers/auth-provider";
import { useI18n } from "@/lib/i18n-context";
import { useApiKeys } from "@/lib/swr/use-api-keys";
import { useLogicalModels } from "@/lib/swr/use-logical-models";
import { useEvalConfig, useUpdateEvalConfig } from "@/lib/swr/use-eval-config";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { UpdateEvalConfigRequest } from "@/lib/api-types";

const EvalConfigForm = dynamic(
  () =>
    import("@/components/dashboard/eval-config-form").then((mod) => ({
      default: mod.EvalConfigForm,
    })),
  {
    loading: () => (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    ),
    ssr: false,
  }
);

export function EvalConfigPageClient() {
  const { t } = useI18n();
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const { apiKeys, loading: isLoadingApiKeys } = useApiKeys();
  const { models, loading: isLoadingModels } = useLogicalModels();
  const [projectId, setProjectId] = useState<string>("");

  const isSuperuser = user?.is_superuser === true;
  const canAccess = !isLoading && !!user && isSuperuser;

  useEffect(() => {
    if (!isLoading && (!user || !isSuperuser)) {
      router.push("/dashboard");
    }
  }, [user, isLoading, isSuperuser, router]);

  useEffect(() => {
    if (projectId) return;
    if (!canAccess) return;
    if (isLoadingApiKeys) return;
    const first = apiKeys?.[0];
    if (first?.id) setProjectId(first.id);
  }, [apiKeys, canAccess, isLoadingApiKeys, projectId]);

  const { config, isLoading: isLoadingConfig } = useEvalConfig(
    canAccess && projectId ? projectId : null
  );
  const updateEvalConfig = useUpdateEvalConfig();

  const availableModels = useMemo(() => {
    const modelSet = new Set<string>();
    modelSet.add("auto");
    for (const model of models) {
      if (!model.enabled) continue;
      if (!model.capabilities?.includes("chat")) continue;
      modelSet.add(model.logical_id);
    }
    for (const model of config?.candidate_logical_models ?? []) {
      modelSet.add(model);
    }
    return ["auto", ...Array.from(modelSet).filter((m) => m !== "auto").sort()];
  }, [config?.candidate_logical_models, models]);

  const handleSubmit = async (data: UpdateEvalConfigRequest) => {
    try {
      if (!projectId) throw new Error("project_id is required");
      if (!canAccess) throw new Error("forbidden");
      await updateEvalConfig(projectId, data);
      toast.success(t("chat.eval_config.saved"));
    } catch (error) {
      console.error("Failed to update eval config:", error);
      toast.error(t("chat.errors.invalid_config"));
      throw error;
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center space-y-2">
          <div className="text-muted-foreground">{t("chat.eval_config.loading")}</div>
        </div>
      </div>
    );
  }

  if (!canAccess) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center space-y-4 max-w-md px-4">
          <div className="flex justify-center">
            <div className="rounded-full bg-muted p-6">
              <Shield className="h-12 w-12 text-muted-foreground" />
            </div>
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-semibold tracking-tight">
              {t("chat.errors.action_contact_admin")}
            </h2>
            <p className="text-muted-foreground">{t("common.error_superuser_required")}</p>
          </div>
        </div>
      </div>
    );
  }

  if (isLoadingApiKeys || isLoadingModels || isLoadingConfig) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center space-y-2">
          <div className="text-muted-foreground">{t("chat.eval_config.loading")}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t("chat.eval_config.title")}</h1>
        <p className="text-muted-foreground mt-2">{t("chat.eval_config.subtitle")}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("chat.project.title")}</CardTitle>
          <CardDescription>{t("chat.project.not_selected")}</CardDescription>
        </CardHeader>
        <CardContent>
          {apiKeys.length === 0 ? (
            <div className="text-sm text-muted-foreground">{t("chat.project.empty")}</div>
          ) : (
            <div className="max-w-sm">
              <Select value={projectId} onValueChange={setProjectId}>
                <SelectTrigger>
                  <SelectValue placeholder={t("chat.project.select_placeholder")} />
                </SelectTrigger>
                <SelectContent>
                  {apiKeys.map((key) => (
                    <SelectItem key={key.id} value={key.id}>
                      {key.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("chat.eval_config.title")}</CardTitle>
          <CardDescription>{t("chat.eval_config.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          {projectId ? (
            <EvalConfigForm
              config={config || null}
              onSubmit={handleSubmit}
              availableModels={availableModels}
            />
          ) : (
            <div className="text-sm text-muted-foreground">{t("chat.project.not_selected")}</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
