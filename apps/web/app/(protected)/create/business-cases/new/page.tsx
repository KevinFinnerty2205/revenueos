import { Suspense } from "react";
import { BusinessCaseNew } from "@/components/business-case-new";

export default function NewBusinessCasePage() {
  return (
    <Suspense fallback={<p role="status">Loading Business Case options…</p>}>
      <BusinessCaseNew />
    </Suspense>
  );
}
