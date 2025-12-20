import React from "react";

import { ChatNavRail } from "./components/chat-nav-rail";
import { ChatLayoutRootClient } from "./components/chat-layout-root-client";

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <ChatNavRail />
      <div className="flex-1 h-full overflow-hidden">
        <ChatLayoutRootClient>{children}</ChatLayoutRootClient>
      </div>
    </div>
  );
}
