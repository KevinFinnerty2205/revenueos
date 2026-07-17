import { PlaceholderPage } from "@/components/placeholder-page";

export default function AssistantPage() {
  return (
    <PlaceholderPage
      eyebrow="Sales Brain"
      title="Assistant"
      description="The future assistant will answer from authorised evidence and be explicit when information is unavailable."
      emptyTitle="No AI provider is connected"
      emptyDescription="This build makes no OpenAI calls, generates no answers and grants no model access to tools or customer data."
    />
  );
}
