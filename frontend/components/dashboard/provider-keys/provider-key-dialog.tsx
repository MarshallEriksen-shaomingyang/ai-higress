"use client";

import React, { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
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
import { useI18n } from "@/lib/i18n-context";
import { Loader2 } from "lucide-react";
import type { ProviderKey } from "@/lib/api-types";

// 表单验证 schema
const providerKeySchema = z.object({
  key: z.string().optional(),
  label: z.string().min(1, "标签不能为空").max(100, "标签不能超过100字符"),
  weight: z.number().min(0, "权重不能为负数").max(100, "权重不能超过100"),
  max_qps: z.number().min(1, "QPS必须大于0").optional().or(z.literal(0)),
  status: z.enum(['active', 'inactive']),
});

type ProviderKeyFormData = z.infer<typeof providerKeySchema>;

interface ProviderKeyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editingKey: ProviderKey | null;
  providerId: string;
  onSuccess: () => void;
  onSubmit: (data: ProviderKeyFormData) => Promise<void>;
}

export function ProviderKeyDialog({
  open,
  onOpenChange,
  editingKey,
  providerId,
  onSuccess,
  onSubmit,
}: ProviderKeyDialogProps) {
  const { t } = useI18n();
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
    setValue,
  } = useForm<ProviderKeyFormData>({
    resolver: zodResolver(providerKeySchema),
    defaultValues: {
      key: "",
      label: "",
      weight: 1.0,
      max_qps: 0,
      status: 'active',
    },
  });

  // 当编辑密钥变化时，更新表单
  useEffect(() => {
    if (editingKey) {
      setValue("label", editingKey.label);
      setValue("weight", editingKey.weight);
      setValue("max_qps", editingKey.max_qps || 0);
      setValue("status", editingKey.status);
      // 编辑时不显示密钥字段
      setValue("key", "");
    } else {
      reset({
        key: "",
        label: "",
        weight: 1.0,
        max_qps: 0,
        status: 'active',
      });
    }
  }, [editingKey, setValue, reset]);

  const handleFormSubmit = async (data: ProviderKeyFormData) => {
    setIsSubmitting(true);
    try {
      // 如果 max_qps 为 0，转换为 null
      const submitData = {
        ...data,
        max_qps: data.max_qps && data.max_qps > 0 ? data.max_qps : undefined,
      };
      
      await onSubmit(submitData);
      onSuccess();
      onOpenChange(false);
      reset();
    } catch (error) {
      console.error('Failed to submit:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const isEditing = !!editingKey;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>
            {isEditing 
              ? t("provider_keys.dialog_edit_title") 
              : t("provider_keys.dialog_create_title")}
          </DialogTitle>
          <DialogDescription>
            {isEditing 
              ? t("provider_keys.dialog_edit_description") 
              : t("provider_keys.dialog_create_description")}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4">
          {/* API 密钥字段 - 仅在创建时显示 */}
          {!isEditing && (
            <div className="space-y-2">
              <Label htmlFor="key">
                {t("provider_keys.form_key")} <span className="text-destructive">*</span>
              </Label>
              <Input
                id="key"
                type="password"
                placeholder={t("provider_keys.form_key_placeholder")}
                {...register("key", { required: !isEditing })}
              />
              {errors.key && (
                <p className="text-sm text-destructive">{errors.key.message}</p>
              )}
            </div>
          )}

          {/* 标签 */}
          <div className="space-y-2">
            <Label htmlFor="label">
              {t("provider_keys.form_label")} <span className="text-destructive">*</span>
            </Label>
            <Input
              id="label"
              placeholder={t("provider_keys.form_label_placeholder")}
              {...register("label")}
            />
            {errors.label && (
              <p className="text-sm text-destructive">{errors.label.message}</p>
            )}
          </div>

          {/* 权重 */}
          <div className="space-y-2">
            <Label htmlFor="weight">
              {t("provider_keys.form_weight")}
            </Label>
            <Input
              id="weight"
              type="number"
              step="0.1"
              {...register("weight", { valueAsNumber: true })}
            />
            <p className="text-xs text-muted-foreground">
              {t("provider_keys.form_weight_description")}
            </p>
            {errors.weight && (
              <p className="text-sm text-destructive">{errors.weight.message}</p>
            )}
          </div>

          {/* QPS 限制 */}
          <div className="space-y-2">
            <Label htmlFor="max_qps">
              {t("provider_keys.form_qps")}
            </Label>
            <Input
              id="max_qps"
              type="number"
              placeholder={t("provider_keys.form_qps_placeholder")}
              {...register("max_qps", { valueAsNumber: true })}
            />
            <p className="text-xs text-muted-foreground">
              {t("provider_keys.form_qps_description")}
            </p>
            {errors.max_qps && (
              <p className="text-sm text-destructive">{errors.max_qps.message}</p>
            )}
          </div>

          {/* 状态 */}
          <div className="space-y-2">
            <Label htmlFor="status">
              {t("provider_keys.form_status")}
            </Label>
            <select
              id="status"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              {...register("status")}
            >
              <option value="active">{t("provider_keys.status_active")}</option>
              <option value="inactive">{t("provider_keys.status_inactive")}</option>
            </select>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              {isEditing 
                ? t("providers.btn_save") 
                : t("providers.btn_create")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}