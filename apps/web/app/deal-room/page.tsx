import type { Metadata } from "next";
import { PublicDealRoom } from "@/components/public-deal-room";

export const metadata: Metadata = {
  title: "Secure Deal Room",
  description: "A secure, read-only customer Deal Room.",
  robots: { index: false, follow: false, noarchive: true },
};

export default function DealRoomPage() {
  return <PublicDealRoom />;
}
