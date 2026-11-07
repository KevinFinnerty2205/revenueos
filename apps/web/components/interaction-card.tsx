import type { Interaction } from "@revenueos/shared";
import Link from "next/link";
import { humanise } from "@/lib/business-entities";
import { formatInteractionDate } from "@/lib/interactions";

export function InteractionCard({
  interaction,
  companyName,
  contactName,
  headingLevel = 3,
}: {
  interaction: Interaction;
  companyName?: string | null;
  contactName?: string | null;
  headingLevel?: 2 | 3;
}) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const liveWorkspaceAvailable =
    interaction.lifecycleStatus === "planned" ||
    interaction.lifecycleStatus === "in_progress";

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center gap-2 text-xs font-bold uppercase tracking-wide">
        <span className="rounded-full bg-brand-secondary/10 px-3 py-1 text-brand-secondary">
          {humanise(interaction.interactionType)}
        </span>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">
          {humanise(interaction.lifecycleStatus)}
        </span>
        <span
          className={`rounded-full px-3 py-1 ${
            interaction.briefState === "completed"
              ? "bg-emerald-50 text-emerald-800"
              : interaction.briefState === "not_generated"
                ? "bg-amber-50 text-amber-900"
                : "bg-slate-100 text-slate-600"
          }`}
        >
          {interaction.briefState === "completed"
            ? "Brief ready"
            : interaction.briefState === "not_generated"
              ? "Not prepared"
              : "Link context"}
        </span>
        {interaction.interactionType === "phone_call" ? (
          <span className="rounded-full bg-indigo-50 px-3 py-1 text-indigo-800">
            {humanise(interaction.callDirection ?? "unknown")}
          </span>
        ) : null}
      </div>
      <Heading className="mt-4 text-xl font-semibold text-slate-950">
        <Link
          className="rounded focus:outline-none focus:ring-2 focus:ring-brand-focus"
          href={`/conversations/${interaction.id}`}
        >
          {interaction.title}
        </Link>
      </Heading>
      <p className="mt-2 text-sm text-slate-600">
        {formatInteractionDate(
          interaction.actualStartAt ?? interaction.scheduledStartAt,
        )}
      </p>
      {companyName !== undefined ? (
        <p className="mt-1 text-sm text-slate-600">
          {companyName ?? "No account linked"}
        </p>
      ) : null}
      {interaction.interactionType === "phone_call" ? (
        <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-slate-600">
          <span>{contactName ?? "No contact linked"}</span>
          {interaction.durationSeconds !== null &&
          interaction.durationSeconds !== undefined ? (
            <span>· {formatDuration(interaction.durationSeconds)}</span>
          ) : null}
          {interaction.callOutcome ? (
            <span>· {humanise(interaction.callOutcome)}</span>
          ) : null}
        </div>
      ) : null}
      {interaction.interactionType === "phone_call" ||
      interaction.captureMethods?.length ? (
        <p className="mt-3 text-xs font-semibold text-brand-secondary">
          Capture:{" "}
          {interaction.captureMethods?.length
            ? interaction.captureMethods.map(humanise).join(" · ")
            : "None yet"}
          {interaction.intelligenceState
            ? ` · Intelligence ${humanise(interaction.intelligenceState).toLowerCase()}`
            : ""}
          {interaction.recordingAvailable ? " · Recording available" : ""}
        </p>
      ) : null}
      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2">
        {interaction.lifecycleStatus === "completed" ? (
          <Link
            className="text-sm font-bold text-brand-secondary underline-offset-4 hover:underline"
            href={`/conversations/${interaction.id}#debrief`}
          >
            Open notes and follow-up
          </Link>
        ) : null}
        {liveWorkspaceAvailable ? (
          <Link
            className="text-sm font-bold text-brand-secondary underline-offset-4 hover:underline"
            href={`/conversations/${interaction.id}/workspace`}
          >
            Open live workspace
          </Link>
        ) : null}
        {interaction.briefState !== "unavailable" ? (
          <Link
            className="text-sm font-bold text-brand-secondary underline-offset-4 hover:underline"
            href={`/conversations/${interaction.id}#preparation`}
          >
            {interaction.briefState === "completed"
              ? "Open brief"
              : "Prepare brief"}
          </Link>
        ) : null}
      </div>
    </article>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m${seconds % 60 ? ` ${seconds % 60}s` : ""}`;
}
