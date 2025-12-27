"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useI18n } from "@/lib/i18n-context";
import { useErrorDisplay } from "@/lib/errors";
import { useAdminUserAutoTopup } from "@/lib/swr/use-credits";
import { toast } from "sonner";
import { Info, Loader2, ShieldOff } from "lucide-react";

// 动态加载 Tooltip 组件
const Tooltip = dynamic(() => import("@/components/ui/tooltip").then(mod => ({ default: mod.Tooltip })), { ssr: false });
const TooltipContent = dynamic(() => import("@/components/ui/tooltip").then(mod => ({ default: mod.TooltipContent })), { ssr: false });
const TooltipTrigger = dynamic(() => import("@/components/ui/tooltip").then(mod => ({ default: mod.TooltipTrigger })), { ssr: false });

interface AutoTopupDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  userId: string | null;
  userLabel?: string;
  onSuccess?: () => void;
}

export function AutoTopupDialog({
  open,
  onOpenChange,
  userId,
  userLabel,
  onSuccess,
}: AutoTopupDialogProps) {
  const { t } = useI18n();
  const { showError } = useErrorDisplay();
  const {
    config,
    loading,
    error,
    save,
    disable,
    refresh,
    saving,
    disabling,
    isSuperUser,
  } = useAdminUserAutoTopup(userId);

  const [threshold, setThreshold] = useState<string>("");
  const [target, setTarget] = useState<string>("");
  const [isActive, setIsActive] = useState<boolean>(true);
  const [formErrors, setFormErrors] = useState<{ threshold?: string; target?: string }>(
    {}
  );

  // 非超级管理员不渲染组件
  if (!isSuperUser) {
    return null;
  }

  useEffect(() => {
    if (config) {
      setThreshold(config.min_balance_threshold.toString());
      setTarget(config.target_balance.toString());
      setIsActive(config.is_active);
      setFormErrors({});
    } else if (!loading && open) {
      // 未配置时使用默认值
      setThreshold("");
      setTarget("");
      setIsActive(true);
      setFormErrors({});
    }
  }, [config, loading, open]);

  const resetForm = () => {
    if (config) {
      setThreshold(config.min_balance_threshold.toString());
      setTarget(config.target_balance.toString());
      setIsActive(config.is_active);
    } else {
      setThreshold("");
      setTarget("");
      setIsActive(true);
    }
    setFormErrors({});
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen && !saving && !disabling) {
      resetForm();
    }
    onOpenChange(newOpen);
  };

  const validate = (): boolean => {
    const errors: { threshold?: string; target?: string } = {};

    const thresholdNum = parseInt(threshold, 10);
    const targetNum = parseInt(target, 10);

    if (Number.isNaN(thresholdNum) || thresholdNum <= 0) {
      errors.threshold = t("credits.auto_topup_threshold_required");
    }
    if (Number.isNaN(targetNum) || targetNum <= 0) {
      errors.target = t("credits.auto_topup_target_required");
    } else if (!Number.isNaN(thresholdNum) && targetNum <= thresholdNum) {
      errors.target = t("credits.auto_topup_target_must_gt_threshold");
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate() || !userId) return;
    try {
      await save({
        min_balance_threshold: parseInt(threshold, 10),
        target_balance: parseInt(target, 10),
        is_active: isActive,
      });
      toast.success(t("credits.auto_topup_success"));
      onSuccess?.();
      handleOpenChange(false);
    } catch (err) {
      showError(err, { context: t("credits.auto_topup_error") });
    }
  };

  const handleDisable = async () => {
    if (!userId) return;
    try {
      await disable();
      toast.success(t("credits.auto_topup_disable_success"));
      onSuccess?.();
      await refresh();
    } catch (err) {
      showError(err, { context: t("credits.auto_topup_disable_error") });
    }
  };

  const previewText = useMemo(() => {
    const thresholdNum = parseInt(threshold, 10);
    const targetNum = parseInt(target, 10);

    if (
      !Number.isNaN(thresholdNum) &&
      !Number.isNaN(targetNum) &&
      thresholdNum > 0 &&
      targetNum > thresholdNum
    ) {
      return t("credits.auto_topup_preview")
        .replace("{threshold}", thresholdNum.toString())
        .replace("{target}", targetNum.toString());
    }

    return t("credits.auto_topup_preview_placeholder");
  }, [threshold, target, t]);

  const currentStatus = useMemo(() => {
    if (!config) return t("credits.auto_topup_not_configured");
    return config.is_active
      ? t("credits.auto_topup_status_active")
      : t("credits.auto_topup_status_inactive");
  }, [config, t]);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>{t("credits.auto_topup_manage")}</DialogTitle>
          <DialogDescription className="flex items-center gap-2">
            <span>
              {t("credits.auto_topup_single_description")}
              {userLabel ? ` (${userLabel})` : ""}
            </span>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="inline-flex items-center text-muted-foreground hover:text-foreground"
                >
                  <Info className="w-4 h-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent className="max-w-xs text-xs">
                {t("credits.auto_topup_help")}
              </TooltipContent>
            </Tooltip>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" />
              {t("credits.auto_topup_loading")}
            </div>
          ) : error ? (
            <p className="text-sm text-destructive">{t("credits.auto_topup_load_error")}</p>
          ) : (
            <div className="rounded-md border p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">{t("credits.auto_topup_current")}</p>
                <Badge variant={config?.is_active ? "default" : "outline"}>
                  {currentStatus}
                </Badge>
              </div>
              {config ? (
                <div className="mt-2 space-y-1 text-sm text-muted-foreground">
                  <p>
                    {t("credits.auto_topup_threshold")}: {config.min_balance_threshold}
                  </p>
                  <p>
                    {t("credits.auto_topup_target")}: {config.target_balance}
                  </p>
                  <p>
                    {t("credits.auto_topup_last_updated")}:{" "}
                    {config.updated_at
                      ? new Date(config.updated_at).toLocaleString()
                      : "-"}
                  </p>
                </div>
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">
                  {t("credits.auto_topup_not_configured")}
                </p>
              )}
            </div>
          )}

          {/* 触发阈值 */}
          <div className="space-y-2">
            <Label htmlFor="auto-topup-threshold-single">
              {t("credits.auto_topup_threshold")} <span className="text-destructive">*</span>
            </Label>
            <Input
              id="auto-topup-threshold-single"
              type="number"
              min={0}
              value={threshold}
              onChange={(e) => {
                setThreshold(e.target.value);
                if (formErrors.threshold) {
                  setFormErrors((prev) => ({ ...prev, threshold: undefined }));
                }
              }}
              disabled={saving || disabling}
              className={formErrors.threshold ? "border-destructive" : ""}
            />
            {formErrors.threshold && (
              <p className="text-sm text-destructive">{formErrors.threshold}</p>
            )}
          </div>

          {/* 目标余额 */}
          <div className="space-y-2">
            <Label htmlFor="auto-topup-target-single">
              {t("credits.auto_topup_target")} <span className="text-destructive">*</span>
            </Label>
            <Input
              id="auto-topup-target-single"
              type="number"
              min={1}
              value={target}
              onChange={(e) => {
                setTarget(e.target.value);
                if (formErrors.target) {
                  setFormErrors((prev) => ({ ...prev, target: undefined }));
                }
              }}
              disabled={saving || disabling}
              className={formErrors.target ? "border-destructive" : ""}
            />
            {formErrors.target && (
              <p className="text-sm text-destructive">{formErrors.target}</p>
            )}
          </div>

          {/* 启用开关 */}
          <div className="flex items-center space-x-2">
            <Checkbox
              id="auto-topup-enabled-single"
              checked={isActive}
              onCheckedChange={(checked) => setIsActive(checked === true)}
              disabled={saving || disabling}
            />
            <Label
              htmlFor="auto-topup-enabled-single"
              className="text-sm font-medium leading-none"
            >
              {t("credits.auto_topup_enabled")}
            </Label>
          </div>

          {/* 规则预览 */}
          <div className="pt-2 border-t">
            <p className="text-xs text-muted-foreground">{previewText}</p>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          {config && (
            <Button
              type="button"
              variant="ghost"
              className="text-destructive"
              onClick={handleDisable}
              disabled={saving || disabling}
            >
              <ShieldOff className="w-4 h-4 mr-2" />
              {disabling ? t("credits.auto_topup_saving") : t("credits.auto_topup_disable")}
            </Button>
          )}
          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={saving || disabling}
            >
              {t("common.cancel")}
            </Button>
            <Button onClick={handleSubmit} disabled={saving || disabling}>
              {saving ? t("credits.auto_topup_saving") : t("credits.auto_topup_save")}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
