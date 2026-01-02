import { httpClient } from "./client";

export type ConversationAudioUploadResponse = {
  audio_id: string;
  object_key: string;
  url: string;
  content_type: string;
  size_bytes: number;
  format: "wav" | "mp3";
};

export type AudioAssetItem = {
  audio_id: string;
  owner_id: string;
  owner_username: string;
  owner_display_name?: string | null;
  conversation_id?: string | null;
  object_key: string;
  url: string;
  content_type: string;
  size_bytes: number;
  format: "wav" | "mp3";
  filename?: string | null;
  display_name?: string | null;
  visibility: "private" | "public";
  created_at: string;
  updated_at: string;
};

export type AudioAssetListResponse = {
  items: AudioAssetItem[];
};

export type ConversationAudioTranscriptionResponse = {
  text: string;
};

export const audioService = {
  uploadConversationAudio: async (
    conversationId: string,
    file: File
  ): Promise<ConversationAudioUploadResponse> => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await httpClient.post<ConversationAudioUploadResponse>(
      `/v1/conversations/${conversationId}/audio-uploads`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  },

  listAudioAssets: async (params?: { visibility?: "all" | "private" | "public"; limit?: number }): Promise<AudioAssetListResponse> => {
    const response = await httpClient.get<AudioAssetListResponse>(`/v1/audio-assets`, {
      params,
    });
    return response.data;
  },

  updateAudioAssetVisibility: async (audioId: string, visibility: "private" | "public"): Promise<AudioAssetItem> => {
    const response = await httpClient.put<AudioAssetItem>(`/v1/audio-assets/${audioId}/visibility`, {
      visibility,
    });
    return response.data;
  },

  deleteAudioAsset: async (audioId: string): Promise<void> => {
    await httpClient.delete(`/v1/audio-assets/${audioId}`);
  },

  transcribeConversationAudio: async (
    conversationId: string,
    file: File,
    params?: { model?: string | null; language?: string | null; prompt?: string | null }
  ): Promise<ConversationAudioTranscriptionResponse> => {
    const formData = new FormData();
    formData.append("file", file);
    const model = (params?.model ?? "").trim();
    const language = (params?.language ?? "").trim();
    const prompt = (params?.prompt ?? "").trim();
    if (model) formData.append("model", model);
    if (language) formData.append("language", language);
    if (prompt) formData.append("prompt", prompt);

    const response = await httpClient.post<ConversationAudioTranscriptionResponse>(
      `/v1/conversations/${conversationId}/audio-transcriptions`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  },
};
