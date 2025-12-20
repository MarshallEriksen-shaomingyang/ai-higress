import type { ModelParameterKey, ModelParameters } from "./types";

export function buildModelPreset(
  enabled: Partial<Record<ModelParameterKey, boolean>>,
  parameters: ModelParameters
): Record<string, number> | undefined {
  const preset: Record<string, number> = {};

  if (enabled.temperature) preset.temperature = parameters.temperature;
  if (enabled.top_p) preset.top_p = parameters.top_p;
  if (enabled.frequency_penalty) preset.frequency_penalty = parameters.frequency_penalty;
  if (enabled.presence_penalty) preset.presence_penalty = parameters.presence_penalty;

  return Object.keys(preset).length > 0 ? preset : undefined;
}

