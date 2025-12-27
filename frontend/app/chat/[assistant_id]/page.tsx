import { ChatHomeClient } from "../components/chat-home-client";

export default async function AssistantPage({
  params,
}: {
  params: { assistant_id: string } | Promise<{ assistant_id: string }>;
}) {
  const resolvedParams = await params;
  return <ChatHomeClient assistantId={resolvedParams.assistant_id} />;
}
