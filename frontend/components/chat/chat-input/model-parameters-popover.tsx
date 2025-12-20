"use client";

import { Settings2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Slider } from "@/components/ui/slider";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import type { ModelParameterKey, ModelParameters } from "./types";

export type ModelParameterEnabled = Partial<Record<ModelParameterKey, boolean>>;

export type ModelParametersPopoverProps = {
  idPrefix: string;
  disabled?: boolean;
  enabled: ModelParameterEnabled;
  parameters: ModelParameters;
  onEnabledChange: (next: ModelParameterEnabled) => void;
  onParametersChange: (next: ModelParameters) => void;
  onReset: () => void;
  title: string;
  resetLabel: string;
  labels: Record<ModelParameterKey, string>;
};

export function ModelParametersPopover({
  idPrefix,
  disabled = false,
  enabled,
  parameters,
  onEnabledChange,
  onParametersChange,
  onReset,
  title,
  resetLabel,
  labels,
}: ModelParametersPopoverProps) {
  const hasActive = Boolean(
    enabled.temperature ||
      enabled.top_p ||
      enabled.frequency_penalty ||
      enabled.presence_penalty
  );

  const toggle = (key: ModelParameterKey, value: boolean) => {
    onEnabledChange({ ...enabled, [key]: value });
  };

  const setValue = (key: ModelParameterKey, value: number | undefined) => {
    if (value == null) return;
    onParametersChange({ ...parameters, [key]: value });
  };

  return (
    <Popover>
      <Tooltip>
        <TooltipTrigger asChild>
          <PopoverTrigger asChild>
            <Button
              type="button"
              size="icon-sm"
              variant={hasActive ? "secondary" : "ghost"}
              disabled={disabled}
              aria-label={title}
            >
              <Settings2 className="size-4" />
            </Button>
          </PopoverTrigger>
        </TooltipTrigger>
        <TooltipContent>
          <p>{title}</p>
        </TooltipContent>
      </Tooltip>

      <PopoverContent className="w-80" align="start">
        <div className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Checkbox
                  checked={Boolean(enabled.temperature)}
                  onCheckedChange={(v) => toggle("temperature", Boolean(v))}
                  id={`${idPrefix}-param-temperature`}
                  disabled={disabled}
                />
                <Label className="text-xs" htmlFor={`${idPrefix}-param-temperature`}>
                  {labels.temperature}
                </Label>
              </div>
              <span className="text-xs text-muted-foreground">
                {parameters.temperature.toFixed(1)}
              </span>
            </div>
            <Slider
              value={[parameters.temperature]}
              onValueChange={([v]) => setValue("temperature", v)}
              min={0}
              max={2}
              step={0.1}
              disabled={!enabled.temperature || disabled}
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Checkbox
                  checked={Boolean(enabled.top_p)}
                  onCheckedChange={(v) => toggle("top_p", Boolean(v))}
                  id={`${idPrefix}-param-top_p`}
                  disabled={disabled}
                />
                <Label className="text-xs" htmlFor={`${idPrefix}-param-top_p`}>
                  {labels.top_p}
                </Label>
              </div>
              <span className="text-xs text-muted-foreground">
                {parameters.top_p.toFixed(1)}
              </span>
            </div>
            <Slider
              value={[parameters.top_p]}
              onValueChange={([v]) => setValue("top_p", v)}
              min={0}
              max={1}
              step={0.1}
              disabled={!enabled.top_p || disabled}
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Checkbox
                  checked={Boolean(enabled.frequency_penalty)}
                  onCheckedChange={(v) => toggle("frequency_penalty", Boolean(v))}
                  id={`${idPrefix}-param-frequency_penalty`}
                  disabled={disabled}
                />
                <Label className="text-xs" htmlFor={`${idPrefix}-param-frequency_penalty`}>
                  {labels.frequency_penalty}
                </Label>
              </div>
              <span className="text-xs text-muted-foreground">
                {parameters.frequency_penalty.toFixed(1)}
              </span>
            </div>
            <Slider
              value={[parameters.frequency_penalty]}
              onValueChange={([v]) => setValue("frequency_penalty", v)}
              min={0}
              max={2}
              step={0.1}
              disabled={!enabled.frequency_penalty || disabled}
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Checkbox
                  checked={Boolean(enabled.presence_penalty)}
                  onCheckedChange={(v) => toggle("presence_penalty", Boolean(v))}
                  id={`${idPrefix}-param-presence_penalty`}
                  disabled={disabled}
                />
                <Label className="text-xs" htmlFor={`${idPrefix}-param-presence_penalty`}>
                  {labels.presence_penalty}
                </Label>
              </div>
              <span className="text-xs text-muted-foreground">
                {parameters.presence_penalty.toFixed(1)}
              </span>
            </div>
            <Slider
              value={[parameters.presence_penalty]}
              onValueChange={([v]) => setValue("presence_penalty", v)}
              min={0}
              max={2}
              step={0.1}
              disabled={!enabled.presence_penalty || disabled}
            />
          </div>

          <Button size="sm" variant="outline" onClick={onReset} className="w-full" type="button">
            {resetLabel}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
