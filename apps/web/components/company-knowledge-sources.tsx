"use client";

import type {
  CompanyKnowledgeSource,
  CompanyKnowledgeSourceKind,
} from "@revenueos/shared";
import { FormEvent, useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

type SourceMode = "website" | "text";

function idempotencyKey(prefix: string): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? `${prefix}-${crypto.randomUUID()}`
    : `${prefix}-${Date.now()}`;
}

export function CompanyKnowledgeSources() {
  const [sources, setSources] = useState<CompanyKnowledgeSource[]>([]);
  const [mode, setMode] = useState<SourceMode>("website");
  const [label, setLabel] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [sourceText, setSourceText] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const [authorityConfirmed, setAuthorityConfirmed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const retryRef = useRef<{ fingerprint: string; key: string } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<CompanyKnowledgeSource[]>(
      "/api/v1/selling-profile/knowledge-sources",
      { signal: controller.signal },
    )
      .then((items) => {
        setSources(items);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(
          reason instanceof Error
            ? reason.message
            : "Company knowledge sources could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    const sourceKind: CompanyKnowledgeSourceKind =
      mode === "website"
        ? "website"
        : fileName
          ? "text_file"
          : "supporting_text";
    const payload = {
      sourceKind,
      label: label.trim(),
      websiteUrl: mode === "website" ? websiteUrl.trim() : null,
      sourceText: mode === "text" ? sourceText.trim() : null,
      authorityConfirmed,
    };
    const fingerprint = JSON.stringify(payload);
    const retry =
      retryRef.current?.fingerprint === fingerprint
        ? retryRef.current
        : {
            fingerprint,
            key: idempotencyKey("company-knowledge"),
          };
    retryRef.current = retry;
    try {
      const saved = await apiRequest<CompanyKnowledgeSource>(
        "/api/v1/selling-profile/knowledge-sources",
        {
          method: "POST",
          body: JSON.stringify({ ...payload, idempotencyKey: retry.key }),
        },
      );
      setSources((current) => [saved, ...current]);
      setLabel("");
      setWebsiteUrl("");
      setSourceText("");
      setFileName(null);
      setAuthorityConfirmed(false);
      retryRef.current = null;
      setMessage(saved.safeMessage);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The company knowledge source could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function removeSource(source: CompanyKnowledgeSource) {
    if (
      !window.confirm(
        `Delete “${source.label}”? It will no longer be available for company-profile review.`,
      )
    ) {
      return;
    }
    setError(null);
    setMessage(null);
    try {
      await apiRequest(
        `/api/v1/selling-profile/knowledge-sources/${source.id}`,
        { method: "DELETE" },
      );
      setSources((current) => current.filter((item) => item.id !== source.id));
      setMessage("Company knowledge source deleted.");
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The company knowledge source could not be deleted.",
      );
    }
  }

  async function selectFile(file: File | undefined) {
    if (!file) return;
    if (file.type && file.type !== "text/plain") {
      setError("Choose a plain-text .txt file.");
      return;
    }
    const text = await file.text();
    if (text.length > 40_000) {
      setError("Supporting text must be 40,000 characters or fewer.");
      return;
    }
    setSourceText(text);
    setFileName(file.name);
    if (!label) setLabel(file.name);
    setError(null);
  }

  return (
    <section className="form-card" aria-labelledby="knowledge-sources-title">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
        Step 1 · Sources
      </p>
      <div className="mt-2 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl">
          <h2 id="knowledge-sources-title" className="form-legend">
            Add company knowledge
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Save your company website and add approved supporting text. Website
            ingestion is externally gated in this build: saving an address does
            not mean Oryntela has fetched or learned it.
          </p>
        </div>
        <span className="w-fit rounded-full border border-brand-secondary/20 bg-brand-secondary/10 px-3 py-1 text-xs font-bold text-brand-primary">
          No external processing
        </span>
      </div>

      <div
        className="mt-6 inline-flex rounded-xl border border-slate-200 bg-slate-50 p-1"
        aria-label="Knowledge source type"
        role="group"
      >
        {(["website", "text"] as const).map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={mode === value}
            className={`min-h-10 rounded-lg px-4 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-brand-focus ${
              mode === value
                ? "bg-white text-brand-primary shadow-sm"
                : "text-slate-600"
            }`}
            onClick={() => {
              setMode(value);
              setError(null);
            }}
          >
            {value === "website" ? "Company website" : "Text or .txt file"}
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="mt-5 grid gap-4">
        <label className="grid gap-2 text-sm font-bold text-slate-800">
          Source label
          <input
            className="form-control"
            required
            maxLength={200}
            value={label}
            onChange={(event) => setLabel(event.target.value)}
            placeholder={
              mode === "website" ? "Company website" : "Product overview"
            }
          />
        </label>
        {mode === "website" ? (
          <label className="grid gap-2 text-sm font-bold text-slate-800">
            Website address
            <input
              className="form-control"
              required
              type="url"
              maxLength={2000}
              value={websiteUrl}
              onChange={(event) => setWebsiteUrl(event.target.value)}
              placeholder="https://example.test"
            />
          </label>
        ) : (
          <>
            <label className="grid gap-2 text-sm font-bold text-slate-800">
              Supporting text
              <textarea
                className="form-control min-h-36 py-3"
                required
                maxLength={40_000}
                value={sourceText}
                onChange={(event) => {
                  setSourceText(event.target.value);
                  setFileName(null);
                }}
                placeholder="Paste approved product, audience, objection or outcome context."
              />
            </label>
            <label className="w-fit text-sm font-bold text-slate-800">
              Or choose a .txt file
              <input
                className="mt-2 block max-w-full text-sm font-normal"
                type="file"
                accept=".txt,text/plain"
                onChange={(event) => void selectFile(event.target.files?.[0])}
              />
            </label>
          </>
        )}
        <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
          <input
            type="checkbox"
            className="mt-1 size-5"
            checked={authorityConfirmed}
            onChange={(event) => setAuthorityConfirmed(event.target.checked)}
          />
          <span>
            I confirm this is company-approved material that I am authorised to
            store. It contains no customer records, credentials or hidden data.
          </span>
        </label>
        <div>
          <button
            type="submit"
            className="primary-button"
            disabled={saving || !authorityConfirmed}
          >
            {saving ? "Saving source…" : "Save source"}
          </button>
        </div>
      </form>

      {error ? (
        <p
          role="alert"
          className="mt-4 rounded-xl bg-rose-50 p-4 text-sm text-rose-900"
        >
          {error}
        </p>
      ) : null}
      {message ? (
        <p
          role="status"
          className="mt-4 rounded-xl bg-brand-secondary/10 p-4 text-sm text-brand-primary"
        >
          {message}
        </p>
      ) : null}

      <div className="mt-7 border-t border-slate-200 pt-6">
        <h3 className="font-semibold text-slate-950">Saved sources</h3>
        {loading ? (
          <p role="status" className="mt-3 text-sm text-slate-600">
            Loading sources…
          </p>
        ) : sources.length === 0 ? (
          <p className="mt-3 text-sm text-slate-600">
            No company knowledge sources have been saved yet.
          </p>
        ) : (
          <ul className="mt-4 grid gap-3">
            {sources.map((source) => (
              <li
                key={source.id}
                className="rounded-2xl border border-slate-200 p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-slate-950">
                      {source.label}
                    </p>
                    <p className="mt-1 text-xs font-bold uppercase tracking-wide text-slate-500">
                      {humanise(source.sourceKind)} ·{" "}
                      {humanise(source.processingStatus)}
                    </p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                    {source.characterCount > 0
                      ? `${source.characterCount.toLocaleString()} characters`
                      : "Address only"}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-600">
                  {source.safeMessage}
                </p>
                {source.websiteUrl ? (
                  <p className="mt-3 break-all rounded-xl bg-slate-50 p-3 text-sm text-slate-700">
                    {source.websiteUrl}
                  </p>
                ) : null}
                {source.sourceText ? (
                  <details className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                    <summary className="cursor-pointer text-sm font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-focus">
                      Review stored source text
                    </summary>
                    <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                      {source.sourceText}
                    </p>
                  </details>
                ) : null}
                <div className="mt-4 flex flex-wrap gap-3">
                  <a className="secondary-button" href="#company-understanding">
                    Review company understanding
                  </a>
                  <button
                    type="button"
                    className="secondary-button border-rose-200 text-rose-800"
                    onClick={() => void removeSource(source)}
                  >
                    Delete source
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
