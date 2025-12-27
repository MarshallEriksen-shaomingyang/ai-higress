"use client";

import { useEffect, useMemo } from "react";
import { useLogicalModels } from "@/lib/swr/use-logical-models";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useI18n } from "@/lib/i18n-context";

export interface ImageGenParams {
  model: string;
  size: string;
  n: number;
  quality?: "auto" | "low" | "medium" | "high";
  enableGoogleSearch?: boolean;
  sendResponseFormat?: boolean;
}

interface ImageGenParamsBarProps {
  projectId?: string | null;
  params: ImageGenParams;
  onChange: (params: ImageGenParams) => void;
  disabled?: boolean;
}

const AVAILABLE_SIZES = ["1024x1024", "1536x1024", "1024x1536"];
const AVAILABLE_COUNTS = [1, 2, 3, 4];

export function ImageGenParamsBar({
  projectId,
  params,
  onChange,
  disabled,
}: ImageGenParamsBarProps) {
  const { t } = useI18n();
  const { models } = useLogicalModels(projectId);

  const imageModels = useMemo(() => {
    return models.filter((m) => m.enabled);
  }, [models]);

  // Ensure selected model is valid or select first available
  const selectedModel = useMemo(() => {
    if (imageModels.find((m) => m.logical_id === params.model)) {
      return params.model;
    }
    return imageModels[0]?.logical_id || "";
  }, [imageModels, params.model]);

  useEffect(() => {
    if (!selectedModel) return;
    if (selectedModel === params.model) return;
    onChange({ ...params, model: selectedModel });
  }, [selectedModel, params, onChange]);

  return (
    <div className="flex items-center gap-4 px-4 py-2 border-b bg-muted/30 text-xs">
      {/* Model Selector */}
      <div className="flex items-center gap-2">
        <Label className="text-muted-foreground whitespace-nowrap">{t("chat.image_gen.model")}</Label>
        <Select
          value={selectedModel}
          onValueChange={(val) => onChange({ ...params, model: val })}
          disabled={disabled || imageModels.length === 0}
        >
          <SelectTrigger className="h-7 w-[160px] text-xs">
            <SelectValue placeholder={t("chat.image_gen.select_model")} />
          </SelectTrigger>
          <SelectContent>
            {imageModels.map((m) => (
              <SelectItem key={m.logical_id} value={m.logical_id} className="text-xs">
                {m.display_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Size Selector */}
      <div className="flex items-center gap-2">
        <Label className="text-muted-foreground whitespace-nowrap">{t("chat.image_gen.size")}</Label>
        <Select
          value={params.size}
          onValueChange={(val) => onChange({ ...params, size: val })}
          disabled={disabled}
        >
          <SelectTrigger className="h-7 w-[100px] text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {AVAILABLE_SIZES.map((s) => (
              <SelectItem key={s} value={s} className="text-xs">
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Count Selector */}
      <div className="flex items-center gap-2">
        <Label className="text-muted-foreground whitespace-nowrap">{t("chat.image_gen.number")}</Label>
        <Select
          value={String(params.n)}
          onValueChange={(val) => onChange({ ...params, n: parseInt(val, 10) })}
          disabled={disabled}
        >
          <SelectTrigger className="h-7 w-[60px] text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {AVAILABLE_COUNTS.map((n) => (
              <SelectItem key={n} value={String(n)} className="text-xs">
                {n}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Quality Selector */}
      <div className="flex items-center gap-2">
        <Label className="text-muted-foreground whitespace-nowrap">{t("chat.image_gen.quality")}</Label>
        <Select
          value={params.quality || "auto"}
          onValueChange={(val) => onChange({ ...params, quality: val as ImageGenParams["quality"] })}
          disabled={disabled}
        >
          <SelectTrigger className="h-7 w-[100px] text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {["auto", "low", "medium", "high"].map((q) => (
              <SelectItem key={q} value={q} className="text-xs">
                {q}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Google Search toggle (Gemini lane grounding) */}
      <div className="flex items-center gap-2">
        <Label className="text-muted-foreground whitespace-nowrap">{t("chat.image_gen.google_search")}</Label>
        <Switch
          checked={!!params.enableGoogleSearch}
          onCheckedChange={(val) => onChange({ ...params, enableGoogleSearch: val })}
          disabled={disabled}
        />
      </div>

      {/* Response format toggle */}
      <div className="flex items-center gap-2">
        <Label className="text-muted-foreground whitespace-nowrap">{t("chat.image_gen.response_format")}</Label>
        <Switch
          checked={params.sendResponseFormat !== false}
          onCheckedChange={(val) => onChange({ ...params, sendResponseFormat: val })}
          disabled={disabled}
        />
      </div>
    </div>
  );
}
