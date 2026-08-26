import { ProspectTargetMarketDetail } from "@/components/prospect-target-market";

export default async function TargetMarketPage({
  params,
}: {
  params: Promise<{ marketId: string }>;
}) {
  const { marketId } = await params;
  return <ProspectTargetMarketDetail marketId={marketId} />;
}
