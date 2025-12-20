import { ConversationPageClient } from "./components/conversation-page-client";

export default async function ConversationPage({
  params,
}: {
  params:
    | { assistant_id: string; conversation_id: string }
    | Promise<{ assistant_id: string; conversation_id: string }>;
}) {
  const resolvedParams = await params;
  return (
    <ConversationPageClient
      assistantId={resolvedParams.assistant_id}
      conversationId={resolvedParams.conversation_id}
    />
  );
}
