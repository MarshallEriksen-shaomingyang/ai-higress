import { MESSAGE_MAX_LENGTH } from "./types";

export function composeMessageContent(text: string, imageDataUrls: string[]) {
  const trimmed = (text || "").trim();
  const urls = imageDataUrls.map((u) => (u || "").trim()).filter(Boolean);
  const composed = [trimmed, ...urls].filter(Boolean).join("\n\n");
  return composed;
}

export function isMessageTooLong(content: string) {
  return content.length > MESSAGE_MAX_LENGTH;
}

