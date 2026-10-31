"use client";

import type { DailyResponse } from "@revenueos/shared";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

interface ConversationDeliveryPreference {
  timezone: string;
  morningDigestEnabled: boolean;
  morningDigestTime: string;
  preMeetingEnabled: boolean;
  preMeetingMinutes: number;
}

interface Preview {
  kind: "morning" | "pre_meeting";
  subject: string;
  lines: string[];
  link: string;
  duplicateKey: string;
  reused: boolean;
}

const STORAGE_KEY = "revenueos:conversation-delivery-preferences";

function defaults(): ConversationDeliveryPreference {
  return {
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    morningDigestEnabled: true,
    morningDigestTime: "07:30",
    preMeetingEnabled: true,
    preMeetingMinutes: 30,
  };
}

export function ConversationDeliveryPreferences() {
  const [preference, setPreference] = useState(defaults);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) return;
    let active = true;
    window.queueMicrotask(() => {
      if (!active) return;
      try {
        setPreference({ ...defaults(), ...(JSON.parse(stored) as object) });
      } catch {
        window.localStorage.removeItem(STORAGE_KEY);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  function save() {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preference));
    setMessage(
      "Preferences saved in this browser for the local demo. No scheduled job or email was created.",
    );
  }

  async function createPreview(kind: Preview["kind"]) {
    setWorking(true);
    setError(null);
    setMessage(null);
    try {
      const day = await apiRequest<DailyResponse>(
        `/api/v1/daily?${new URLSearchParams({ timezone: preference.timezone }).toString()}`,
      );
      const next = day.nextInteraction;
      const link = next
        ? `/conversations/${next.id}${next.preparationState === "prepared" ? "#preparation" : ""}`
        : "/conversations";
      const duplicateKey = [
        "local-preview",
        kind,
        day.localDate,
        next?.id ?? "no-next-conversation",
        kind === "morning"
          ? preference.morningDigestTime
          : preference.preMeetingMinutes,
      ].join(":");
      const storageKey = `revenueos:test-transport:${duplicateKey}`;
      const reused = window.localStorage.getItem(storageKey) === "prepared";
      window.localStorage.setItem(storageKey, "prepared");
      setPreview({
        kind,
        subject:
          kind === "morning"
            ? `Your conversation plan for ${day.localDate}`
            : next
              ? `Prepare for ${next.title}`
              : "No upcoming conversation to brief",
        lines:
          kind === "morning"
            ? [
                `${day.todayInteractions.length} conversation${day.todayInteractions.length === 1 ? "" : "s"} today`,
                next
                  ? `Next: ${next.title}`
                  : "No upcoming conversation is currently scheduled.",
                `${day.actions.attentionCount} follow-up item${day.actions.attentionCount === 1 ? "" : "s"} need attention`,
              ]
            : [
                next
                  ? `Current calendar state: ${next.title} is upcoming.`
                  : "The current calendar state has no upcoming conversation.",
                next?.preparationState === "prepared"
                  ? "A preparation brief is ready for review."
                  : "A preparation brief is not yet available.",
                "Changes and cancellations are reflected when this preview is regenerated from current data.",
              ],
        link,
        duplicateKey,
        reused,
      });
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The local email preview could not be prepared.",
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
        Configure and preview the intended experience. This first pass uses a
        deterministic local test transport only: it never schedules or sends an
        email.
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
        <button type="button" className="primary-button" onClick={save}>
          Save local preferences
        </button>
        <button
          type="button"
          className="secondary-button"
          disabled={working || !preference.morningDigestEnabled}
          onClick={() => void createPreview("morning")}
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

      {message ? (
        <p role="status" className="mt-4 text-sm text-brand-primary">
          {message}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-4 text-sm text-rose-800">
          {error}
        </p>
      ) : null}
      {preview ? (
        <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-5">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
            Local test transport ·{" "}
            {preview.reused ? "duplicate reused" : "new preview"}
          </p>
          <h3 className="mt-2 font-semibold text-slate-950">
            {preview.subject}
          </h3>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-700">
            {preview.lines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <a className="secondary-button mt-4" href={preview.link}>
            Open in Oryntela
          </a>
          <p className="mt-3 break-all text-xs text-slate-500">
            Duplicate-prevention key: {preview.duplicateKey}
          </p>
        </div>
      ) : null}
    </section>
  );
}
