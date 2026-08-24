"use client";

import type {
  Contact,
  DocumentEmailEvidenceCapabilities,
  DocumentEvidenceSource,
  DocumentEvidenceType,
  DocumentSourceOwnership,
  EmailEvidenceDirection,
  EmailEvidenceSource,
  EmailEvidenceSourceType,
  EntityPage,
  OpportunitySourceEvidenceItem,
  SourceEvidenceCandidate,
  SourceEvidenceReviewResponse,
} from "@revenueos/shared";
import {
  ChangeEvent,
  FormEvent,
  ReactNode,
  useCallback,
  useEffect,
  useState,
} from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import { formatMeetingDate } from "@/lib/meetings";

type Source = DocumentEvidenceSource | EmailEvidenceSource;
type ReviewChoice = "accept" | "reject";

export function CustomerEvidencePanel({
  opportunityId,
  companyId,
}: {
  opportunityId: string;
  companyId: string | null;
}) {
  const [items, setItems] = useState<OpportunitySourceEvidenceItem[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [capabilities, setCapabilities] =
    useState<DocumentEmailEvidenceCapabilities | null>(null);
  const [mode, setMode] = useState<"document" | "email" | null>(null);
  const [source, setSource] = useState<Source | null>(null);
  const [choices, setChoices] = useState<Record<string, ReviewChoice>>({});
  const [statements, setStatements] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadItems = useCallback(
    (signal?: AbortSignal) =>
      apiRequest<OpportunitySourceEvidenceItem[]>(
        `/api/v1/evidence/opportunities/${opportunityId}`,
        { signal },
      ),
    [opportunityId],
  );

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      loadItems(controller.signal),
      apiRequest<DocumentEmailEvidenceCapabilities>(
        "/api/v1/evidence/capabilities",
        { signal: controller.signal },
      ),
    ])
      .then(([loadedItems, loadedCapabilities]) => {
        setItems(loadedItems);
        setCapabilities(loadedCapabilities);
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
            : "Customer evidence could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [companyId, loadItems]);

  async function openEmail() {
    setMode("email");
    setSource(null);
    setError(null);
    setMessage(null);
    try {
      const contactPage = await apiRequest<EntityPage<Contact>>(
        "/api/v1/contacts?pageSize=100",
      );
      setContacts(
        contactPage.items.filter(
          (contact) => companyId === null || contact.companyId === companyId,
        ),
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Customer Contacts could not be loaded.",
      );
    }
  }

  function prepareReview(nextSource: Source) {
    setSource(nextSource);
    setChoices({});
    setStatements(
      Object.fromEntries(
        nextSource.candidates.map((candidate) => [
          candidate.id,
          candidate.statement,
        ]),
      ),
    );
  }

  async function review() {
    if (!source) return;
    const pending = source.candidates.filter(
      (candidate) => candidate.reviewState === "pending",
    );
    if (pending.some((candidate) => choices[candidate.id] === undefined)) {
      setError("Accept or reject every finding before finishing the review.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const collection =
        sourceKind(source) === "document" ? "documents" : "emails";
      const result = await apiRequest<SourceEvidenceReviewResponse>(
        `/api/v1/evidence/${collection}/${source.id}/review`,
        {
          method: "POST",
          body: JSON.stringify({
            decisions: pending.map((candidate) => ({
              candidateId: candidate.id,
              decision: choices[candidate.id],
              ...(choices[candidate.id] === "accept"
                ? { statement: statements[candidate.id] }
                : {}),
            })),
            idempotencyKey: crypto.randomUUID(),
          }),
        },
      );
      setMessage(
        `${result.acceptedCount} finding${result.acceptedCount === 1 ? "" : "s"} added with source labels to the Opportunity Workspace and Revenue Brain.`,
      );
      setSource(null);
      setMode(null);
      setItems(await loadItems());
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The evidence review could not be saved.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="customer-evidence-title" className="form-card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
            Source-aware evidence
          </p>
          <h2 id="customer-evidence-title" className="form-legend mt-2">
            Add customer evidence
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            Add only material you are authorised to process. AI findings stay in
            review until you accept or reject every item, and seller-created
            content remains clearly separated from customer-direct evidence.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {capabilities?.documentEvidence ? (
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                setMode("document");
                setSource(null);
                setError(null);
                setMessage(null);
              }}
            >
              Add document
            </button>
          ) : null}
          {capabilities?.emailEvidence ? (
            <button
              type="button"
              className="secondary-button"
              onClick={() => void openEmail()}
            >
              Paste email
            </button>
          ) : null}
        </div>
      </div>

      {capabilities &&
      !capabilities.documentEvidence &&
      !capabilities.emailEvidence ? (
        <p role="status" className="mt-5 text-sm text-slate-600">
          Document and email evidence are not enabled for this workspace.
        </p>
      ) : capabilities ? (
        <p className="mt-4 text-xs leading-5 text-slate-500">
          {capabilities.safeMessage}
        </p>
      ) : null}

      {message ? (
        <p
          role="status"
          className="mt-5 rounded-xl bg-teal-50 p-4 text-sm font-semibold text-teal-900"
        >
          {message}
        </p>
      ) : null}
      {error ? (
        <p
          role="alert"
          className="mt-5 rounded-xl bg-rose-50 p-4 text-sm font-semibold text-rose-900"
        >
          {error}
        </p>
      ) : null}

      {mode === "document" && !source ? (
        <DocumentForm
          companyId={companyId}
          opportunityId={opportunityId}
          busy={busy}
          onCancel={() => setMode(null)}
          onError={setError}
          onBusy={setBusy}
          onReady={prepareReview}
        />
      ) : null}
      {mode === "email" && !source ? (
        <EmailForm
          companyId={companyId}
          opportunityId={opportunityId}
          contacts={contacts}
          busy={busy}
          onCancel={() => setMode(null)}
          onError={setError}
          onBusy={setBusy}
          onReady={prepareReview}
        />
      ) : null}
      {source ? (
        <ReviewPanel
          source={source}
          choices={choices}
          statements={statements}
          busy={busy}
          onChoice={(candidateId, choice) =>
            setChoices((current) => ({ ...current, [candidateId]: choice }))
          }
          onStatement={(candidateId, statement) =>
            setStatements((current) => ({
              ...current,
              [candidateId]: statement,
            }))
          }
          onAcceptAll={() =>
            setChoices(
              Object.fromEntries(
                source.candidates
                  .filter((candidate) => candidate.reviewState === "pending")
                  .map((candidate) => [candidate.id, "accept"]),
              ),
            )
          }
          onReview={() => void review()}
        />
      ) : null}

      <div className="mt-7 border-t border-slate-100 pt-6">
        <h3 className="font-semibold text-slate-950">Accepted evidence</h3>
        {loading ? (
          <p role="status" className="mt-3 text-sm text-slate-600">
            Loading document and email evidence…
          </p>
        ) : items.length === 0 ? (
          <p className="mt-3 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-600">
            No reviewed document or email evidence yet.
          </p>
        ) : (
          <ul className="mt-4 grid gap-3 lg:grid-cols-2">
            {items.map((item) => (
              <li
                key={item.evidenceId}
                className="rounded-2xl border border-slate-200 p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs font-bold uppercase tracking-wide text-teal-800">
                    {humanise(item.category)} · {humanise(item.sourceKind)}
                  </p>
                  <time
                    dateTime={item.occurredAt}
                    className="text-xs text-slate-500"
                  >
                    {formatMeetingDate(item.occurredAt)}
                  </time>
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-800">
                  {item.statement}
                </p>
                <p className="mt-2 text-xs font-semibold text-slate-600">
                  {item.sourceLabel} · {humanise(item.sourceType)} ·{" "}
                  {humanise(item.supportClass)}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {item.location.reference}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function DocumentForm({
  companyId,
  opportunityId,
  busy,
  onCancel,
  onError,
  onBusy,
  onReady,
}: EvidenceFormProps<DocumentEvidenceSource>) {
  const [file, setFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState<DocumentEvidenceType>("rfp");
  const [ownership, setOwnership] =
    useState<DocumentSourceOwnership>("customer_provided");
  const [documentAt, setDocumentAt] = useState(localDateTime());
  const [authority, setAuthority] = useState(false);
  const [processing, setProcessing] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || !authority || !processing) {
      onError(
        "Choose a file and confirm both authority and external processing.",
      );
      return;
    }
    if (file.size > 15_000_000) {
      onError("Documents must be 15 MB or smaller.");
      return;
    }
    onBusy(true);
    onError(null);
    try {
      const buffer = await file.arrayBuffer();
      const bytes = new Uint8Array(buffer);
      const mimeType =
        file.type === "application/pdf" ? "application/pdf" : "text/plain";
      const created = await apiRequest<DocumentEvidenceSource>(
        "/api/v1/evidence/documents",
        {
          method: "POST",
          body: JSON.stringify({
            companyId,
            opportunityId,
            documentType,
            sourceOwnership: ownership,
            filename: file.name,
            mimeType,
            contentBase64: encodeBase64(bytes),
            checksumSha256: await sha256(buffer),
            documentAt: new Date(documentAt).toISOString(),
            authorityConfirmed: true,
            externalProcessingAcknowledged: true,
            idempotencyKey: crypto.randomUUID(),
          }),
        },
      );
      const processed = await apiRequest<DocumentEvidenceSource>(
        `/api/v1/evidence/documents/${created.id}/process`,
        {
          method: "POST",
          body: JSON.stringify({ idempotencyKey: crypto.randomUUID() }),
        },
      );
      onReady(processed);
    } catch (requestError: unknown) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "The document could not be processed.",
      );
    } finally {
      onBusy(false);
    }
  }

  return (
    <form
      onSubmit={(event) => void submit(event)}
      className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-5"
    >
      <fieldset disabled={busy} className="grid gap-4 sm:grid-cols-2">
        <legend className="font-semibold text-slate-950">
          Add document evidence
        </legend>
        <label className="sm:col-span-2 text-sm font-semibold text-slate-800">
          PDF or TXT file
          <input
            type="file"
            accept=".pdf,.txt,application/pdf,text/plain"
            required
            onChange={(event: ChangeEvent<HTMLInputElement>) =>
              setFile(event.target.files?.[0] ?? null)
            }
            className="mt-2 block w-full rounded-xl border border-slate-300 bg-white p-3 text-sm"
          />
        </label>
        <SelectField
          label="Document type"
          value={documentType}
          onChange={(value) => setDocumentType(value as DocumentEvidenceType)}
          options={documentTypes}
        />
        <SelectField
          label="Who supplied it?"
          value={ownership}
          onChange={(value) => setOwnership(value as DocumentSourceOwnership)}
          options={ownershipTypes}
        />
        <label className="text-sm font-semibold text-slate-800">
          Document date
          <input
            type="datetime-local"
            required
            value={documentAt}
            onChange={(event) => setDocumentAt(event.target.value)}
            className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3"
          />
        </label>
        <div className="sm:col-span-2 space-y-3">
          <ConsentCheckbox checked={authority} onChange={setAuthority}>
            I confirm I am authorised to use this document.
          </ConsentCheckbox>
          <ConsentCheckbox checked={processing} onChange={setProcessing}>
            I understand the text may be sent to the configured external AI
            service for extraction.
          </ConsentCheckbox>
        </div>
        <FormActions
          busy={busy}
          onCancel={onCancel}
          label="Upload and review"
        />
      </fieldset>
    </form>
  );
}

function EmailForm({
  companyId,
  opportunityId,
  contacts,
  busy,
  onCancel,
  onError,
  onBusy,
  onReady,
}: EvidenceFormProps<EmailEvidenceSource> & { contacts: Contact[] }) {
  const [sourceType, setSourceType] =
    useState<EmailEvidenceSourceType>("manually_pasted");
  const [direction, setDirection] = useState<EmailEvidenceDirection>("unknown");
  const [senderContactId, setSenderContactId] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [messageAt, setMessageAt] = useState(localDateTime());
  const [authority, setAuthority] = useState(false);
  const [processing, setProcessing] = useState(false);

  function changeSourceType(value: string) {
    const next = value as EmailEvidenceSourceType;
    setSourceType(next);
    if (next === "customer_sent") setDirection("inbound");
    if (next === "salesperson_sent") setDirection("outbound");
    if (next === "internal_forward") setDirection("internal");
    if (next !== "customer_sent") setSenderContactId("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!authority || !processing) {
      onError(
        "Confirm both authority and external processing before continuing.",
      );
      return;
    }
    onBusy(true);
    onError(null);
    try {
      const created = await apiRequest<EmailEvidenceSource>(
        "/api/v1/evidence/emails",
        {
          method: "POST",
          body: JSON.stringify({
            companyId,
            opportunityId,
            sourceType,
            direction,
            senderContactId: senderContactId || null,
            subject: subject.trim() || null,
            body,
            messageAt: new Date(messageAt).toISOString(),
            authorityConfirmed: true,
            externalProcessingAcknowledged: true,
            idempotencyKey: crypto.randomUUID(),
          }),
        },
      );
      const processed = await apiRequest<EmailEvidenceSource>(
        `/api/v1/evidence/emails/${created.id}/process`,
        {
          method: "POST",
          body: JSON.stringify({ idempotencyKey: crypto.randomUUID() }),
        },
      );
      onReady(processed);
    } catch (requestError: unknown) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "The email could not be processed.",
      );
    } finally {
      onBusy(false);
    }
  }

  return (
    <form
      onSubmit={(event) => void submit(event)}
      className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-5"
    >
      <fieldset disabled={busy} className="grid gap-4 sm:grid-cols-2">
        <legend className="font-semibold text-slate-950">
          Paste email evidence
        </legend>
        <SelectField
          label="Email source"
          value={sourceType}
          onChange={changeSourceType}
          options={emailSourceTypes}
        />
        <SelectField
          label="Direction"
          value={direction}
          onChange={(value) => setDirection(value as EmailEvidenceDirection)}
          options={emailDirections}
          disabled={sourceType !== "manually_pasted"}
        />
        {sourceType === "customer_sent" ? (
          <label className="text-sm font-semibold text-slate-800">
            Verified customer sender
            <select
              value={senderContactId}
              onChange={(event) => setSenderContactId(event.target.value)}
              className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3"
            >
              <option value="">Unknown sender</option>
              {contacts.map((contact) => (
                <option key={contact.id} value={contact.id}>
                  {contact.firstName} {contact.lastName}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <label className="text-sm font-semibold text-slate-800">
          Message date
          <input
            type="datetime-local"
            required
            value={messageAt}
            onChange={(event) => setMessageAt(event.target.value)}
            className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3"
          />
        </label>
        <label className="sm:col-span-2 text-sm font-semibold text-slate-800">
          Subject (optional)
          <input
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            maxLength={500}
            className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3"
          />
        </label>
        <label className="sm:col-span-2 text-sm font-semibold text-slate-800">
          Plain-text email
          <textarea
            required
            value={body}
            onChange={(event) => setBody(event.target.value)}
            rows={8}
            maxLength={200000}
            className="mt-2 block w-full rounded-xl border border-slate-300 bg-white p-3"
          />
        </label>
        <div className="sm:col-span-2 space-y-3">
          <ConsentCheckbox checked={authority} onChange={setAuthority}>
            I confirm I am authorised to use this email.
          </ConsentCheckbox>
          <ConsentCheckbox checked={processing} onChange={setProcessing}>
            I understand the email text may be sent to the configured external
            AI service for extraction.
          </ConsentCheckbox>
        </div>
        <FormActions
          busy={busy}
          onCancel={onCancel}
          label="Analyse and review"
        />
      </fieldset>
    </form>
  );
}

function ReviewPanel({
  source,
  choices,
  statements,
  busy,
  onChoice,
  onStatement,
  onAcceptAll,
  onReview,
}: {
  source: Source;
  choices: Record<string, ReviewChoice>;
  statements: Record<string, string>;
  busy: boolean;
  onChoice: (candidateId: string, choice: ReviewChoice) => void;
  onStatement: (candidateId: string, statement: string) => void;
  onAcceptAll: () => void;
  onReview: () => void;
}) {
  const pending = source.candidates.filter(
    (candidate) => candidate.reviewState === "pending",
  );
  const ready = pending.every(
    (candidate) =>
      choices[candidate.id] === "reject" ||
      (choices[candidate.id] === "accept" &&
        (statements[candidate.id] ?? candidate.statement).trim().length > 0),
  );
  return (
    <section
      aria-labelledby="source-review-title"
      className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 id="source-review-title" className="font-semibold text-slate-950">
            Review every AI finding
          </h3>
          <p className="mt-1 text-sm text-slate-700">
            Source: {sourceLabel(source)}. AI interpretation is not accepted
            evidence until you finish this review.
          </p>
        </div>
        {pending.length > 0 ? (
          <button
            type="button"
            className="secondary-button"
            disabled={busy}
            onClick={onAcceptAll}
          >
            Accept all
          </button>
        ) : null}
      </div>
      {pending.length === 0 ? (
        <p className="mt-4 text-sm text-slate-700">
          No candidate findings were extracted. Finish the review to close this
          source.
        </p>
      ) : (
        <ul className="mt-5 space-y-4">
          {pending.map((candidate) => (
            <CandidateReviewCard
              key={candidate.id}
              candidate={candidate}
              choice={choices[candidate.id]}
              statement={statements[candidate.id] ?? candidate.statement}
              busy={busy}
              onChoice={onChoice}
              onStatement={onStatement}
            />
          ))}
        </ul>
      )}
      <button
        type="button"
        className="primary-button mt-5"
        disabled={busy || !ready}
        onClick={onReview}
      >
        {busy ? "Saving review…" : "Finish review"}
      </button>
    </section>
  );
}

function CandidateReviewCard({
  candidate,
  choice,
  statement,
  busy,
  onChoice,
  onStatement,
}: {
  candidate: SourceEvidenceCandidate;
  choice?: ReviewChoice;
  statement: string;
  busy: boolean;
  onChoice: (id: string, choice: ReviewChoice) => void;
  onStatement: (id: string, value: string) => void;
}) {
  return (
    <li className="rounded-xl border border-amber-200 bg-white p-4">
      <p className="text-xs font-bold uppercase tracking-wide text-amber-800">
        {humanise(candidate.category)} · {candidate.sourceLocation.reference}
      </p>
      <label className="mt-3 block text-sm font-semibold text-slate-800">
        Finding
        <textarea
          value={statement}
          disabled={busy || choice === "reject"}
          onChange={(event) => onStatement(candidate.id, event.target.value)}
          rows={3}
          maxLength={1000}
          className="mt-2 block w-full rounded-xl border border-slate-300 p-3 font-normal"
        />
      </label>
      <p className="mt-2 text-xs text-slate-500">
        {candidate.sourceLabel} · {humanise(candidate.originClass)} ·
        AI-inferred
      </p>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          aria-pressed={choice === "accept"}
          disabled={busy}
          onClick={() => onChoice(candidate.id, "accept")}
          className={
            choice === "accept" ? "primary-button" : "secondary-button"
          }
        >
          Accept
        </button>
        <button
          type="button"
          aria-pressed={choice === "reject"}
          disabled={busy}
          onClick={() => onChoice(candidate.id, "reject")}
          className={
            choice === "reject"
              ? "rounded-lg bg-rose-800 px-4 py-2 text-sm font-bold text-white"
              : "secondary-button"
          }
        >
          Reject
        </button>
      </div>
    </li>
  );
}

interface EvidenceFormProps<T extends Source> {
  companyId: string | null;
  opportunityId: string;
  busy: boolean;
  onCancel: () => void;
  onError: (message: string | null) => void;
  onBusy: (busy: boolean) => void;
  onReady: (source: T) => void;
}

function SelectField({
  label,
  value,
  options,
  disabled = false,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly string[];
  disabled?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="text-sm font-semibold text-slate-800">
      {label}
      <select
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {humanise(option)}
          </option>
        ))}
      </select>
    </label>
  );
}

function ConsentCheckbox({
  checked,
  onChange,
  children,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children: ReactNode;
}) {
  return (
    <label className="flex gap-3 text-sm leading-6 text-slate-700">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-1 h-4 w-4"
      />{" "}
      <span>{children}</span>
    </label>
  );
}

function FormActions({
  busy,
  onCancel,
  label,
}: {
  busy: boolean;
  onCancel: () => void;
  label: string;
}) {
  return (
    <div className="sm:col-span-2 flex flex-wrap gap-3">
      <button type="submit" className="primary-button" disabled={busy}>
        {busy ? "Processing…" : label}
      </button>
      <button
        type="button"
        className="secondary-button"
        disabled={busy}
        onClick={onCancel}
      >
        Cancel
      </button>
    </div>
  );
}

function sourceKind(source: Source): "document" | "email" {
  return "documentType" in source ? "document" : "email";
}

function sourceLabel(source: Source): string {
  return "filename" in source
    ? source.filename
    : source.subjectPresent
      ? "Email with subject"
      : "Email without subject";
}

function localDateTime(): string {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 16);
}

async function sha256(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (value) =>
    value.toString(16).padStart(2, "0"),
  ).join("");
}

function encodeBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 32_768) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 32_768));
  }
  return btoa(binary);
}

const documentTypes = [
  "proposal",
  "rfp",
  "rfq",
  "requirements",
  "contract",
  "sow",
  "pricing",
  "procurement",
  "security_questionnaire",
  "implementation_plan",
  "technical_specification",
  "customer_presentation",
  "sales_material",
  "other",
] as const;
const ownershipTypes = [
  "customer_provided",
  "salesperson_provided",
  "jointly_created",
  "externally_generated",
  "unknown",
] as const;
const emailSourceTypes = [
  "manually_pasted",
  "customer_sent",
  "salesperson_sent",
  "internal_forward",
] as const;
const emailDirections = ["unknown", "inbound", "outbound", "internal"] as const;
