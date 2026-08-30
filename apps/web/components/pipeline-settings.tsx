"use client";

import type {
  CRMAvailability,
  PipelineStage,
  SalesPipeline,
} from "@revenueos/shared";
import { FormEvent, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

export function PipelineSettings() {
  const [availability, setAvailability] = useState<CRMAvailability | null>(
    null,
  );
  const [pipelines, setPipelines] = useState<SalesPipeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [newStageNames, setNewStageNames] = useState<Record<string, string>>(
    {},
  );

  async function load() {
    setLoading(true);
    try {
      const currentAvailability = await apiRequest<CRMAvailability>(
        "/api/v1/crm/availability",
      );
      setAvailability(currentAvailability);
      const currentPipelines =
        await apiRequest<SalesPipeline[]>("/api/v1/pipelines");
      setPipelines(currentPipelines);
      setError(null);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Pipeline settings could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    Promise.all([
      apiRequest<CRMAvailability>("/api/v1/crm/availability"),
      apiRequest<SalesPipeline[]>("/api/v1/pipelines"),
    ])
      .then(([currentAvailability, currentPipelines]) => {
        if (!active) return;
        setAvailability(currentAvailability);
        setPipelines(currentPipelines);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(
          reason instanceof Error
            ? reason.message
            : "Pipeline settings could not be loaded.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function mutate(path: string, method: "POST" | "PATCH", body?: object) {
    setSaving(true);
    setError(null);
    try {
      await apiRequest(path, {
        method,
        body: body ? JSON.stringify(body) : undefined,
      });
      await load();
      return true;
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The pipeline change could not be saved.",
      );
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!newName.trim()) return;
    const saved = await mutate("/api/v1/pipelines", "POST", {
      name: newName.trim(),
      stages: [
        { name: "Discovery", stageType: "open" },
        { name: "Evaluation", stageType: "open" },
        { name: "Proposal", stageType: "open" },
        { name: "Commercial", stageType: "open" },
        { name: "Closed Won", stageType: "won" },
        { name: "Closed Lost", stageType: "lost" },
      ],
      isDefault: false,
    });
    if (saved) setNewName("");
  }

  if (loading && !availability) {
    return (
      <section className="form-card" aria-label="Pipeline settings">
        <p role="status" className="text-sm text-slate-600">
          Loading pipeline settings…
        </p>
      </section>
    );
  }

  const manageable =
    availability?.enabled === true &&
    availability.mode === "native" &&
    availability.canManage;
  return (
    <section className="form-card" aria-labelledby="pipeline-settings-title">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">
        CRM
      </p>
      <h2
        id="pipeline-settings-title"
        className="mt-2 text-2xl font-semibold text-slate-950"
      >
        Pipelines
      </h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
        Configure a bounded sales workflow. Stage names and order guide the
        team; they do not create probabilities, gates, automation or customer
        Evidence.
      </p>
      {error ? (
        <p
          role="alert"
          className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-900"
        >
          {error}
        </p>
      ) : null}
      {!manageable ? (
        <p className="mt-5 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-950">
          {availability?.mode === "external"
            ? "Pipeline stages are managed in HubSpot. Native definitions remain historical and read-only."
            : availability?.enabled && availability.mode === "native"
              ? "An organisation administrator manages native pipeline definitions."
              : "Enable RevenueOS CRM and choose RevenueOS as the system of record to configure native pipelines."}
        </p>
      ) : (
        <>
          <div className="mt-6 grid gap-5">
            {pipelines.map((pipeline) => (
              <PipelineEditor
                key={pipeline.id}
                pipeline={pipeline}
                saving={saving}
                newStageName={newStageNames[pipeline.id] ?? ""}
                setNewStageName={(value) =>
                  setNewStageNames((current) => ({
                    ...current,
                    [pipeline.id]: value,
                  }))
                }
                mutate={mutate}
              />
            ))}
          </div>
          <form
            onSubmit={(event) => void create(event)}
            className="mt-6 rounded-2xl bg-slate-50 p-4"
          >
            <h3 className="font-semibold text-slate-950">Create pipeline</h3>
            <p className="mt-1 text-xs leading-5 text-slate-600">
              Starts with four editable open stages plus required Won and Lost
              stages. Maximum five active pipelines.
            </p>
            <div className="mt-3 flex flex-col gap-3 sm:flex-row">
              <label className="flex-1 text-sm font-bold text-slate-700">
                Pipeline name
                <input
                  required
                  maxLength={100}
                  className="form-control mt-2 w-full"
                  value={newName}
                  onChange={(event) => setNewName(event.target.value)}
                />
              </label>
              <button
                type="submit"
                disabled={saving}
                className="primary-button self-end"
              >
                Create pipeline
              </button>
            </div>
          </form>
        </>
      )}
    </section>
  );
}

function PipelineEditor({
  pipeline,
  saving,
  newStageName,
  setNewStageName,
  mutate,
}: {
  pipeline: SalesPipeline;
  saving: boolean;
  newStageName: string;
  setNewStageName: (value: string) => void;
  mutate: (
    path: string,
    method: "POST" | "PATCH",
    body?: object,
  ) => Promise<boolean>;
}) {
  async function addStage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const openCount = pipeline.stages.filter(
      (stage) => stage.stageType === "open",
    ).length;
    const saved = await mutate(
      `/api/v1/pipelines/${pipeline.id}/stages`,
      "POST",
      {
        name: newStageName.trim(),
        position: openCount,
      },
    );
    if (saved) setNewStageName("");
  }

  return (
    <article className="rounded-2xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-slate-950">{pipeline.name}</h3>
          <p className="mt-1 text-xs text-slate-500">
            {pipeline.isDefault
              ? "Default for new opportunities"
              : "Active pipeline"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {!pipeline.isDefault ? (
            <button
              type="button"
              disabled={saving}
              className="secondary-button"
              onClick={() =>
                void mutate(`/api/v1/pipelines/${pipeline.id}`, "PATCH", {
                  isDefault: true,
                })
              }
            >
              Make default
            </button>
          ) : null}
          {!pipeline.isDefault ? (
            <button
              type="button"
              disabled={saving}
              className="secondary-button text-rose-700"
              onClick={() =>
                void mutate(`/api/v1/pipelines/${pipeline.id}/archive`, "POST")
              }
            >
              Archive
            </button>
          ) : null}
        </div>
      </div>
      <ol className="mt-4 grid gap-2">
        {pipeline.stages.map((stage, index) => (
          <StageEditor
            key={stage.id}
            pipeline={pipeline}
            stage={stage}
            index={index}
            saving={saving}
            mutate={mutate}
          />
        ))}
      </ol>
      <form
        onSubmit={(event) => void addStage(event)}
        className="mt-4 flex flex-col gap-2 sm:flex-row"
      >
        <label className="flex-1 text-xs font-bold text-slate-600">
          Add open stage
          <input
            required
            maxLength={100}
            className="form-control mt-1 w-full"
            value={newStageName}
            onChange={(event) => setNewStageName(event.target.value)}
          />
        </label>
        <button
          type="submit"
          disabled={saving || pipeline.stages.length >= 12}
          className="secondary-button self-end"
        >
          Add stage
        </button>
      </form>
    </article>
  );
}

function StageEditor({
  pipeline,
  stage,
  index,
  saving,
  mutate,
}: {
  pipeline: SalesPipeline;
  stage: PipelineStage;
  index: number;
  saving: boolean;
  mutate: (
    path: string,
    method: "POST" | "PATCH",
    body?: object,
  ) => Promise<boolean>;
}) {
  const [name, setName] = useState(stage.name);
  const [guidance, setGuidance] = useState(stage.guidance ?? "");
  const unchanged =
    name.trim() === stage.name && guidance.trim() === (stage.guidance ?? "");
  return (
    <li className="grid gap-2 rounded-xl bg-slate-50 p-3 sm:grid-cols-[auto_minmax(10rem,1fr)_minmax(12rem,1.5fr)_auto] sm:items-end">
      <span className="self-center text-xs font-bold text-slate-500">
        {index + 1}
      </span>
      <label className="text-xs font-bold text-slate-600">
        {stage.stageType === "open"
          ? "Open stage"
          : stage.stageType === "won"
            ? "Won stage"
            : "Lost stage"}
        <input
          maxLength={100}
          className="form-control mt-1 w-full"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <label className="text-xs font-bold text-slate-600">
        Stage guidance (optional)
        <input
          maxLength={300}
          className="form-control mt-1 w-full"
          value={guidance}
          onChange={(event) => setGuidance(event.target.value)}
          placeholder="What should be true in this stage?"
        />
      </label>
      <div className="flex flex-wrap gap-1">
        <button
          type="button"
          disabled={saving || !name.trim() || unchanged}
          className="secondary-button"
          onClick={() =>
            void mutate(
              `/api/v1/pipelines/${pipeline.id}/stages/${stage.id}`,
              "PATCH",
              { name: name.trim(), guidance: guidance.trim() || null },
            )
          }
        >
          Save
        </button>
        <button
          type="button"
          aria-label={`Move ${stage.name} up`}
          disabled={saving || index === 0}
          className="secondary-button"
          onClick={() =>
            void mutate(
              `/api/v1/pipelines/${pipeline.id}/stages/${stage.id}`,
              "PATCH",
              { position: index - 1 },
            )
          }
        >
          ↑
        </button>
        <button
          type="button"
          aria-label={`Move ${stage.name} down`}
          disabled={saving || index === pipeline.stages.length - 1}
          className="secondary-button"
          onClick={() =>
            void mutate(
              `/api/v1/pipelines/${pipeline.id}/stages/${stage.id}`,
              "PATCH",
              { position: index + 1 },
            )
          }
        >
          ↓
        </button>
        {stage.stageType === "open" ? (
          <button
            type="button"
            disabled={saving}
            className="secondary-button text-rose-700"
            onClick={() =>
              void mutate(
                `/api/v1/pipelines/${pipeline.id}/stages/${stage.id}/archive`,
                "POST",
              )
            }
          >
            Archive
          </button>
        ) : null}
      </div>
      {stage.currentOpportunityCount ? (
        <p className="text-xs text-slate-500 sm:col-start-2 sm:col-span-2">
          {stage.currentOpportunityCount} current opportunities
        </p>
      ) : null}
    </li>
  );
}
