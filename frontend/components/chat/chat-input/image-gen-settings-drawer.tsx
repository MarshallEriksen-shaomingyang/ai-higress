"use client";

import { useEffect, useMemo } from "react";

import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useI18n } from "@/lib/i18n-context";
import { useLogicalModels } from "@/lib/swr/use-logical-models";
import { useResponsiveDrawerDirection } from "@/lib/hooks/use-responsive-drawer-direction";
import type { ImageGenParams } from "@/components/chat/chat-input/image-gen-params-bar";

const AVAILABLE_SIZES = ["256x256", "512x512", "1024x1024"];
const AVAILABLE_COUNTS = [1, 2, 3, 4];

export function ImageGenSettingsDrawer({
  projectId,
  open,
  onOpenChange,
  params,
  onChange,
  disabled = false,
  showModelSelect = true,
}: {
  projectId?: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  params: ImageGenParams;
  onChange: (params: ImageGenParams) => void;
  disabled?: boolean;
  showModelSelect?: boolean;
}) {
  const { t } = useI18n();
  const direction = useResponsiveDrawerDirection();
  const { models } = useLogicalModels(projectId);

  const imageModels = useMemo(() => {
    return models.filter((m) => m.enabled);
  }, [models]);

  const selectedModel = useMemo(() => {
    if (imageModels.some((m) => m.logical_id === params.model)) return params.model;
    return imageModels[0]?.logical_id || "";
  }, [imageModels, params.model]);

  useEffect(() => {
    if (!showModelSelect) return;
    if (!selectedModel) return;
    if (selectedModel === params.model) return;
    onChange({ ...params, model: selectedModel });
  }, [onChange, params, selectedModel, showModelSelect]);

  return (
    <Drawer open={open} onOpenChange={onOpenChange} direction={direction}>
      <DrawerContent className="mx-auto w-full max-w-md">
        <DrawerHeader className="pb-2">
          <DrawerTitle>{t("chat.image_gen.params")}</DrawerTitle>
        </DrawerHeader>

        <div className="px-4 pb-4 space-y-4">
          {showModelSelect ? (
            <div className="space-y-2">
              <Label className="text-muted-foreground">{t("chat.image_gen.model")}</Label>
              <Select
                value={selectedModel}
                onValueChange={(val) => onChange({ ...params, model: val })}
                disabled={disabled || imageModels.length === 0}
              >
                <SelectTrigger className="h-9">
                  <SelectValue placeholder={t("chat.image_gen.select_model")} />
                </SelectTrigger>
                <SelectContent>
                  {imageModels.map((m) => (
                    <SelectItem
                      key={m.logical_id}
                      value={m.logical_id}
                      textValue={m.display_name || m.logical_id}
                    >
                      {m.display_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}

          <div className="space-y-2">
            <Label className="text-muted-foreground">{t("chat.image_gen.size")}</Label>
            <Select
              value={params.size}
              onValueChange={(val) => onChange({ ...params, size: val })}
              disabled={disabled}
            >
              <SelectTrigger className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AVAILABLE_SIZES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label className="text-muted-foreground">{t("chat.image_gen.number")}</Label>
            <Select
              value={String(params.n)}
              onValueChange={(val) =>
                onChange({ ...params, n: Math.max(1, parseInt(val, 10) || 1) })
              }
              disabled={disabled}
            >
              <SelectTrigger className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AVAILABLE_COUNTS.map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
