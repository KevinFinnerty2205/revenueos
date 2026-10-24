import type { OpportunityStatus } from "@revenueos/shared";

const OPPORTUNITY_CHANGED_EVENT = "revenueos:opportunity-changed";

export interface OpportunityChangedDetail {
  opportunityId: string;
  status?: OpportunityStatus;
}

export function notifyOpportunityChanged(
  opportunityId: string,
  status?: OpportunityStatus,
): void {
  window.dispatchEvent(
    new CustomEvent<OpportunityChangedDetail>(OPPORTUNITY_CHANGED_EVENT, {
      detail: { opportunityId, status },
    }),
  );
}

export function onOpportunityChanged(
  opportunityId: string,
  listener: (detail: OpportunityChangedDetail) => void,
): () => void {
  const handle = (event: Event) => {
    if (
      event instanceof CustomEvent &&
      (event.detail as OpportunityChangedDetail | undefined)?.opportunityId ===
        opportunityId
    ) {
      listener(event.detail as OpportunityChangedDetail);
    }
  };
  window.addEventListener(OPPORTUNITY_CHANGED_EVENT, handle);
  return () => window.removeEventListener(OPPORTUNITY_CHANGED_EVENT, handle);
}
