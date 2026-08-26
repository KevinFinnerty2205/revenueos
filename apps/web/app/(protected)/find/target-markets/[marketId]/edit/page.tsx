import { ProspectTargetMarketBuilder } from "@/components/prospect-target-market";

export default async function EditTargetMarketPage({
  params,
}: {
  params: Promise<{ marketId: string }>;
}) {
  const { marketId } = await params;
  return <ProspectTargetMarketBuilder marketId={marketId} />;
}
