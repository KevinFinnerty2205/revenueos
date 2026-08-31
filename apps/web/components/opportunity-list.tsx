"use client";

import type {
  PipelineBoard,
  PipelineCard,
  PipelineStage,
} from "@revenueos/shared";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";
import { notifyOpportunityChanged } from "@/lib/opportunity-events";
import { humanise } from "@/lib/business-entities";
import { ManagerPipelineView } from "@/components/manager-pipeline-view";

type DisplayMode = "board" | "list" | "manager";
const PIPELINE_RENDER_BATCH = 100;

export function OpportunityList() {
  const [board, setBoard] = useState<PipelineBoard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [pipelineId, setPipelineId] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [attentionOnly, setAttentionOnly] = useState(false);
  const [closed, setClosed] = useState(false);
  const [display, setDisplay] = useState<DisplayMode>("board");
  const [refreshKey, setRefreshKey] = useState(0);
  const [movingId, setMovingId] = useState<string | null>(null);
  const [managerAvailable, setManagerAvailable] = useState(false);
  const [visibleCardCount, setVisibleCardCount] = useState(
    PIPELINE_RENDER_BATCH,
  );

  useEffect(() => {
    const controller = new AbortController();
    const parameters = new URLSearchParams({
      view: closed ? "closed" : "open",
    });
    if (pipelineId) parameters.set("pipelineId", pipelineId);
    if (ownerId) parameters.set("ownerUserId", ownerId);
    if (search) parameters.set("search", search);
    if (attentionOnly && !closed) parameters.set("attentionOnly", "true");
    apiRequest<PipelineBoard>(`/api/v1/pipeline?${parameters.toString()}`, {
      signal: controller.signal,
    })
      .then((response) => {
        setBoard(response);
        setManagerAvailable(response.managerIntelligenceAvailable === true);
        if (
          response.managerIntelligenceAvailable === true &&
          new URLSearchParams(window.location.search).get("view") ===
            "attention"
        ) {
          setDisplay("manager");
        }
        if (!pipelineId) setPipelineId(response.pipeline.id);
        setVisibleCardCount(PIPELINE_RENDER_BATCH);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(
          reason instanceof Error
            ? reason.message
            : "Pipeline could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [attentionOnly, closed, ownerId, pipelineId, refreshKey, search]);

  const owners = useMemo(() => {
    const values = new Map<string, string>();
    board?.cards.forEach((card) =>
      values.set(card.ownerUserId, card.ownerName),
    );
    return [...values].sort((left, right) => left[1].localeCompare(right[1]));
  }, [board]);

  function applySearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setSearch(searchDraft.trim());
  }

  async function move(card: PipelineCard, targetStageId: string) {
    if (!targetStageId || targetStageId === card.stageId) return;
    setMovingId(card.opportunityId);
    setError(null);
    try {
      await apiRequest(`/api/v1/opportunities/${card.opportunityId}/stage`, {
        method: "POST",
        body: JSON.stringify({
          targetStageId,
          expectedCurrentStageId: card.stageId,
          idempotencyKey: requestKey("move"),
        }),
      });
      notifyOpportunityChanged(card.opportunityId);
      setRefreshKey((key) => key + 1);
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The opportunity could not be moved.",
      );
    } finally {
      setMovingId(null);
    }
  }

  return (
    <section aria-labelledby="pipeline-title">
      <header className="mb-7 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
            Sell
          </p>
          <h1
            id="pipeline-title"
            className="mt-3 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl"
          >
            Pipeline
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
            See every open deal, its workflow stage and the next thing that
            needs attention. Stage is workflow state—not customer Evidence or a
            forecast.
          </p>
        </div>
        <Link href="/opportunities/new" className="primary-button">
          New opportunity
        </Link>
      </header>

      <div className="mb-5 flex flex-wrap gap-2" aria-label="Pipeline views">
        <ViewButton
          active={!closed && display === "board"}
          onClick={() => {
            if (closed) setLoading(true);
            setClosed(false);
            setDisplay("board");
          }}
        >
          Board
        </ViewButton>
        {managerAvailable ? (
          <ViewButton
            active={!closed && display === "manager"}
            onClick={() => {
              setClosed(false);
              setDisplay("manager");
              setAttentionOnly(false);
            }}
          >
            Manager view
          </ViewButton>
        ) : null}
        <ViewButton
          active={!closed && display === "list"}
          onClick={() => {
            if (closed) setLoading(true);
            setClosed(false);
            setDisplay("list");
          }}
        >
          List
        </ViewButton>
        <ViewButton
          active={closed}
          onClick={() => {
            setClosed(true);
            setDisplay("list");
            setAttentionOnly(false);
            setLoading(true);
          }}
        >
          Closed
        </ViewButton>
      </div>

      <form
        role="search"
        onSubmit={applySearch}
        className="mb-5 grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-[minmax(12rem,1fr)_auto_auto_auto_auto]"
      >
        <label className="sr-only" htmlFor="pipeline-search">
          Search opportunity or account
        </label>
        <input
          id="pipeline-search"
          className="form-control"
          value={searchDraft}
          onChange={(event) => setSearchDraft(event.target.value)}
          placeholder="Search opportunity or account"
        />
        <label className="sr-only" htmlFor="pipeline-definition">
          Pipeline
        </label>
        <select
          id="pipeline-definition"
          className="form-control"
          value={pipelineId}
          onChange={(event) => {
            setLoading(true);
            setPipelineId(event.target.value);
          }}
        >
          {board?.pipelines.map((pipeline) => (
            <option key={pipeline.id} value={pipeline.id}>
              {pipeline.name}
            </option>
          ))}
        </select>
        <label className="sr-only" htmlFor="pipeline-owner">
          Owner
        </label>
        <select
          id="pipeline-owner"
          className="form-control"
          value={ownerId}
          onChange={(event) => {
            setLoading(true);
            setOwnerId(event.target.value);
          }}
        >
          <option value="">All owners</option>
          {owners.map(([id, name]) => (
            <option key={id} value={id}>
              {name}
            </option>
          ))}
        </select>
        {!closed ? (
          <label className="flex min-h-11 items-center gap-2 rounded-xl border border-slate-300 px-3 text-sm font-semibold text-slate-700">
            <input
              type="checkbox"
              checked={attentionOnly}
              onChange={(event) => {
                setLoading(true);
                setAttentionOnly(event.target.checked);
              }}
            />
            Needs attention
          </label>
        ) : (
          <span />
        )}
        <button type="submit" className="secondary-button">
          Search
        </button>
      </form>

      {loading ? (
        <div role="status" className="form-card">
          Loading pipeline…
        </div>
      ) : null}
      {error ? (
        <div
          role="alert"
          className="mb-5 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"
        >
          {error}
          <button
            type="button"
            className="ml-3 font-bold underline"
            onClick={() => {
              setLoading(true);
              setRefreshKey((key) => key + 1);
            }}
          >
            Refresh
          </button>
        </div>
      ) : null}
      {!loading && board && display === "manager" && !closed ? (
        <ManagerPipelineView pipelineId={pipelineId} ownerUserId={ownerId} />
      ) : !loading && board ? (
        <>
          {board.authorityMessage ? (
            <div className="mb-5 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-950">
              <strong>Managed in HubSpot.</strong> {board.authorityMessage}
            </div>
          ) : null}
          <PipelineSummaryStrip board={board} />
          {board.cards.length === 0 ? (
            <div className="form-card text-center">
              <h2 className="text-xl font-semibold text-slate-950">
                {closed ? "No closed opportunities" : "No open opportunities"}
              </h2>
              <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-600">
                {closed
                  ? "Won and Lost opportunities will appear here with their seller-reported outcome."
                  : "Create an opportunity to start tracking it in the first open stage."}
              </p>
              {!closed ? (
                <Link href="/opportunities/new" className="primary-button mt-5">
                  New opportunity
                </Link>
              ) : null}
            </div>
          ) : closed || display === "list" ? (
            <PipelineList
              board={board}
              cards={board.cards.slice(0, visibleCardCount)}
              movingId={movingId}
              move={move}
            />
          ) : (
            <PipelineBoardView
              board={board}
              cards={board.cards.slice(0, visibleCardCount)}
              movingId={movingId}
              move={move}
            />
          )}
          {board.cards.length > PIPELINE_RENDER_BATCH ? (
            <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4">
              <p className="text-sm text-slate-600" aria-live="polite">
                Showing {Math.min(visibleCardCount, board.cards.length)} of{" "}
                {board.cards.length} opportunities. Filters still apply to the
                complete pipeline.
              </p>
              {visibleCardCount < board.cards.length ? (
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() =>
                    setVisibleCardCount((value) =>
                      Math.min(
                        value + PIPELINE_RENDER_BATCH,
                        board.cards.length,
                      ),
                    )
                  }
                >
                  Show next{" "}
                  {Math.min(
                    PIPELINE_RENDER_BATCH,
                    board.cards.length - visibleCardCount,
                  )}
                </button>
              ) : null}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function ViewButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`rounded-xl px-4 py-2 text-sm font-bold ${
        active
          ? "bg-slate-950 text-white"
          : "border border-slate-300 bg-white text-slate-700"
      }`}
    >
      {children}
    </button>
  );
}

function PipelineSummaryStrip({ board }: { board: PipelineBoard }) {
  return (
    <dl className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Summary
        label={
          board.view === "open" ? "Open opportunities" : "Closed opportunities"
        }
      >
        {board.summary.openOpportunityCount}
      </Summary>
      <Summary label="Open pipeline value">
        {board.summary.values.length
          ? board.summary.values
              .map((value) => formatCurrency(value.amount, value.currency))
              .join(" · ")
          : "No valued deals"}
      </Summary>
      <Summary label="Needs attention">
        {board.view === "open" ? board.summary.needsAttentionCount : "—"}
      </Summary>
      <Summary label="Close dates this month">
        {board.summary.closeDatesThisMonthCount}
      </Summary>
    </dl>
  );
}

function Summary({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-2 text-xl font-semibold text-slate-950">{children}</dd>
    </div>
  );
}

function PipelineBoardView({
  board,
  cards,
  movingId,
  move,
}: {
  board: PipelineBoard;
  cards: PipelineCard[];
  movingId: string | null;
  move: (card: PipelineCard, stageId: string) => Promise<void>;
}) {
  const stages = board.pipeline.stages.filter(
    (stage) => stage.stageType === "open" && stage.active,
  );
  return (
    <>
      <div className="grid gap-5 md:hidden">
        {stages.map((stage) => (
          <StageGroup
            key={stage.id}
            stage={stage}
            cards={cards.filter((card) => card.stageId === stage.id)}
            totalCount={
              board.cards.filter((card) => card.stageId === stage.id).length
            }
            board={board}
            movingId={movingId}
            move={move}
          />
        ))}
      </div>
      <div
        className="hidden overflow-x-auto pb-4 md:block"
        aria-label="Pipeline board"
      >
        <div
          className="grid min-w-max gap-4"
          style={{
            gridTemplateColumns: `repeat(${stages.length}, minmax(18rem, 20rem))`,
          }}
        >
          {stages.map((stage) => (
            <StageGroup
              key={stage.id}
              stage={stage}
              cards={cards.filter((card) => card.stageId === stage.id)}
              totalCount={
                board.cards.filter((card) => card.stageId === stage.id).length
              }
              board={board}
              movingId={movingId}
              move={move}
            />
          ))}
        </div>
      </div>
    </>
  );
}

function StageGroup({
  stage,
  cards,
  totalCount,
  board,
  movingId,
  move,
}: {
  stage: PipelineStage;
  cards: PipelineCard[];
  totalCount: number;
  board: PipelineBoard;
  movingId: string | null;
  move: (card: PipelineCard, stageId: string) => Promise<void>;
}) {
  return (
    <section
      aria-labelledby={`stage-${stage.id}`}
      className="rounded-2xl bg-slate-100/80 p-3"
    >
      <header className="mb-3 flex items-start justify-between gap-2 px-1">
        <div>
          <h2 id={`stage-${stage.id}`} className="font-semibold text-slate-950">
            {stage.name}
          </h2>
          {stage.guidance ? (
            <p className="mt-1 text-xs leading-5 text-slate-600">
              {stage.guidance}
            </p>
          ) : null}
        </div>
        <span className="rounded-full bg-white px-2 py-1 text-xs font-bold text-slate-600">
          {totalCount}
        </span>
      </header>
      <div className="grid gap-3">
        {cards.map((card) => (
          <OpportunityCard
            key={card.opportunityId}
            card={card}
            board={board}
            moving={movingId === card.opportunityId}
            move={move}
          />
        ))}
        {cards.length === 0 ? (
          <p className="rounded-xl border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500">
            No opportunities
          </p>
        ) : null}
      </div>
    </section>
  );
}

function OpportunityCard({
  card,
  board,
  moving,
  move,
}: {
  card: PipelineCard;
  board: PipelineBoard;
  moving: boolean;
  move: (card: PipelineCard, stageId: string) => Promise<void>;
}) {
  const openStages = board.pipeline.stages.filter(
    (stage) => stage.stageType === "open" && stage.active,
  );
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold text-slate-500">
        {card.companyName ?? "No account"}
      </p>
      <h3 className="mt-1 font-semibold leading-6 text-slate-950">
        <Link
          href={`/opportunities/${card.opportunityId}`}
          className="rounded hover:text-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600"
        >
          {card.opportunityName}
        </Link>
      </h3>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-700">
        <span>{formatCurrency(card.estimatedValue, card.currency)}</span>
        <span>Close {formatDate(card.expectedCloseDate)}</span>
      </div>
      <p className="mt-3 text-sm text-slate-700">
        <span className="font-semibold">Next:</span>{" "}
        {card.nextAction ?? "No next Action"}
      </p>
      {card.attentionReasons.length ? (
        <div className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs font-semibold leading-5 text-amber-950">
          <span aria-hidden="true">⚠ </span>
          {card.attentionReasons.join(" · ")}
        </div>
      ) : null}
      <div className="mt-3 flex items-end justify-between gap-3 border-t border-slate-100 pt-3 text-xs text-slate-500">
        <span>
          {card.daysInStage === null
            ? `Tracking since ${formatDateTime(card.stageTrackingStartedAt)}`
            : `${card.daysInStage} days in stage`}
        </span>
        <span>{card.ownerName}</span>
      </div>
      {board.stageChangesAllowed &&
      card.status !== "won" &&
      card.status !== "lost" ? (
        <label className="mt-3 block text-xs font-bold text-slate-600">
          Move stage
          <select
            className="form-control mt-1 w-full"
            value={card.stageId}
            disabled={moving}
            onChange={(event) => void move(card, event.target.value)}
          >
            {openStages.map((stage) => (
              <option key={stage.id} value={stage.id}>
                {stage.name}
              </option>
            ))}
          </select>
        </label>
      ) : null}
    </article>
  );
}

function PipelineList({
  board,
  cards,
  movingId,
  move,
}: {
  board: PipelineBoard;
  cards: PipelineCard[];
  movingId: string | null;
  move: (card: PipelineCard, stageId: string) => Promise<void>;
}) {
  return (
    <>
      <div className="grid gap-3 md:hidden">
        {cards.map((card) => (
          <OpportunityCard
            key={card.opportunityId}
            card={card}
            board={board}
            moving={movingId === card.opportunityId}
            move={move}
          />
        ))}
      </div>
      <div className="hidden overflow-x-auto rounded-2xl border border-slate-200 bg-white md:block">
        <table className="w-full min-w-[60rem] text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Opportunity</th>
              <th className="px-4 py-3">Stage</th>
              <th className="px-4 py-3">Value</th>
              <th className="px-4 py-3">Close date</th>
              <th className="px-4 py-3">Owner</th>
              <th className="px-4 py-3">Time in stage</th>
              <th className="px-4 py-3">Attention / outcome</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {cards.map((card) => (
              <tr key={card.opportunityId}>
                <td className="px-4 py-4">
                  <Link
                    className="font-semibold text-slate-950 hover:text-teal-800"
                    href={`/opportunities/${card.opportunityId}`}
                  >
                    {card.opportunityName}
                  </Link>
                  <span className="mt-1 block text-xs text-slate-500">
                    {card.companyName ?? "No account"}
                  </span>
                </td>
                <td className="px-4 py-4">{card.stageName}</td>
                <td className="px-4 py-4">
                  {formatCurrency(card.estimatedValue, card.currency)}
                </td>
                <td className="px-4 py-4">
                  {formatDate(card.actualCloseDate ?? card.expectedCloseDate)}
                </td>
                <td className="px-4 py-4">{card.ownerName}</td>
                <td className="px-4 py-4">
                  {card.daysInStage === null
                    ? "Timing unavailable"
                    : `${card.daysInStage} days`}
                </td>
                <td className="px-4 py-4">
                  {card.outcomeReason
                    ? `${humanise(card.outcomeReason)} · seller reported`
                    : card.attentionReasons.join(" · ") || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function formatCurrency(value: string | null, currency: string | null) {
  if (!value || !currency) return "Value not set";
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function formatDate(value: string | null) {
  if (!value) return "not set";
  return new Intl.DateTimeFormat("en-AU", { dateStyle: "medium" }).format(
    new Date(`${value}T00:00:00`),
  );
}

function formatDateTime(value: string | null) {
  if (!value) return "tracking began";
  return new Intl.DateTimeFormat("en-AU", { dateStyle: "medium" }).format(
    new Date(value),
  );
}

function requestKey(prefix: string) {
  const suffix =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random()}`;
  return `${prefix}:${suffix}`;
}
