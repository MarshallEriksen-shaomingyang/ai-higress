"use client";

import React, { useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { useI18n } from "@/lib/i18n-context";
import { useErrorDisplay } from "@/lib/errors";
import { useAdminAutoTopupBatch } from "@/lib/swr/use-credits";
import { toast } from "sonner";
import { Info } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface AutoTopupBatchDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  userIds: string[];
  onSuccess?: () => void;
}

export function AutoTopupBatchDialog({
  open,
  onOpenChange,
  userIds,
  onSuccess,
}: AutoTopupBatchDialogProps) {
  const { t } = useI18n();
  const { showError } = useErrorDisplay();
  const { applyBatch, submitting, isSuperUser } = useAdminAutoTopupBatch();

  const [threshold, setThreshold] = useState<string>("");
  const [target, setTarget] = useState<string>("");
  const [isActive, setIsActive] = useState<boolean>(true);
  const [errors, setErrors] = useState<{ threshold?: string; target?: string }>(
    {}
  );

  // 非超级管理员不渲染组件（双重保护）
  if (!isSuperUser) {
    return null;
  }

  const resetForm = () => {
    setThreshold("");
    setTarget("");
    setIsActive(true);
    setErrors({});
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen && !submitting) {
      resetForm();
    }
    onOpenChange(newOpen);
  };

  const validate = (): boolean => {
    const newErrors: { threshold?: string; target?: string } = {};

    if (!userIds.length) {
      toast.error(t("credits.auto_topup_no_selection"));
      return false;
    }

    const thresholdNum = parseInt(threshold, 10);
    const targetNum = parseInt(target, 10);

    if (Number.isNaN(thresholdNum) || thresholdNum <= 0) {
      newErrors.threshold = t("credits.auto_topup_threshold_required");
    }
    if (Number.isNaN(targetNum) || targetNum <= 0) {
      newErrors.target = t("credits.auto_topup_target_required");
    } else if (!Number.isNaN(thresholdNum) && targetNum <= thresholdNum) {
      newErrors.target = t("credits.auto_topup_target_must_gt_threshold");
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;

    const thresholdNum = parseInt(threshold, 10);
    const targetNum = parseInt(target, 10);

    try {
      await applyBatch({
        user_ids: userIds,
        min_balance_threshold: thresholdNum,
        target_balance: targetNum,
        is_active: isActive,
      });

      toast.success(t("credits.auto_topup_success"));
      resetForm();
      onOpenChange(false);
      onSuccess?.();
    } catch (error) {
      showError(error, { context: t("credits.auto_topup_error") });
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

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>{t("credits.auto_topup_dialog_title")}</DialogTitle>
          <DialogDescription className="flex items-center gap-2">
            <span>
              {t("credits.auto_topup_dialog_description").replace(
                "{count}",
                userIds.length.toString()
              )}
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

        <div className="space-y-4 py-4">
          {/* 触发阈值 */}
          <div className="space-y-2">
            <Label htmlFor="auto-topup-threshold">
              {t("credits.auto_topup_threshold")}{" "}
              <span className="text-destructive">*</span>
            </Label>
            <Input
              id="auto-topup-threshold"
              type="number"
              min={0}
              value={threshold}
              onChange={(e) => {
                setThreshold(e.target.value);
                if (errors.threshold) {
                  setErrors((prev) => ({ ...prev, threshold: undefined }));
                }
              }}
              disabled={submitting}
              className={errors.threshold ? "border-destructive" : ""}
            />
            {errors.threshold && (
              <p className="text-sm text-destructive">{errors.threshold}</p>
            )}
          </div>

          {/* 目标余额 */}
          <div className="space-y-2">
            <Label htmlFor="auto-topup-target">
              {t("credits.auto_topup_target")}{" "}
              <span className="text-destructive">*</span>
            </Label>
            <Input
              id="auto-topup-target"
              type="number"
              min={1}
              value={target}
              onChange={(e) => {
                setTarget(e.target.value);
                if (errors.target) {
                  setErrors((prev) => ({ ...prev, target: undefined }));
                }
              }}
              disabled={submitting}
              className={errors.target ? "border-destructive" : ""}
            />
            {errors.target && (
              <p className="text-sm text-destructive">{errors.target}</p>
            )}
          </div>

          {/* 启用开关 */}
          <div className="flex items-center space-x-2">
            <Checkbox
              id="auto-topup-enabled"
              checked={isActive}
              onCheckedChange={(checked) =>
                setIsActive(checked === true ? true : false)
              }
              disabled={submitting}
            />
            <Label
              htmlFor="auto-topup-enabled"
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

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={submitting}
          >
            {t("common.cancel")}
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting
              ? t("credits.auto_topup_submitting")
              : t("credits.auto_topup_submit")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
