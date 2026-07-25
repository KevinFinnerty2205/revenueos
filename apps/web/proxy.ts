import { clerkMiddleware } from "@clerk/nextjs/server";
import {
  type NextFetchEvent,
  type NextRequest,
  NextResponse,
} from "next/server";

const handleClerkRequest = clerkMiddleware();

export default function proxy(request: NextRequest, event: NextFetchEvent) {
  const requestedMode =
    process.env.AUTH_MODE ?? process.env.NEXT_PUBLIC_AUTH_MODE;
  const clerkEnabled =
    requestedMode === "clerk" ||
    (requestedMode === undefined && process.env.NODE_ENV === "production");
  return clerkEnabled
    ? handleClerkRequest(request, event)
    : NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
