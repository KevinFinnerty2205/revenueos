import type {
  RevenueBrainChange,
  RevenueBrainReasoningResponse,
  RevenueBrainSourceCapability,
} from "@revenueos/shared";
import Link from "next/link";
import { humanise } from "@/lib/business-entities";

export function RevenueBrainInsightPanel({
  reasoning,
  heading = "Longitudinal Changes",
  headingId = "longitudinal-changes",
  requesting = false,
  requestError = null,
  onRequest,
}: {
  reasoning: RevenueBrainReasoningResponse;
  heading?: string;
  headingId?: string;
  requesting?: boolean;
  requestError?: string | null;
  onRequest?: () => void;
}) {
  const insight = reasoning.latest;

  return (
    <section
      aria-labelledby={headingId}
      className="rounded-3xl border border-sky-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-sky-700">
            Revenue Brain
          </p>
          <h2
            id={headingId}
            className="mt-2 text-2xl font-semibold tracking-tight text-slate-950"
          >
            {heading}
          </h2>
        </div>
        {onRequest &&
        (reasoning.state === "not_generated" ||
          reasoning.state === "failed" ||
          reasoning.state === "cancelled") ? (
          <button
            type="button"
            className="secondary-button"
            disabled={requesting}
            onClick={onRequest}
          >
            {requesting ? "Generating changes…" : "Generate changes"}
          </button>
        ) : null}
      </div>

      {requestError ? (
        <p
          role="alert"
          className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"
        >
          {requestError}
        </p>
      ) : null}

      {reasoning.state === "insufficient_history" ? (
        <EmptyReasoningState>{reasoning.message}</EmptyReasoningState>
      ) : reasoning.state === "not_generated" ? (
        <EmptyReasoningState>{reasoning.message}</EmptyReasoningState>
      ) : reasoning.state === "queued" || reasoning.state === "running" ? (
        <p
          role="status"
          className="mt-6 rounded-xl border border-sky-200 bg-sky-50 p-5 text-sm leading-6 text-sky-950"
        >
          Revenue Brain is preparing the latest supported changes.
        </p>
      ) : reasoning.state === "failed" ||
        reasoning.state === "cancelled" ||
        !insight ? (
        <EmptyReasoningState>
          Longitudinal reasoning is currently unavailable. Try again when
          appropriate.
        </EmptyReasoningState>
      ) : (
        <div className="mt-6">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-slate-600">
            <span className="font-bold text-slate-900">Comparison period</span>
            <MeetingDateLink
              meetingId={insight.content.fromMeetingId}
              meetingDate={insight.content.fromMeetingDate}
            />
            <span aria-hidden="true">→</span>
            <span className="sr-only">to</span>
            <MeetingDateLink
              meetingId={insight.content.toMeetingId}
              meetingDate={insight.content.toMeetingDate}
            />
            <span>
              Comparison confidence{" "}
              {Math.round(insight.content.confidence * 100)}%
            </span>
          </div>
          <p className="mt-5 text-base font-semibold leading-7 text-slate-950">
            {insight.content.summary}
          </p>

          {insight.content.changes.length === 0 ? null : (
            <ol
              aria-label="Most important supported changes"
              className="mt-6 grid gap-4 lg:grid-cols-2"
            >
              {insight.content.changes.slice(0, 6).map((change, index) => (
                <ChangeCard
                  key={`${change.changeType}-${index}`}
                  change={change}
                />
              ))}
            </ol>
          )}
        </div>
      )}
    </section>
  );
}

function EmptyReasoningState({ children }: { children: string }) {
  return (
    <div className="mt-6 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5">
      <p className="text-sm leading-6 text-slate-700">{children}</p>
    </div>
  );
}

function MeetingDateLink({
  meetingId,
  meetingDate,
}: {
  meetingId: string;
  meetingDate: string;
}) {
  return (
    <Link
      href={`/meetings/${meetingId}`}
      className="font-bold text-sky-800 underline decoration-sky-300 underline-offset-4 hover:text-sky-950 focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2"
    >
      <time dateTime={meetingDate}>{formatDate(meetingDate)}</time>
    </Link>
  );
}

function ChangeCard({ change }: { change: RevenueBrainChange }) {
  return (
    <li className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
      <div className="flex flex-wrap gap-2">
        <ChangeLabel label="Direction" value={humanise(change.direction)} />
        <ChangeLabel label="Importance" value={humanise(change.importance)} />
      </div>
      <h3 className="mt-3 font-bold text-slate-950">{change.title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-700">
        {change.description}
      </p>
      <p className="mt-3 text-xs font-semibold text-slate-600">
        Supported by {change.sourceCapabilities.map(sourceLabel).join(", ")} ·
        Confidence {Math.round(change.confidence * 100)}%
      </p>
    </li>
  );
}

function ChangeLabel({ label, value }: { label: string; value: string }) {
  return (
    <span className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-bold text-slate-700">
      <span className="sr-only">{label}: </span>
      {value}
    </span>
  );
}

function sourceLabel(source: RevenueBrainSourceCapability): string {
  const labels: Record<RevenueBrainSourceCapability, string> = {
    executive_summary: "Executive Summary",
    buying_signals: "Buying Signals",
    objections_competitive_signals: "Objections & Competitive Signals",
    stakeholder_intelligence: "Stakeholder Intelligence",
    decisions: "Decisions",
    action_items: "Action Items",
    risks_blockers: "Risks & Blockers",
    open_questions: "Open Questions",
    next_best_action: "Next Best Action",
  };
  return labels[source];
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}
