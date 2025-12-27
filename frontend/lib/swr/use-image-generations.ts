import { useApiPost } from "./hooks";
import type { ImageGenerationRequest, ImageGenerationResponse } from "@/lib/api-types";

export function useImageGenerations() {
  const { trigger, data, error, submitting } = useApiPost<
    ImageGenerationResponse,
    ImageGenerationRequest
  >("/v1/images/generations");

  return {
    generateImage: trigger,
    data,
    error,
    isGenerating: submitting,
  };
}
