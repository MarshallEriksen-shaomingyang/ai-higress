"use client";

import React, { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useI18n } from "@/lib/i18n-context";
import { Loader2 } from "lucide-react";
import type { ProviderKey } from "@/lib/api-types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type ProviderKeyFormData = {
  key?: string;
  label: string;
  weight: number;
  max_qps?: number;
  status: "active" | "inactive";
};

interface ProviderKeyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editingKey: ProviderKey | null;
  onSuccess: () => void;
  onSubmit: (data: ProviderKeyFormData) => Promise<void>;
}

export function ProviderKeyDialog({
  open,
  onOpenChange,
  editingKey,
  onSuccess,
  onSubmit,
}: ProviderKeyDialogProps) {
  const { t } = useI18n();
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const isEditing = Boolean(editingKey);

  const providerKeySchema = React.useMemo(
    () =>
      z.object({
        key: z.string().optional(),
        label: z
          .string()
          .trim()
          .min(1, t("provider_keys.form_label_required"))
          .max(100, t("provider_keys.form_label_invalid")),
        weight: z
          .number()
          .min(0, t("provider_keys.form_weight_invalid"))
          .max(100, t("provider_keys.form_weight_invalid")),
        max_qps: z.number().min(0, t("provider_keys.form_qps_invalid")).optional(),
        status: z.enum(["active", "inactive"]),
      }),
    [t]
  );

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
    setValue,
    control,
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

  useEffect(() => {
    if (!open) {
      reset({
        key: "",
        label: "",
        weight: 1.0,
        max_qps: 0,
        status: "active",
      });
    }
  }, [open, reset]);

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
      const submitData: ProviderKeyFormData = {
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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="p-0 overflow-hidden">
        <DialogHeader className="px-6 pt-6">
          <DialogTitle>
            {isEditing ? t("provider_keys.dialog_edit_title") : t("provider_keys.dialog_create_title")}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? t("provider_keys.dialog_edit_description")
              : t("provider_keys.dialog_create_description")}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(handleFormSubmit)} className="flex min-h-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-6 space-y-4">
            {!isEditing && (
              <div className="space-y-2">
                <Label htmlFor="key">
                  {t("provider_keys.form_key")} <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="key"
                  type="password"
                  placeholder={t("provider_keys.form_key_placeholder")}
                  {...register("key", { required: t("provider_keys.form_key_required") })}
                />
                {errors.key && (
                  <p className="text-sm text-destructive">{errors.key.message}</p>
                )}
              </div>
            )}

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

            <div className="space-y-2">
              <Label htmlFor="weight">{t("provider_keys.form_weight")}</Label>
              <Input
                id="weight"
                type="number"
                step="0.1"
                {...register("weight", {
                  setValueAs: (value) => {
                    const text = String(value ?? "").trim();
                    if (!text) return 1.0;
                    const parsed = Number(text);
                    return Number.isFinite(parsed) ? parsed : 1.0;
                  },
                })}
              />
              <p className="text-xs text-muted-foreground">
                {t("provider_keys.form_weight_description")}
              </p>
              {errors.weight && (
                <p className="text-sm text-destructive">{errors.weight.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="max_qps">{t("provider_keys.form_qps")}</Label>
              <Input
                id="max_qps"
                type="number"
                placeholder={t("provider_keys.form_qps_placeholder")}
                {...register("max_qps", {
                  setValueAs: (value) => {
                    const text = String(value ?? "").trim();
                    if (!text) return 0;
                    const parsed = Number(text);
                    return Number.isFinite(parsed) ? parsed : 0;
                  },
                })}
              />
              <p className="text-xs text-muted-foreground">
                {t("provider_keys.form_qps_description")}
              </p>
              {errors.max_qps && (
                <p className="text-sm text-destructive">{errors.max_qps.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label>{t("provider_keys.form_status")}</Label>
              <Controller
                control={control}
                name="status"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="active">{t("provider_keys.status_active")}</SelectItem>
                      <SelectItem value="inactive">{t("provider_keys.status_inactive")}</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>

          <DialogFooter className="border-t bg-background/80 backdrop-blur px-6 py-4">
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
              {isEditing ? t("providers.btn_save") : t("providers.btn_create")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
