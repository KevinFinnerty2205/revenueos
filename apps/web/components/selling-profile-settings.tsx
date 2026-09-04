"use client";

import type {
  SellingOffering,
  SellingProfileContent,
  SellingProfileManagement,
} from "@revenueos/shared";
import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

const EMPTY_OFFERING: SellingOffering = {
  name: "",
  description: "",
  whoNormallyBuys: [],
  problemsSolved: [],
  intendedOutcomes: [],
  differentiators: [],
  competitorsAlternatives: [],
  approvedProof: [],
  approvedClaims: [],
};
const EMPTY_CONTENT: SellingProfileContent = {
  companyDescription: "",
  offerings: [{ ...EMPTY_OFFERING }],
};
const OPTIONAL_FIELDS: Array<{
  key: Exclude<keyof SellingOffering, "name" | "description">;
  label: string;
}> = [
  { key: "whoNormallyBuys", label: "Who normally buys" },
  { key: "problemsSolved", label: "Problems solved" },
  { key: "intendedOutcomes", label: "Intended outcomes" },
  { key: "differentiators", label: "Differentiators" },
  { key: "competitorsAlternatives", label: "Competitors and alternatives" },
  { key: "approvedProof", label: "Approved proof" },
  { key: "approvedClaims", label: "Approved claims" },
];

function copyContent(value: SellingProfileContent): SellingProfileContent {
  return {
    companyDescription: value.companyDescription,
    offerings: value.offerings.map((offering) => ({
      ...offering,
      whoNormallyBuys: [...offering.whoNormallyBuys],
      problemsSolved: [...offering.problemsSolved],
      intendedOutcomes: [...offering.intendedOutcomes],
      differentiators: [...offering.differentiators],
      competitorsAlternatives: [...offering.competitorsAlternatives],
      approvedProof: [...offering.approvedProof],
      approvedClaims: [...offering.approvedClaims],
    })),
  };
}

function lines(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function contentMatches(
  first: SellingProfileContent,
  second: SellingProfileContent,
): boolean {
  return JSON.stringify(first) === JSON.stringify(second);
}

export function SellingProfileSettings() {
  const [profile, setProfile] = useState<SellingProfileManagement | null>(null);
  const [content, setContent] = useState(() => copyContent(EMPTY_CONTENT));
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const draftHasUnsavedChanges = Boolean(
    profile?.draft && !contentMatches(content, profile.draft.content),
  );

  const apply = useCallback((next: SellingProfileManagement) => {
    setProfile(next);
    const source =
      next.draft?.content ?? next.current?.content ?? next.history[0]?.content;
    setContent(copyContent(source ?? EMPTY_CONTENT));
    setEditing(Boolean(next.draft) || next.status === "empty");
  }, []);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      apply(
        await apiRequest<SellingProfileManagement>("/api/v1/selling-profile", {
          signal,
        }),
      );
      setError(null);
    },
    [apply],
  );

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void load(controller.signal)
        .catch((reason: unknown) => {
          if (!(
            reason instanceof DOMException && reason.name === "AbortError"
          )) {
            setError(
              reason instanceof Error
                ? reason.message
                : "The Company & Selling Profile could not be loaded.",
            );
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load]);

  async function saveDraft() {
    if (!profile) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const next = profile.draft
        ? await apiRequest<SellingProfileManagement>(
            `/api/v1/selling-profile/revisions/${profile.draft.id}`,
            {
              method: "PATCH",
              body: JSON.stringify({
                expectedLockVersion: profile.draft.lockVersion,
                content,
              }),
            },
          )
        : await apiRequest<SellingProfileManagement>(
            "/api/v1/selling-profile/revisions",
            {
              method: "POST",
              body: JSON.stringify({
                idempotencyKey:
                  globalThis.crypto?.randomUUID?.() ?? `profile-${Date.now()}`,
                content,
              }),
            },
          );
      apply(next);
      setMessage(
        `Draft revision ${next.draft?.revisionNumber ?? ""} saved. It is not current until approved.`,
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The profile draft could not be saved.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function transition(action: "approve" | "retire") {
    const revision = action === "approve" ? profile?.draft : profile?.current;
    if (!revision) return;
    setBusy(true);
    setError(null);
    try {
      const next = await apiRequest<SellingProfileManagement>(
        `/api/v1/selling-profile/revisions/${revision.id}/${action}`,
        {
          method: "POST",
          ...(action === "approve"
            ? {
                body: JSON.stringify({
                  expectedLockVersion: revision.lockVersion,
                }),
              }
            : {}),
        },
      );
      apply(next);
      setMessage(
        action === "approve"
          ? `Revision ${next.current?.revisionNumber ?? ""} is now the approved current context.`
          : "The profile was retired. Members no longer receive it as current context.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : `The profile could not be ${action}d.`,
      );
    } finally {
      setBusy(false);
    }
  }

  function updateOffering(index: number, next: SellingOffering) {
    setContent((current) => ({
      ...current,
      offerings: current.offerings.map((item, position) =>
        position === index ? next : item,
      ),
    }));
  }

  if (loading)
    return (
      <section id="company-selling-profile" className="form-card">
        <p role="status">Loading Company &amp; Selling Profile…</p>
      </section>
    );
  if (!profile)
    return (
      <section
        id="company-selling-profile"
        className="form-card border-rose-200 bg-rose-50"
      >
        <h2 className="form-legend">Company &amp; Selling Profile</h2>
        <p role="alert" className="mt-3 text-sm text-rose-900">
          {error ?? "The profile is unavailable."}
        </p>
        <button
          type="button"
          className="secondary-button mt-4"
          onClick={() => void load()}
        >
          Try again
        </button>
      </section>
    );

  return (
    <section
      id="company-selling-profile"
      className="form-card"
      aria-labelledby="selling-profile-title"
    >
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
        Admin control
      </p>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="selling-profile-title" className="form-legend">
            Company &amp; Selling Profile
          </h2>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">
            Maintain approved context about your company and offers. Members may
            use only the approved current revision.
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold uppercase text-slate-700">
          {profile.status}
        </span>
      </div>
      <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
        <p className="font-bold">Organisation-approved context only</p>
        <p className="mt-1">
          This is not customer Evidence, prospect research, CRM truth, or proof
          about a specific buyer. Add only company-approved material and avoid
          personal or sensitive customer data.
        </p>
      </div>
      {error ? (
        <p role="alert" className="mt-4 text-sm text-rose-800">
          {error}
        </p>
      ) : null}
      {message ? (
        <p role="status" className="mt-4 text-sm font-semibold text-teal-800">
          {message}
        </p>
      ) : null}

      {profile.current ? (
        <article className="mt-6 rounded-2xl border border-teal-200 bg-teal-50 p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase text-teal-800">
                Approved current
              </p>
              <h3 className="mt-1 text-lg font-bold">
                Revision {profile.current.revisionNumber}
              </h3>
            </div>
            <button
              type="button"
              className="secondary-button"
              disabled={busy}
              onClick={() => void transition("retire")}
            >
              Retire current profile
            </button>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-700">
            {profile.current.content.companyDescription}
          </p>
          <ul className="mt-3 space-y-2 text-sm text-slate-700">
            {profile.current.content.offerings.map((offering) => (
              <li key={offering.name}>
                <strong>{offering.name}:</strong> {offering.description}
              </li>
            ))}
          </ul>
        </article>
      ) : null}

      {!editing && !profile.draft ? (
        <button
          type="button"
          className="primary-button mt-6"
          disabled={busy}
          onClick={() => setEditing(true)}
        >
          Create new draft
        </button>
      ) : null}

      {editing ? (
        <form
          className="mt-7 border-t border-slate-200 pt-7"
          onSubmit={(event) => {
            event.preventDefault();
            void saveDraft();
          }}
        >
          <h3 className="text-lg font-bold">
            {profile.draft
              ? `Draft revision ${profile.draft.revisionNumber}`
              : "New draft"}
          </h3>
          <p className="mt-1 text-sm text-slate-600">
            Saving does not make this content current. Approval is a separate
            action.
          </p>
          <label className="mt-5 block text-sm font-bold text-slate-800">
            Company description
            <textarea
              className="form-control mt-2 min-h-28"
              required
              maxLength={2000}
              value={content.companyDescription}
              onChange={(event) =>
                setContent((current) => ({
                  ...current,
                  companyDescription: event.target.value,
                }))
              }
            />
            <span className="mt-1 block text-xs font-normal text-slate-500">
              Do not paste customer records, personal information or hidden
              instructions.
            </span>
          </label>
          <div className="mt-6 space-y-5">
            {content.offerings.map((offering, index) => (
              <fieldset
                key={index}
                className="rounded-2xl border border-slate-200 p-4 sm:p-5"
              >
                <legend className="px-2 font-bold">Offering {index + 1}</legend>
                <label className="block text-sm font-bold">
                  Offering name
                  <input
                    className="form-control mt-2"
                    required
                    maxLength={120}
                    value={offering.name}
                    onChange={(event) =>
                      updateOffering(index, {
                        ...offering,
                        name: event.target.value,
                      })
                    }
                  />
                </label>
                <label className="mt-4 block text-sm font-bold">
                  Concise description
                  <textarea
                    className="form-control mt-2 min-h-24"
                    required
                    maxLength={800}
                    value={offering.description}
                    onChange={(event) =>
                      updateOffering(index, {
                        ...offering,
                        description: event.target.value,
                      })
                    }
                  />
                </label>
                <details className="mt-4 rounded-xl bg-slate-50 p-4">
                  <summary className="cursor-pointer font-bold">
                    Optional approved selling context
                  </summary>
                  <div className="mt-4 grid gap-4 sm:grid-cols-2">
                    {OPTIONAL_FIELDS.map((field) => (
                      <label key={field.key} className="text-sm font-bold">
                        {field.label}
                        <span className="block text-xs font-normal text-slate-500">
                          One approved item per line
                        </span>
                        <textarea
                          className="form-control mt-2 min-h-24"
                          maxLength={4007}
                          value={offering[field.key].join("\n")}
                          onChange={(event) =>
                            updateOffering(index, {
                              ...offering,
                              [field.key]: lines(event.target.value),
                            })
                          }
                        />
                      </label>
                    ))}
                  </div>
                </details>
                {content.offerings.length > 1 ? (
                  <button
                    type="button"
                    className="secondary-button mt-4"
                    onClick={() =>
                      setContent((current) => ({
                        ...current,
                        offerings: current.offerings.filter(
                          (_, position) => position !== index,
                        ),
                      }))
                    }
                  >
                    Remove offering {index + 1}
                  </button>
                ) : null}
              </fieldset>
            ))}
          </div>
          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              className="secondary-button"
              disabled={busy || content.offerings.length >= 8}
              onClick={() =>
                setContent((current) => ({
                  ...current,
                  offerings: [...current.offerings, { ...EMPTY_OFFERING }],
                }))
              }
            >
              Add offering
            </button>
            <button type="submit" className="primary-button" disabled={busy}>
              {busy ? "Saving…" : profile.draft ? "Save draft" : "Create draft"}
            </button>
            {profile.draft ? (
              <button
                type="button"
                className="secondary-button"
                disabled={busy || draftHasUnsavedChanges}
                aria-describedby={
                  draftHasUnsavedChanges
                    ? "selling-profile-approval-help"
                    : undefined
                }
                onClick={() => void transition("approve")}
              >
                Approve as current
              </button>
            ) : null}
          </div>
          {profile.draft && draftHasUnsavedChanges ? (
            <p
              id="selling-profile-approval-help"
              className="mt-3 text-sm text-amber-800"
            >
              Save this draft before approving your latest changes.
            </p>
          ) : null}
        </form>
      ) : null}

      {profile.history.length ? (
        <details className="mt-7 border-t border-slate-200 pt-6">
          <summary className="cursor-pointer font-bold">
            Revision history ({profile.history.length})
          </summary>
          <ol className="mt-4 space-y-3">
            {profile.history.map((revision) => (
              <li
                key={revision.id}
                className="rounded-xl border border-slate-200 p-4 text-sm"
              >
                <div className="flex flex-wrap justify-between gap-2">
                  <strong>Revision {revision.revisionNumber}</strong>
                  <span className="uppercase text-slate-600">
                    {revision.state}
                  </span>
                </div>
                <p className="mt-2 text-slate-600">
                  {revision.content.companyDescription}
                </p>
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </section>
  );
}
