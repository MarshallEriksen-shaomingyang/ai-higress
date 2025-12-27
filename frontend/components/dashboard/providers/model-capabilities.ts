"use client";

import type { LucideIcon } from "lucide-react";
import {
  AudioLines,
  Eye,
  Image as ImageIcon,
  MessageSquare,
  Text,
  Hash,
  FunctionSquare,
} from "lucide-react";

export type ModelCapabilityValue =
  | "chat"
  | "completion"
  | "embedding"
  | "vision"
  | "audio"
  | "function_calling"
  | "image_generation";

export const ALL_MODEL_CAPABILITIES: ModelCapabilityValue[] = [
  "chat",
  "completion",
  "embedding",
  "vision",
  "audio",
  "function_calling",
  "image_generation",
];

export const CAPABILITY_META: Record<
  ModelCapabilityValue,
  { icon: LucideIcon; labelKey: string }
> = {
  chat: { icon: MessageSquare, labelKey: "providers.capability_chat" },
  completion: { icon: Text, labelKey: "providers.capability_completion" },
  embedding: { icon: Hash, labelKey: "providers.capability_embedding" },
  vision: { icon: Eye, labelKey: "providers.capability_vision" },
  audio: { icon: AudioLines, labelKey: "providers.capability_audio" },
  function_calling: { icon: FunctionSquare, labelKey: "providers.capability_function_calling" },
  image_generation: { icon: ImageIcon, labelKey: "providers.capability_image_generation" },
};

export function normalize_capabilities(values: unknown): ModelCapabilityValue[] {
  if (!Array.isArray(values)) return [];
  const out: ModelCapabilityValue[] = [];
  for (const item of values) {
    const v = String(item || "").trim() as ModelCapabilityValue;
    if ((ALL_MODEL_CAPABILITIES as string[]).includes(v) && !out.includes(v)) {
      out.push(v);
    }
  }
  return out;
}

