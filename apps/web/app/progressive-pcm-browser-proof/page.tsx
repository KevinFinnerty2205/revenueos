import { notFound } from "next/navigation";
import { ProgressivePcmBrowserProof } from "@/components/progressive-pcm-browser-proof";

export default function ProgressivePcmBrowserProofPage() {
  if (
    process.env.NODE_ENV === "production" ||
    process.env.PLAYWRIGHT_PROGRESSIVE_PCM_HARNESS !== "1"
  ) {
    notFound();
  }
  return <ProgressivePcmBrowserProof />;
}
