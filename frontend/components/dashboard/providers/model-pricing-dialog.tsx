"use client";

import React from "react";
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
import { Loader2 } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";

interface ModelPricingDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  providerId: string;
  modelId: string;
  inputPrice: string;
  outputPrice: string;
  onInputPriceChange: (value: string) => void;
  onOutputPriceChange: (value: string) => void;
  onSave: () => void;
  loading: boolean;
}

export function ModelPricingDialog({
  open,
  onOpenChange,
  providerId,
  modelId,
  inputPrice,
  outputPrice,
  onInputPriceChange,
  onOutputPriceChange,
  onSave,
  loading,
}: ModelPricingDialogProps) {
  const { t } = useI18n();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {t("providers.pricing_edit_title") ?? "编辑模型计费"}
          </DialogTitle>
          <DialogDescription className="font-mono text-xs break-all">
            {providerId} · {modelId}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="input-price" className="text-xs font-medium">
              {t("providers.pricing_input_label") ?? "输入价格（每 1k tokens）"}
            </Label>
            <Input
              id="input-price"
              type="number"
              step="0.01"
              min="0"
              value={inputPrice}
              onChange={(e) => onInputPriceChange(e.target.value)}
              placeholder={t("providers.pricing_input_placeholder") ?? "例如 5"}
              className="h-9"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="output-price" className="text-xs font-medium">
              {t("providers.pricing_output_label") ?? "输出价格（每 1k tokens）"}
            </Label>
            <Input
              id="output-price"
              type="number"
              step="0.01"
              min="0"
              value={outputPrice}
              onChange={(e) => onOutputPriceChange(e.target.value)}
              placeholder={t("providers.pricing_output_placeholder") ?? "例如 15"}
              className="h-9"
            />
          </div>

          <p className="text-xs text-muted-foreground">
            {t("providers.pricing_edit_desc") ??
              "单位为每 1000 tokens 扣减的积分数，留空表示不配置 / 清空对应方向的价格。"}
          </p>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={loading}
          >
            {t("common.cancel") ?? "取消"}
          </Button>
          <Button onClick={onSave} disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                {t("common.saving") ?? "保存中"}
              </>
            ) : (
              t("common.save") ?? "保存"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}