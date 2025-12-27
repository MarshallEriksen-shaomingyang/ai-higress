"use client";

import type { ComposerTask } from "@/lib/chat/composer-tasks";
import type { UserInfo } from "@/lib/api-types";
import { ImageGenerationMessageItem } from "@/components/chat/image-generation-message-item";

export function ComposerTaskMessageItem({
  role,
  task,
  user,
}: {
  role: "user" | "assistant";
  task: ComposerTask;
  user?: UserInfo | null;
}) {
  switch (task.kind) {
    case "image_generation":
      return <ImageGenerationMessageItem role={role} task={task} user={user} />;
    default:
      return null;
  }
}

