"use client";

import type {
  Company,
  Contact,
  EntityPage,
  Meeting,
  MeetingParticipant,
  MeetingStatus,
  MeetingType,
  Transcript,
} from "@revenueos/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ChangeEvent,
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { ApiClientError, apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";
import {
  attendanceStatuses,
  emptyParticipant,
  meetingStatuses,
  meetingTypes,
  type MeetingParticipantDraft,
  participantRoles,
  toLocalDateTime,
} from "@/lib/meetings";

interface MeetingValues {
  title: string;
  description: string;
  meetingDate: string;
  companyId: string;
  meetingType: MeetingType;
  status: MeetingStatus;
}

const initialValues: MeetingValues = {
  title: "",
  description: "",
  meetingDate: "",
  companyId: "",
  meetingType: "other",
  status: "scheduled",
};

export function MeetingForm({ meetingId }: { meetingId?: string }) {
  const router = useRouter();
  const editing = Boolean(meetingId);
  const [values, setValues] = useState<MeetingValues>(initialValues);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [participants, setParticipants] = useState<MeetingParticipantDraft[]>(
    [],
  );
  const [originalParticipants, setOriginalParticipants] = useState<
    MeetingParticipant[]
  >([]);
  const [transcript, setTranscript] = useState("");
  const [language, setLanguage] = useState("en");
  const [transcriptSource, setTranscriptSource] = useState<"manual" | "upload">(
    "manual",
  );
  const [originalTranscript, setOriginalTranscript] =
    useState<Transcript | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  const loadForm = useCallback(
    async (signal: AbortSignal) => {
      const [companyPage, contactPage] = await Promise.all([
        apiRequest<EntityPage<Company>>("/api/v1/companies?pageSize=100", {
          signal,
        }),
        apiRequest<EntityPage<Contact>>("/api/v1/contacts?pageSize=100", {
          signal,
        }),
      ]);
      if (!meetingId) {
        return {
          companies: companyPage.items,
          contacts: contactPage.items,
          meeting: null,
          participants: [],
          transcript: null,
        };
      }
      const [meeting, meetingParticipants, loadedTranscript] =
        await Promise.all([
          apiRequest<Meeting>(`/api/v1/meetings/${meetingId}`, { signal }),
          apiRequest<MeetingParticipant[]>(
            `/api/v1/meetings/${meetingId}/participants`,
            { signal },
          ),
          loadTranscript(meetingId, signal),
        ]);
      return {
        companies: companyPage.items,
        contacts: contactPage.items,
        meeting,
        participants: meetingParticipants,
        transcript: loadedTranscript,
      };
    },
    [meetingId],
  );

  useEffect(() => {
    const controller = new AbortController();
    loadForm(controller.signal)
      .then((loaded) => {
        setCompanies(loaded.companies);
        setContacts(loaded.contacts);
        if (loaded.meeting) {
          setValues({
            title: loaded.meeting.title,
            description: loaded.meeting.description ?? "",
            meetingDate: toLocalDateTime(loaded.meeting.meetingDate),
            companyId: loaded.meeting.companyId ?? "",
            meetingType: loaded.meeting.meetingType,
            status: loaded.meeting.status,
          });
        }
        setOriginalParticipants(loaded.participants);
        setParticipants(
          loaded.participants.map((participant) => ({
            id: participant.id,
            contactId: participant.contactId ?? "",
            displayName: participant.displayName ?? "",
            email: participant.email ?? "",
            attendanceStatus: participant.attendanceStatus,
            role: participant.role,
          })),
        );
        setOriginalTranscript(loaded.transcript);
        if (loaded.transcript) {
          setTranscript(loaded.transcript.rawText);
          setLanguage(loaded.transcript.language);
          setTranscriptSource(loaded.transcript.source);
        }
      })
      .catch((requestError: unknown) => {
        if (
          requestError instanceof DOMException &&
          requestError.name === "AbortError"
        ) {
          return;
        }
        setLoadError(
          requestError instanceof Error
            ? requestError.message
            : "The meeting form could not be loaded.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [loadForm, retryKey]);

  const contactOptions = useMemo(
    () =>
      contacts.map((contact) => ({
        value: contact.id,
        label: `${contact.firstName} ${contact.lastName}`,
      })),
    [contacts],
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    const invalidParticipant = participants.find(
      (participant) =>
        !participant.contactId &&
        !participant.displayName.trim() &&
        !participant.email.trim(),
    );
    if (invalidParticipant) {
      setSubmitError(
        "Each participant needs a linked contact, display name or email.",
      );
      return;
    }

    setSubmitting(true);
    try {
      const meetingPayload = {
        title: values.title.trim(),
        description: values.description.trim() || null,
        meetingDate: new Date(values.meetingDate).toISOString(),
        companyId: values.companyId || null,
        meetingType: values.meetingType,
        status: values.status,
      };
      if (meetingId) {
        await apiRequest<Meeting>(`/api/v1/meetings/${meetingId}`, {
          method: "PATCH",
          body: JSON.stringify(meetingPayload),
        });
        await syncParticipants(meetingId, originalParticipants, participants);
        await syncTranscript(
          meetingId,
          originalTranscript,
          transcript,
          language,
          transcriptSource,
        );
        router.push(`/meetings/${meetingId}`);
      } else {
        const created = await apiRequest<Meeting>("/api/v1/meetings", {
          method: "POST",
          body: JSON.stringify({
            ...meetingPayload,
            participants: participants.map(participantPayload),
            transcript: transcript.trim()
              ? {
                  rawText: transcript.trim(),
                  language: language.trim(),
                  source: transcriptSource,
                }
              : null,
          }),
        });
        router.push(`/meetings/${created.id}`);
      }
    } catch (requestError: unknown) {
      setSubmitError(
        requestError instanceof Error
          ? requestError.message
          : "The meeting could not be saved.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function chooseTranscriptFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    setFileError(null);
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".txt")) {
      setFileError("Choose a plain text (.txt) file.");
      event.target.value = "";
      return;
    }
    if (file.size > 1_000_000) {
      setFileError("The transcript file must be 1 MB or smaller.");
      event.target.value = "";
      return;
    }
    let rawText: string;
    try {
      rawText = await file.text();
    } catch {
      setFileError("The transcript file could not be read.");
      event.target.value = "";
      return;
    }
    if (!rawText.trim()) {
      setFileError("The transcript file is empty.");
      event.target.value = "";
      return;
    }
    setTranscript(rawText);
    setTranscriptSource("upload");
  }

  async function deleteMeeting() {
    if (
      !meetingId ||
      !window.confirm(
        "Delete this meeting? It will be hidden using the soft-delete policy.",
      )
    ) {
      return;
    }
    setDeleting(true);
    setSubmitError(null);
    try {
      await apiRequest(`/api/v1/meetings/${meetingId}`, { method: "DELETE" });
      router.push("/meetings");
    } catch (requestError: unknown) {
      setSubmitError(
        requestError instanceof Error
          ? requestError.message
          : "The meeting could not be deleted.",
      );
    } finally {
      setDeleting(false);
    }
  }

  return (
    <section aria-labelledby="meeting-form-title">
      <header className="mb-8">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
          {editing ? "Edit meeting" : "New meeting"}
        </p>
        <h1
          id="meeting-form-title"
          className="mt-3 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl"
        >
          {editing ? "Edit meeting" : "Create meeting"}
        </h1>
        <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
          Add only information and transcript text you are authorised to store
          for the active organisation.
        </p>
      </header>

      {loading ? (
        <div
          role="status"
          className="rounded-2xl border border-slate-200 bg-white p-8"
        >
          Loading meeting form…
        </div>
      ) : null}
      {!loading && loadError ? (
        <div
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 p-6"
        >
          <h2 className="font-bold text-rose-950">
            Meeting form could not be loaded
          </h2>
          <p className="mt-2 text-sm text-rose-800">{loadError}</p>
          <button
            className="mt-4 rounded-lg bg-rose-900 px-4 py-2 text-sm font-bold text-white"
            type="button"
            onClick={() => {
              setLoading(true);
              setLoadError(null);
              setRetryKey((value) => value + 1);
            }}
          >
            Retry
          </button>
        </div>
      ) : null}
      {!loading && !loadError ? (
        <form onSubmit={submit} className="space-y-6">
          {submitError ? (
            <div
              id="meeting-form-error"
              role="alert"
              className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"
            >
              {submitError}
            </div>
          ) : null}

          <fieldset className="form-card">
            <legend className="form-legend">Meeting details</legend>
            <div className="grid gap-6 sm:grid-cols-2">
              <FormText
                id="meeting-title"
                label="Title"
                value={values.title}
                required
                onChange={(title) =>
                  setValues((current) => ({ ...current, title }))
                }
              />
              <FormText
                id="meeting-date"
                label="Meeting date"
                type="datetime-local"
                value={values.meetingDate}
                required
                onChange={(meetingDate) =>
                  setValues((current) => ({ ...current, meetingDate }))
                }
              />
              <label className="text-sm font-bold text-slate-800">
                Company
                <select
                  className="form-control mt-2 w-full"
                  value={values.companyId}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      companyId: event.target.value,
                    }))
                  }
                >
                  <option value="">No company</option>
                  {companies.map((company) => (
                    <option key={company.id} value={company.id}>
                      {company.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-bold text-slate-800">
                Meeting type
                <select
                  className="form-control mt-2 w-full"
                  value={values.meetingType}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      meetingType: event.target.value as MeetingType,
                    }))
                  }
                >
                  {meetingTypes.map((value) => (
                    <option key={value} value={value}>
                      {humanise(value)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-bold text-slate-800">
                Status
                <select
                  className="form-control mt-2 w-full"
                  value={values.status}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      status: event.target.value as MeetingStatus,
                    }))
                  }
                >
                  {meetingStatuses.map((value) => (
                    <option key={value} value={value}>
                      {humanise(value)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-bold text-slate-800 sm:col-span-2">
                Description
                <textarea
                  className="form-control mt-2 w-full py-3"
                  rows={5}
                  value={values.description}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      description: event.target.value,
                    }))
                  }
                />
              </label>
            </div>
          </fieldset>

          <fieldset className="form-card">
            <legend className="form-legend">Participants</legend>
            <div className="mt-4 flex justify-end">
              <button
                type="button"
                className="secondary-button"
                onClick={() =>
                  setParticipants((current) => [...current, emptyParticipant()])
                }
              >
                Add participant
              </button>
            </div>
            {participants.length === 0 ? (
              <p className="mt-4 text-sm text-slate-600">
                No participants added. Participants are optional.
              </p>
            ) : (
              <div className="mt-5 space-y-4">
                {participants.map((participant, index) => (
                  <ParticipantFields
                    key={participant.id ?? `participant-${index}`}
                    index={index}
                    participant={participant}
                    contactOptions={contactOptions}
                    onChange={(patch) =>
                      setParticipants((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, ...patch } : item,
                        ),
                      )
                    }
                    onRemove={() =>
                      setParticipants((current) =>
                        current.filter((_, itemIndex) => itemIndex !== index),
                      )
                    }
                  />
                ))}
              </div>
            )}
          </fieldset>

          <fieldset className="form-card">
            <legend className="form-legend">Transcript</legend>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Optional. Paste plain text or deliberately choose a .txt file.
              RevenueOS does not record or transcribe meetings in this sprint.
            </p>
            <div className="mt-5 grid gap-5 sm:grid-cols-[minmax(0,1fr)_12rem]">
              <label className="text-sm font-bold text-slate-800">
                Plain-text file
                <input
                  type="file"
                  accept=".txt,text/plain"
                  onChange={chooseTranscriptFile}
                  className="mt-2 block w-full text-sm text-slate-700 file:mr-4 file:rounded-lg file:border-0 file:bg-slate-100 file:px-4 file:py-3 file:font-bold file:text-slate-800"
                />
              </label>
              <FormText
                id="transcript-language"
                label="Language"
                value={language}
                required={Boolean(transcript.trim())}
                onChange={setLanguage}
              />
            </div>
            {fileError ? (
              <p className="mt-3 text-sm font-semibold text-rose-700">
                {fileError}
              </p>
            ) : null}
            <label className="mt-5 block text-sm font-bold text-slate-800">
              Transcript text
              <textarea
                className="form-control mt-2 w-full font-mono leading-6"
                rows={14}
                maxLength={1_000_000}
                value={transcript}
                onChange={(event) => {
                  setTranscript(event.target.value);
                  if (transcriptSource !== "upload")
                    setTranscriptSource("manual");
                }}
                placeholder="Paste authorised plain-text transcript content"
              />
            </label>
          </fieldset>

          <div className="flex flex-col-reverse gap-3 border-t border-slate-200 pt-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              {meetingId ? (
                <button
                  type="button"
                  className="min-h-11 rounded-xl border border-rose-300 px-5 text-sm font-bold text-rose-800 hover:bg-rose-50 disabled:opacity-60"
                  disabled={deleting || submitting}
                  onClick={deleteMeeting}
                >
                  {deleting ? "Deleting…" : "Delete meeting"}
                </button>
              ) : null}
            </div>
            <div className="flex flex-col-reverse gap-3 sm:flex-row">
              <Link
                href={meetingId ? `/meetings/${meetingId}` : "/meetings"}
                className="secondary-button"
              >
                Cancel
              </Link>
              <button
                type="submit"
                disabled={submitting || deleting}
                aria-describedby={
                  submitError ? "meeting-form-error" : undefined
                }
                className="primary-button"
              >
                {submitting
                  ? "Saving…"
                  : editing
                    ? "Save meeting"
                    : "Create meeting"}
              </button>
            </div>
          </div>
        </form>
      ) : null}
    </section>
  );
}

function ParticipantFields({
  index,
  participant,
  contactOptions,
  onChange,
  onRemove,
}: {
  index: number;
  participant: MeetingParticipantDraft;
  contactOptions: { value: string; label: string }[];
  onChange: (patch: Partial<MeetingParticipantDraft>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h3 className="font-bold text-slate-900">Participant {index + 1}</h3>
        <button
          type="button"
          className="text-sm font-bold text-rose-700 hover:text-rose-900"
          onClick={onRemove}
        >
          Remove
        </button>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <label className="text-sm font-bold text-slate-800">
          Linked contact
          <select
            className="form-control mt-2 w-full"
            value={participant.contactId}
            onChange={(event) => onChange({ contactId: event.target.value })}
          >
            <option value="">No linked contact</option>
            {contactOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <FormText
          id={`participant-${index}-name`}
          label="Display name"
          value={participant.displayName}
          onChange={(displayName) => onChange({ displayName })}
        />
        <FormText
          id={`participant-${index}-email`}
          label="Email"
          type="email"
          value={participant.email}
          onChange={(email) => onChange({ email })}
        />
        <label className="text-sm font-bold text-slate-800">
          Attendance
          <select
            className="form-control mt-2 w-full"
            value={participant.attendanceStatus}
            onChange={(event) =>
              onChange({
                attendanceStatus: event.target
                  .value as MeetingParticipantDraft["attendanceStatus"],
              })
            }
          >
            {attendanceStatuses.map((value) => (
              <option key={value} value={value}>
                {humanise(value)}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-bold text-slate-800">
          Role
          <select
            className="form-control mt-2 w-full"
            value={participant.role}
            onChange={(event) =>
              onChange({
                role: event.target.value as MeetingParticipantDraft["role"],
              })
            }
          >
            {participantRoles.map((value) => (
              <option key={value} value={value}>
                {humanise(value)}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}

function FormText({
  id,
  label,
  value,
  type = "text",
  required = false,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  type?: "text" | "email" | "datetime-local";
  required?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label htmlFor={id} className="text-sm font-bold text-slate-800">
      {label}
      {required ? <span aria-hidden="true"> *</span> : null}
      <input
        id={id}
        className="form-control mt-2 w-full"
        type={type}
        value={value}
        required={required}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

async function loadTranscript(
  meetingId: string,
  signal: AbortSignal,
): Promise<Transcript | null> {
  try {
    return await apiRequest<Transcript>(
      `/api/v1/meetings/${meetingId}/transcript`,
      { signal },
    );
  } catch (error) {
    if (error instanceof ApiClientError && error.status === 404) return null;
    throw error;
  }
}

function participantPayload(participant: MeetingParticipantDraft) {
  return {
    contactId: participant.contactId || null,
    displayName: participant.displayName.trim() || null,
    email: participant.email.trim() || null,
    attendanceStatus: participant.attendanceStatus,
    role: participant.role,
  };
}

async function syncParticipants(
  meetingId: string,
  original: MeetingParticipant[],
  current: MeetingParticipantDraft[],
) {
  const originalsById = new Map(
    original.map((participant) => [participant.id, participant]),
  );
  const currentIds = new Set(
    current
      .map((participant) => participant.id)
      .filter((id): id is string => Boolean(id)),
  );
  await Promise.all(
    original
      .filter((participant) => !currentIds.has(participant.id))
      .map((participant) =>
        apiRequest(
          `/api/v1/meetings/${meetingId}/participants/${participant.id}`,
          { method: "DELETE" },
        ),
      ),
  );
  await Promise.all(
    current
      .filter((participant) => {
        if (!participant.id) return true;
        const originalParticipant = originalsById.get(participant.id);
        return (
          !originalParticipant ||
          !participantMatches(originalParticipant, participant)
        );
      })
      .map((participant) =>
        apiRequest(
          `/api/v1/meetings/${meetingId}/participants${participant.id ? `/${participant.id}` : ""}`,
          {
            method: participant.id ? "PATCH" : "POST",
            body: JSON.stringify(participantPayload(participant)),
          },
        ),
      ),
  );
}

function participantMatches(
  original: MeetingParticipant,
  current: MeetingParticipantDraft,
): boolean {
  const payload = participantPayload(current);
  return (
    original.contactId === payload.contactId &&
    original.displayName === payload.displayName &&
    original.email === payload.email &&
    original.attendanceStatus === payload.attendanceStatus &&
    original.role === payload.role
  );
}

async function syncTranscript(
  meetingId: string,
  original: Transcript | null,
  rawText: string,
  language: string,
  source: "manual" | "upload",
) {
  const trimmedText = rawText.trim();
  if (!trimmedText && original) {
    await apiRequest(`/api/v1/meetings/${meetingId}/transcript`, {
      method: "DELETE",
    });
  } else if (
    trimmedText &&
    original &&
    (trimmedText !== original.rawText || language.trim() !== original.language)
  ) {
    await apiRequest(`/api/v1/meetings/${meetingId}/transcript`, {
      method: "PATCH",
      body: JSON.stringify({
        rawText: trimmedText,
        language: language.trim(),
        version: original.version,
      }),
    });
  } else if (trimmedText && !original) {
    await apiRequest(`/api/v1/meetings/${meetingId}/transcript`, {
      method: "POST",
      body: JSON.stringify({
        rawText: trimmedText,
        language: language.trim(),
        source,
      }),
    });
  }
}
