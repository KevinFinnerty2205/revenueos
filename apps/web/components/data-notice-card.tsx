"use client";

import { apiRequest } from "@/lib/api";
import { useEffect, useState } from "react";

interface DataNotice {
  version: number;
  acknowledged: boolean;
  acknowledgedAt: string | null;
  providerMode: "mock" | "openai";
  externalProcessingEnabled: boolean;
  notice: string[];
}

export function DataNoticeCard({
  onAcknowledged,
}: {
  onAcknowledged?: () => void;
}) {
  const [notice, setNotice] = useState<DataNotice | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest<DataNotice>("/api/v1/beta/data-notice", {
      signal: controller.signal,
    })
      .then(setNotice)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            reason instanceof Error
              ? reason.message
              : "The data notice could not be loaded.",
          );
        }
      });
    return () => controller.abort();
  }, []);

  async function acknowledge() {
    setSaving(true);
    setError(null);
    try {
      const next = await apiRequest<DataNotice>(
        "/api/v1/beta/data-notice/acknowledgements",
        {
          method: "POST",
          body: JSON.stringify({ acknowledged: true }),
        },
      );
      setNotice(next);
      onAcknowledged?.();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The acknowledgement could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (error && !notice) {
    return (
      <p
        role="alert"
        className="rounded-2xl bg-rose-50 p-4 text-sm text-rose-900"
      >
        {error}
      </p>
    );
  }
  if (!notice) {
    return (
      <p role="status" className="text-sm text-slate-600">
        Loading the private beta data notice…
      </p>
    );
  }
  if (notice.acknowledged) {
    return (
      <p
        role="status"
        className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-950"
      >
        Data notice version {notice.version} acknowledged.{" "}
        {notice.providerMode === "mock"
          ? "Mock processing stays internal."
          : "OpenAI processing is enabled for this environment."}
      </p>
    );
  }

  return (
    <section
      className="rounded-3xl border border-amber-200 bg-amber-50 p-6"
      aria-labelledby="data-notice-title"
    >
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-amber-800">
        Required before transcript processing
      </p>
      <h2
        id="data-notice-title"
        className="mt-2 text-xl font-semibold text-amber-950"
      >
        Private beta data notice · version {notice.version}
      </h2>
      <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-6 text-amber-950">
        {notice.notice.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <label className="mt-5 flex items-start gap-3 text-sm font-semibold text-amber-950">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(event) => setConfirmed(event.target.checked)}
          className="mt-1 size-4"
        />
        I understand this notice and confirm I have authority to process the
        meeting content.
      </label>
      <button
        type="button"
        className="primary-button mt-5"
        disabled={!confirmed || saving}
        onClick={() => void acknowledge()}
      >
        {saving ? "Saving acknowledgement…" : "Acknowledge and continue"}
      </button>
      {error ? (
        <p role="alert" className="mt-3 text-sm text-rose-800">
          {error}
        </p>
      ) : null}
    </section>
  );
}
