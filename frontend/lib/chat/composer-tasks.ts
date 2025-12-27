import type { ImageGenerationRequest, ImageGenerationResponse } from "@/lib/api-types";

export type ComposerTaskStatus = "pending" | "success" | "failed";

export type ComposerTaskKind = "image_generation";

export interface BaseComposerTask {
  id: string;
  conversationId: string;
  kind: ComposerTaskKind;
  status: ComposerTaskStatus;
  createdAt: number;
}

export interface ImageGenerationTask extends BaseComposerTask {
  kind: "image_generation";
  prompt: string;
  params: ImageGenerationRequest;
  result?: ImageGenerationResponse;
  error?: string;
}

export type ComposerTask = ImageGenerationTask;

export function isImageGenerationTask(task: ComposerTask): task is ImageGenerationTask {
  return task.kind === "image_generation";
}

