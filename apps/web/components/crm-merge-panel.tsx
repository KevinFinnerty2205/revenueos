"use client";

import type {
  CRMMergePreview,
  CRMMergeResult,
  CRMRecord,
} from "@revenueos/shared";
import { useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

export function CRMMergePanel({
  record,
  onMerged,
}: {
  record: CRMRecord;
  onMerged: () => Promise<void>;
}) {
  const [survivorId, setSurvivorId] = useState("");
  const [preview, setPreview] = useState<CRMMergePreview | null>(null);
  const [selections, setSelections] = useState<
    Record<string, "source" | "survivor">
  >({});
  const [confirmed, setConfirmed] = useState(false);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  if (
    record.entityType === "opportunity" ||
    !record.crmEnabled ||
    !record.canManage ||
    record.mode !== "native" ||
    record.archivedAt ||
    record.mergedIntoEntityId
  )
    return null;

  async function previewMerge() {
    setWorking(true);
    setMessage(null);
    try {
      const next = await apiRequest<CRMMergePreview>(
        "/api/v1/crm/merges/preview",
        {
          method: "POST",
          body: JSON.stringify({
            entityType: record.entityType,
            sourceEntityId: record.entityId,
            survivorEntityId: survivorId.trim(),
          }),
        },
      );
      setPreview(next);
      setSelections(
        Object.fromEntries(
          next.conflicts.map((conflict) => [conflict.fieldKey, "survivor"]),
        ),
      );
      setConfirmed(false);
      setMessage(
        next.blockedReasons.length
          ? "This merge is blocked. Resolve every blocker before previewing again."
          : "Merge preview complete. No records have changed.",
      );
    } catch (reason) {
      setPreview(null);
      setMessage(
        reason instanceof Error
          ? reason.message
          : "The merge could not be previewed.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function confirmMerge() {
    if (!preview || !confirmed || preview.blockedReasons.length) return;
    setWorking(true);
    setMessage(null);
    try {
      const result = await apiRequest<CRMMergeResult>(
        "/api/v1/crm/merges/confirm",
        {
          method: "POST",
          body: JSON.stringify({
            entityType: preview.entityType,
            sourceEntityId: preview.sourceEntityId,
            survivorEntityId: preview.survivorEntityId,
            previewFingerprint: preview.previewFingerprint,
            fieldSelection: selections,
            idempotencyKey: `web-merge-${globalThis.crypto.randomUUID()}`,
          }),
        },
      );
      setMessage(
        `Merge complete. This record now points to survivor ${result.survivorEntityId}.`,
      );
      setPreview(null);
      setConfirmed(false);
      await onMerged();
    } catch (reason) {
      setMessage(
        reason instanceof Error
          ? reason.message
          : "The merge could not be confirmed.",
      );
    } finally {
      setWorking(false);
    }
  }

  return (
    <details className="form-card group">
      <summary className="cursor-pointer list-none font-semibold text-slate-950 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2">
        <span className="flex items-center justify-between gap-4">
          <span>
            Merge a duplicate
            <span className="mt-1 block text-sm font-normal text-slate-600">
              Admin-only, previewed and irreversible. This record becomes the
              source tombstone.
            </span>
          </span>
          <span aria-hidden="true" className="text-teal-700">
            <span className="group-open:hidden">Show</span>
            <span className="hidden group-open:inline">Hide</span>
          </span>
        </span>
      </summary>
      <div className="mt-5 border-t border-slate-200 pt-5">
        <label className="text-sm font-semibold text-slate-700">
          Survivor {humanise(record.entityType)} ID
          <input
            className="form-input mt-2 font-mono"
            value={survivorId}
            onChange={(event) => {
              setSurvivorId(event.target.value);
              setPreview(null);
              setConfirmed(false);
            }}
            placeholder="00000000-0000-4000-8000-000000000000"
            aria-describedby="merge-survivor-help"
          />
        </label>
        <p id="merge-survivor-help" className="mt-2 text-xs text-slate-500">
          Copy the ID from the survivor record URL. RevenueOS verifies that both
          records belong to this organisation.
        </p>
        <button
          type="button"
          className="secondary-button mt-4"
          disabled={
            working ||
            survivorId.trim() === record.entityId ||
            !uuidLike(survivorId)
          }
          onClick={() => void previewMerge()}
        >
          {working ? "Checking…" : "Preview merge"}
        </button>

        {preview ? (
          <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-5">
            <h3 className="font-semibold text-amber-950">Merge impact</h3>
            {preview.blockedReasons.length ? (
              <div className="mt-3" role="alert">
                <p className="font-semibold text-rose-900">Merge blocked</p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-rose-900">
                  {preview.blockedReasons.map((reason) => (
                    <li key={reason}>{humanise(reason)}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <>
                <p className="mt-2 text-sm leading-6 text-amber-950">
                  Related Opportunities, Contacts, Interactions, Actions,
                  history and provenance move to the survivor. Suppression
                  remains restrictive. The source becomes an archived tombstone
                  with a survivor link.
                </p>
                {preview.conflicts.length ? (
                  <fieldset className="mt-5 space-y-4">
                    <legend className="font-semibold text-amber-950">
                      Choose every conflicting value
                    </legend>
                    {preview.conflicts.map((conflict) => (
                      <div
                        key={conflict.fieldKey}
                        className="rounded-xl border border-amber-200 bg-white p-4"
                      >
                        <p className="text-sm font-bold text-slate-900">
                          {humanise(
                            conflict.fieldKey.replace(
                              /^custom:/u,
                              "custom field ",
                            ),
                          )}
                        </p>
                        <div className="mt-3 grid gap-2 sm:grid-cols-2">
                          {(["survivor", "source"] as const).map((choice) => (
                            <label
                              key={choice}
                              className="flex min-h-11 items-start gap-2 rounded-lg border border-slate-200 p-3 text-sm text-slate-700"
                            >
                              <input
                                type="radio"
                                name={`merge-${conflict.fieldKey}`}
                                value={choice}
                                checked={
                                  selections[conflict.fieldKey] === choice
                                }
                                onChange={() => {
                                  setSelections((current) => ({
                                    ...current,
                                    [conflict.fieldKey]: choice,
                                  }));
                                  setConfirmed(false);
                                }}
                              />
                              <span>
                                <strong>{humanise(choice)}</strong>
                                <br />
                                {displayValue(
                                  choice === "source"
                                    ? conflict.sourceValue
                                    : conflict.survivorValue,
                                )}
                              </span>
                            </label>
                          ))}
                        </div>
                      </div>
                    ))}
                  </fieldset>
                ) : (
                  <p className="mt-4 text-sm text-amber-950">
                    There are no field conflicts; related records will still
                    move.
                  </p>
                )}
                <label className="mt-5 flex items-start gap-3 text-sm font-semibold text-amber-950">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4 accent-rose-700"
                    checked={confirmed}
                    onChange={(event) => setConfirmed(event.target.checked)}
                  />
                  I reviewed the survivor and understand this merge cannot be
                  undone.
                </label>
                <button
                  type="button"
                  className="mt-4 inline-flex min-h-11 items-center rounded-xl bg-rose-700 px-4 text-sm font-bold text-white hover:bg-rose-800 focus:outline-none focus:ring-2 focus:ring-rose-700 focus:ring-offset-2 disabled:opacity-50"
                  disabled={
                    working ||
                    !confirmed ||
                    Object.keys(selections).length !== preview.conflicts.length
                  }
                  onClick={() => void confirmMerge()}
                >
                  {working ? "Merging…" : "Merge into survivor"}
                </button>
              </>
            )}
          </div>
        ) : null}
        {message ? (
          <p role="status" className="mt-4 text-sm text-slate-700">
            {message}
          </p>
        ) : null}
      </div>
    </details>
  );
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not set";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function uuidLike(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu.test(
    value.trim(),
  );
}
