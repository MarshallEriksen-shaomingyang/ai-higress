"use client";

import { useEffect, useMemo, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Loader2, Info } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import { toast } from "sonner";
import type { EvalConfig, UpdateEvalConfigRequest, ProviderScope } from "@/lib/api-types";

interface EvalConfigFormData {
  enabled: boolean;
  max_challengers: number;
  provider_scopes: ProviderScope[];
  candidate_logical_models: string[];
  cooldown_seconds: number;
  budget_per_eval_credits?: number;
  rubric?: string;
  project_ai_enabled: boolean;
  project_ai_provider_model?: string;
}

interface EvalConfigFormProps {
  config: EvalConfig | null;
  onSubmit: (data: UpdateEvalConfigRequest) => Promise<void>;
  isSubmitting?: boolean;
  availableModels?: string[];
}

const PROVIDER_SCOPES: ProviderScope[] = ["private", "shared", "public"];

export function EvalConfigForm({
  config,
  onSubmit,
  isSubmitting = false,
  availableModels = ["auto", "gpt-4", "gpt-4-turbo", "claude-3-opus", "claude-3-sonnet", "gpt-3.5-turbo"],
}: EvalConfigFormProps) {
  const { t } = useI18n();
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set());

  // 创建表单验证 schema
  const evalConfigSchema = useMemo(
    () =>
      z.object({
        enabled: z.boolean(),
        max_challengers: z
          .number()
          .int()
          .min(1, t("chat.eval_config.validation_max_challengers"))
          .max(10, t("chat.eval_config.validation_max_challengers")),
        provider_scopes: z.array(z.enum(["private", "shared", "public"])).min(1),
        candidate_logical_models: z
          .array(z.string())
          .min(1, t("chat.eval_config.validation_candidate_models")),
        cooldown_seconds: z
          .number()
          .int()
          .min(0, t("chat.eval_config.validation_cooldown")),
        budget_per_eval_credits: z.number().optional(),
        rubric: z.string().optional(),
        project_ai_enabled: z.boolean(),
        project_ai_provider_model: z.string().optional(),
      })
      .refine(
        (data) => {
          // 如果启用 Project AI，必须选择模型
          if (data.project_ai_enabled && !data.project_ai_provider_model) {
            return false;
          }
          return true;
        },
        {
          message: t("chat.eval_config.validation_project_ai"),
          path: ["project_ai_provider_model"],
        }
      ),
    [t]
  );

  const {
    register,
    handleSubmit,
    formState: { errors },
    control,
    watch,
    setValue,
    reset,
  } = useForm<EvalConfigFormData>({
    resolver: zodResolver(evalConfigSchema),
    defaultValues: {
      enabled: true,
      max_challengers: 2,
      provider_scopes: ["private", "shared", "public"],
      candidate_logical_models: [],
      cooldown_seconds: 60,
      budget_per_eval_credits: undefined,
      rubric: "",
      project_ai_enabled: false,
      project_ai_provider_model: undefined,
    },
  });

  const projectAiEnabled = watch("project_ai_enabled");
  const candidateModels = watch("candidate_logical_models") ?? [];

  // 当配置加载时，更新表单
  useEffect(() => {
    if (config) {
      reset({
        enabled: config.enabled,
        max_challengers: config.max_challengers,
        provider_scopes: config.provider_scopes,
        candidate_logical_models: config.candidate_logical_models ?? [],
        cooldown_seconds: config.cooldown_seconds,
        budget_per_eval_credits: config.budget_per_eval_credits,
        rubric: config.rubric || "",
        project_ai_enabled: config.project_ai_enabled,
        project_ai_provider_model: config.project_ai_provider_model,
      });
      setSelectedModels(new Set(config.candidate_logical_models ?? []));
    }
  }, [config, reset]);

  const handleFormSubmit = async (data: EvalConfigFormData) => {
    try {
      const updateData: UpdateEvalConfigRequest = {
        enabled: data.enabled,
        max_challengers: data.max_challengers,
        provider_scopes: data.provider_scopes,
        candidate_logical_models: data.candidate_logical_models,
        cooldown_seconds: data.cooldown_seconds,
        budget_per_eval_credits: data.budget_per_eval_credits || undefined,
        rubric: data.rubric || undefined,
        project_ai_enabled: data.project_ai_enabled,
        project_ai_provider_model: data.project_ai_provider_model || undefined,
      };
      await onSubmit(updateData);
      toast.success(t("chat.eval_config.saved"));
    } catch (error) {
      console.error("Failed to save eval config:", error);
      toast.error(t("chat.errors.invalid_config"));
    }
  };

  const handleModelToggle = (model: string, checked: boolean) => {
    const newSelected = new Set(selectedModels);
    if (checked) {
      newSelected.add(model);
    } else {
      newSelected.delete(model);
    }
    setSelectedModels(newSelected);
    setValue("candidate_logical_models", Array.from(newSelected));
  };

  const handleProviderScopeToggle = (scope: ProviderScope, checked: boolean) => {
    const currentScopes = watch("provider_scopes");
    if (checked) {
      setValue("provider_scopes", [...currentScopes, scope]);
    } else {
      setValue(
        "provider_scopes",
        currentScopes.filter((s) => s !== scope)
      );
    }
  };

  if (!config) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          <span className="ml-2 text-muted-foreground">
            {t("chat.eval_config.loading")}
          </span>
        </CardContent>
      </Card>
    );
  }

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-6">
      {/* 基本设置 */}
      <Card>
        <CardHeader>
          <CardTitle>{t("chat.eval_config.title")}</CardTitle>
          <CardDescription>{t("chat.eval_config.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* 启用评测 */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="enabled">{t("chat.eval_config.enabled")}</Label>
              <p className="text-sm text-muted-foreground">
                {t("chat.eval_config.enabled_description")}
              </p>
            </div>
            <Controller
              name="enabled"
              control={control}
              render={({ field }) => (
                <Switch
                  id="enabled"
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              )}
            />
          </div>

          {/* 最大挑战者数 */}
          <div className="space-y-2">
            <Label htmlFor="max_challengers">
              {t("chat.eval_config.max_challengers")}
              <span className="text-destructive ml-1">*</span>
            </Label>
            <p className="text-sm text-muted-foreground">
              {t("chat.eval_config.max_challengers_description")}
            </p>
            <Input
              id="max_challengers"
              type="number"
              min={1}
              max={10}
              {...register("max_challengers", { valueAsNumber: true })}
              aria-invalid={!!errors.max_challengers}
            />
            {errors.max_challengers && (
              <p className="text-sm text-destructive">
                {errors.max_challengers.message}
              </p>
            )}
          </div>

          {/* 冷却时间 */}
          <div className="space-y-2">
            <Label htmlFor="cooldown_seconds">
              {t("chat.eval_config.cooldown_seconds")}
              <span className="text-destructive ml-1">*</span>
            </Label>
            <p className="text-sm text-muted-foreground">
              {t("chat.eval_config.cooldown_seconds_description")}
            </p>
            <Input
              id="cooldown_seconds"
              type="number"
              min={0}
              {...register("cooldown_seconds", { valueAsNumber: true })}
              aria-invalid={!!errors.cooldown_seconds}
            />
            {errors.cooldown_seconds && (
              <p className="text-sm text-destructive">
                {errors.cooldown_seconds.message}
              </p>
            )}
          </div>

          {/* 每次评测预算 */}
          <div className="space-y-2">
            <Label htmlFor="budget_per_eval_credits">
              {t("chat.eval_config.budget_per_eval")}
            </Label>
            <p className="text-sm text-muted-foreground">
              {t("chat.eval_config.budget_per_eval_description")}
            </p>
            <Input
              id="budget_per_eval_credits"
              type="number"
              min={0}
              step={0.01}
              placeholder="Optional"
              {...register("budget_per_eval_credits", { valueAsNumber: true })}
            />
          </div>
        </CardContent>
      </Card>

      {/* 候选模型 */}
      <Card>
        <CardHeader>
          <CardTitle>{t("chat.eval_config.candidate_models")}</CardTitle>
          <CardDescription>
            {t("chat.eval_config.candidate_models_description")}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ScrollArea className="h-[40vh] md:h-[50vh] pr-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {availableModels.map((model) => (
                <div key={model} className="flex items-start space-x-2">
                  <Checkbox
                    id={`model-${model}`}
                    checked={selectedModels.has(model)}
                    onCheckedChange={(checked) =>
                      handleModelToggle(model, checked as boolean)
                    }
                    className="mt-0.5"
                  />
                  <Label
                    htmlFor={`model-${model}`}
                    className="text-sm font-normal cursor-pointer break-all"
                  >
                    {model}
                  </Label>
                </div>
              ))}
            </div>
          </ScrollArea>
          {errors.candidate_logical_models && (
            <p className="text-sm text-destructive">
              {errors.candidate_logical_models.message}
            </p>
          )}
          {candidateModels.length === 0 && (
            <div className="flex items-start space-x-2 p-3 bg-muted rounded-md">
              <Info className="w-4 h-4 mt-0.5 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {t("chat.eval_config.validation_candidate_models")}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 提供商范围 */}
      <Card>
        <CardHeader>
          <CardTitle>{t("chat.eval_config.provider_scopes")}</CardTitle>
          <CardDescription>
            {t("chat.eval_config.provider_scopes_description")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Controller
            name="provider_scopes"
            control={control}
            render={({ field }) => (
              <div className="space-y-3">
                {PROVIDER_SCOPES.map((scope) => (
                  <div key={scope} className="flex items-center space-x-2">
                    <Checkbox
                      id={`scope-${scope}`}
                      checked={field.value?.includes(scope) ?? false}
                      onCheckedChange={(checked) =>
                        handleProviderScopeToggle(scope, checked as boolean)
                      }
                    />
                    <Label
                      htmlFor={`scope-${scope}`}
                      className="text-sm font-normal cursor-pointer"
                    >
                      {t(`chat.eval_config.scope_${scope}`)}
                    </Label>
                  </div>
                ))}
              </div>
            )}
          />
        </CardContent>
      </Card>

      {/* Project AI 设置 */}
      <Card>
        <CardHeader>
          <CardTitle>{t("chat.eval_config.project_ai_enabled")}</CardTitle>
          <CardDescription>
            {t("chat.eval_config.project_ai_enabled_description")}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* 启用 Project AI */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="project_ai_enabled">
                {t("chat.eval_config.project_ai_enabled")}
              </Label>
              <p className="text-sm text-muted-foreground">
                {t("chat.eval_config.project_ai_enabled_description")}
              </p>
            </div>
            <Controller
              name="project_ai_enabled"
              control={control}
              render={({ field }) => (
                <Switch
                  id="project_ai_enabled"
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              )}
            />
          </div>

          {/* Project AI 模型 */}
          {projectAiEnabled && (
            <div className="space-y-2">
              <Label htmlFor="project_ai_provider_model">
                {t("chat.eval_config.project_ai_model")}
                <span className="text-destructive ml-1">*</span>
              </Label>
              <p className="text-sm text-muted-foreground">
                {t("chat.eval_config.project_ai_model_description")}
              </p>
              <Controller
                name="project_ai_provider_model"
                control={control}
                render={({ field }) => (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {availableModels
                      .filter((m) => m !== "auto")
                      .map((model) => (
                        <div key={model} className="flex items-center space-x-2">
                          <input
                            type="radio"
                            id={`ai-model-${model}`}
                            value={model}
                            checked={field.value === model}
                            onChange={(e) => field.onChange(e.target.value)}
                            className="w-4 h-4"
                          />
                          <Label
                            htmlFor={`ai-model-${model}`}
                            className="text-sm font-normal cursor-pointer"
                          >
                            {model}
                          </Label>
                        </div>
                      ))}
                  </div>
                )}
              />
              {errors.project_ai_provider_model && (
                <p className="text-sm text-destructive">
                  {errors.project_ai_provider_model.message}
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 评测标准 */}
      <Card>
        <CardHeader>
          <CardTitle>{t("chat.eval_config.rubric")}</CardTitle>
          <CardDescription>
            {t("chat.eval_config.rubric_description")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Textarea
            id="rubric"
            placeholder={t("chat.eval_config.rubric_placeholder")}
            rows={6}
            {...register("rubric")}
          />
        </CardContent>
      </Card>

      {/* 提交按钮 */}
      <div className="flex justify-end">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
          {isSubmitting
            ? t("chat.eval_config.saving")
            : t("chat.eval_config.save")}
        </Button>
      </div>
    </form>
  );
}
