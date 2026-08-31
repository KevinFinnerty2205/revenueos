const OPPORTUNITY_CHANGED_EVENT = "revenueos:opportunity-changed";

interface OpportunityChangedDetail {
  opportunityId: string;
}

export function notifyOpportunityChanged(opportunityId: string): void {
  window.dispatchEvent(
    new CustomEvent<OpportunityChangedDetail>(OPPORTUNITY_CHANGED_EVENT, {
      detail: { opportunityId },
    }),
  );
}

export function onOpportunityChanged(
  opportunityId: string,
  listener: () => void,
): () => void {
  const handle = (event: Event) => {
    if (
      event instanceof CustomEvent &&
      (event.detail as OpportunityChangedDetail | undefined)?.opportunityId ===
        opportunityId
    ) {
      listener();
    }
  };
  window.addEventListener(OPPORTUNITY_CHANGED_EVENT, handle);
  return () => window.removeEventListener(OPPORTUNITY_CHANGED_EVENT, handle);
}
