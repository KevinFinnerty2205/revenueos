import { NextResponse } from "next/server";
import { assertWebRuntimeConfiguration } from "@/lib/deployment";

export const dynamic = "force-dynamic";

export function GET() {
  try {
    assertWebRuntimeConfiguration();
    return NextResponse.json(
      { status: "ready" },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return NextResponse.json(
      { status: "not_ready" },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
