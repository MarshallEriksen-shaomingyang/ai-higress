"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Settings2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/lib/i18n-context";
import { useErrorDisplay } from "@/lib/errors";
import { toast } from "sonner";

import type { Model } from "@/http/provider";
import { providerService } from "@/http/provider";
import {
  ALL_MODEL_CAPABILITIES,
  CAPABILITY_META,
  normalize_capabilities,
  type ModelCapabilityValue,
} from "./model-capabilities";

interface ModelSettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  providerId: string;
  model: Model | null;
  canEditModelMapping: boolean;
  onRefresh: () => Promise<void>;
}

export function ModelSettingsDialog({
  open,
  onOpenChange,
  providerId,
  model,
  canEditModelMapping,
  onRefresh,
}: ModelSettingsDialogProps) {
  const { t } = useI18n();
  const { showError } = useErrorDisplay();

  const modelId = model?.model_id || "";

  const initialAlias = useMemo(() => (model?.alias ?? "") || "", [model?.alias]);
  const initialCapabilities = useMemo(
    () => normalize_capabilities(model?.capabilities),
    [model?.capabilities]
  );

  const [activeTab, setActiveTab] = useState<"config" | "pricing">("config");

  const [aliasDraft, setAliasDraft] = useState("");
  const [capabilitiesDraft, setCapabilitiesDraft] = useState<ModelCapabilityValue[]>([]);

  const [pricingInput, setPricingInput] = useState("");
  const [pricingOutput, setPricingOutput] = useState("");
  const [pricingLoading, setPricingLoading] = useState(false);
  const [pricingLoaded, setPricingLoaded] = useState(false);
  const [pricingUnavailable, setPricingUnavailable] = useState(false);
  const [initialPricingInput, setInitialPricingInput] = useState("");
  const [initialPricingOutput, setInitialPricingOutput] = useState("");

  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setActiveTab("config");
    setAliasDraft(initialAlias);
    setCapabilitiesDraft(initialCapabilities);
    setPricingInput("");
    setPricingOutput("");
    setInitialPricingInput("");
    setInitialPricingOutput("");
    setPricingLoaded(false);
    setPricingUnavailable(false);
  }, [open, initialAlias, initialCapabilities]);

  useEffect(() => {
    if (!open) return;
    if (!providerId || !modelId) return;
    setPricingLoading(true);
    setPricingLoaded(false);
    let cancelled = false;
    (async () => {
      try {
        const pricing = await providerService.getProviderModelPricing(providerId, modelId);
        if (cancelled) return;
        const inputVal = pricing?.pricing?.input != null ? String(pricing.pricing.input) : "";
        const outputVal = pricing?.pricing?.output != null ? String(pricing.pricing.output) : "";
        setPricingInput(inputVal);
        setPricingOutput(outputVal);
        setInitialPricingInput(inputVal);
        setInitialPricingOutput(outputVal);
        setPricingUnavailable(false);
        setPricingLoaded(true);
      } catch (err: any) {
        if (cancelled) return;
        if (err?.response?.status === 403) {
          setPricingUnavailable(true);
          return;
        }
        // 404 表示未配置计费，按空值展示即可
        if (err?.response?.status === 404) {
          setPricingInput("");
          setPricingOutput("");
          setInitialPricingInput("");
          setInitialPricingOutput("");
          setPricingUnavailable(false);
          setPricingLoaded(true);
          return;
        }
        showError(err, { context: t("providers.pricing_load_error") });
        setPricingUnavailable(true);
      } finally {
        if (!cancelled) setPricingLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, providerId, modelId, showError, t]);

  const toggleCapability = useCallback(
    (cap: ModelCapabilityValue, checked: boolean) => {
      setCapabilitiesDraft((prev) => {
        if (checked) {
          return prev.includes(cap) ? prev : [...prev, cap];
        }
        return prev.filter((x) => x !== cap);
      });
    },
    []
  );

  const hasConfigChanges = useMemo(() => {
    const aliasChanged = aliasDraft.trim() !== initialAlias.trim();
    const capsA = [...capabilitiesDraft].sort().join(",");
    const capsB = [...initialCapabilities].sort().join(",");
    return aliasChanged || capsA !== capsB;
  }, [aliasDraft, capabilitiesDraft, initialAlias, initialCapabilities]);

  const hasPricingChanges = useMemo(() => {
    if (pricingUnavailable || !pricingLoaded) return false;
    return (
      pricingInput.trim() !== initialPricingInput.trim() ||
      pricingOutput.trim() !== initialPricingOutput.trim()
    );
  }, [
    pricingInput,
    pricingOutput,
    pricingUnavailable,
    pricingLoaded,
    initialPricingInput,
    initialPricingOutput,
  ]);

  const handleSave = useCallback(async () => {
    if (!providerId || !modelId || !model) return;
    if (saving) return;
    setSaving(true);

    const tasks: Array<Promise<unknown>> = [];
    const aliasTrimmed = aliasDraft.trim();

    if (canEditModelMapping) {
      if (aliasTrimmed !== initialAlias.trim()) {
        tasks.push(
          providerService.updateProviderModelAlias(providerId, modelId, {
            alias: aliasTrimmed === "" ? null : aliasTrimmed,
          })
        );
      }

      const capsA = [...capabilitiesDraft].sort().join(",");
      const capsB = [...initialCapabilities].sort().join(",");
      if (capsA !== capsB) {
        tasks.push(
          providerService.updateProviderModelCapabilities(providerId, modelId, {
            capabilities: capabilitiesDraft,
          })
        );
      }
    }

    if (!pricingUnavailable && pricingLoaded && hasPricingChanges) {
      const payload: { input?: number; output?: number } = {};
      if (pricingInput.trim() !== "") payload.input = Number(pricingInput);
      if (pricingOutput.trim() !== "") payload.output = Number(pricingOutput);
      const body = Object.keys(payload).length > 0 ? payload : null;
      tasks.push(providerService.updateProviderModelPricing(providerId, modelId, body));
    }

    if (tasks.length === 0) {
      setSaving(false);
      onOpenChange(false);
      return;
    }

    try {
      await Promise.all(tasks);
      toast.success(t("providers.model_settings_save_success"));
      await onRefresh();
      onOpenChange(false);
    } catch (err: any) {
      showError(err, { context: t("providers.model_settings_save_error") });
    } finally {
      setSaving(false);
    }
  }, [
    providerId,
    modelId,
    model,
    saving,
    aliasDraft,
    initialAlias,
    canEditModelMapping,
    capabilitiesDraft,
    initialCapabilities,
    pricingUnavailable,
    pricingInput,
    pricingOutput,
    onRefresh,
    onOpenChange,
    showError,
    t,
  ]);

  const footerHint = useMemo(() => {
    if (!modelId) return "";
    if (saving) return t("common.saving");
    if (activeTab === "pricing") return t("providers.model_settings_footer_pricing");
    return t("providers.model_settings_footer_config");
  }, [activeTab, modelId, saving, t]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="p-0 sm:max-w-md">
        <div className="flex max-h-[85vh] flex-col">
          <DialogHeader className="px-6 pt-6">
            <DialogTitle className="flex items-center gap-2">
              <Settings2 className="h-4 w-4" />
              {t("providers.model_settings_title")}
            </DialogTitle>
            <DialogDescription className="font-mono text-xs break-all">
              {providerId} · {modelId}
            </DialogDescription>
          </DialogHeader>

          <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-4">
            <Tabs
              value={activeTab}
              onValueChange={(v) => setActiveTab(v as any)}
              className="space-y-4"
            >
              <TabsList className="grid grid-cols-2">
                <TabsTrigger value="config">{t("providers.model_settings_tab_config")}</TabsTrigger>
                <TabsTrigger value="pricing">{t("providers.model_settings_tab_pricing")}</TabsTrigger>
              </TabsList>

              <TabsContent value="config" className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="model-alias" className="text-xs font-medium">
                    {t("providers.alias_edit_label")}
                  </Label>
                  <Input
                    id="model-alias"
                    type="text"
                    value={aliasDraft}
                    onChange={(e) => setAliasDraft(e.target.value)}
                    placeholder={t("providers.alias_placeholder")}
                    className="h-9"
                    disabled={!canEditModelMapping || saving}
                  />
                  <p className="text-xs text-muted-foreground">{t("providers.alias_hint")}</p>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs font-medium">
                      {t("providers.model_capabilities_title")}
                    </Label>
                    {!canEditModelMapping ? (
                      <Badge variant="outline" className="text-[10px] font-normal">
                        {t("providers.model_settings_readonly")}
                      </Badge>
                    ) : null}
                  </div>
                  <div className="space-y-2">
                    {ALL_MODEL_CAPABILITIES.map((cap) => {
                      const meta = CAPABILITY_META[cap];
                      const Icon = meta.icon;
                      const checked = capabilitiesDraft.includes(cap);
                      return (
                        <div
                          key={cap}
                          className="flex items-center justify-between rounded-md border bg-muted/20 px-3 py-2"
                        >
                          <div className="flex items-center gap-2">
                            <Icon className="h-4 w-4 text-muted-foreground" />
                            <span className="text-sm">{t(meta.labelKey)}</span>
                          </div>
                          <Checkbox
                            checked={checked}
                            onCheckedChange={(val) => toggleCapability(cap, Boolean(val))}
                            disabled={!canEditModelMapping || saving}
                          />
                        </div>
                      );
                    })}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {t("providers.model_capabilities_hint")}
                  </p>
                </div>
              </TabsContent>

              <TabsContent value="pricing" className="space-y-4">
                {pricingUnavailable ? (
                  <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
                    {t("providers.pricing_permission_denied")}
                  </div>
                ) : null}

                <div className="space-y-2">
                  <Label htmlFor="input-price" className="text-xs font-medium">
                    {t("providers.pricing_input_label")}
                  </Label>
                  <Input
                    id="input-price"
                    type="number"
                    step="0.01"
                    min="0"
                    value={pricingInput}
                    onChange={(e) => setPricingInput(e.target.value)}
                    placeholder={t("providers.pricing_input_placeholder")}
                    className="h-9"
                    disabled={pricingUnavailable || pricingLoading || saving}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="output-price" className="text-xs font-medium">
                    {t("providers.pricing_output_label")}
                  </Label>
                  <Input
                    id="output-price"
                    type="number"
                    step="0.01"
                    min="0"
                    value={pricingOutput}
                    onChange={(e) => setPricingOutput(e.target.value)}
                    placeholder={t("providers.pricing_output_placeholder")}
                    className="h-9"
                    disabled={pricingUnavailable || pricingLoading || saving}
                  />
                </div>

                <p className="text-xs text-muted-foreground">{t("providers.pricing_edit_desc")}</p>
              </TabsContent>
            </Tabs>
          </div>

          <DialogFooter className="border-t bg-background/80 px-6 py-4 backdrop-blur sm:justify-between">
            <span className="text-xs text-muted-foreground">{footerHint}</span>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
                {t("common.cancel")}
              </Button>
              <Button
                onClick={handleSave}
                disabled={
                  saving ||
                  (activeTab === "config" && !hasConfigChanges) ||
                  (activeTab === "pricing" &&
                    (!pricingLoaded || pricingUnavailable || pricingLoading || !hasPricingChanges))
                }
              >
                {saving ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    {t("common.saving")}
                  </>
                ) : (
                  t("common.save")
                )}
              </Button>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
