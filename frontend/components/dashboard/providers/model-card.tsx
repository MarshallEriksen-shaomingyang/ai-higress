"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import {
  DollarSign,
  Calendar,
  User,
  Tag,
  ArrowDownToLine,
  ArrowUpFromLine,
  Sparkles,
  Settings2
} from "lucide-react";
import type { Model } from "@/http/provider";
import { providerService } from "@/http/provider";
import { useI18n } from "@/lib/i18n-context";
import { useErrorDisplay } from "@/lib/errors";
import { toast } from "sonner";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { CAPABILITY_META, normalize_capabilities } from "./model-capabilities";

interface ModelCardProps {
  providerId: string;
  model: Model;
  canEdit: boolean;
  onOpenSettings: () => void;
  onRefresh: () => Promise<void>;
}

/**
 * 计费标签组件 - 现代化设计
 */
function PricingBadge({ model }: { model: Model }) {
  const { t } = useI18n();
  const pricing = (model.pricing || {}) as Record<string, number>;
  const hasInput = typeof pricing.input === "number";
  const hasOutput = typeof pricing.output === "number";

  if (!hasInput && !hasOutput) {
    return (
      <Badge variant="outline" className="text-xs shrink-0 font-normal gap-1">
        <DollarSign className="h-3 w-3" />
        {t("providers.model_pricing_not_configured")}
      </Badge>
    );
  }

  return (
    <div className="flex items-center gap-2 shrink-0">
      {hasInput && (
        <Badge variant="secondary" className="text-xs font-mono font-normal gap-1 bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-800">
          <ArrowDownToLine className="h-3 w-3" />
          {pricing.input}
        </Badge>
      )}
      {hasOutput && (
        <Badge variant="secondary" className="text-xs font-mono font-normal gap-1 bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-900/20 dark:text-purple-300 dark:border-purple-800">
          <ArrowUpFromLine className="h-3 w-3" />
          {pricing.output}
        </Badge>
      )}
    </div>
  );
}

/**
 * 格式化日期
 */
function formatDate(timestamp?: number): string {
  if (!timestamp) return "-";
  return new Date(timestamp * 1000).toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

/**
 * 模型卡片组件 - 现代化设计
 *
 * 设计特点：
 * - 使用 Card 组件提供更好的结构
 * - 添加图标增强视觉识别
 * - 渐变背景和悬停效果
 * - 更清晰的信息层次
 * - 流畅的动画过渡
 */
export function ModelCard({
  providerId,
  model,
  canEdit,
  onOpenSettings,
  onRefresh,
}: ModelCardProps) {
  const { t } = useI18n();
  const { showError } = useErrorDisplay();
  const [toggling, setToggling] = useState(false);
  const disabled = Boolean(model.disabled);
  const [localDisabled, setLocalDisabled] = useState(disabled);
  const capabilities = useMemo(() => normalize_capabilities(model.capabilities), [model.capabilities]);

  useEffect(() => {
    setLocalDisabled(Boolean(model.disabled));
  }, [model.disabled, model.model_id]);

  const toggleDisabled = async (nextDisabled: boolean) => {
    if (toggling) return;
    setToggling(true);
    const prev = localDisabled;
    setLocalDisabled(nextDisabled);
    try {
      await providerService.updateProviderModelDisabled(
        providerId,
        model.model_id,
        { disabled: nextDisabled }
      );
      toast.success(
        nextDisabled ? t("providers.model_disable_success") : t("providers.model_enable_success")
      );
      await onRefresh();
    } catch (err: any) {
      setLocalDisabled(prev);
      showError(err, {
        context: nextDisabled ? t("providers.model_disable_error") : t("providers.model_enable_error"),
      });
    } finally {
      setToggling(false);
    }
  };

  return (
    <Card
      className="group relative overflow-hidden transition-all duration-300
                 hover:shadow-lg hover:shadow-primary/5 hover:-translate-y-1
                 hover:border-primary/20 bg-gradient-to-br from-card to-card/50"
    >
      {/* 装饰性渐变条 */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 via-purple-500 to-blue-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
      
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2 flex-1 min-w-0">
            <div className="mt-0.5 p-1.5 rounded-lg bg-primary/5 text-primary shrink-0 group-hover:bg-primary/10 transition-colors">
              <Sparkles className="h-4 w-4" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-base leading-tight break-words mb-1.5">
                {model.display_name || model.model_id}
              </h3>
              <code className="text-xs text-muted-foreground font-mono block break-all bg-muted/50 px-2 py-1 rounded">
                {model.model_id}
              </code>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2 shrink-0">
            <PricingBadge model={model} />
            {capabilities.length > 0 ? (
              <TooltipProvider>
                <div className="flex items-center gap-1">
                  {capabilities.map((cap) => {
                    const meta = CAPABILITY_META[cap];
                    const Icon = meta.icon;
                    return (
                      <Tooltip key={cap}>
                        <TooltipTrigger asChild>
                          <div className="rounded-md border bg-muted/30 p-1 text-muted-foreground">
                            <Icon className="h-3.5 w-3.5" />
                          </div>
                        </TooltipTrigger>
                        <TooltipContent>{t(meta.labelKey)}</TooltipContent>
                      </Tooltip>
                    );
                  })}
                </div>
              </TooltipProvider>
            ) : null}
            {localDisabled && (
              <Badge variant="destructive" className="text-xs font-normal">
                {t("providers.model_disabled_badge")}
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>


      <CardContent className="pt-4 pb-3">
        <div className="space-y-2.5">
          {/* 所有者信息 */}
          <div className="flex items-start gap-2 text-sm">
            <User className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <span className="text-muted-foreground text-xs">{t("providers.model_owned_by")}</span>
              <p className="font-medium truncate">{model.metadata?.owned_by || "-"}</p>
            </div>
          </div>

          {/* 创建时间 */}
          <div className="flex items-start gap-2 text-sm">
            <Calendar className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <span className="text-muted-foreground text-xs">{t("providers.model_created")}</span>
              <p className="font-medium">{formatDate(model.metadata?.created)}</p>
            </div>
          </div>

          {/* 别名信息 */}
          {model.alias && (
            <div className="flex items-start gap-2 text-sm">
              <Tag className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <span className="text-muted-foreground text-xs">{t("providers.model_alias")}</span>
                <p className="font-mono text-xs break-all">
                  <span className="text-primary font-medium">{model.alias}</span>
                  <span className="text-muted-foreground mx-1">→</span>
                  <span>{model.model_id}</span>
                </p>
              </div>
            </div>
          )}

          {canEdit && (
            <div className="flex items-center justify-between rounded-md border bg-muted/30 px-3 py-2">
              <span className="text-xs text-muted-foreground">
                {t("providers.model_disable_toggle_label")}
              </span>
              <Switch
                checked={localDisabled}
                onCheckedChange={(checked) => void toggleDisabled(Boolean(checked))}
                disabled={toggling}
              />
            </div>
          )}
        </div>
      </CardContent>


      <CardFooter className="pt-3 pb-3 gap-2 opacity-0 group-hover:opacity-100 transition-all duration-300">
        <Button
          variant="outline"
          size="sm"
          onClick={onOpenSettings}
          className="flex-1 h-9 text-xs gap-1.5 hover:bg-primary/5 hover:text-primary hover:border-primary/20"
        >
          <Settings2 className="h-3.5 w-3.5" />
          {t("providers.model_settings_button")}
        </Button>
      </CardFooter>
    </Card>
  );
}
