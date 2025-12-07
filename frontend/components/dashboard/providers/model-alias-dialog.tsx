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

interface ModelAliasDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  providerId: string;
  modelId: string;
  alias: string;
  onAliasChange: (value: string) => void;
  onSave: () => void;
  loading: boolean;
}

export function ModelAliasDialog({
  open,
  onOpenChange,
  providerId,
  modelId,
  alias,
  onAliasChange,
  onSave,
  loading,
}: ModelAliasDialogProps) {
  const { t } = useI18n();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {t("providers.alias_edit_title") ?? "编辑模型别名"}
          </DialogTitle>
          <DialogDescription className="font-mono text-xs break-all">
            {providerId} · {modelId}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="model-alias" className="text-xs font-medium">
              {t("providers.alias_edit_label") ?? "模型别名映射"}
            </Label>
            <Input
              id="model-alias"
              type="text"
              value={alias}
              onChange={(e) => onAliasChange(e.target.value)}
              placeholder={t("providers.alias_placeholder") ?? "例如 claude-sonnet-4-5"}
              className="h-9"
            />
          </div>

          <p className="text-xs text-muted-foreground">
            {t("providers.alias_hint") ??
              "为长版本模型 ID 配置一个更易记的别名，例如将 claude-sonnet-4-5-20250929 映射为 claude-sonnet-4-5。留空后保存可清除别名。"}
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