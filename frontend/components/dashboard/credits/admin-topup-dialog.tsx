"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useI18n } from "@/lib/i18n-context";
import { toast } from "sonner";
import { useErrorDisplay } from "@/lib/errors";
import { useAdminTopup } from "@/lib/swr/use-credits";

interface AdminTopupDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  userId: string;
  onSuccess?: () => void;
}

export function AdminTopupDialog({
  open,
  onOpenChange,
  userId,
  onSuccess
}: AdminTopupDialogProps) {
  const { t } = useI18n();
  const { showError } = useErrorDisplay();
  const { topup, submitting, isSuperUser } = useAdminTopup();
  
  const [amount, setAmount] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const [errors, setErrors] = useState<{ amount?: string }>({});

  // 如果不是超级管理员，不渲染组件
  if (!isSuperUser) {
    return null;
  }

  // 验证表单
  const validateForm = (): boolean => {
    const newErrors: { amount?: string } = {};
    
    const amountNum = parseInt(amount);
    if (!amount || isNaN(amountNum)) {
      newErrors.amount = t("credits.topup_amount_required");
    } else if (amountNum <= 0) {
      newErrors.amount = t("credits.topup_amount_positive");
    } else if (amountNum > 1000000) {
      newErrors.amount = t("credits.topup_amount_max");
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // 处理提交
  const handleSubmit = async () => {
    if (!validateForm()) return;
    
    try {
      await topup(userId, {
        amount: parseInt(amount),
        description: description.trim() || undefined
      });
      
      toast.success(t("credits.topup_success"));
      
      // 重置表单
      setAmount('');
      setDescription('');
      setErrors({});
      
      // 关闭对话框
      onOpenChange(false);
      
      // 调用成功回调
      onSuccess?.();
    } catch (error) {
      showError(error, { context: t("credits.topup_error") });
    }
  };

  // 处理对话框关闭
  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen && !submitting) {
      // 重置表单
      setAmount('');
      setDescription('');
      setErrors({});
    }
    onOpenChange(newOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>{t("credits.topup_dialog_title")}</DialogTitle>
          <DialogDescription>
            {t("credits.topup_dialog_description")}
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4 py-4">
          {/* 充值金额 */}
          <div className="space-y-2">
            <Label htmlFor="amount">
              {t("credits.topup_amount")} <span className="text-destructive">*</span>
            </Label>
            <Input
              id="amount"
              type="number"
              placeholder="1000"
              value={amount}
              onChange={(e) => {
                setAmount(e.target.value);
                if (errors.amount) {
                  setErrors({ ...errors, amount: undefined });
                }
              }}
              disabled={submitting}
              min="1"
              max="1000000"
              className={errors.amount ? 'border-destructive' : ''}
            />
            {errors.amount && (
              <p className="text-sm text-destructive">{errors.amount}</p>
            )}
          </div>

          {/* 充值说明 */}
          <div className="space-y-2">
            <Label htmlFor="description">
              {t("credits.topup_description")}
            </Label>
            <Textarea
              id="description"
              placeholder={t("credits.topup_description_placeholder")}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={submitting}
              rows={3}
              maxLength={200}
            />
            <p className="text-xs text-muted-foreground">
              {description.length} / 200
            </p>
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
          <Button
            onClick={handleSubmit}
            disabled={submitting}
          >
            {submitting ? t("credits.topup_submitting") : t("credits.topup_submit")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
