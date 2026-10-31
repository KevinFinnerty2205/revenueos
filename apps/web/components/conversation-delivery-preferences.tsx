"use client";

import type {
  BriefingPreviewResponse,
  DailyResponse,
  DeliveryPreferenceResponse,
} from "@revenueos/shared";
import { useCallback, useEffect, useState } from "react";
import { ApiClientError, apiRequest } from "@/lib/api";

interface PreferenceValues {
  timezone: string;
  morningDigestEnabled: boolean;
  morningDigestTime: string;
  preMeetingEnabled: boolean;
  preMeetingMinutes: number;
}

const STORAGE_KEY = "revenueos:conversation-delivery-preferences";

function browserDefaults(): PreferenceValues {
  return {
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    morningDigestEnabled: true,
    morningDigestTime: "07:30",
    preMeetingEnabled: true,
    preMeetingMinutes: 30,
  };
}

export function ConversationDeliveryPreferences() {
  const [server, setServer] = useState<DeliveryPreferenceResponse | null>(null);
  const [preference, setPreference] = useState(browserDefaults);
  const [preview, setPreview] = useState<BriefingPreviewResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [legacyRecoveryAvailable, setLegacyRecoveryAvailable] = useState(false);

  const load = useCallback(async () => {
    setWorking(true);
    setError(null);
    try {
      const response = await apiRequest<DeliveryPreferenceResponse>(
        "/api/v1/daily/preferences",
      );
      setServer(response);
      setPreference({
        timezone: response.exists
          ? response.timezone
          : browserDefaults().timezone,
        morningDigestEnabled: response.morningDigestEnabled,
        morningDigestTime: response.morningDigestTime,
        preMeetingEnabled: response.preMeetingEnabled,
        preMeetingMinutes: response.preMeetingMinutes,
      });
      setLegacyRecoveryAvailable(
        window.localStorage.getItem(STORAGE_KEY) !== null,
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Conversation briefing preferences could not be loaded.",
      );
    } finally {
      setWorking(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    window.queueMicrotask(() => {
      if (active) void load();
    });
    return () => {
      active = false;
    };
  }, [load]);

  async function save(options: { importFromBrowser?: boolean } = {}) {
    if (!server) return false;
    setWorking(true);
    setError(null);
    setMessage(null);
    try {
      const response = await apiRequest<DeliveryPreferenceResponse>(
        "/api/v1/daily/preferences",
        {
          method: "PUT",
          body: JSON.stringify({
            expectedLockVersion: server.lockVersion,
            ...preference,
            importFromBrowser: options.importFromBrowser === true,
          }),
        },
      );
      setServer(response);
      setMessage("Preferences saved privately. No email was sent.");
      return true;
    } catch (reason: unknown) {
      const conflict =
        reason instanceof ApiClientError &&
        reason.code === "delivery_preference_conflict";
      setError(
        conflict
          ? "These preferences changed in another session. Reload before saving."
          : reason instanceof Error
            ? reason.message
            : "Conversation briefing preferences could not be saved.",
      );
      return false;
    } finally {
      setWorking(false);
    }
  }

  async function recoverLegacyPreferences() {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored || !server) return;
    try {
      const recovered = {
        ...browserDefaults(),
        ...(JSON.parse(stored) as Partial<PreferenceValues>),
      };
      setPreference(recovered);
      setWorking(true);
      const response = await apiRequest<DeliveryPreferenceResponse>(
        "/api/v1/daily/preferences",
        {
          method: "PUT",
          body: JSON.stringify({
            expectedLockVersion: server.lockVersion,
            ...recovered,
            importFromBrowser: true,
          }),
        },
      );
      setServer(response);
      window.localStorage.removeItem(STORAGE_KEY);
      setLegacyRecoveryAvailable(false);
      setMessage(
        "Earlier browser preferences were imported and saved privately.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Earlier browser preferences could not be imported safely.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function createPreview(kind: "morning_digest" | "pre_meeting") {
    setWorking(true);
    setError(null);
    setMessage(null);
    try {
      let interactionId: string | null = null;
      if (kind === "pre_meeting") {
        const day = await apiRequest<DailyResponse>(
          `/api/v1/daily?${new URLSearchParams({ timezone: preference.timezone }).toString()}`,
        );
        interactionId = day.nextInteraction?.id ?? null;
        if (!interactionId) {
          throw new Error(
            "No upcoming conversation is available for a pre-meeting preview.",
          );
        }
      }
      const response = await apiRequest<BriefingPreviewResponse>(
        "/api/v1/daily/briefing-preview",
        {
          method: "POST",
          body: JSON.stringify({ kind, interactionId }),
        },
      );
      setPreview(response);
      setMessage(
        response.duplicateSuppressed
          ? "The existing identical local outbox preview was reused."
          : "Exact content prepared in the local test outbox. Nothing was sent.",
      );
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The local briefing preview could not be prepared.",
      );
    } finally {
      setWorking(false);
    }
  }

  return (
    <section
      className="form-card"
      aria-labelledby="conversation-delivery-title"
    >
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
        Conversation briefings
      </p>
      <h2 id="conversation-delivery-title" className="form-legend mt-2">
        Digest and pre-meeting preferences
      </h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        Preferences persist across sessions. Previewed content is prepared in a
        local test outbox only; this build never sends an email.
      </p>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-bold text-slate-800">
          Timezone
          <input
            className="form-control mt-2"
            value={preference.timezone}
            onChange={(event) =>
              setPreference((current) => ({
                ...current,
                timezone: event.target.value,
              }))
            }
          />
        </label>
        <label className="text-sm font-bold text-slate-800">
          Morning digest time
          <input
            className="form-control mt-2"
            type="time"
            value={preference.morningDigestTime}
            onChange={(event) =>
              setPreference((current) => ({
                ...current,
                morningDigestTime: event.target.value,
              }))
            }
          />
        </label>
        <label className="flex items-center gap-3 rounded-xl border border-slate-200 p-4 text-sm font-semibold text-slate-800">
          <input
            type="checkbox"
            checked={preference.morningDigestEnabled}
            onChange={(event) =>
              setPreference((current) => ({
                ...current,
                morningDigestEnabled: event.target.checked,
              }))
            }
          />
          Morning digest enabled
        </label>
        <label className="flex items-center gap-3 rounded-xl border border-slate-200 p-4 text-sm font-semibold text-slate-800">
          <input
            type="checkbox"
            checked={preference.preMeetingEnabled}
            onChange={(event) =>
              setPreference((current) => ({
                ...current,
                preMeetingEnabled: event.target.checked,
              }))
            }
          />
          Pre-meeting briefing enabled
        </label>
        <label className="text-sm font-bold text-slate-800 sm:col-span-2">
          Briefing lead time (minutes)
          <input
            className="form-control mt-2"
            type="number"
            min={5}
            max={1440}
            value={preference.preMeetingMinutes}
            onChange={(event) =>
              setPreference((current) => ({
                ...current,
                preMeetingMinutes: Number(event.target.value),
              }))
            }
          />
        </label>
      </div>

      <div className="mt-5 flex flex-wrap gap-3">
        <button
          type="button"
          className="primary-button"
          disabled={working || !server}
          onClick={() => void save()}
        >
          {working ? "Working…" : "Save preferences"}
        </button>
        <button
          type="button"
          className="secondary-button"
          disabled={working || !preference.morningDigestEnabled}
          onClick={() => void createPreview("morning_digest")}
        >
          Preview morning digest
        </button>
        <button
          type="button"
          className="secondary-button"
          disabled={working || !preference.preMeetingEnabled}
          onClick={() => void createPreview("pre_meeting")}
        >
          Preview pre-meeting email
        </button>
      </div>

      {legacyRecoveryAvailable ? (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
          <p>
            Earlier browser-only preferences are available. They remain local
            until you explicitly import them.
          </p>
          <button
            type="button"
            className="secondary-button mt-3"
            disabled={working}
            onClick={() => void recoverLegacyPreferences()}
          >
            Import browser preferences
          </button>
        </div>
      ) : null}
      {message ? (
        <p role="status" className="mt-4 text-sm text-brand-primary">
          {message}
        </p>
      ) : null}
      {error ? (
        <div role="alert" className="mt-4 text-sm text-rose-800">
          <p>{error}</p>
          <button
            type="button"
            className="secondary-button mt-3"
            onClick={() => void load()}
          >
            Reload saved preferences
          </button>
        </div>
      ) : null}
      {preview ? (
        <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-5">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
            Local test outbox ·{" "}
            {preview.duplicateSuppressed ? "duplicate reused" : "new preview"}
          </p>
          <h3 className="mt-2 font-semibold text-slate-950">
            {preview.subject}
          </h3>
          <pre className="mt-3 whitespace-pre-wrap font-sans text-sm leading-6 text-slate-700">
            {preview.bodyText}
          </pre>
          <a className="secondary-button mt-4" href={preview.href}>
            Open in Oryntela
          </a>
          <p className="mt-3 text-xs text-slate-500">
            Prepared for {new Date(preview.preparedForAt).toLocaleString()}
          </p>
        </div>
      ) : null}
    </section>
  );
}
