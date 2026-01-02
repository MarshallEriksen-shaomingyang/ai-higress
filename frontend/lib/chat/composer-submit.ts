import type { ImageGenParams } from "@/components/chat/chat-input/image-gen-params-bar";
import type { ModelParameters } from "@/components/chat/chat-input/types";
import type { ComposerMode } from "@/lib/chat/composer-modes";

export type ChatComposerSubmitPayload = {
  mode: "chat";
  content: string;
  images: string[];
  input_audio?: {
    audio_id?: string;
    object_key?: string;
    format?: "wav" | "mp3";
  } | null;
  model_preset?: Record<string, number>;
  parameters: ModelParameters;
};

export type ImageComposerSubmitPayload = {
  mode: "image";
  prompt: string;
  params: ImageGenParams;
};

export type SpeechComposerSubmitPayload = {
  mode: "speech";
  content: string;
  voice_audio?: {
    audio_id: string;
    format: "wav" | "mp3";
  } | null;
  model_preset?: Record<string, number>;
  parameters: ModelParameters;
};

export type ComposerSubmitPayload = ChatComposerSubmitPayload | ImageComposerSubmitPayload | SpeechComposerSubmitPayload;

export function isComposerMode(value: string): value is ComposerMode {
  return value === "chat" || value === "image" || value === "speech";
}
