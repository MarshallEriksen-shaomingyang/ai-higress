export const composerModes = ["chat", "image"] as const;

export type ComposerMode = (typeof composerModes)[number];

export const composerModeLabelKeys: Record<ComposerMode, string> = {
  chat: "chat.image_gen.mode_chat",
  image: "chat.image_gen.mode_image",
};

export const composerModeCapabilities = {
  chat: {
    supportsStreaming: true,
    supportsAttachments: true,
    supportsModelParameters: true,
    hasSettingsDrawer: false,
  },
  image: {
    supportsStreaming: false,
    supportsAttachments: false,
    supportsModelParameters: false,
    hasSettingsDrawer: true,
    requiredModelCapability: "image_generation",
  },
} as const;

