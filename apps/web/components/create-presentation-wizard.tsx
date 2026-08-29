"use client";

import type {
  BusinessCaseList,
  Company,
  Contact,
  CreatePresentation,
  CreatePresentationObjective,
  CreateTemplateList,
  EntityPage,
  Opportunity,
} from "@revenueos/shared";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { apiRequest } from "@/lib/api";
import { humanise } from "@/lib/business-entities";

const objectives: Array<{
  value: CreatePresentationObjective;
  label: string;
  description: string;
}> = [
  {
    value: "introductory_meeting",
    label: "Introductory meeting",
    description: "A concise first conversation using approved company context.",
  },
  {
    value: "discovery_follow_up",
    label: "Discovery follow-up",
    description:
      "Reflect reviewed customer needs and confirm the next discussion.",
  },
  {
    value: "solution_overview",
    label: "Solution overview",
    description: "Connect approved capabilities to customer-safe context.",
  },
  {
    value: "technical_workshop",
    label: "Technical workshop",
    description: "Use approved architecture, capability and process content.",
  },
  {
    value: "executive_presentation",
    label: "Executive presentation",
    description: "A focused narrative for senior stakeholders.",
  },
  {
    value: "proposal_presentation",
    label: "Proposal presentation",
    description:
      "A reviewed presentation proposal; pricing remains out of scope.",
  },
  {
    value: "business_case",
    label: "Business case",
    description:
      "Use an approved deterministic Business Case; RevenueOS never invents ROI inputs or outputs.",
  },
  {
    value: "event_follow_up",
    label: "Event follow-up",
    description: "A relevant post-event conversation starter.",
  },
];

export function CreatePresentationWizard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [templates, setTemplates] = useState<CreateTemplateList | null>(null);
  const [businessCases, setBusinessCases] = useState<BusinessCaseList | null>(
    null,
  );
  const [accountId, setAccountId] = useState(
    searchParams.get("accountId") ?? "",
  );
  const [opportunityId, setOpportunityId] = useState(
    searchParams.get("opportunityId") ?? "",
  );
  const [businessCaseVersionId, setBusinessCaseVersionId] = useState(
    searchParams.get("businessCaseVersionId") ?? "",
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      apiRequest<EntityPage<Company>>("/api/v1/companies?pageSize=100", {
        signal: controller.signal,
      }),
      apiRequest<EntityPage<Opportunity>>(
        "/api/v1/opportunities?pageSize=100",
        { signal: controller.signal },
      ),
      apiRequest<EntityPage<Contact>>("/api/v1/contacts?pageSize=100", {
        signal: controller.signal,
      }),
      apiRequest<CreateTemplateList>("/api/v1/create/templates", {
        signal: controller.signal,
      }),
      apiRequest<BusinessCaseList>(
        "/api/v1/create/business-cases?approvedOnly=true",
        { signal: controller.signal },
      ),
    ])
      .then(
        ([
          companyPage,
          opportunityPage,
          contactPage,
          templateList,
          caseList,
        ]) => {
          setCompanies(companyPage.items);
          setOpportunities(opportunityPage.items);
          setContacts(contactPage.items);
          setTemplates(templateList);
          setBusinessCases(caseList);
        },
      )
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(
          reason instanceof Error
            ? reason.message
            : "Presentation options could not be loaded.",
        );
      });
    return () => controller.abort();
  }, []);

  const accountOpportunities = useMemo(
    () => opportunities.filter((item) => item.companyId === accountId),
    [accountId, opportunities],
  );
  const accountContacts = useMemo(
    () => contacts.filter((item) => item.companyId === accountId),
    [accountId, contacts],
  );
  const approvedTemplates =
    templates?.items.filter(
      (item) => item.latestVersion.approvalState === "approved",
    ) ?? [];
  const approvedBusinessCases =
    businessCases?.items.filter(
      (item) =>
        item.accountId === accountId &&
        (item.opportunityId === null ||
          item.opportunityId === (opportunityId || null)) &&
        item.currentVersion?.reviewState === "approved",
    ) ?? [];

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const contactId = String(data.get("contactId") ?? "");
    const audienceName = String(data.get("audienceName") ?? "").trim();
    const audienceRole = String(data.get("audienceRole") ?? "").trim();
    setSaving(true);
    setError(null);
    try {
      const created = await apiRequest<CreatePresentation>(
        "/api/v1/create/presentations",
        {
          method: "POST",
          body: JSON.stringify({
            accountId,
            opportunityId: opportunityId || null,
            objective: data.get("objective"),
            audience: [
              {
                contactId: contactId || null,
                name: audienceName || null,
                role: audienceRole || null,
                audienceType: data.get("audienceType"),
              },
            ],
            templateVersionId: data.get("templateVersionId"),
            businessCaseVersionId: businessCaseVersionId || null,
            businessCaseScenario: businessCaseVersionId
              ? data.get("businessCaseScenario")
              : null,
            focusInstruction:
              String(data.get("focusInstruction") ?? "").trim() || null,
            title: String(data.get("title") ?? "").trim() || null,
            idempotencyKey: `web-plan-${crypto.randomUUID()}`,
          }),
        },
      );
      router.push(`/create/presentations/${created.id}`);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The presentation plan could not be created.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Create · Guided brief"
        title="Plan a presentation"
        description="Choose the customer context and approved source template. RevenueOS will show a deterministic slide plan before it generates anything."
      />
      <nav aria-label="Breadcrumb" className="text-sm text-slate-600">
        <Link
          href="/create"
          className="font-semibold text-teal-800 hover:underline"
        >
          Create
        </Link>{" "}
        <span aria-hidden="true">/</span> New presentation
      </nav>

      <form onSubmit={(event) => void submit(event)} className="space-y-6">
        <fieldset className="form-card" disabled={saving}>
          <legend className="form-legend">1. Customer context</legend>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            An Account is required. The optional Opportunity must belong to that
            Account. Internal forecasting and financial fields are not loaded
            into Create.
          </p>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="field-label">
              Account
              <select
                required
                value={accountId}
                onChange={(event) => {
                  setAccountId(event.target.value);
                  setOpportunityId("");
                  setBusinessCaseVersionId("");
                }}
                className="field-input mt-2"
              >
                <option value="">Choose an Account</option>
                {companies.map((company) => (
                  <option key={company.id} value={company.id}>
                    {company.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-label">
              Opportunity (optional)
              <select
                value={opportunityId}
                disabled={!accountId}
                onChange={(event) => {
                  setOpportunityId(event.target.value);
                  setBusinessCaseVersionId("");
                }}
                className="field-input mt-2"
              >
                <option value="">Account-level presentation</option>
                {accountOpportunities.map((opportunity) => (
                  <option key={opportunity.id} value={opportunity.id}>
                    {opportunity.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </fieldset>

        <fieldset className="form-card" disabled={saving}>
          <legend className="form-legend">2. Objective and audience</legend>
          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <label className="field-label">
              Objective
              <select
                name="objective"
                required
                defaultValue="solution_overview"
                className="field-input mt-2"
              >
                {objectives.map((objective) => (
                  <option key={objective.value} value={objective.value}>
                    {objective.label}
                  </option>
                ))}
              </select>
              <span className="mt-2 block text-xs font-normal leading-5 text-slate-500">
                The objective prioritises approved slide categories; it does not
                invent claims.
              </span>
            </label>
            <label className="field-label">
              Audience type
              <select
                name="audienceType"
                required
                defaultValue="executive"
                className="field-input mt-2"
              >
                {[
                  "executive",
                  "technical",
                  "finance",
                  "procurement",
                  "mixed",
                  "other",
                ].map((value) => (
                  <option key={value} value={value}>
                    {humanise(value)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-label">
              Known Contact (optional)
              <select
                name="contactId"
                disabled={!accountId}
                className="field-input mt-2"
              >
                <option value="">Use a role or name instead</option>
                {accountContacts.map((contact) => (
                  <option key={contact.id} value={contact.id}>
                    {contact.firstName} {contact.lastName}
                    {contact.jobTitle ? ` · ${contact.jobTitle}` : ""}
                  </option>
                ))}
              </select>
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="field-label">
                Name (optional)
                <input
                  name="audienceName"
                  maxLength={200}
                  className="field-input mt-2"
                />
              </label>
              <label className="field-label">
                Role (optional)
                <input
                  name="audienceRole"
                  maxLength={120}
                  className="field-input mt-2"
                />
              </label>
            </div>
          </div>
        </fieldset>

        <fieldset className="form-card" disabled={saving}>
          <legend className="form-legend">
            3. Approved Business Case (optional)
          </legend>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Only the current approved immutable version can enter a customer
            deck. Choose the base case, or show all explicitly labelled
            scenarios. Material assumptions remain visible.
          </p>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="field-label">
              Business Case
              <select
                value={businessCaseVersionId}
                disabled={!accountId}
                onChange={(event) =>
                  setBusinessCaseVersionId(event.target.value)
                }
                className="field-input mt-2"
              >
                <option value="">Do not include a Business Case</option>
                {approvedBusinessCases.map((item) => (
                  <option
                    key={item.currentVersion?.id}
                    value={item.currentVersion?.id}
                  >
                    {item.title} · {item.currency} · version{" "}
                    {item.currentVersion?.version}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-label">
              Scenario display
              <select
                name="businessCaseScenario"
                disabled={!businessCaseVersionId}
                defaultValue="base"
                className="field-input mt-2"
              >
                <option value="base">Base case + key assumptions</option>
                <option value="all">Conservative + base + upside</option>
              </select>
            </label>
          </div>
          {accountId && approvedBusinessCases.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">
              No approved Business Case matches this Account and Opportunity.
              You can still create a presentation from other approved sources.
            </p>
          ) : null}
        </fieldset>

        <fieldset className="form-card" disabled={saving}>
          <legend className="form-legend">
            4. Approved template and focus
          </legend>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="field-label">
              Template version
              <select
                name="templateVersionId"
                required
                className="field-input mt-2"
              >
                <option value="">Choose an approved template</option>
                {approvedTemplates.map((template) => (
                  <option
                    key={template.latestVersion.id}
                    value={template.latestVersion.id}
                  >
                    {template.name} · version {template.latestVersion.version}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-label">
              Presentation title (optional)
              <input
                name="title"
                maxLength={240}
                className="field-input mt-2"
              />
            </label>
          </div>
          <label className="field-label mt-4 block">
            Bounded focus instruction (optional)
            <textarea
              name="focusInstruction"
              maxLength={500}
              rows={3}
              className="field-input mt-2"
              placeholder="For example: Keep the implementation discussion concise."
            />
          </label>
          <p className="mt-3 text-xs leading-5 text-slate-500">
            Focus can prioritise approved material. It cannot introduce pricing,
            ROI, unsupported customer claims or internal deal guidance.
          </p>
        </fieldset>

        {error ? (
          <p
            role="alert"
            className="rounded-xl bg-rose-50 p-4 text-sm text-rose-900"
          >
            {error}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-3">
          <button
            type="submit"
            disabled={saving || !accountId || approvedTemplates.length === 0}
            className="primary-button"
          >
            {saving ? "Building plan…" : "Review slide plan"}
          </button>
          <Link href="/create" className="secondary-button">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
