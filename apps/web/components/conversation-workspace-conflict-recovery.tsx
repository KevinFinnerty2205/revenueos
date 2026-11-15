"use client";

import type {
  ConversationWorkspaceController,
  WorkspaceValues,
} from "@/lib/use-conversation-workspace";

type ConflictField = {
  key: keyof WorkspaceValues;
  label: string;
  emptyLabel: string;
};

export function ConversationWorkspaceConflictRecovery({
  controller,
  fields,
  reviewedValues,
  saveLabel,
  latestLabel = "Use latest saved version",
  idPrefix,
  onResolved,
  onSaved,
  onUsedLatest,
}: {
  controller: ConversationWorkspaceController;
  fields: readonly ConflictField[];
  reviewedValues: Partial<WorkspaceValues>;
  saveLabel: string;
  latestLabel?: string;
  idPrefix: string;
  onResolved?: () => void;
  onSaved?: () => void;
  onUsedLatest?: () => void;
}) {
  const recovery = controller.conflictRecovery;
  if (controller.saveState !== "conflict" && recovery.state !== "saving") {
    return null;
  }
  const waiting = recovery.state === "loading";
  const saving = recovery.state === "saving";
  const latest = recovery.latestValues;

  return (
    <section
      className="mt-5 rounded-2xl border border-amber-300 bg-amber-50 p-5"
      aria-labelledby={`${idPrefix}-title`}
      aria-busy={waiting || saving}
    >
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-amber-800">
        Review before saving
      </p>
      <h3
        id={`${idPrefix}-title`}
        className="mt-2 text-lg font-semibold text-amber-950"
      >
        Private notes changed in another session
      </h3>
      <p role="alert" className="sr-only">
        A different private version was saved. Your unsaved version remains in
        the editor. Review both versions before saving again.
      </p>
      <p className="mt-2 text-sm leading-6 text-amber-950">
        Your unsaved version remains editable above. Compare it with the latest
        saved version below, merge anything you need into your editor, then save
        the reviewed version. Nothing is copied or sent automatically.
      </p>

      {waiting ? (
        <p role="status" className="mt-4 text-sm font-semibold text-amber-900">
          Loading the latest saved private notes…
        </p>
      ) : null}

      {recovery.state === "failed" ? (
        <div className="mt-4">
          <p role="alert" className="text-sm font-semibold text-rose-800">
            {recovery.error ??
              "The latest saved private notes could not be loaded. Your local text is unchanged."}
          </p>
          <button
            type="button"
            className="secondary-button mt-3"
            onClick={() => void controller.loadLatestConflict()}
          >
            Try loading the latest version again
          </button>
        </div>
      ) : null}

      {latest && recovery.state !== "failed" ? (
        <div className="mt-4 space-y-4">
          {fields.map((field) => {
            const value = latest[field.key];
            const text = typeof value === "string" ? value : String(value);
            return (
              <div key={field.key}>
                <label
                  htmlFor={`${idPrefix}-latest-${field.key}`}
                  className="block text-sm font-semibold text-amber-950"
                >
                  {field.label}
                </label>
                <textarea
                  id={`${idPrefix}-latest-${field.key}`}
                  className="form-control mt-2 min-h-28 w-full bg-white py-3"
                  readOnly
                  value={text}
                  placeholder={field.emptyLabel}
                />
              </div>
            );
          })}
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className="primary-button"
              disabled={saving}
              onClick={() => {
                void controller
                  .saveReviewedConflict(reviewedValues)
                  .then((saved) => {
                    if (saved) {
                      onSaved?.();
                      onResolved?.();
                    }
                  });
              }}
            >
              {saving ? "Saving reviewed version…" : saveLabel}
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={saving}
              onClick={() => {
                if (controller.useLatestConflict()) {
                  onUsedLatest?.();
                  onResolved?.();
                }
              }}
            >
              {latestLabel}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
