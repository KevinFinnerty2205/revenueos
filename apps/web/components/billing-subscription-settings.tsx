"use client";

import type {
  BillingCheckoutResponse,
  BillingHostedAction,
  BillingPlanOption,
  BillingProjection,
} from "@revenueos/shared";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value));
}

function operationKey(kind: string, target: string): string {
  const storageKey = `oryntela-billing:${kind}:${target}`;
  const existing = window.sessionStorage.getItem(storageKey);
  if (existing) return existing;
  const value = `web-${globalThis.crypto.randomUUID()}`;
  window.sessionStorage.setItem(storageKey, value);
  return value;
}

function clearOperationKey(kind: string, target: string): void {
  window.sessionStorage.removeItem(`oryntela-billing:${kind}:${target}`);
}

const planRank = {
  core: 0,
  growth: 1,
  complete: 2,
  enterprise: 3,
} as const;

export function BillingSubscriptionSettings() {
  const [billing, setBilling] = useState<BillingProjection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [hostedUrl, setHostedUrl] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const titleRef = useRef<HTMLHeadingElement>(null);

  const load = useCallback(async (signal: AbortSignal) => {
    setError(null);
    setBilling(
      await apiRequest<BillingProjection>("/api/v1/billing", { signal }),
    );
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void load(controller.signal).catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Billing information could not be loaded.",
          );
        }
      });
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load, retryKey]);

  const selfServiceOptions = useMemo(
    () =>
      billing?.checkoutOptions.filter(
        (
          option,
        ): option is BillingPlanOption & {
          billingInterval: "monthly" | "annual";
          amount: string;
        } =>
          option.selfServiceAvailable &&
          option.billingInterval !== null &&
          option.amount !== null,
      ) ?? [],
    [billing],
  );
  const selected = selfServiceOptions.find(
    (option) => `${option.planCode}:${option.billingInterval}` === selectedKey,
  );
  const canStartCheckout =
    billing?.subscription === null ||
    billing?.subscription.status === "cancelled";
  const canChangePlan =
    billing?.subscription?.status === "active" &&
    billing.subscription.cancelAtPeriodEnd !== true;
  const planSelectionAvailable = canStartCheckout || canChangePlan;
  const selectionKind = (() => {
    const subscription = billing?.subscription;
    if (!selected || !subscription || canStartCheckout) return "checkout";
    if (
      selected.planCode === subscription.planCode &&
      selected.billingInterval === subscription.billingInterval
    ) {
      return subscription.pendingPlanCode ? "keep-current" : "unchanged";
    }
    return planRank[selected.planCode] > planRank[subscription.planCode]
      ? "upgrade"
      : "scheduled";
  })();

  async function submitSelection(): Promise<void> {
    if (!selected) return;
    setBusy(true);
    setActionError(null);
    setHostedUrl(null);
    const target = `${selected.planCode}:${selected.billingInterval}`;
    try {
      if (!canStartCheckout) {
        const idempotencyKey = operationKey("plan-change", target);
        const result = await apiRequest<BillingHostedAction>(
          "/api/v1/billing/plan-change",
          {
            method: "POST",
            body: JSON.stringify({
              planCode: selected.planCode,
              billingInterval: selected.billingInterval,
              idempotencyKey,
            }),
          },
        );
        setActionMessage(result.message);
        if (result.status === "succeeded") {
          clearOperationKey("plan-change", target);
        }
        setRetryKey((value) => value + 1);
      } else {
        const result = await apiRequest<BillingCheckoutResponse>(
          "/api/v1/billing/checkout",
          {
            method: "POST",
            body: JSON.stringify({
              planCode: selected.planCode,
              billingInterval: selected.billingInterval,
              idempotencyKey: operationKey("checkout", target),
            }),
          },
        );
        setHostedUrl(result.checkoutUrl);
        setActionMessage(
          "Secure hosted checkout is ready. Payment is not confirmed until the provider webhook is reconciled.",
        );
      }
    } catch (reason: unknown) {
      setActionError(
        reason instanceof Error
          ? reason.message
          : "The billing request could not be completed.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function runAction(
    kind: "portal" | "cancel" | "reactivate",
  ): Promise<void> {
    setBusy(true);
    setActionError(null);
    setHostedUrl(null);
    try {
      const target = billing?.subscription?.id ?? "account";
      const idempotencyKey = operationKey(kind, target);
      const result = await apiRequest<BillingHostedAction>(
        `/api/v1/billing/${kind}`,
        {
          method: "POST",
          body: JSON.stringify({
            idempotencyKey,
          }),
        },
      );
      setActionMessage(result.message);
      setHostedUrl(result.hostedUrl);
      if (result.status === "succeeded") clearOperationKey(kind, target);
      if (kind !== "portal") setRetryKey((value) => value + 1);
    } catch (reason: unknown) {
      setActionError(
        reason instanceof Error
          ? reason.message
          : "The billing request could not be completed.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (error && !billing) {
    return (
      <section className="form-card" aria-labelledby="billing-operations-title">
        <h2 id="billing-operations-title" className="form-legend">
          Subscription &amp; invoices
        </h2>
        <p role="alert" className="mt-3 text-sm text-rose-800">
          {error}
        </p>
        <button
          type="button"
          className="secondary-button mt-4"
          onClick={() => setRetryKey((value) => value + 1)}
        >
          Try again
        </button>
      </section>
    );
  }

  if (!billing) {
    return (
      <section className="form-card" aria-labelledby="billing-operations-title">
        <h2 id="billing-operations-title" className="form-legend">
          Subscription &amp; invoices
        </h2>
        <p role="status" className="mt-3 text-sm text-slate-600">
          Loading billing information…
        </p>
      </section>
    );
  }

  const subscription = billing.subscription;

  return (
    <section
      className="form-card min-w-0 overflow-hidden"
      aria-labelledby="billing-operations-title"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
            Test billing operations
          </p>
          <h2
            ref={titleRef}
            id="billing-operations-title"
            className="form-legend mt-2"
          >
            Subscription &amp; invoices
          </h2>
        </div>
        <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-950">
          {billing.provider} · {billing.mode} mode only
        </span>
      </div>

      <p className="mt-4 text-sm leading-6 text-slate-700">{billing.message}</p>
      <p className="mt-2 text-xs leading-5 text-slate-500">
        Billed by {billing.legalEntityName}, ABN {billing.legalEntityAbn}.
        Hosted checkout keeps card details outside Oryntela.
      </p>

      {subscription ? (
        <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <Metric label="Subscription" value={subscription.planName} />
            <Metric
              label="Billing interval"
              value={subscription.billingInterval}
            />
            <Metric
              label="Status"
              value={subscription.status.replaceAll("_", " ")}
            />
          </div>
          {subscription.currentPeriodEnd ? (
            <p className="mt-4 text-sm text-slate-700">
              {subscription.cancelAtPeriodEnd
                ? `Access continues until ${formatDate(subscription.currentPeriodEnd)}.`
                : `Next renewal: ${formatDate(subscription.currentPeriodEnd)}.`}
            </p>
          ) : null}
          {subscription.paymentNeedsAttention ? (
            <p
              role="alert"
              className="mt-3 text-sm font-semibold text-amber-900"
            >
              {subscription.status === "unpaid"
                ? "Provider payment recovery has ended. Paid functionality is inactive, but your data is preserved. Open hosted billing management to resolve it."
                : subscription.status === "past_due"
                  ? "Payment recovery is in progress. Access and your data are preserved while the provider runs its bounded retry policy. Open hosted billing management to resolve it."
                  : "Payment is not confirmed. No new paid entitlement has been granted, and your data is preserved. Open hosted billing management to resolve it."}
            </p>
          ) : null}
          {subscription.pendingPlanCode ? (
            <p className="mt-3 text-sm text-slate-700">
              Change scheduled for next renewal: {subscription.pendingPlanCode}{" "}
              ({subscription.pendingBillingInterval}). No immediate proration.
            </p>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-3">
            {billing.portalAvailable ? (
              <button
                type="button"
                className="secondary-button"
                disabled={busy}
                onClick={() => void runAction("portal")}
              >
                Manage billing securely
              </button>
            ) : null}
            {subscription.cancelAtPeriodEnd ? (
              <button
                type="button"
                className="secondary-button"
                disabled={busy}
                onClick={() => void runAction("reactivate")}
              >
                Keep subscription
              </button>
            ) : subscription.status !== "cancelled" ? (
              <button
                type="button"
                className="secondary-button"
                disabled={busy}
                onClick={() => void runAction("cancel")}
              >
                Cancel at period end
              </button>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm font-semibold text-slate-950">
            Billing not configured / manually managed
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-700">
            A trial remains no-card with no automatic conversion or charge.
            Choose a plan only when you are ready to subscribe explicitly.
          </p>
        </div>
      )}

      <fieldset className="mt-6 min-w-0" disabled={!planSelectionAvailable}>
        <legend className="text-sm font-bold text-slate-950">
          {!planSelectionAvailable
            ? subscription?.paymentNeedsAttention
              ? "Resolve payment attention before changing plan"
              : "Keep the subscription before changing plan"
            : canStartCheckout
              ? "Choose a paid plan"
              : "Change plan"}
        </legend>
        <div className="mt-3 grid min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {selfServiceOptions.map((option) => {
            const key = `${option.planCode}:${option.billingInterval}`;
            return (
              <label
                key={key}
                className="min-w-0 cursor-pointer rounded-xl border border-slate-200 p-4 has-[:checked]:border-teal-700 has-[:checked]:ring-2 has-[:checked]:ring-teal-100"
              >
                <span className="flex items-start gap-3">
                  <input
                    type="radio"
                    name="billing-option"
                    value={key}
                    checked={selectedKey === key}
                    onChange={() => setSelectedKey(key)}
                    className="mt-1"
                  />
                  <span className="min-w-0">
                    <span className="block font-semibold text-slate-950">
                      {option.displayName} · {option.billingInterval}
                    </span>
                    <span className="mt-1 block text-sm leading-6 text-slate-700">
                      {option.paymentStatement}
                    </span>
                    <span className="mt-1 block text-xs text-slate-500">
                      Up to {option.includedUserLimit} users
                    </span>
                  </span>
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      {selected && planSelectionAvailable ? (
        <div className="mt-4 rounded-xl border border-teal-200 bg-teal-50 p-4">
          <p className="font-semibold text-slate-950">
            Review before continuing
          </p>
          <p className="mt-2 text-sm text-slate-700">
            {selected.displayName}: {selected.paymentStatement} No add-ons are
            included.{" "}
            {canStartCheckout
              ? "You will continue in hosted checkout."
              : selectionKind === "upgrade"
                ? "This higher-tier change takes effect immediately only after provider payment confirmation. The provider calculates and invoices the proration; Oryntela does not estimate it here."
                : selectionKind === "keep-current"
                  ? "This keeps the current plan and cancels the scheduled renewal change."
                  : selectionKind === "unchanged"
                    ? "This plan and billing interval are already active."
                    : "This lower-tier or interval change takes effect at the next renewal. Paid capabilities remain available until then, with no immediate proration."}
          </p>
          <button
            type="button"
            className="primary-button mt-4"
            disabled={busy || selectionKind === "unchanged"}
            onClick={() => void submitSelection()}
          >
            {busy
              ? "Preparing…"
              : canStartCheckout
                ? "Prepare secure checkout"
                : selectionKind === "upgrade"
                  ? "Confirm immediate upgrade"
                  : selectionKind === "keep-current"
                    ? "Keep current plan"
                    : selectionKind === "unchanged"
                      ? "Already active"
                      : "Schedule renewal change"}
          </button>
        </div>
      ) : null}

      {actionError ? (
        <p role="alert" className="mt-4 text-sm text-rose-800">
          {actionError}
        </p>
      ) : null}
      {actionMessage ? (
        <p role="status" className="mt-4 text-sm text-slate-700">
          {actionMessage}
        </p>
      ) : null}
      {hostedUrl ? (
        <a className="primary-button mt-3" href={hostedUrl} rel="noreferrer">
          Continue to hosted billing
        </a>
      ) : null}

      <div className="mt-7">
        <h3 className="text-sm font-bold text-slate-950">Invoice history</h3>
        {billing.invoices.length === 0 ? (
          <p role="status" className="mt-3 text-sm text-slate-600">
            No provider invoices have been reconciled.
          </p>
        ) : (
          <ul className="mt-3 grid min-w-0 gap-3" aria-label="Invoice history">
            {billing.invoices.map((invoice) => (
              <li
                key={invoice.id}
                className="flex min-w-0 flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 p-4"
              >
                <span className="min-w-0 text-sm text-slate-700">
                  <span className="block font-semibold text-slate-950">
                    {formatDate(invoice.invoiceDate)} · {invoice.status}
                  </span>
                  <span className="mt-1 block">
                    AUD ${invoice.amountDue} · paid AUD ${invoice.amountPaid}
                  </span>
                  {invoice.taxAmount ? (
                    <span className="mt-1 block">
                      Provider-reported tax: AUD ${invoice.taxAmount}
                    </span>
                  ) : null}
                </span>
                {invoice.hostedInvoiceUrl ? (
                  <a
                    className="secondary-button"
                    href={invoice.hostedInvoiceUrl}
                    rel="noreferrer"
                  >
                    View provider invoice
                  </a>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="mt-5 text-xs leading-5 text-slate-500">
        Enterprise uses a contact and manual commercial process. Production
        Credit packs and purchases are not available; the Credits section below
        is TEST-only infrastructure. GST presentation and provider tax settings
        require owner/accounting approval before live billing.
      </p>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
        {label}
      </p>
      <p className="mt-1 break-words font-semibold capitalize text-slate-950">
        {value}
      </p>
    </div>
  );
}
