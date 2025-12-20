import { AssistantPageClient } from "./components/assistant-page-client";

export default async function AssistantPage({
  params,
}: {
  params: { assistant_id: string } | Promise<{ assistant_id: string }>;
}) {
  const resolvedParams = await params;
  return <AssistantPageClient assistantId={resolvedParams.assistant_id} />;
}
