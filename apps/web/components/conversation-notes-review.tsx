"use client";

import type { ConversationWorkspaceResponse } from "@revenueos/shared";
import { useState } from "react";
import type {
  ConversationWorkspaceController,
  WorkspaceGenerationActionState,
} from "@/lib/use-conversation-workspace";

export function ConversationNotesReview({
  controller,
  onApplyGeneratedVersion,
}: {
  controller: ConversationWorkspaceController;
  onApplyGeneratedVersion: () => Promise<void>;
}) {
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const workspace = controller.workspace;

  if (controller.loading && workspace === null) {
    return (
      <section className="form-card" aria-labelledby="conversation-notes-title">
        <h2 id="conversation-notes-title" className="form-legend">
          Conversation notes
        </h2>
        <p role="status" className="mt-3 text-sm text-slate-600">
          Loading your private notes…
        </p>
      </section>
    );
  }

  if (workspace === null) {
    return (
      <section
        className="form-card border-rose-200 bg-rose-50"
        aria-labelledby="conversation-notes-title"
      >
        <h2 id="conversation-notes-title" className="form-legend text-rose-950">
          Conversation notes could not be loaded
        </h2>
        <p role="alert" className="mt-3 text-sm text-rose-900">
          {controller.error ??
            "Your private conversation notes are temporarily unavailable."}
        </p>
        <button
          type="button"
          className="secondary-button mt-4"
          onClick={() => void controller.reload()}
        >
          Try again
        </button>
      </section>
    );
  }

  const saveDisabled = controller.loading || controller.saveState === "saving";

  async function copyFollowUp() {
    setCopyStatus(null);
    try {
      await navigator.clipboard.writeText(controller.values.followUpDraft);
      setCopyStatus("Follow-up draft copied.");
    } catch {
      setCopyStatus("Select the follow-up text and copy it manually.");
    }
  }

  return (
    <section className="form-card" aria-labelledby="conversation-notes-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-secondary">
            Private to you
          </p>
          <h2
            id="conversation-notes-title"
            className="mt-2 text-2xl font-semibold text-slate-950"
          >
            Conversation notes
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            Keep your original rough notes beside an editable enhanced version.
            Oryntela never sends or shares either draft automatically.
          </p>
        </div>
        {controller.isDirty ? (
          <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-900">
            Unsaved changes
          </span>
        ) : null}
      </div>

      <PostConversationDraftStatus
        workspace={workspace}
        actionState={controller.generationActionState}
        actionError={controller.generationError}
        checking={controller.loading}
        hasUnsavedChanges={controller.isDirty}
        personalNotesChangedLocally={controller.dirtyFields.liveNotes}
        onRetry={() => void controller.retryGeneration()}
        onApply={() => void onApplyGeneratedVersion()}
        onRefresh={() => void controller.refresh()}
      />

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
          <label
            htmlFor="conversation-rough-notes"
            className="font-semibold text-slate-950"
          >
            Your rough notes (original)
          </label>
          <p
            id="conversation-rough-notes-description"
            className="mt-2 text-sm leading-6 text-slate-600"
          >
            These are preserved separately. Generating or applying enhanced
            notes never replaces this field.
          </p>
          <textarea
            id="conversation-rough-notes"
            className="form-control mt-4 min-h-52 py-3"
            maxLength={20_000}
            disabled={controller.loading}
            value={controller.values.liveNotes}
            aria-describedby="conversation-rough-notes-description"
            placeholder="No rough notes were saved."
            onChange={(event) =>
              controller.setValues((current) => ({
                ...current,
                liveNotes: event.target.value,
              }))
            }
          />
          <button
            type="button"
            className="secondary-button mt-3"
            disabled={saveDisabled}
            onClick={() => void controller.save()}
          >
            {controller.saveState === "saving" ? "Saving…" : "Save rough notes"}
          </button>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5">
          <label
            htmlFor="conversation-enhanced-notes"
            className="font-semibold text-slate-950"
          >
            Enhanced conversation notes
          </label>
          <p
            id="conversation-enhanced-notes-description"
            className="mt-2 text-sm leading-6 text-slate-600"
          >
            Review and edit this private draft. Your changes are not treated as
            customer-confirmed evidence.
          </p>
          <textarea
            id="conversation-enhanced-notes"
            className="form-control mt-4 min-h-52 py-3"
            maxLength={100_000}
            disabled={controller.loading}
            value={controller.values.enhancedNotes}
            aria-describedby="conversation-enhanced-notes-description"
            placeholder="Enhanced notes will appear here when a private draft is ready."
            onChange={(event) =>
              controller.setValues((current) => ({
                ...current,
                enhancedNotes: event.target.value,
              }))
            }
          />
          <button
            type="button"
            className="secondary-button mt-3"
            disabled={saveDisabled}
            onClick={() => void controller.save()}
          >
            {controller.saveState === "saving"
              ? "Saving…"
              : "Save enhanced notes"}
          </button>
        </section>
      </div>

      <section className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-5">
        <label
          htmlFor="conversation-follow-up-draft"
          className="font-semibold text-amber-950"
        >
          Private follow-up draft
        </label>
        <p
          id="conversation-follow-up-description"
          className="mt-2 text-sm leading-6 text-amber-900"
        >
          Private rough notes are not added automatically. Automatic transcript
          drafts use transcript evidence only; debrief drafts use only items you
          reviewed and accepted. Review every statement before copying or
          exporting; Oryntela never sends it.
        </p>
        <textarea
          id="conversation-follow-up-draft"
          className="form-control mt-4 min-h-64 py-3"
          maxLength={100_000}
          disabled={controller.loading}
          value={controller.values.followUpDraft}
          aria-describedby="conversation-follow-up-description"
          placeholder="A transcript-supported follow-up draft will appear here when ready."
          onChange={(event) =>
            controller.setValues((current) => ({
              ...current,
              followUpDraft: event.target.value,
              followUpReviewed: false,
            }))
          }
        />
        <div className="mt-3 flex flex-wrap gap-3">
          <button
            type="button"
            className="secondary-button"
            disabled={saveDisabled}
            onClick={() => void controller.save({ followUpReviewed: false })}
          >
            Save follow-up draft
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={saveDisabled || !controller.values.followUpDraft.trim()}
            onClick={() => void controller.save({ followUpReviewed: true })}
          >
            Mark reviewed
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={!controller.values.followUpDraft.trim()}
            onClick={() => void copyFollowUp()}
          >
            Copy draft
          </button>
        </div>
        {copyStatus ? (
          <p role="status" className="mt-3 text-sm text-amber-900">
            {copyStatus}
          </p>
        ) : null}
      </section>

      <WorkspaceSaveStatus controller={controller} />
    </section>
  );
}

function WorkspaceSaveStatus({
  controller,
}: {
  controller: ConversationWorkspaceController;
}) {
  if (controller.saveState === "saved") {
    return (
      <p
        role="status"
        className="mt-5 text-sm font-semibold text-brand-primary"
      >
        {controller.isDirty
          ? "An earlier version was saved privately. Newer changes remain unsaved."
          : "Saved privately to your Oryntela workspace. No external action was taken."}
      </p>
    );
  }
  if (!controller.error) return null;
  return (
    <div role="alert" className="mt-5 text-sm font-semibold text-rose-800">
      <p>{controller.error}</p>
      {controller.saveState === "conflict" ? (
        <>
          <p className="mt-2 font-normal">
            Your local text remains visible. Reloading will discard those local
            changes and show the latest saved version.
          </p>
          <button
            type="button"
            className="secondary-button mt-3"
            onClick={() => void controller.reload()}
          >
            Discard local changes and reload
          </button>
        </>
      ) : null}
    </div>
  );
}

export function PostConversationDraftStatus({
  workspace,
  actionState,
  actionError,
  checking = false,
  hasUnsavedChanges = false,
  personalNotesChangedLocally = false,
  onRetry,
  onApply,
  onRefresh,
}: {
  workspace: ConversationWorkspaceResponse;
  actionState: WorkspaceGenerationActionState;
  actionError: string | null;
  checking?: boolean;
  hasUnsavedChanges?: boolean;
  personalNotesChangedLocally?: boolean;
  onRetry: () => void;
  onApply: () => void;
  onRefresh: () => void;
}) {
  const version = workspace.generationTranscriptVersion;
  const versionLabel =
    version === null ? "" : ` for transcript version ${version}`;
  const actionPending =
    actionState === "retrying" || actionState === "applying";

  return (
    <section
      className="mt-5 rounded-2xl border border-brand-primary/20 bg-brand-primary/5 p-4"
      aria-labelledby="private-draft-status-title"
      aria-busy={
        checking ||
        workspace.generationState === "pending" ||
        workspace.generationState === "processing"
      }
    >
      <h3
        id="private-draft-status-title"
        className="text-sm font-bold text-slate-950"
      >
        Private post-conversation draft
      </h3>
      <GenerationPersonalNotesCopy
        workspace={workspace}
        personalNotesChangedLocally={personalNotesChangedLocally}
      />
      {workspace.generationState === "not_started" ? (
        <p className="mt-2 text-sm leading-6 text-slate-700" role="status">
          No automatic transcript version has been prepared yet. Saved rough
          notes remain available above and are never replaced by generation.
        </p>
      ) : null}
      {workspace.generationState === "pending" ||
      workspace.generationState === "processing" ? (
        <>
          <p className="mt-2 text-sm leading-6 text-slate-700" role="status">
            {workspace.generationState === "pending" ? "Pending" : "Preparing"}
            {versionLabel}. Oryntela is building enhanced notes, decisions,
            suggested actions and a transcript-only follow-up draft. The result
            stays private to you and is never sent or shared automatically.
          </p>
          <button
            type="button"
            className="secondary-button mt-3"
            disabled={checking}
            onClick={onRefresh}
          >
            {checking ? "Checking…" : "Check status"}
          </button>
        </>
      ) : null}
      {workspace.generationState === "failed" ? (
        <>
          <p className="mt-2 text-sm leading-6 text-red-800" role="alert">
            The private draft{versionLabel} could not be prepared. Your rough
            notes and edited drafts were preserved.
          </p>
          {workspace.generationRetryAvailable ? (
            <button
              type="button"
              className="secondary-button mt-3"
              disabled={actionPending}
              onClick={onRetry}
            >
              {actionState === "retrying" ? "Retrying…" : "Retry private draft"}
            </button>
          ) : null}
        </>
      ) : null}
      {workspace.generationState === "ready" ? (
        <>
          <p className="mt-2 text-sm leading-6 text-slate-700" role="status">
            {workspace.generationUpdateAvailable
              ? `A newer private draft${versionLabel} is ready. Your edited enhanced notes and follow-up were preserved.`
              : `Your private draft${versionLabel} is ready.`}{" "}
            It is never sent or shared automatically.
          </p>
          {workspace.generationUpdateAvailable && workspace.generationId ? (
            <>
              <p className="mt-2 text-xs leading-5 text-slate-600">
                Choosing this version replaces enhanced notes and the follow-up
                draft, but keeps your original rough notes.
              </p>
              {hasUnsavedChanges ? (
                <p className="mt-2 text-xs font-semibold leading-5 text-amber-800">
                  Save or discard your unsaved changes before choosing this
                  generated version.
                </p>
              ) : null}
              <button
                type="button"
                className="secondary-button mt-3"
                disabled={actionPending || hasUnsavedChanges}
                onClick={onApply}
              >
                {actionState === "applying"
                  ? "Using version…"
                  : `Use generated version ${version ?? ""}`}
              </button>
            </>
          ) : null}
        </>
      ) : null}
      {actionError ? (
        <p className="mt-3 text-sm text-red-800" role="alert">
          {actionError}
        </p>
      ) : null}
    </section>
  );
}

function GenerationPersonalNotesCopy({
  workspace,
  personalNotesChangedLocally,
}: {
  workspace: ConversationWorkspaceResponse;
  personalNotesChangedLocally: boolean;
}) {
  if (workspace.generationState === "not_started") return null;
  if (personalNotesChangedLocally) {
    const copy =
      workspace.generationPersonalNotesState === "current"
        ? "This version used your last saved rough notes together with transcript evidence. Your unsaved rough-note changes were not included."
        : workspace.generationPersonalNotesState === "changed"
          ? "This version used an earlier saved rough-note version. Your current saved and unsaved rough-note changes were not included."
          : "This version uses transcript evidence only. Your unsaved rough-note changes were not included.";
    return <p className="mt-2 text-xs leading-5 text-slate-600">{copy}</p>;
  }
  const copy =
    workspace.generationPersonalNotesState === "current"
      ? "This version used the saved rough notes shown below together with transcript evidence."
      : workspace.generationPersonalNotesState === "changed"
        ? "This version used an earlier saved rough-note version. Your current rough notes remain unchanged."
        : "This version uses transcript evidence only; no saved rough notes were included.";
  return <p className="mt-2 text-xs leading-5 text-slate-600">{copy}</p>;
}
