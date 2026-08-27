import { Suspense } from "react";
import { CreatePresentationWizard } from "@/components/create-presentation-wizard";

export default function NewCreatePresentationPage() {
  return (
    <Suspense fallback={<p role="status">Loading presentation options…</p>}>
      <CreatePresentationWizard />
    </Suspense>
  );
}
