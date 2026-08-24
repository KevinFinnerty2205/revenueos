"use client";

import type {
  InteractionLifecycleStatus,
  InteractionType,
  VisualCandidateEvidence,
  VisualEvidence,
  VisualReviewResponse,
  VisualSourceOwnership,
  VisualType,
  VisualUploadCreateResponse,
} from "@revenueos/shared";
import {
  type ChangeEvent,
  type DragEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { apiBlob, apiRequest, apiUpload } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

type ReviewDecision = { decision: "accept" | "reject"; statement: string };

const VISUAL_TYPES: VisualType[] = [
  "whiteboard",
  "workshop_output",
  "architecture_diagram",
  "handwritten_notes",
  "agenda",
  "business_card",
  "presentation_slide",
  "presentation_deck_page",
  "customer_document_photo",
  "site_photo",
  "product_photo",
  "screenshot",
  "other",
];
const OWNERSHIP: VisualSourceOwnership[] = [
  "customer_created",
  "salesperson_created",
  "jointly_created",
  "unknown_origin",
];

function requestKey(prefix: string): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? `${prefix}-${crypto.randomUUID()}`
    : `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function sha256(file: File): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    await file.arrayBuffer(),
  );
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

function initialDecisions(
  candidates: VisualCandidateEvidence[],
): Record<string, ReviewDecision> {
  return Object.fromEntries(
    candidates
      .filter((candidate) => candidate.reviewState === "pending")
      .map((candidate) => [
        candidate.id,
        { decision: "accept", statement: candidate.statement },
      ]),
  );
}

function quickType(interactionType: InteractionType): VisualType {
  if (interactionType === "presentation") return "presentation_slide";
  if (interactionType === "site_visit") return "site_photo";
  if (interactionType === "workshop") return "whiteboard";
  return "whiteboard";
}

export function VisualEvidenceCapture({
  interactionId,
  interactionType,
  lifecycleStatus,
}: {
  interactionId: string;
  interactionType: InteractionType;
  lifecycleStatus: InteractionLifecycleStatus;
}) {
  const [visuals, setVisuals] = useState<VisualEvidence[] | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [visualType, setVisualType] = useState<VisualType>(
    quickType(interactionType),
  );
  const [sourceOwnership, setSourceOwnership] =
    useState<VisualSourceOwnership>("unknown_origin");
  const [contextLabel, setContextLabel] = useState("");
  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [progress, setProgress] = useState(0);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Record<string, ReviewDecision>>(
    {},
  );
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const previewUrlRef = useRef<string | null>(null);

  const load = useCallback(async () => {
    const loaded = await apiRequest<VisualEvidence[]>(
      `/api/v1/interactions/${interactionId}/visual-evidence`,
    );
    setVisuals(loaded);
    const awaiting = loaded.find(
      (visual) => visual.processingStatus === "review",
    );
    if (awaiting) {
      setReviewingId(awaiting.id);
      setDecisions(initialDecisions(awaiting.candidates));
    }
  }, [interactionId]);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<VisualEvidence[]>(
      `/api/v1/interactions/${interactionId}/visual-evidence`,
      { signal: controller.signal },
    )
      .then((loaded) => {
        setVisuals(loaded);
        const awaiting = loaded.find(
          (visual) => visual.processingStatus === "review",
        );
        if (awaiting) {
          setReviewingId(awaiting.id);
          setDecisions(initialDecisions(awaiting.candidates));
        }
      })
      .catch((requestError: unknown) => {
        if (
          requestError instanceof DOMException &&
          requestError.name === "AbortError"
        ) {
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Visual evidence could not be loaded.",
        );
      });
    return () => controller.abort();
  }, [interactionId]);

  useEffect(
    () => () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
    },
    [],
  );

  function selectFile(next: File | null) {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
    }
    const nextPreviewUrl = next ? URL.createObjectURL(next) : null;
    previewUrlRef.current = nextPreviewUrl;
    setPreviewUrl(nextPreviewUrl);
    setFile(next);
  }

  function chooseFile(next: File | null) {
    setError(null);
    setMessage(null);
    if (!next) return;
    if (!["image/jpeg", "image/png"].includes(next.type)) {
      setError(
        "Choose a JPEG or PNG image. Other file types are not accepted.",
      );
      return;
    }
    if (next.size > 10_000_000) {
      setError("Choose an image smaller than 10 MB.");
      return;
    }
    selectFile(next);
    setProgress(0);
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    chooseFile(event.target.files?.[0] ?? null);
    event.target.value = "";
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    chooseFile(event.dataTransfer.files[0] ?? null);
  }

  async function uploadAndAnalyse() {
    if (!file || !consentConfirmed) {
      setError("Choose an image and confirm you are authorised to share it.");
      return;
    }
    setWorking(true);
    setError(null);
    setMessage(null);
    try {
      setProgress(10);
      const checksum = await sha256(file);
      setProgress(25);
      const created = await apiRequest<VisualUploadCreateResponse>(
        `/api/v1/interactions/${interactionId}/visual-evidence/uploads`,
        {
          method: "POST",
          body: JSON.stringify({
            visualType,
            sourceOwnership,
            contextLabel: contextLabel.trim() || null,
            filename: file.name,
            mimeType: file.type,
            byteSize: file.size,
            checksumSha256: checksum,
            capturedAt: new Date(file.lastModified || Date.now()).toISOString(),
            consentConfirmed: true,
            idempotencyKey: requestKey("visual-upload"),
          }),
        },
      );
      setProgress(45);
      await apiUpload(created.uploadUrl, file, file.type);
      setProgress(70);
      await apiRequest<VisualEvidence>(
        `/api/v1/interactions/${interactionId}/visual-evidence/${created.id}/complete`,
        {
          method: "POST",
          body: JSON.stringify({
            checksumSha256: checksum,
            idempotencyKey: requestKey("visual-complete"),
          }),
        },
      );
      setProgress(85);
      const processed = await apiRequest<VisualEvidence>(
        `/api/v1/interactions/${interactionId}/visual-evidence/${created.id}/process`,
        {
          method: "POST",
          body: JSON.stringify({
            idempotencyKey: requestKey("visual-process"),
          }),
        },
      );
      setProgress(100);
      selectFile(null);
      setConsentConfirmed(false);
      setContextLabel("");
      if (processed.processingStatus === "review") {
        setReviewingId(processed.id);
        setDecisions(initialDecisions(processed.candidates));
        setMessage(
          "Image analysed. Review every suggested item before it updates RevenueOS.",
        );
      } else {
        setMessage(
          processed.sourceOwnership === "salesperson_created"
            ? "Image saved as presentation context. Seller-authored material was not treated as a buying signal."
            : "Image saved. No reviewable evidence was suggested.",
        );
      }
      await load();
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The image could not be uploaded and analysed.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function retry(visual: VisualEvidence) {
    setWorking(true);
    setError(null);
    try {
      const processed = await apiRequest<VisualEvidence>(
        `/api/v1/interactions/${interactionId}/visual-evidence/${visual.id}/process`,
        {
          method: "POST",
          body: JSON.stringify({ idempotencyKey: requestKey("visual-retry") }),
        },
      );
      if (processed.processingStatus === "review") {
        setReviewingId(processed.id);
        setDecisions(initialDecisions(processed.candidates));
      }
      await load();
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Visual analysis could not be retried.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function finishReview(visual: VisualEvidence) {
    const pending = visual.candidates.filter(
      (candidate) => candidate.reviewState === "pending",
    );
    if (pending.some((candidate) => !decisions[candidate.id])) {
      setError("Review every suggested item before finishing.");
      return;
    }
    setWorking(true);
    setError(null);
    try {
      const reviewed = await apiRequest<VisualReviewResponse>(
        `/api/v1/interactions/${interactionId}/visual-evidence/${visual.id}/review`,
        {
          method: "POST",
          body: JSON.stringify({
            decisions: pending.map((candidate) => ({
              candidateId: candidate.id,
              decision: decisions[candidate.id]?.decision,
              statement:
                decisions[candidate.id]?.decision === "accept"
                  ? decisions[candidate.id]?.statement
                  : null,
            })),
            idempotencyKey: requestKey("visual-review"),
          }),
        },
      );
      setReviewingId(null);
      setDecisions({});
      setMessage(
        reviewed.interactionUpdated
          ? "Reviewed visual evidence was added to Interaction Intelligence and Revenue Brain."
          : "Review saved. This visual remains context only and did not create buying signals.",
      );
      await load();
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The visual review could not be saved.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function deleteVisual(visual: VisualEvidence) {
    if (
      !window.confirm(`Delete ${visual.filename} and its derived evidence?`)
    ) {
      return;
    }
    setWorking(true);
    setError(null);
    try {
      const response = await apiRequest<{
        deleted: boolean;
        retryRequired: boolean;
      }>(`/api/v1/interactions/${interactionId}/visual-evidence/${visual.id}`, {
        method: "DELETE",
      });
      setMessage(
        response.deleted
          ? "Visual and its current derived evidence were deleted."
          : "Deletion needs to be retried because private storage is temporarily unavailable.",
      );
      await load();
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The visual could not be deleted.",
      );
    } finally {
      setWorking(false);
    }
  }

  const reviewing =
    visuals?.find((visual) => visual.id === reviewingId) ?? null;
  const captureDisabled = lifecycleStatus === "cancelled";

  return (
    <section aria-labelledby="visual-evidence-title" className="form-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
            Browser visual capture
          </p>
          <h2 id="visual-evidence-title" className="form-legend mt-2">
            Visual evidence
          </h2>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">
          Private storage
        </span>
      </div>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
        Take a photo or choose an image you are authorised to share. RevenueOS
        strips location metadata, keeps the original private, and requires your
        review before AI-suggested evidence updates intelligence.
      </p>

      {interactionType === "presentation" ? (
        <div className="mt-4 rounded-2xl border border-indigo-200 bg-indigo-50 p-4 text-sm leading-6 text-indigo-950">
          <p>
            Add a customer question photo, whiteboard, or presentation context.
            Slides created by the seller remain presentation context and are
            never treated as customer-confirmed buying signals.
          </p>
          <div
            className="mt-3 flex flex-wrap gap-2"
            aria-label="Presentation visual choices"
          >
            <button
              type="button"
              className="secondary-button"
              disabled={captureDisabled}
              onClick={() => {
                setVisualType("screenshot");
                setSourceOwnership("customer_created");
              }}
            >
              Add customer question photo
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={captureDisabled}
              onClick={() => {
                setVisualType("whiteboard");
                setSourceOwnership("customer_created");
              }}
            >
              Add whiteboard or photo
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={captureDisabled}
              onClick={() => {
                setVisualType("presentation_slide");
                setSourceOwnership("salesperson_created");
              }}
            >
              Add presentation context
            </button>
          </div>
        </div>
      ) : null}
      {interactionType === "site_visit" ? (
        <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
          Site photos are labelled as observed evidence. They are not treated as
          customer-confirmed facts.
        </div>
      ) : null}

      {!captureDisabled ? (
        <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.8fr)]">
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png"
              onChange={onFileChange}
              className="sr-only"
              aria-label="Choose an image"
            />
            <input
              id={`visual-camera-${interactionId}`}
              type="file"
              accept="image/jpeg,image/png"
              capture="environment"
              onChange={onFileChange}
              className="sr-only"
            />
            <div
              role="button"
              tabIndex={0}
              onDragOver={(event) => event.preventDefault()}
              onDrop={onDrop}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  fileInputRef.current?.click();
                }
              }}
              onClick={() => fileInputRef.current?.click()}
              className="flex min-h-44 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 p-6 text-center focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2"
            >
              <span className="font-bold text-slate-900">
                Choose or drop a JPEG or PNG
              </span>
              <span className="mt-2 text-sm text-slate-600">Maximum 10 MB</span>
            </div>
            <label
              htmlFor={`visual-camera-${interactionId}`}
              className="secondary-button mt-3 inline-flex cursor-pointer"
            >
              Take a photo
            </label>
          </div>

          <div className="space-y-4">
            {previewUrl ? (
              <div>
                {/* The object URL exists only after local selection and before upload confirmation. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={previewUrl}
                  alt="Selected visual preview"
                  className="max-h-64 w-full rounded-2xl border border-slate-200 object-contain"
                />
                <button
                  type="button"
                  className="mt-2 text-sm font-bold text-red-800 underline underline-offset-4 focus:outline-none focus:ring-2 focus:ring-red-700 focus:ring-offset-2"
                  onClick={() => {
                    selectFile(null);
                    setProgress(0);
                  }}
                >
                  Remove selected image
                </button>
              </div>
            ) : (
              <div className="flex min-h-36 items-center justify-center rounded-2xl bg-slate-100 p-4 text-sm text-slate-500">
                Preview appears before anything is uploaded.
              </div>
            )}
            <label className="block text-sm font-bold text-slate-800">
              Visual type
              <select
                value={visualType}
                onChange={(event) =>
                  setVisualType(event.target.value as VisualType)
                }
                className="form-input mt-2"
              >
                {VISUAL_TYPES.map((value) => (
                  <option key={value} value={value}>
                    {humanise(value)}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-bold text-slate-800">
              Who created the source?
              <select
                value={sourceOwnership}
                onChange={(event) =>
                  setSourceOwnership(
                    event.target.value as VisualSourceOwnership,
                  )
                }
                className="form-input mt-2"
              >
                {OWNERSHIP.map((value) => (
                  <option key={value} value={value}>
                    {humanise(value)}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-bold text-slate-800">
              Context label (optional)
              <input
                value={contextLabel}
                maxLength={200}
                onChange={(event) => setContextLabel(event.target.value)}
                className="form-input mt-2"
                placeholder="For example: customer Q&A whiteboard"
              />
            </label>
            {visualType === "business_card" ? (
              <p className="rounded-xl bg-amber-50 p-3 text-xs leading-5 text-amber-950">
                Business cards can suggest contact details only. Nothing is
                saved to Contacts and no role is inferred until you confirm it.
              </p>
            ) : null}
            <label className="flex items-start gap-3 text-sm leading-6 text-slate-700">
              <input
                type="checkbox"
                checked={consentConfirmed}
                onChange={(event) => setConsentConfirmed(event.target.checked)}
                className="mt-1 h-5 w-5 rounded border-slate-400 text-teal-700 focus:ring-teal-600"
              />
              I am authorised to upload this image and understand that it may be
              sent to the configured external visual-analysis service.
            </label>
            <button
              type="button"
              className="primary-button"
              disabled={!file || !consentConfirmed || working}
              onClick={() => void uploadAndAnalyse()}
            >
              {working ? "Working…" : "Upload and prepare review"}
            </button>
            {progress > 0 ? (
              <div>
                <label
                  htmlFor={`visual-progress-${interactionId}`}
                  className="text-xs font-bold text-slate-600"
                >
                  Upload and processing progress
                </label>
                <progress
                  id={`visual-progress-${interactionId}`}
                  value={progress}
                  max={100}
                  className="mt-2 block w-full"
                >
                  {progress}%
                </progress>
              </div>
            ) : null}
          </div>
        </div>
      ) : (
        <p className="mt-5 rounded-xl bg-slate-100 p-4 text-sm text-slate-700">
          Visual capture is unavailable for a cancelled interaction.
        </p>
      )}

      {error ? (
        <p
          role="alert"
          className="mt-5 rounded-xl bg-red-50 p-4 text-sm text-red-900"
        >
          {error}
        </p>
      ) : null}
      {message ? (
        <p
          role="status"
          className="mt-5 rounded-xl bg-teal-50 p-4 text-sm text-teal-950"
        >
          {message}
        </p>
      ) : null}

      {reviewing ? (
        <VisualReview
          visual={reviewing}
          decisions={decisions}
          working={working}
          onChange={(candidateId, decision) =>
            setDecisions((current) => ({ ...current, [candidateId]: decision }))
          }
          onAcceptAll={() =>
            setDecisions(initialDecisions(reviewing.candidates))
          }
          onFinish={() => void finishReview(reviewing)}
        />
      ) : null}

      <div className="mt-8 border-t border-slate-200 pt-6">
        <h3 className="font-semibold text-slate-950">Saved visuals</h3>
        {visuals === null ? (
          <p role="status" className="mt-3 text-sm text-slate-600">
            Loading saved visuals…
          </p>
        ) : visuals.length === 0 ? (
          <p className="mt-3 text-sm text-slate-600">
            No visual evidence added.
          </p>
        ) : (
          <ul className="mt-4 grid gap-4 md:grid-cols-2">
            {visuals.map((visual) => (
              <li
                key={visual.id}
                className="rounded-2xl border border-slate-200 p-4"
              >
                <PrivateVisualPreview visual={visual} />
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-bold text-slate-700">
                    {humanise(visual.visualType)}
                  </span>
                  <span className="rounded-full bg-teal-50 px-2 py-1 text-xs font-bold text-teal-800">
                    {humanise(visual.processingStatus)}
                  </span>
                </div>
                <p className="mt-2 truncate text-sm font-semibold text-slate-900">
                  {visual.filename}
                </p>
                <p className="mt-1 text-xs leading-5 text-slate-600">
                  {humanise(visual.sourceOwnership)} ·{" "}
                  {visual.sourceOwnership === "salesperson_created" &&
                  visual.processingStatus === "completed"
                    ? "Seller material · context only"
                    : visual.processingStatus === "completed" &&
                        visual.candidates.length > 0
                      ? "AI-interpreted, user-reviewed"
                      : visual.processingStatus === "completed"
                        ? "No reviewable evidence suggested"
                        : "AI-interpreted items require user review"}
                </p>
                {visual.candidates.length > 0 ? (
                  <ul
                    className="mt-3 space-y-2"
                    aria-label={`Evidence history for ${visual.filename}`}
                  >
                    {visual.candidates.map((candidate) => (
                      <li
                        key={candidate.id}
                        className="rounded-xl bg-slate-50 p-3 text-xs leading-5 text-slate-700"
                      >
                        <p className="font-bold uppercase tracking-wide text-slate-500">
                          {humanise(candidate.category)} ·{" "}
                          {humanise(candidate.supportClassification)}
                        </p>
                        <p className="mt-1 text-sm text-slate-800">
                          {candidate.statement}
                        </p>
                        <p className="mt-1 font-semibold text-teal-800">
                          {candidate.reviewState === "accepted"
                            ? "Accepted · AI-interpreted, user-reviewed"
                            : candidate.reviewState === "rejected"
                              ? "Rejected · not used downstream"
                              : "Review required"}
                        </p>
                      </li>
                    ))}
                  </ul>
                ) : null}
                <div className="mt-3 flex flex-wrap gap-2">
                  {visual.processingStatus === "failed" ||
                  visual.processingStatus === "uploaded" ? (
                    <button
                      type="button"
                      className="secondary-button"
                      disabled={working}
                      onClick={() => void retry(visual)}
                    >
                      Retry analysis
                    </button>
                  ) : null}
                  {visual.processingStatus === "review" ? (
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => {
                        setReviewingId(visual.id);
                        setDecisions(initialDecisions(visual.candidates));
                      }}
                    >
                      Review suggestions
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="text-sm font-bold text-red-800 underline underline-offset-4 focus:outline-none focus:ring-2 focus:ring-red-700 focus:ring-offset-2"
                    disabled={working}
                    onClick={() => void deleteVisual(visual)}
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function VisualReview({
  visual,
  decisions,
  working,
  onChange,
  onAcceptAll,
  onFinish,
}: {
  visual: VisualEvidence;
  decisions: Record<string, ReviewDecision>;
  working: boolean;
  onChange: (candidateId: string, decision: ReviewDecision) => void;
  onAcceptAll: () => void;
  onFinish: () => void;
}) {
  const candidates = visual.candidates.filter(
    (candidate) => candidate.reviewState === "pending",
  );
  return (
    <section
      aria-labelledby={`visual-review-${visual.id}`}
      className="mt-8 rounded-2xl border border-indigo-200 bg-indigo-50 p-5"
    >
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-indigo-700">
        AI-generated · user review required
      </p>
      <h3
        id={`visual-review-${visual.id}`}
        className="mt-2 text-xl font-semibold text-slate-950"
      >
        Review suggested evidence
      </h3>
      <p className="mt-2 text-sm leading-6 text-slate-700">
        Confirm, edit, or reject every suggestion. Extracted text is bounded and
        remains a suggestion until you accept it.
      </p>
      <div className="mt-4 max-w-sm">
        <PrivateVisualPreview visual={visual} />
      </div>
      <button
        type="button"
        className="secondary-button mt-4"
        onClick={onAcceptAll}
      >
        Accept all suggestions
      </button>
      <ul className="mt-4 space-y-4">
        {candidates.map((candidate) => {
          const decision = decisions[candidate.id] ?? {
            decision: "accept" as const,
            statement: candidate.statement,
          };
          return (
            <li
              key={candidate.id}
              className="rounded-2xl bg-white p-4 shadow-sm"
            >
              <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
                {humanise(candidate.category)} ·{" "}
                {humanise(candidate.supportClassification)}
              </p>
              <label className="mt-3 block text-sm font-bold text-slate-800">
                Suggested statement
                <textarea
                  value={decision.statement}
                  maxLength={1000}
                  rows={3}
                  disabled={decision.decision === "reject"}
                  onChange={(event) =>
                    onChange(candidate.id, {
                      ...decision,
                      statement: event.target.value,
                    })
                  }
                  className="form-input mt-2"
                />
              </label>
              <div className="mt-3 flex flex-wrap gap-4">
                <label className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                  <input
                    type="radio"
                    name={`visual-decision-${candidate.id}`}
                    checked={decision.decision === "accept"}
                    onChange={() =>
                      onChange(candidate.id, {
                        decision: "accept",
                        statement: decision.statement || candidate.statement,
                      })
                    }
                  />
                  Accept
                </label>
                <label className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                  <input
                    type="radio"
                    name={`visual-decision-${candidate.id}`}
                    checked={decision.decision === "reject"}
                    onChange={() =>
                      onChange(candidate.id, {
                        decision: "reject",
                        statement: decision.statement,
                      })
                    }
                  />
                  Reject
                </label>
              </div>
            </li>
          );
        })}
      </ul>
      <button
        type="button"
        className="primary-button mt-5"
        disabled={working || candidates.length === 0}
        onClick={onFinish}
      >
        {working ? "Saving review…" : "Finish review"}
      </button>
    </section>
  );
}

function PrivateVisualPreview({ visual }: { visual: VisualEvidence }) {
  const [source, setSource] = useState<string | null>(null);
  useEffect(() => {
    if (!visual.downloadUrl) return;
    let objectUrl: string | null = null;
    let active = true;
    apiBlob(visual.downloadUrl)
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setSource(objectUrl);
      })
      .catch(() => setSource(null));
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [visual.downloadUrl]);
  return source ? (
    // The source is a short-lived in-memory object URL loaded through an authenticated grant.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={source}
      alt={visual.contextLabel ?? humanise(visual.visualType)}
      className="h-40 w-full rounded-xl bg-slate-100 object-contain"
    />
  ) : (
    <div className="flex h-40 items-center justify-center rounded-xl bg-slate-100 text-sm text-slate-500">
      Private preview unavailable
    </div>
  );
}
