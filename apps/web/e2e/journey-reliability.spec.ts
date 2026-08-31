import { expect, test, type Page, type Route } from "@playwright/test";

const ids = {
  target: "target-northstar-flagship",
  person: "person-jane-flagship",
  account: "company-northstar-flagship",
  contact: "contact-jane-flagship",
  outreach: "outreach-jane-flagship",
  action: "action-jane-flagship",
  interaction: "interaction-northstar-flagship",
  evidence: "evidence-northstar-flagship",
  opportunity: "opportunity-northstar-flagship",
  pipeline: "pipeline-flagship",
  discovery: "stage-discovery-flagship",
  proposal: "stage-proposal-flagship",
  won: "stage-won-flagship",
  businessCase: "case-northstar-flagship",
  presentation: "presentation-northstar-flagship",
  targetGoal: "target-goal-northstar-flagship",
} as const;

interface JourneyState {
  researchStarted: boolean;
  peopleFound: boolean;
  accountPromoted: boolean;
  contactPromoted: boolean;
  outreachApproved: boolean;
  outreachSimulated: boolean;
  briefReviewed: boolean;
  interactionStarted: boolean;
  interactionReviewed: boolean;
  debriefAnswerSaved: boolean;
  debriefReviewReady: boolean;
  evidenceAccepted: boolean;
  actionApproved: boolean;
  opportunityCreated: boolean;
  presentationState: "not_created" | "draft_plan" | "needs_review" | "ready";
  presentationClaimReviewed: boolean;
  stage: "discovery" | "proposal" | "closed_won";
  closedWon: boolean;
}

const state: JourneyState = {
  researchStarted: false,
  peopleFound: false,
  accountPromoted: false,
  contactPromoted: false,
  outreachApproved: false,
  outreachSimulated: false,
  briefReviewed: false,
  interactionStarted: false,
  interactionReviewed: false,
  debriefAnswerSaved: false,
  debriefReviewReady: false,
  evidenceAccepted: false,
  actionApproved: false,
  opportunityCreated: false,
  presentationState: "not_created",
  presentationClaimReviewed: false,
  stage: "discovery",
  closedWon: false,
};

const account = {
  id: ids.account,
  organisationId: "organisation-flagship",
  name: "Northstar Facilities Group",
  website: "https://northstar-facilities.example/",
  industry: "Facilities services",
  location: "Sydney, Australia",
  employeeCount: 750,
  status: "prospect",
  ownerUserId: "user-flagship",
  archivedAt: null,
  createdAt: "2026-08-31T00:00:00Z",
  updatedAt: "2026-08-31T00:00:00Z",
};

const contact = {
  id: ids.contact,
  organisationId: "organisation-flagship",
  companyId: ids.account,
  firstName: "Jane",
  lastName: "Smith",
  email: "jane.smith@northstar-facilities.example",
  phone: null,
  jobTitle: "Chief Technology Officer",
  linkedinUrl: null,
  status: "active",
  ownerUserId: "user-flagship",
  archivedAt: null,
  createdAt: "2026-08-31T00:00:00Z",
  updatedAt: "2026-08-31T00:00:00Z",
};

const researchRun = {
  id: "research-run-flagship",
  status: "completed",
  refreshOfRunId: null,
  createdAt: "2026-08-31T00:00:00Z",
  startedAt: "2026-08-31T00:00:01Z",
  completedAt: "2026-08-31T00:00:02Z",
  sourceCount: 1,
  observationCount: 1,
  errorCode: null,
};

const source = {
  id: "source-northstar-flagship",
  sourceType: "official_website",
  url: "https://northstar-facilities.example/about",
  canonicalUrl: "https://northstar-facilities.example/about",
  domain: "northstar-facilities.example",
  title: "About Northstar Facilities Group",
  publisher: "Northstar Facilities Group",
  publishedAt: "2026-05-14T00:00:00Z",
  retrievedAt: "2026-08-31T00:00:02Z",
  authorityClass: "official_public",
};

function companyBrief() {
  return {
    target: {
      id: ids.target,
      name: account.name,
      domain: "northstar-facilities.example",
      websiteUrl: account.website,
      location: account.location,
      industry: account.industry,
      providerAttribution: "RevenueOS synthetic research data",
      promotedCompanyId: state.accountPromoted ? ids.account : null,
      promotedAt: state.accountPromoted ? "2026-08-31T00:04:00Z" : null,
      createdAt: "2026-08-31T00:00:00Z",
      updatedAt: "2026-08-31T00:02:00Z",
    },
    status: state.researchStarted ? "ready" : "not_started",
    statusMessage: state.researchStarted
      ? "Research ready."
      : "Ready to research. No research job has been started.",
    currentRun: state.researchStarted ? researchRun : null,
    latestRun: state.researchStarted ? researchRun : null,
    observations: state.researchStarted
      ? [
          {
            id: "observation-northstar-flagship",
            observationKey: "company_profile",
            category: "company_profile",
            statement:
              "Northstar Facilities Group manages facilities operations across 18 Australian sites.",
            trustState: "verified",
            relevance: "high",
            observedAt: "2026-05-14T00:00:00Z",
            freshness: "stable",
            sourceIds: [source.id],
          },
        ]
      : [],
    sources: state.researchStarted ? [source] : [],
    changes: [],
    history: state.researchStarted ? [researchRun] : [],
    existingCompanyMatch: null,
  };
}

const person = {
  id: ids.person,
  companyTargetId: ids.target,
  displayName: "Jane Smith",
  currentRole: "Chief Technology Officer",
  currentCompany: account.name,
  publicProfessionalLocation: "Sydney, Australia",
  publicProfileUrl:
    "https://northstar-facilities.example/leadership/jane-smith",
  relevantFunction: "technology",
  whyMayMatter:
    "Her public remit suggests she may help evaluate operational technology change.",
  providerAttribution: "RevenueOS synthetic research data",
  identityState: "supported",
  employmentState: "current",
  researchStatus: "ready",
  promotedContactId: state.contactPromoted ? ids.contact : null,
  promotedAt: state.contactPromoted ? "2026-08-31T00:05:00Z" : null,
  createdAt: "2026-08-31T00:00:00Z",
  updatedAt: "2026-08-31T00:03:00Z",
};

function personBrief() {
  return {
    person: {
      ...person,
      promotedContactId: state.contactPromoted ? ids.contact : null,
    },
    status: "ready",
    statusMessage: "Public professional research is ready.",
    currentRun: researchRun,
    latestRun: researchRun,
    observations: [
      {
        id: "person-observation-flagship",
        observationKey: "current_role",
        category: "current_role",
        statement: "Northstar lists Jane Smith as Chief Technology Officer.",
        trustState: "verified",
        relevance: "high",
        observedAt: "2026-08-31T00:00:00Z",
        freshness: "current",
        sourceIds: [source.id],
      },
    ],
    sources: [source],
    buyingRoles: [
      {
        id: "role-technical-evaluator-flagship",
        role: "technical_evaluator",
        rationale:
          "Jane may evaluate technical fit; seller validation is required.",
        trustState: "inferred",
        reviewState: "needs_validation",
        assessmentOrigin: "system_hypothesis",
        sourceIds: [source.id],
        reviewedAt: null,
      },
    ],
    contactPoints: [
      {
        id: "email-jane-flagship",
        pointType: "business_email",
        value: contact.email,
        trustState: "provider_supplied",
        verificationMethod: "provider_reported",
        sourceId: source.id,
        observedAt: "2026-08-31T00:00:00Z",
        expiresAt: "2026-09-30T00:00:00Z",
        exportAllowed: true,
        permissionStatus: "not_assessed",
      },
    ],
    changes: [],
    history: [researchRun],
    existingContactMatches: [],
  };
}

const stages = [
  {
    id: ids.discovery,
    pipelineId: ids.pipeline,
    key: "discovery",
    name: "Discovery",
    position: 0,
    stageType: "open",
    guidance: null,
    active: true,
    archivedAt: null,
    currentOpportunityCount: state.stage === "discovery" ? 1 : 0,
  },
  {
    id: ids.proposal,
    pipelineId: ids.pipeline,
    key: "proposal",
    name: "Proposal",
    position: 1,
    stageType: "open",
    guidance: null,
    active: true,
    archivedAt: null,
    currentOpportunityCount: state.stage === "proposal" ? 1 : 0,
  },
  {
    id: ids.won,
    pipelineId: ids.pipeline,
    key: "closed_won",
    name: "Closed Won",
    position: 2,
    stageType: "won",
    guidance: null,
    active: true,
    archivedAt: null,
    currentOpportunityCount: state.closedWon ? 1 : 0,
  },
];

function opportunity() {
  return {
    id: ids.opportunity,
    organisationId: "organisation-flagship",
    companyId: ids.account,
    name: "National operations rollout",
    stage: state.stage,
    status: state.closedWon ? "won" : "open",
    estimatedValue: "420000.00",
    currency: "AUD",
    expectedCloseDate: "2026-09-30",
    ownerUserId: "user-flagship",
    description: "Synthetic flagship Opportunity.",
    archivedAt: null,
    createdAt: "2026-08-31T00:00:00Z",
    updatedAt: "2026-08-31T00:10:00Z",
  };
}

function crmRecord(entityType: "account" | "contact" | "opportunity") {
  const entityId =
    entityType === "account"
      ? ids.account
      : entityType === "contact"
        ? ids.contact
        : ids.opportunity;
  const title =
    entityType === "account"
      ? account.name
      : entityType === "contact"
        ? "Jane Smith"
        : "National operations rollout";
  return {
    entityType,
    entityId,
    title,
    ownerUserId: "user-flagship",
    ownerName: "Alex Morgan",
    archivedAt: null,
    recordUpdatedAt: "2026-08-31T00:10:00Z",
    mode: "native",
    crmEnabled: true,
    canManage: true,
    customFieldsReadOnly: false,
    fieldAuthority: {},
    coreFields: [],
    customFields: [],
    history: [],
    activity: [],
    cursor: null,
  };
}

function contactWorkspace() {
  return {
    availability: {
      moduleKey: "engage",
      state: "available",
      enabled: true,
      canManage: true,
      message: "RevenueOS Engage is available for this organisation.",
    },
    contactId: ids.contact,
    contactName: "Jane Smith",
    companyId: ids.account,
    companyName: account.name,
    jobTitle: contact.jobTitle,
    email: contact.email,
    emailTrust: "provider_supplied",
    permissionStatus: "assessed_by_organisation_policy",
    contactability: {
      state: "allowed",
      allowed: true,
      reason: "Allowed by the synthetic organisation policy.",
      trustState: "provider_supplied",
      permissionAssessedSeparately: true,
    },
    policyConfigured: true,
    productionMailboxAvailable: false,
    simulationAvailable: true,
    history: state.outreachSimulated
      ? [
          {
            id: ids.outreach,
            subject: "Northstar's next phase",
            status: "simulated_success",
            simulationOnly: true,
            createdAt: "2026-08-31T00:06:00Z",
          },
        ]
      : [],
  };
}

function outreach() {
  return {
    id: ids.outreach,
    actionId: ids.action,
    contactId: ids.contact,
    purpose: "request_meeting",
    state: state.outreachSimulated
      ? "simulated_success"
      : state.outreachApproved
        ? "approved"
        : "draft",
    currentVersion: 1,
    approvedVersion: state.outreachApproved ? 1 : null,
    version: {
      id: "outreach-version-flagship",
      version: 1,
      subject: "Northstar's next phase",
      body: "Hi Jane,\n\nWould a short conversation about consistent multi-site operations be useful?\n\nRegards,\nAlex",
      senderName: "Alex Morgan",
      senderEmail: "alex@example.test",
      recipientName: "Jane Smith",
      recipientEmail: contact.email,
      recipientTrust: "provider_supplied",
      creationType: "generated",
      composerVersion: "outreach_deterministic_v1",
      personalizationUsed: true,
      sources: [],
      warnings: [],
      createdAt: "2026-08-31T00:06:00Z",
    },
    contactability: contactWorkspace().contactability,
    relationshipWarning: null,
    execution: state.outreachSimulated
      ? {
          id: "execution-flagship",
          executionStatus: "simulated_success",
          executionMode: "simulation",
          simulationOnly: true,
          safeMessage: "The email simulation completed successfully.",
        }
      : null,
    createdAt: "2026-08-31T00:06:00Z",
    updatedAt: "2026-08-31T00:06:00Z",
  };
}

function preparationBrief() {
  return {
    state: "completed",
    generationAvailable: true,
    unavailableReason: null,
    safeMessage: null,
    generatedAt: "2026-08-31T00:06:30Z",
    reviewed: state.briefReviewed,
    reviewedAt: state.briefReviewed ? "2026-08-31T00:06:45Z" : null,
    priorVersions: [],
    sourceLabels: [
      "Interaction details",
      "Account record",
      "Reviewed public research",
    ],
    brief: {
      interactionId: ids.interaction,
      interactionType: "phone_call",
      briefVersion: 1,
      headline: "Confirm rollout ownership and agree the next workshop.",
      accountContext:
        "Northstar operates 18 Australian sites and Jane is the reviewed technology Contact.",
      recentChanges: [
        {
          change: "Northstar expanded its multi-site operating footprint.",
          importance: "high",
          source: "prospect_research",
        },
      ],
      objectives: [
        {
          objective: "Confirm who owns the national rollout.",
          priority: "high",
          reason: "Ownership is not yet customer-confirmed.",
        },
      ],
      questionsToAsk: [
        {
          question: "Who owns approval for the national rollout?",
          purpose: "Clarify the decision path.",
          priority: "high",
        },
      ],
      stakeholderFocus: [
        {
          name: "Jane Smith",
          role: "Technical evaluator",
          focus:
            "Validate ownership without upgrading public research to customer evidence.",
        },
      ],
      openCommitments: [],
      risksToWatch: [
        {
          risk: "The commercial approval path is not yet confirmed.",
          severity: "medium",
        },
      ],
      successCriteria: ["A next step, owner and timing are agreed."],
      interactionGuidance:
        "Keep the call concise and close with one customer-confirmed next step.",
      confidence: 0.82,
      companyName: account.name,
      opportunityName: null,
      participants: [{ name: "Jane Smith", role: "Technical evaluator" }],
      nextBestAction: "Confirm rollout ownership.",
    },
  };
}

function interaction() {
  const lifecycleStatus = state.interactionReviewed
    ? "completed"
    : state.interactionStarted
      ? "in_progress"
      : "planned";
  return {
    id: ids.interaction,
    organisationId: "organisation-flagship",
    companyId: ids.account,
    opportunityId: state.opportunityCreated ? ids.opportunity : null,
    contactId: ids.contact,
    meetingId: null,
    eventId: null,
    interactionType: "phone_call",
    lifecycleStatus,
    title: "Northstar rollout discovery",
    scheduledStartAt: "2026-08-31T01:00:00Z",
    scheduledEndAt: null,
    actualStartAt:
      state.interactionStarted || state.interactionReviewed
        ? "2026-08-31T01:00:00Z"
        : null,
    actualEndAt: state.interactionReviewed ? "2026-08-31T01:30:00Z" : null,
    timezone: "Australia/Sydney",
    creationOrigin: "manual",
    callDirection: "outbound",
    callOutcome: state.interactionReviewed ? "connected" : null,
    meetingPlatform: null,
    meetingUrl: null,
    externalMeetingId: null,
    captureSource: null,
    ingestionState: null,
    durationSeconds: state.interactionReviewed ? 1800 : null,
    captureMethods: state.evidenceAccepted ? ["debrief"] : [],
    intelligenceState: state.evidenceAccepted ? "ready" : "not_started",
    recordingAvailable: false,
    createdByUserId: "user-flagship",
    briefState: "completed",
    briefGeneratedAt: "2026-08-31T00:06:30Z",
    createdAt: "2026-08-31T00:07:00Z",
    updatedAt: "2026-08-31T00:08:00Z",
  };
}

function reportedCandidate() {
  return {
    id: "candidate-northstar-flagship",
    evidenceCategory: "decision_process",
    statement:
      "Jane confirmed that she owns the technical review and will schedule the rollout workshop.",
    originalStatement:
      "Jane confirmed that she owns the technical review and will schedule the rollout workshop.",
    origin: "salesperson_reported",
    sourceLabel: "Reported by you",
    supportClassification: "reported",
    validationState: "unreviewed",
    conflictState: "not_assessed",
    userReviewState: "pending",
    sourceCaptureSessionId: "debrief-session-flagship",
    evidenceFragmentId: "debrief-fragment-flagship",
    acceptedEvidenceId: null,
    entityReference: null,
    explicitlyReportedAt: null,
    edited: false,
  };
}

function debriefSession(
  lifecycleStatus: "collecting" | "review" | "completed",
) {
  const candidate = reportedCandidate();
  return {
    id: "debrief-session-flagship",
    interactionId: ids.interaction,
    captureType: "ai_debrief",
    lifecycleStatus,
    questionCount:
      lifecycleStatus === "collecting" && !state.debriefAnswerSaved ? 0 : 1,
    maxQuestions: 2,
    currentQuestion:
      lifecycleStatus === "collecting"
        ? state.debriefAnswerSaved
          ? {
              status: "complete",
              question: null,
              reason: "The material outcome is ready for review.",
              target: null,
              priority: null,
            }
          : {
              status: "ask",
              question: "What changed and what happens next?",
              reason: "Capture the material outcome while it is fresh.",
              target: "other",
              priority: "high",
            }
        : null,
    canFinish: lifecycleStatus !== "collecting" || state.debriefAnswerSaved,
    finishedEarly: false,
    turns:
      lifecycleStatus === "collecting" && !state.debriefAnswerSaved
        ? []
        : [
            {
              id: "debrief-turn-flagship",
              turnNumber: 1,
              question: {
                status: "ask",
                question: "What changed and what happens next?",
                reason: "Capture the material outcome while it is fresh.",
                target: "other",
                priority: "high",
              },
              answerText:
                "Jane confirmed that she owns the technical review and will schedule the rollout workshop.",
              inputMode: "text",
              createdAt: "2026-08-31T00:08:00Z",
            },
          ],
    candidates:
      lifecycleStatus === "collecting"
        ? []
        : [
            lifecycleStatus === "completed"
              ? {
                  ...candidate,
                  validationState: "verified",
                  userReviewState: "accepted",
                  acceptedEvidenceId: ids.evidence,
                  explicitlyReportedAt: "2026-08-31T00:09:00Z",
                }
              : candidate,
          ],
    interactionIntelligenceId:
      lifecycleStatus === "completed"
        ? "interaction-intelligence-flagship"
        : null,
    revenueBrainSnapshotId:
      lifecycleStatus === "completed" ? "brain-snapshot-flagship" : null,
    startedAt: "2026-08-31T00:07:30Z",
    updatedAt: "2026-08-31T00:09:00Z",
    completedAt:
      lifecycleStatus === "completed" ? "2026-08-31T00:09:00Z" : null,
    ...(lifecycleStatus === "completed"
      ? {
          acceptedCount: 1,
          rejectedCount: 0,
          interactionUpdated: true,
          revenueBrainUpdated: true,
        }
      : {}),
  };
}

function reportedIntelligence() {
  return {
    id: "interaction-intelligence-flagship",
    interactionId: ids.interaction,
    generatedAt: "2026-08-31T00:09:00Z",
    sourceLabel: "Reported by you",
    items: [
      {
        evidenceId: ids.evidence,
        category: "decision_process",
        statement:
          "Jane confirmed that she owns the technical review and will schedule the rollout workshop.",
        origin: "salesperson_reported",
        sourceLabel: "Reported by you",
        validationState: "verified",
        conflictState: "not_assessed",
      },
    ],
  };
}

function methodology() {
  const source = {
    sourceType: "evidence",
    sourceId: ids.evidence,
    itemKey: "decision_process",
    label: "Reported by you",
    origin: "salesperson_reported",
    supportedAt: "2026-08-31T00:09:00Z",
    sourceClassification: "Reviewed salesperson-reported evidence",
  };
  return {
    state: state.evidenceAccepted ? "current" : "not_generated",
    generationAvailable: state.evidenceAccepted,
    needsRefresh: false,
    safeMessage: state.evidenceAccepted
      ? "Current evidence-backed methodology view."
      : "Accept reviewed evidence before generating this view.",
    definition: state.evidenceAccepted
      ? {
          id: null,
          key: "meddpicc",
          name: "MEDDPICC",
          description: "Understand the current evidence-backed buying path.",
          version: 1,
          standard: true,
          status: "active",
          fieldCount: 1,
          fields: [
            {
              key: "decision_process",
              displayName: "Decision Process",
              explanation: "Understand the current approval path.",
              order: 1,
              required: true,
              evidenceExpectations: ["Current validated evidence"],
              canonicalFacts: ["decision_process"],
              evidenceCategories: ["decision_process"],
              freshnessDays: 90,
              suggestedQuestions: ["Who owns final commercial approval?"],
              stageExpectation: "evaluation",
            },
          ],
          createdAt: null,
        }
      : null,
    projectionId: state.evidenceAccepted
      ? "methodology-projection-flagship"
      : null,
    projection: state.evidenceAccepted
      ? {
          opportunityId: ids.opportunity,
          methodologyKey: "meddpicc",
          methodologyName: "MEDDPICC",
          definitionVersion: 1,
          projectionVersion: 1,
          engineVersion: 1,
          stateCounts: {
            confirmed: 0,
            partiallySupported: 1,
            unknown: 0,
            conflicting: 0,
            stale: 0,
          },
          items: [
            {
              fieldKey: "decision_process",
              displayName: "Decision Process",
              explanation:
                "Reviewed salesperson-reported evidence identifies technical ownership; customer-direct commercial approval is still unknown.",
              required: true,
              state: "partially_supported",
              conclusion:
                "Jane owns the technical review and will schedule the rollout workshop.",
              sources: [source],
              conflicts: [],
              lastSupportedAt: source.supportedAt,
              freshness: "current",
              suggestedQuestion: "Who owns final commercial approval?",
              stageExpectation: "evaluation",
              reviews: [],
            },
          ],
          generatedAt: "2026-08-31T00:09:30Z",
        }
      : null,
    generatedAt: state.evidenceAccepted ? "2026-08-31T00:09:30Z" : null,
  };
}

function nextAction() {
  return {
    id: ids.action,
    organisationId: "organisation-flagship",
    opportunityId: ids.opportunity,
    interactionId: ids.interaction,
    actionType: "follow_up_email",
    status: state.actionApproved ? "approved" : "proposed",
    priority: "high",
    audience: "customer_facing",
    riskClass: "external_customer_facing",
    currentVersion: 1,
    approvedVersion: state.actionApproved ? 1 : null,
    title: "Confirm the rollout workshop",
    description:
      "Review the suggested follow-up before taking any external action.",
    proposedDueAt: "2026-09-01T02:00:00Z",
    targetEntityType: "contact",
    targetEntityId: ids.contact,
    proposedPayload: {
      kind: "follow_up_email",
      draftArtifactId: "artifact-action-flagship",
      recipientContactId: ids.contact,
      recipientEmail: contact.email,
      recipientConfirmed: true,
      subject: "Northstar rollout workshop",
      body: "Hi Jane,\n\nThank you for confirming the technical review. Shall we schedule the rollout workshop?",
    },
    sourceRefs: [
      {
        sourceType: "interaction_intelligence",
        sourceId: "interaction-intelligence-flagship",
        itemKey: "decision_process",
        label: "Reviewed post-interaction report",
        origin: "validated_intelligence",
      },
    ],
    provenanceSummary: "Derived from reviewed salesperson-reported evidence.",
    generatedAt: "2026-08-31T00:09:30Z",
    versionCreatedAt: "2026-08-31T00:09:30Z",
    createdByUserId: "user-flagship",
    reviewedByUserId: state.actionApproved ? "user-flagship" : null,
    reviewedAt: state.actionApproved ? "2026-08-31T00:10:00Z" : null,
    approvedAt: state.actionApproved ? "2026-08-31T00:10:00Z" : null,
    rejectedAt: null,
    rejectionReasonCode: null,
    supersedesActionId: null,
    completedByUserId: null,
    completedAt: null,
    executionState: "not_executed",
    sendReady: false,
  };
}

function opportunityWorkspace() {
  return {
    opportunity: {
      ...opportunity(),
      companyName: account.name,
      ownerName: "Alex Morgan",
    },
    reportedIntelligence: state.evidenceAccepted
      ? reportedIntelligence()
      : null,
    visualIntelligence: null,
    latestInteractionCapture: null,
    latestMeeting: null,
    recentMeetings: [],
    reasoning: {
      state: "insufficient_history",
      message: "More reviewed history is required.",
      latest: null,
      history: [],
    },
    intelligence: null,
    methodology: methodology(),
    intelligenceSectionsAvailable: state.evidenceAccepted ? 1 : 0,
    partialData: false,
    generatedAt: "2026-08-31T00:10:00Z",
  };
}

const createTemplate = {
  id: "template-northstar-flagship",
  name: "Approved synthetic company story",
  state: "active",
  latestVersion: {
    id: "template-version-flagship",
    templateId: "template-northstar-flagship",
    version: 1,
    processingState: "ready",
    approvalState: "approved",
    fileName: "approved-synthetic-company-story.pptx",
    byteSize: 42_000,
    checksumSha256: "a".repeat(64),
    slideCount: 2,
    approvedSlideCount: 2,
    requiredSlideCount: 1,
    widthEmu: 12_192_000,
    heightEmu: 6_858_000,
    warningCodes: [],
    safeFailureCode: null,
    authorityAttestationVersion: 1,
    authorityAttestedAt: "2026-08-31T00:12:00Z",
    processedAt: "2026-08-31T00:12:30Z",
    approvedAt: "2026-08-31T00:13:00Z",
    slides: [],
    contentItems: [],
    createdAt: "2026-08-31T00:12:00Z",
  },
  createdAt: "2026-08-31T00:12:00Z",
  updatedAt: "2026-08-31T00:13:00Z",
};

function presentation() {
  const created = state.presentationState !== "not_created";
  const generated = ["needs_review", "ready"].includes(state.presentationState);
  return {
    id: ids.presentation,
    title: "Northstar solution overview",
    accountId: ids.account,
    accountName: account.name,
    opportunityId: ids.opportunity,
    opportunityName: "National operations rollout",
    objective: "solution_overview",
    audience: [
      {
        contactId: ids.contact,
        name: "Jane Smith",
        role: contact.jobTitle,
        audienceType: "executive",
      },
    ],
    focusInstruction: "Keep the synthetic rollout concise.",
    templateVersionId: createTemplate.latestVersion.id,
    templateName: createTemplate.name,
    templateVersion: 1,
    state: created ? state.presentationState : "draft_plan",
    reviewState: state.presentationState === "ready" ? "approved" : "pending",
    plan: [
      {
        id: "plan-title-flagship",
        templateSlideId: "slide-title-flagship",
        order: 1,
        title: "Approved company story",
        category: "title",
        required: true,
        modificationPolicy: "locked",
        sourceClasses: ["approved_company_content"],
        included: true,
      },
      {
        id: "plan-solution-flagship",
        templateSlideId: "slide-solution-flagship",
        order: 2,
        title: "A staged national rollout",
        category: "solution",
        required: false,
        modificationPolicy: "text_placeholders_only",
        sourceClasses: ["approved_company_content", "salesperson_reported"],
        included: true,
      },
    ],
    currentVersion: generated
      ? {
          id: "presentation-version-flagship",
          version: 1,
          state: state.presentationState,
          reviewState:
            state.presentationState === "ready" ? "approved" : "pending",
          slides: [
            {
              planItemId: "plan-solution-flagship",
              templateSlideId: "slide-solution-flagship",
              order: 1,
              title: "A staged national rollout",
              bodyBlocks: [
                "Northstar will review a staged rollout across its Australian sites.",
              ],
              required: false,
              modificationPolicy: "text_placeholders_only",
              reviewState: "needs_review",
              warningCodes: ["claim_review_required"],
            },
          ],
          claims: [
            {
              id: "claim-presentation-flagship",
              planItemId: "plan-solution-flagship",
              blockIndex: 0,
              claim:
                "Northstar will review a staged rollout across its Australian sites.",
              contentType: "implementation",
              origin: "salesperson_reported",
              supportState: "reported",
              customerSafeClassification: "requires_review",
              sourceIds: [ids.evidence],
              sourceLabels: ["Reviewed post-interaction report"],
              freshness: "current",
              paraphraseAllowed: true,
              exactTextRequired: false,
              reviewState: state.presentationClaimReviewed ? "kept" : "pending",
            },
          ],
          warningCodes: ["review_required"],
          safeFailureCode: null,
          generatedAt: "2026-08-31T00:15:00Z",
          approvedAt:
            state.presentationState === "ready" ? "2026-08-31T00:16:00Z" : null,
          downloadAvailable: state.presentationState === "ready",
          createdAt: "2026-08-31T00:15:00Z",
        }
      : null,
    createdByUserId: "user-flagship",
    createdAt: "2026-08-31T00:14:00Z",
    updatedAt: "2026-08-31T00:16:00Z",
  };
}

const targetMetric = {
  metricId: "won_value",
  definitionVersion: "1",
  label: "Won value",
  description: "Sum of valued Opportunities currently Won in the period.",
  unit: "currency",
  category: "outcome",
  allowedScopes: ["personal", "organisation"],
  requiresCurrency: true,
  displayOrder: 1,
  dateSemantics: "Actual close date falls in the inclusive local-date range.",
  exclusions: ["Unvalued Won Opportunities"],
};

function salesTarget() {
  const actual = state.closedWon ? "420000.00" : "0.00";
  return {
    id: ids.targetGoal,
    metric: targetMetric,
    scope: "personal",
    origin: "self_set",
    ownerUserId: "user-flagship",
    ownerDisplayName: "Alex Morgan",
    pipelineId: ids.pipeline,
    pipelineName: "RevenueOS Sales Pipeline",
    periodType: "quarter",
    periodStart: "2026-07-01",
    periodEnd: "2026-09-30",
    periodLabel: "Q3 2026",
    timezone: "Australia/Sydney",
    currency: "AUD",
    status: "active",
    latestRevision: {
      id: "target-revision-flagship",
      revisionNumber: 1,
      goalValue: "500000.00",
      createdByUserId: "user-flagship",
      createdByDisplayName: "Alex Morgan",
      createdAt: "2026-08-01T00:00:00Z",
    },
    revisions: [],
    progress: {
      state: "available",
      actualValue: actual,
      targetValue: "500000.00",
      remainingValue: state.closedWon ? "80000.00" : "500000.00",
      aboveTargetValue: "0.00",
      percentageComplete: state.closedWon ? "84.0" : "0.0",
      targetReached: false,
      calculatedThrough: "2026-08-31",
      generatedAt: "2026-08-31T00:20:00Z",
      disclosures: [
        "Actuals use canonical records through 31 August 2026.",
        "This is an operational goal, not a forecast or compensation measure.",
      ],
    },
    createdByUserId: "user-flagship",
    createdByDisplayName: "Alex Morgan",
    archivedAt: null,
    createdAt: "2026-08-01T00:00:00Z",
    updatedAt: "2026-08-01T00:00:00Z",
    canRevise: true,
    canArchive: true,
  };
}

const forecastPeriod = {
  id: "forecast-period-flagship",
  periodType: "quarter",
  periodStart: "2026-07-01",
  periodEnd: "2026-09-30",
  periodLabel: "Q3 2026",
  timezone: "Australia/Sydney",
  status: "active",
};

const forecastBaseline = {
  status: "available",
  modelVersion: "forecast_historical_stage_outcome_v1",
  pipelineId: ids.pipeline,
  pipelineName: "RevenueOS Sales Pipeline",
  stageId: ids.proposal,
  stageName: "Proposal",
  wonCount: 8,
  lostCount: 4,
  sampleSize: 12,
  observedWinRate: "66.7",
  expectedContribution: "280000.00",
  lookbackStart: "2024-08-31",
  lookbackEnd: "2026-08-31",
  minimumSample: 10,
  explanation:
    "8 of 12 reliably tracked Opportunities in this exact Pipeline stage finished Won.",
};

function salesForecast() {
  const zero = { amount: "0.00", opportunityCount: 0, unvaluedCount: 0 };
  return {
    period: forecastPeriod,
    currency: "AUD",
    pipelineId: null,
    ownerUserId: null,
    organisationScope: true,
    actual: {
      state: "available",
      amount: state.closedWon ? "420000.00" : "0.00",
      calculatedThrough: "2026-08-31",
      metricId: "won_value",
      metricDefinitionVersion: "1",
    },
    targets: [
      {
        id: ids.targetGoal,
        label: "Q3 Won value",
        scope: "personal",
        origin: "self_set",
        targetValue: "500000.00",
      },
    ],
    sellerForecast: state.closedWon
      ? {
          commit: zero,
          likely: zero,
          possible: zero,
          unreviewedCount: 0,
          notThisPeriodCount: 0,
          needsReviewCount: 0,
          disclosure:
            "Closed Opportunities are excluded from the seller forecast.",
        }
      : {
          commit: zero,
          likely: {
            amount: "420000.00",
            opportunityCount: 1,
            unvaluedCount: 0,
          },
          possible: {
            amount: "420000.00",
            opportunityCount: 1,
            unvaluedCount: 0,
          },
          unreviewedCount: 0,
          notThisPeriodCount: 0,
          needsReviewCount: 0,
          disclosure:
            "Likely includes the explicit seller judgment without probability weighting.",
        },
    managerForecast: {
      commit: zero,
      likely: zero,
      possible: zero,
      unreviewedCount: state.closedWon ? 0 : 1,
      notThisPeriodCount: 0,
      needsReviewCount: 0,
      disclosure:
        "The independent manager view is not blended with the seller forecast.",
    },
    revenueosBaseline: state.closedWon
      ? {
          expectedContribution: "0.00",
          coveredOpportunityCount: 0,
          uncoveredOpportunityCount: 0,
          coveredAmount: "0.00",
          uncoveredAmount: "0.00",
          unvaluedOpportunityCount: 0,
          modelVersion: "forecast_historical_stage_outcome_v1",
          lookbackDays: 730,
          minimumSample: 10,
          disclosure: "Closed Opportunities are not forecast inputs.",
        }
      : {
          expectedContribution: "280000.00",
          coveredOpportunityCount: 1,
          uncoveredOpportunityCount: 0,
          coveredAmount: "420000.00",
          uncoveredAmount: "0.00",
          unvaluedOpportunityCount: 0,
          modelVersion: "forecast_historical_stage_outcome_v1",
          lookbackDays: 730,
          minimumSample: 10,
          disclosure:
            "This separate historical baseline is not a seller forecast.",
        },
    inputQuality: {
      eligibleOpportunityCount: state.closedWon ? 0 : 1,
      valuedOpportunityCount: state.closedWon ? 0 : 1,
      unvaluedOpportunityCount: 0,
      missingExpectedCloseCount: 0,
      insufficientHistoryCount: 0,
    },
    opportunities: state.closedWon
      ? []
      : [
          {
            opportunityId: ids.opportunity,
            opportunityName: "National operations rollout",
            companyName: account.name,
            ownerUserId: "user-flagship",
            ownerDisplayName: "Alex Morgan",
            amount: "420000.00",
            currency: "AUD",
            expectedCloseDate: "2026-09-30",
            pipelineId: ids.pipeline,
            pipelineName: "RevenueOS Sales Pipeline",
            stageId: ids.proposal,
            stageName: "Proposal",
            stageEnteredAt: "2026-08-31T00:10:00Z",
            status: "open",
            judgment: {
              judgmentId: "forecast-judgment-flagship",
              revisionId: "forecast-revision-flagship",
              revisionNumber: 1,
              category: "likely",
              createdByUserId: "user-flagship",
              createdByDisplayName: "Alex Morgan",
              createdAt: "2026-08-31T00:18:00Z",
              staleReasons: [],
              canReview: true,
            },
            historicalBaseline: forecastBaseline,
          },
        ],
    totalOpportunities: state.closedWon ? 0 : 1,
    page: 1,
    pageSize: 100,
    generatedAt: "2026-08-31T00:20:00Z",
  };
}

function managerReview() {
  const sourceRef = {
    sourceType: "opportunity",
    sourceId: ids.opportunity,
    label: "Current Opportunity state",
    href: `/opportunities/${ids.opportunity}`,
  };
  return {
    deal: {
      opportunityId: ids.opportunity,
      opportunityName: "National operations rollout",
      companyName: account.name,
      ownerUserId: "user-flagship",
      ownerDisplayName: "Alex Morgan",
      pipelineId: ids.pipeline,
      pipelineName: "RevenueOS Sales Pipeline",
      stageId: state.closedWon ? ids.won : ids.proposal,
      stageName: state.closedWon ? "Closed Won" : "Proposal",
      amount: "420000.00",
      currency: "AUD",
      expectedCloseDate: "2026-09-30",
      sellerForecast: state.closedWon
        ? null
        : {
            category: "likely",
            revisionNumber: 1,
            reviewedAt: "2026-08-31T00:18:00Z",
            staleReasons: [],
          },
      managerForecast: null,
      reasons: state.closedWon
        ? []
        : [
            {
              id: "methodology_gap:decision_process",
              code: "methodology_gap",
              label: "Commercial approval still unknown",
              explanation:
                "Technical ownership is reviewed, but final commercial approval is not customer-confirmed.",
              detectedAt: "2026-08-31T00:20:00Z",
              sources: [sourceRef],
            },
          ],
      href: `/opportunities/${ids.opportunity}`,
    },
    historicalBaseline: {
      state: "available",
      expectedContribution: state.closedWon ? "0.00" : "280000.00",
      wonCount: 8,
      lostCount: 4,
      explanation: "8 of 12 comparable Opportunities finished Won.",
    },
    methodologyGaps: [],
    currentActions: state.closedWon
      ? []
      : [
          {
            id: ids.action,
            title: "Confirm the rollout workshop",
            status: state.actionApproved ? "approved" : "proposed",
            priority: "high",
            dueAt: "2026-09-01T02:00:00Z",
            href: `/opportunities/${ids.opportunity}#recommended-actions`,
          },
        ],
    latestInteraction: {
      id: ids.interaction,
      title: "Northstar rollout discovery",
      occurredAt: "2026-08-31T00:08:00Z",
      href: `/interactions/${ids.interaction}`,
    },
    recentChanges: [],
    questions: state.closedWon
      ? []
      : [
          {
            id: "question:commercial-approval",
            question: "Who owns final commercial approval for the rollout?",
            whyShown:
              "The current reviewed evidence confirms technical ownership only.",
            sourceReasonIds: ["methodology_gap:decision_process"],
            sources: [sourceRef],
          },
        ],
    generatedAt: "2026-08-31T00:20:00Z",
  };
}

async function captureFlagship(page: Page, name: string) {
  if (process.env.WO039A_SCREENSHOTS !== "1") return;
  await page.screenshot({
    path: `../../docs/07-sprints/assets/wo-039a-${name}.png`,
    fullPage: true,
  });
}

function pipelineResponse(view = "open") {
  const activeStage =
    stages.find((item) => item.key === state.stage) ?? stages[0];
  const card = {
    opportunityId: ids.opportunity,
    opportunityName: "National operations rollout",
    companyId: ids.account,
    companyName: account.name,
    pipelineId: ids.pipeline,
    pipelineName: "RevenueOS Sales Pipeline",
    stageId: activeStage.id,
    stageName: activeStage.name,
    stageType: activeStage.stageType,
    status: state.closedWon ? "won" : "open",
    estimatedValue: "420000.00",
    currency: "AUD",
    expectedCloseDate: "2026-09-30",
    actualCloseDate: state.closedWon ? "2026-08-31" : null,
    ownerUserId: "user-flagship",
    ownerName: "Alex Morgan",
    stageEnteredAt: "2026-08-31T00:10:00Z",
    stageTrackingStartedAt: "2026-08-31T00:10:00Z",
    daysInStage: 0,
    nextAction: state.closedWon ? null : "Confirm the rollout workshop.",
    attentionReasons: [],
    outcomeReason: state.closedWon ? "solution_fit" : null,
    outcomeProvenance: state.closedWon ? "seller_reported" : null,
  };
  const visible = view === "closed" ? state.closedWon : !state.closedWon;
  const pipeline = {
    id: ids.pipeline,
    name: "RevenueOS Sales Pipeline",
    isDefault: true,
    active: true,
    archivedAt: null,
    stages,
    createdAt: "2026-08-31T00:00:00Z",
    updatedAt: "2026-08-31T00:00:00Z",
  };
  return {
    pipeline,
    pipelines: [pipeline],
    view,
    summary: {
      openOpportunityCount: state.closedWon ? 0 : 1,
      needsAttentionCount: 0,
      closeDatesThisMonthCount: state.closedWon ? 0 : 1,
      unvaluedOpportunityCount: 0,
      values: visible
        ? [{ currency: "AUD", amount: "420000.00", opportunityCount: 1 }]
        : [],
    },
    cards: visible ? [card] : [],
    managerIntelligenceAvailable: true,
    stageChangesAllowed: true,
    managedExternally: false,
    authorityMessage: null,
    generatedAt: "2026-08-31T00:10:00Z",
  };
}

function opportunityPipeline() {
  const data = pipelineResponse();
  const activeStage =
    stages.find((item) => item.key === state.stage) ?? stages[0];
  return {
    opportunityId: ids.opportunity,
    status: state.closedWon ? "won" : "open",
    pipeline: data.pipeline,
    stage: activeStage,
    stageEnteredAt: "2026-08-31T00:10:00Z",
    stageTrackingStartedAt: "2026-08-31T00:10:00Z",
    daysInStage: 0,
    actualCloseDate: state.closedWon ? "2026-08-31" : null,
    outcomeReason: state.closedWon ? "solution_fit" : null,
    outcomeNote: null,
    outcomeProvenance: state.closedWon ? "seller_reported" : null,
    availablePipelines: [data.pipeline],
    history: state.closedWon
      ? [
          {
            id: "history-won-flagship",
            fromStageName: "Proposal",
            toStageName: "Closed Won",
            changedAt: "2026-08-31T00:20:00Z",
            source: "seller",
            isBaseline: false,
            outcomeReason: "solution_fit",
          },
        ]
      : [],
    stageChangesAllowed: true,
    managedExternally: false,
    authorityMessage: null,
  };
}

async function fulfilJson(route: Route, json: object, status = 200) {
  await route.fulfill({ json, status });
}

async function routeFlagship(page: Page) {
  await page.route("https://northstar-facilities.example/**", async (route) =>
    route.fulfill({
      contentType: "text/html",
      body: "<title>Northstar source</title><h1>Northstar public source</h1>",
    }),
  );

  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (path === "/api/v1/me") {
      await fulfilJson(route, {
        user: {
          id: "user-flagship",
          externalAuthId: "user_dev_001",
          displayName: "Alex Morgan",
          email: "alex@example.test",
        },
        organisation: {
          id: "organisation-flagship",
          name: "Synthetic Revenue Team",
          slug: "synthetic-revenue-team",
        },
        role: "admin",
        authMode: "mock",
        requestId: "request-flagship",
      });
      return;
    }
    if (path === "/api/v1/beta/capabilities") {
      await fulfilJson(route, {
        featureFlags: {
          prospect: true,
          engage: true,
          engageEvents: true,
          nativePipeline: true,
          salesAnalytics: true,
          salesTargets: true,
          salesForecasting: true,
          opportunityWorkspace: true,
          revenueBrain: true,
          aiCompanion: true,
          aiDebrief: true,
          recordingCapture: false,
          visualEvidence: false,
          actionLayer: true,
        },
        noticeVersion: 1,
        maxTranscriptCharacters: 200000,
      });
      return;
    }
    if (path.endsWith("/availability")) {
      await fulfilJson(route, {
        moduleKey: path.includes("create")
          ? "create"
          : path.includes("engage")
            ? "engage"
            : "prospect",
        state: "available",
        enabled: true,
        canManage: true,
        canUploadTemplates: true,
        canCreatePresentations: true,
        message: "This synthetic module is available.",
        description: "Synthetic flagship capability.",
        learnMorePath: "/dashboard",
      });
      return;
    }
    if (path === "/api/v1/daily") {
      await fulfilJson(route, {
        generatedAt: "2026-08-31T00:00:00Z",
        localDate: "2026-08-31",
        timezone: "Australia/Sydney",
        userDisplayName: "Alex Morgan",
        topPriority: null,
        nextInteraction: null,
        todayInteractions: [],
        totalTodayInteractions: 0,
        actions: {
          attentionCount: 0,
          overdueCount: 0,
          dueTodayCount: 0,
          pendingReviewCount: 0,
          approvedOpenCount: 0,
          items: [],
          truncated: false,
        },
        dealAttention: { attentionCount: 0, items: [], truncated: false },
        pipeline: {
          state: state.closedWon ? "empty" : "single_currency",
          openOpportunityCount: state.closedWon
            ? 0
            : state.opportunityCreated
              ? 1
              : 0,
          unvaluedOpportunityCount: 0,
          currencyCount: state.closedWon || !state.opportunityCreated ? 0 : 1,
          currencies:
            state.closedWon || !state.opportunityCreated
              ? []
              : [
                  {
                    currency: "AUD",
                    openValue: "420000.00",
                    closingThisMonthValue: "420000.00",
                    openOpportunityCount: 1,
                    closingThisMonthCount: 1,
                  },
                ],
          safeMessage: "Canonical synthetic pipeline.",
        },
        recommendations: [],
        availability: {
          interactions: true,
          actions: true,
          dealAttention: true,
          pipeline: true,
          recommendations: true,
          methodology: true,
          revenueBrain: true,
          targets: true,
          forecast: true,
        },
        hasOpportunities: state.opportunityCreated,
        caughtUp: true,
      });
      return;
    }
    if (path === "/api/v1/prospect/companies/search") {
      await fulfilJson(route, {
        items: [
          {
            candidateId: "northstar-facilities-group",
            name: account.name,
            domain: "northstar-facilities.example",
            websiteUrl: account.website,
            location: account.location,
            industry: account.industry,
            providerAttribution: "RevenueOS synthetic research data",
          },
        ],
        query: "Northstar",
        ambiguous: false,
      });
      return;
    }
    if (path === "/api/v1/prospect/research" && method === "GET") {
      await fulfilJson(route, { items: [] });
      return;
    }
    if (path === "/api/v1/prospect/research" && method === "POST") {
      state.researchStarted = true;
      await fulfilJson(route, companyBrief(), 202);
      return;
    }
    if (
      path === `/api/v1/prospect/research/${ids.target}` &&
      method === "GET"
    ) {
      await fulfilJson(route, companyBrief());
      return;
    }
    if (path === `/api/v1/prospect/research/${ids.target}/refresh`) {
      state.researchStarted = true;
      await fulfilJson(route, companyBrief(), 202);
      return;
    }
    if (path === `/api/v1/prospect/research/${ids.target}/promote`) {
      state.accountPromoted = true;
      await fulfilJson(route, {
        status: "created",
        companyId: ids.account,
        companyName: account.name,
        researchTargetId: ids.target,
        message: "The Account was added to Sales.",
      });
      return;
    }
    if (path === `/api/v1/prospect/research/${ids.target}/people`) {
      await fulfilJson(route, {
        companyTargetId: ids.target,
        functions: [],
        people: state.peopleFound ? [person] : [],
        gaps: [],
        resultLimit: 15,
        message: state.peopleFound
          ? "RevenueOS found 1 person worth understanding."
          : "Find relevant people when you are ready.",
      });
      return;
    }
    if (path === `/api/v1/prospect/research/${ids.target}/people/discover`) {
      state.peopleFound = true;
      await fulfilJson(route, {
        companyTargetId: ids.target,
        functions: [],
        people: [person],
        gaps: [],
        resultLimit: 15,
        message: "RevenueOS found 1 person worth understanding.",
      });
      return;
    }
    if (path === `/api/v1/prospect/people/${ids.person}/promote`) {
      if (!state.accountPromoted) {
        await fulfilJson(
          route,
          {
            code: "company_not_in_sales",
            message: "Save the Account before adding this Contact.",
            requestId: "request-company-first",
          },
          409,
        );
        return;
      }
      state.contactPromoted = true;
      await fulfilJson(route, {
        status: "created",
        contactId: ids.contact,
        companyId: ids.account,
        prospectPersonId: ids.person,
        message:
          "The Contact was added to Sales with reviewed field provenance.",
      });
      return;
    }
    if (path.startsWith(`/api/v1/prospect/people/${ids.person}`)) {
      await fulfilJson(route, personBrief());
      return;
    }
    if (path === "/api/v1/prospect/target-markets") {
      await fulfilJson(route, { items: [], activeLimit: 10, canCreate: true });
      return;
    }
    if (path === `/api/v1/prospect/accounts/${ids.account}/research-link`) {
      await fulfilJson(route, {
        companyId: ids.account,
        researchTargetId: ids.target,
        label: "Public account research",
        updatedAt: "2026-08-31T00:04:00Z",
      });
      return;
    }
    if (path === `/api/v1/prospect/contacts/${ids.contact}/research-link`) {
      await fulfilJson(route, {
        contactId: ids.contact,
        prospectPersonId: ids.person,
        companyTargetId: ids.target,
        label: "Public professional research",
        updatedAt: "2026-08-31T00:05:00Z",
      });
      return;
    }
    if (path === "/api/v1/crm/members") {
      await fulfilJson(route, [
        {
          userId: "user-flagship",
          displayName: "Alex Morgan",
          active: true,
        },
      ]);
      return;
    }
    if (path === "/api/v1/companies") {
      await fulfilJson(route, {
        items: state.accountPromoted ? [account] : [],
        page: 1,
        pageSize: 100,
        total: state.accountPromoted ? 1 : 0,
        pages: state.accountPromoted ? 1 : 0,
      });
      return;
    }
    if (path === "/api/v1/contacts") {
      await fulfilJson(route, {
        items: state.contactPromoted ? [contact] : [],
        page: 1,
        pageSize: 100,
        total: state.contactPromoted ? 1 : 0,
        pages: state.contactPromoted ? 1 : 0,
      });
      return;
    }
    if (path === "/api/v1/opportunities") {
      if (method === "POST") {
        state.opportunityCreated = true;
        await fulfilJson(route, opportunity(), 201);
        return;
      }
      await fulfilJson(route, {
        items: state.opportunityCreated ? [opportunity()] : [],
        page: 1,
        pageSize: 100,
        total: state.opportunityCreated ? 1 : 0,
        pages: state.opportunityCreated ? 1 : 0,
      });
      return;
    }
    if (path === `/api/v1/companies/${ids.account}`) {
      await fulfilJson(route, account);
      return;
    }
    if (path === `/api/v1/contacts/${ids.contact}`) {
      await fulfilJson(route, contact);
      return;
    }
    if (path === `/api/v1/accounts/${ids.account}/brain/reasoning`) {
      await fulfilJson(route, {
        state: "insufficient_history",
        message: "More reviewed interaction history is required.",
        latest: null,
        history: [],
      });
      return;
    }
    if (path === `/api/v1/accounts/${ids.account}/brain/visual-evidence`) {
      await fulfilJson(route, []);
      return;
    }
    if (
      path === `/api/v1/accounts/${ids.account}/brain/reported-interactions`
    ) {
      await fulfilJson(
        route,
        state.evidenceAccepted
          ? [
              {
                id: "brain-snapshot-flagship",
                interactionId: ids.interaction,
                opportunityId: ids.opportunity,
                interactionTitle: "Northstar rollout discovery",
                interactionType: "phone_call",
                interactionDate: "2026-08-31T00:08:00Z",
                createdAt: "2026-08-31T00:09:00Z",
                sourceLabel: "Reported by you",
                items: reportedIntelligence().items,
              },
            ]
          : [],
      );
      return;
    }
    if (path === `/api/v1/accounts/${ids.account}/brain`) {
      await fulfilJson(route, []);
      return;
    }
    if (path === `/api/v1/evidence/accounts/${ids.account}/brain`) {
      await fulfilJson(route, []);
      return;
    }
    if (path === `/api/v1/crm/records/account/${ids.account}`) {
      await fulfilJson(route, crmRecord("account"));
      return;
    }
    if (path === `/api/v1/crm/records/contact/${ids.contact}`) {
      await fulfilJson(route, crmRecord("contact"));
      return;
    }
    if (path === `/api/v1/crm/records/opportunity/${ids.opportunity}`) {
      await fulfilJson(route, crmRecord("opportunity"));
      return;
    }
    if (path === `/api/v1/engage/contacts/${ids.contact}`) {
      await fulfilJson(route, contactWorkspace());
      return;
    }
    if (path === `/api/v1/engage/contacts/${ids.contact}/outreach`) {
      await fulfilJson(route, outreach(), 201);
      return;
    }
    if (path === `/api/v1/engage/outreach/${ids.outreach}/approve`) {
      state.outreachApproved = true;
      await fulfilJson(route, outreach());
      return;
    }
    if (path === `/api/v1/engage/outreach/${ids.outreach}`) {
      await fulfilJson(route, outreach());
      return;
    }
    if (path === `/api/v1/actions/${ids.action}/execution-options`) {
      await fulfilJson(route, {
        items: [
          {
            connectionId: "connection-mock-email",
            connectorKey: "mock_email",
            connectorDisplayName: "Mock Email",
            capability: "send_email",
            riskClass: "external_customer_facing",
            executionMode: "simulation",
            simulationOnly: true,
          },
        ],
        total: 1,
      });
      return;
    }
    if (path === `/api/v1/engage/outreach/${ids.outreach}/execution-preview`) {
      await fulfilJson(route, {
        id: "preview-flagship",
        actionProposalId: ids.action,
        actionVersion: 1,
        connectionId: "connection-mock-email",
        connectorKey: "mock_email",
        connectorDisplayName: "Mock Email",
        capability: "send_email",
        riskClass: "external_customer_facing",
        executionMode: "simulation",
        simulationOnly: true,
        readiness: "ready",
        summary: "Review the exact email before simulation.",
        confirmationLabel: "Run email simulation",
        previewFingerprint: "a".repeat(64),
        content: {
          kind: "email",
          senderName: "Alex Morgan",
          senderEmail: "alex@example.test",
          recipientName: "Jane Smith",
          recipient: contact.email,
          subject: "Northstar's next phase",
          body: outreach().version.body,
          action: "send_email",
        },
        expiresAt: "2026-08-31T00:20:00Z",
        createdAt: "2026-08-31T00:06:00Z",
      });
      return;
    }
    if (path === `/api/v1/engage/outreach/${ids.outreach}/send`) {
      state.outreachSimulated = true;
      await fulfilJson(
        route,
        {
          id: "execution-flagship",
          actionProposalId: ids.action,
          actionVersion: 1,
          connectionId: "connection-mock-email",
          connectorKey: "mock_email",
          connectorDisplayName: "Mock Email",
          capability: "send_email",
          riskClass: "external_customer_facing",
          executionStatus: "simulated_success",
          executionMode: "simulation",
          simulationOnly: true,
          attemptCount: 1,
          providerReference: null,
          safeMessage: "The email simulation completed successfully.",
          requestedAt: "2026-08-31T00:06:00Z",
          confirmedAt: "2026-08-31T00:06:00Z",
          startedAt: "2026-08-31T00:06:01Z",
          completedAt: "2026-08-31T00:06:01Z",
          createdAt: "2026-08-31T00:06:00Z",
          updatedAt: "2026-08-31T00:06:01Z",
        },
        202,
      );
      return;
    }
    if (path === "/api/v1/executions/execution-flagship") {
      await fulfilJson(route, outreach().execution ?? {});
      return;
    }
    if (
      path === `/api/v1/interactions/${ids.interaction}/companion/brief/review`
    ) {
      state.briefReviewed = true;
      await fulfilJson(route, preparationBrief());
      return;
    }
    if (path === `/api/v1/interactions/${ids.interaction}/companion/brief`) {
      await fulfilJson(route, preparationBrief());
      return;
    }
    if (path === `/api/v1/interactions/${ids.interaction}/start`) {
      state.interactionStarted = true;
      await fulfilJson(route, interaction());
      return;
    }
    if (path === `/api/v1/interactions/${ids.interaction}/complete`) {
      state.interactionStarted = true;
      state.interactionReviewed = true;
      await fulfilJson(route, interaction());
      return;
    }
    if (path === `/api/v1/interactions/${ids.interaction}/debrief`) {
      await fulfilJson(route, debriefSession("collecting"), 201);
      return;
    }
    if (
      path ===
      `/api/v1/interactions/${ids.interaction}/debrief/debrief-session-flagship/response`
    ) {
      state.debriefAnswerSaved = true;
      await fulfilJson(route, debriefSession("collecting"));
      return;
    }
    if (
      path ===
      `/api/v1/interactions/${ids.interaction}/debrief/debrief-session-flagship/finish`
    ) {
      state.debriefReviewReady = true;
      await fulfilJson(route, debriefSession("review"));
      return;
    }
    if (
      path ===
      `/api/v1/interactions/${ids.interaction}/debrief/debrief-session-flagship/review`
    ) {
      state.evidenceAccepted = true;
      await fulfilJson(route, debriefSession("completed"));
      return;
    }
    if (
      path ===
      `/api/v1/interactions/${ids.interaction}/debrief/debrief-session-flagship`
    ) {
      await fulfilJson(
        route,
        debriefSession(
          state.evidenceAccepted
            ? "completed"
            : state.debriefReviewReady
              ? "review"
              : "collecting",
        ),
      );
      return;
    }
    if (path === `/api/v1/interactions/${ids.interaction}/recordings`) {
      await fulfilJson(route, []);
      return;
    }
    if (path === `/api/v1/interactions/${ids.interaction}`) {
      await fulfilJson(route, interaction());
      return;
    }
    if (path === `/api/v1/opportunities/${ids.opportunity}/workspace`) {
      await fulfilJson(route, opportunityWorkspace());
      return;
    }
    if (path === `/api/v1/opportunities/${ids.opportunity}/actions`) {
      await fulfilJson(route, {
        items: state.evidenceAccepted ? [nextAction()] : [],
        total: state.evidenceAccepted ? 1 : 0,
      });
      return;
    }
    if (path === `/api/v1/actions/${ids.action}/approve`) {
      state.actionApproved = true;
      await fulfilJson(route, nextAction());
      return;
    }
    if (path === `/api/v1/evidence/opportunities/${ids.opportunity}`) {
      await fulfilJson(route, []);
      return;
    }
    if (path === "/api/v1/evidence/capabilities") {
      await fulfilJson(route, {
        documentEvidence: false,
        emailEvidence: false,
        supportedDocumentMimeTypes: ["application/pdf", "text/plain"],
        emailProviderImport: false,
        documentProviderImport: false,
        safeMessage:
          "Document and email evidence are disabled in this synthetic journey.",
      });
      return;
    }
    if (path === "/api/v1/meetings") {
      await fulfilJson(route, {
        items: [],
        page: 1,
        pageSize: 100,
        total: 0,
        pages: 0,
      });
      return;
    }
    if (path === `/api/v1/manager/opportunities/${ids.opportunity}`) {
      await fulfilJson(route, managerReview());
      return;
    }
    if (path === `/api/v1/opportunities/${ids.opportunity}`) {
      await fulfilJson(route, opportunity());
      return;
    }
    if (path === `/api/v1/opportunities/${ids.opportunity}/pipeline`) {
      await fulfilJson(route, opportunityPipeline());
      return;
    }
    if (path === `/api/v1/opportunities/${ids.opportunity}/stage`) {
      state.stage = "proposal";
      await fulfilJson(route, opportunityPipeline());
      return;
    }
    if (path === `/api/v1/opportunities/${ids.opportunity}/close-won`) {
      state.stage = "closed_won";
      state.closedWon = true;
      await fulfilJson(route, opportunityPipeline());
      return;
    }
    if (path === "/api/v1/pipeline") {
      await fulfilJson(
        route,
        pipelineResponse(url.searchParams.get("view") ?? "open"),
      );
      return;
    }
    if (path === "/api/v1/create/templates") {
      await fulfilJson(route, {
        items: [createTemplate],
        canUpload: true,
        maxActiveTemplates: 20,
      });
      return;
    }
    if (path === "/api/v1/create/presentations") {
      if (method === "POST") {
        state.presentationState = "draft_plan";
        await fulfilJson(route, presentation(), 201);
        return;
      }
      await fulfilJson(route, {
        items:
          state.presentationState === "not_created" ? [] : [presentation()],
        canCreate: true,
        maxPresentationsPerUserPerDay: 10,
        maxPresentationsPerOrganisationPerDay: 50,
      });
      return;
    }
    if (path === `/api/v1/create/presentations/${ids.presentation}/plan`) {
      await fulfilJson(route, presentation());
      return;
    }
    if (path === `/api/v1/create/presentations/${ids.presentation}/generate`) {
      state.presentationState = "needs_review";
      await fulfilJson(route, presentation(), 202);
      return;
    }
    if (path === `/api/v1/create/presentations/${ids.presentation}/review`) {
      state.presentationClaimReviewed = true;
      await fulfilJson(route, presentation());
      return;
    }
    if (path === `/api/v1/create/presentations/${ids.presentation}/approve`) {
      state.presentationState = "ready";
      await fulfilJson(route, presentation());
      return;
    }
    if (path === `/api/v1/create/presentations/${ids.presentation}`) {
      await fulfilJson(route, presentation());
      return;
    }
    if (path === "/api/v1/create/business-cases") {
      await fulfilJson(route, {
        items: [
          {
            id: ids.businessCase,
            title: "Northstar rollout Business Case",
            accountId: ids.account,
            accountName: account.name,
            opportunityId: ids.opportunity,
            opportunityName: "National operations rollout",
            state: "approved",
            currentVersion: null,
            createdAt: "2026-08-31T00:14:00Z",
            updatedAt: "2026-08-31T00:14:00Z",
          },
        ],
        canCreate: true,
        maxActiveCasesPerAccount: 20,
      });
      return;
    }
    if (path === "/api/v1/create/value-models") {
      await fulfilJson(route, {
        items: [],
        canManage: true,
        maxActiveModels: 50,
      });
      return;
    }
    if (path === "/api/v1/targets/metadata") {
      await fulfilJson(route, {
        currentUserId: "user-flagship",
        currentUserRole: "admin",
        organisationTimezone: "Australia/Sydney",
        metrics: [targetMetric],
        owners: [{ userId: "user-flagship", displayName: "Alex Morgan" }],
        pipelines: [
          { id: ids.pipeline, name: "RevenueOS Sales Pipeline", active: true },
        ],
        canAssignPersonalTargets: true,
        canCreateOrganisationTargets: true,
      });
      return;
    }
    if (path === `/api/v1/targets/${ids.targetGoal}`) {
      await fulfilJson(route, salesTarget());
      return;
    }
    if (path === "/api/v1/targets") {
      await fulfilJson(route, {
        items: [salesTarget()],
        canAssignPersonalTargets: true,
        canCreateOrganisationTargets: true,
        maximumVisibleTargets: 200,
      });
      return;
    }
    if (path === "/api/v1/forecast/metadata") {
      await fulfilJson(route, {
        currentUserId: "user-flagship",
        currentUserRole: "admin",
        organisationTimezone: "Australia/Sydney",
        owners: [
          { userId: "user-flagship", displayName: "Alex Morgan", active: true },
        ],
        pipelines: [
          { id: ids.pipeline, name: "RevenueOS Sales Pipeline", active: true },
        ],
        canViewOrganisationForecast: true,
        canReviewManagerView: true,
        modelVersion: "forecast_historical_stage_outcome_v1",
        modelLookbackDays: 730,
        modelMinimumSample: 10,
        supportedPeriodTypes: ["month", "quarter"],
        categories: ["commit", "likely", "possible", "not_this_period"],
      });
      return;
    }
    if (path === "/api/v1/forecast/calibration") {
      await fulfilJson(route, {
        periodType: "quarter",
        periodsIncluded: 0,
        categories: [],
        minimumRateSample: 5,
        disclosure:
          "No completed synthetic periods are available for calibration.",
        generatedAt: "2026-08-31T00:20:00Z",
      });
      return;
    }
    if (path === "/api/v1/forecast") {
      await fulfilJson(route, salesForecast());
      return;
    }
    if (path === "/api/v1/insights/sales/metadata") {
      await fulfilJson(route, {
        currentUserId: "user-flagship",
        pipelines: [],
        owners: [
          { userId: "user-flagship", displayName: "Alex Morgan", active: true },
        ],
        metrics: [],
        outcomeWindowDays: 30,
        maximumRangeDays: 1827,
        generatedAt: "2026-08-31T00:20:00Z",
      });
      return;
    }
    if (path === "/api/v1/insights/sales/overview") {
      await fulfilJson(route, {
        scope: {
          startDate: url.searchParams.get("startDate"),
          endDate: url.searchParams.get("endDate"),
          timezone: url.searchParams.get("timezone"),
          pipelineId: null,
          ownerUserId: null,
          generatedAt: "2026-08-31T00:20:00Z",
        },
        openOpportunityCount: state.closedWon ? 0 : 1,
        opportunitiesCreatedCount: 1,
        wonCount: state.closedWon ? 1 : 0,
        lostCount: 0,
        closedCount: state.closedWon ? 1 : 0,
        winRate: state.closedWon ? "100.0" : null,
        medianSalesCycleDays: state.closedWon ? "0.0" : null,
        wonValues: state.closedWon
          ? [{ currency: "AUD", amount: "420000.00", opportunityCount: 1 }]
          : [],
        unvaluedWonCount: 0,
        hasOpportunities: true,
      });
      return;
    }

    await fulfilJson(
      route,
      { code: "not_found", message: `Synthetic route not configured: ${path}` },
      404,
    );
  });
}

test("flagship seller journey keeps one canonical Northstar loop through Won", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await routeFlagship(page);

  await test.step("01 Home", async () => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Alex");
  });
  await test.step("02 Find / Prospect", async () => {
    await page.goto("/find");
    await page
      .getByRole("searchbox", { name: /Search company/i })
      .fill("Northstar");
    await page.getByRole("button", { name: "Search companies" }).click();
    await expect(page.getByText(account.name)).toBeVisible();
  });
  await test.step("03 Research a Company", async () => {
    await page.getByRole("button", { name: "Research company" }).click();
    await expect(page).toHaveURL(`/find/${ids.target}`);
    await expect(
      page.getByText("Research ready", { exact: true }),
    ).toBeVisible();
  });
  await test.step("04 Inspect sourced research", async () => {
    await expect(page.getByRole("heading", { name: "Sources" })).toBeVisible();
    await expect(page.getByText(source.publisher).first()).toBeVisible();
  });
  await test.step("05 Find and research a Person", async () => {
    await page.getByRole("button", { name: "Find relevant people" }).click();
    await page
      .getByRole("link", { name: "View professional research" })
      .click();
    await expect(page).toHaveURL(`/find/${ids.target}/people/${ids.person}`);
    await expect(
      page.getByRole("heading", { name: /Why this person may matter/i }),
    ).toBeVisible();
  });
  await test.step("06 Add Company to Sales with Company-first recovery", async () => {
    await page.getByRole("button", { name: "Add to Sales as Contact" }).click();
    await page.getByRole("button", { name: "Add Contact" }).click();
    await expect(
      page.getByRole("link", { name: "Save Company first" }),
    ).toBeVisible();
    await page.getByRole("link", { name: "Save Company first" }).click();
    await expect(page).toHaveURL(
      `/find/${ids.target}?returnToPerson=${ids.person}`,
    );
    await page
      .getByRole("button", { name: "Add to Sales", exact: true })
      .click();
    const accountDialog = page.getByRole("dialog");
    await expect(accountDialog).toBeVisible();
    await accountDialog.getByRole("button", { name: "Add account" }).click();
    await expect(
      page.getByRole("link", { name: "Continue adding Contact" }),
    ).toBeVisible();
  });
  await test.step("07 Add Contact to Sales", async () => {
    await page.getByRole("link", { name: "Continue adding Contact" }).click();
    await expect(page).toHaveURL(`/find/${ids.target}/people/${ids.person}`);
    await page.getByRole("button", { name: "Add to Sales as Contact" }).click();
    await page.getByRole("button", { name: "Add Contact" }).click();
    await expect(
      page.getByRole("link", { name: "Open Contact" }),
    ).toBeVisible();
    expect(state.contactPromoted).toBe(true);
  });
  await test.step("08 Open canonical Account", async () => {
    await page.goto(`/companies/${ids.account}`);
    await expect(
      page.getByRole("heading", { level: 1, name: account.name }),
    ).toBeVisible();
  });
  await test.step("09 Open canonical Contact", async () => {
    await page.goto(`/contacts/${ids.contact}`);
    await expect(
      page.getByRole("heading", { level: 1, name: "Jane Smith" }),
    ).toBeVisible();
  });
  await test.step("10 Prepare Outreach", async () => {
    await page.getByRole("button", { name: "Create outreach draft" }).click();
    await expect(
      page.getByRole("heading", { name: "Review personalised email" }),
    ).toBeVisible();
  });
  await test.step("11 Review exact Outreach", async () => {
    await page.getByRole("button", { name: "Approve current version" }).click();
    await page.getByRole("button", { name: "Review before send" }).click();
    await expect(
      page.getByRole("heading", { name: "Review exact email" }),
    ).toBeVisible();
    await expect(page.getByText("Simulation only")).toBeVisible();
  });
  await test.step("12 Complete safe simulation", async () => {
    await page.getByRole("button", { name: "Run email simulation" }).click();
    expect(state.outreachSimulated).toBe(true);
  });
  await test.step("13 Create or open Interaction", async () => {
    await page.goto(`/interactions/${ids.interaction}`);
    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "Northstar rollout discovery",
      }),
    ).toBeVisible();
  });
  await test.step("14 Prepare", async () => {
    await expect(
      page.getByRole("heading", { name: "Prepare for this interaction" }),
    ).toBeVisible();
    await expect(
      page
        .getByText("Confirm rollout ownership and agree the next workshop.")
        .first(),
    ).toBeVisible();
    await page.getByRole("button", { name: "Mark as reviewed" }).click();
    await expect(page.getByRole("button", { name: "Reviewed" })).toBeVisible();
    await captureFlagship(page, "interaction-prepare");
  });
  await test.step("15 Capture what happened", async () => {
    await page.getByRole("button", { name: "Start call" }).click();
    await expect(
      page.getByRole("status", { name: "Interaction lifecycle status" }),
    ).toHaveText("In Progress");
    await page.getByRole("button", { name: "End connected call" }).click();
    await expect(
      page.getByRole("heading", {
        name: "Capture this call while it’s fresh",
      }),
    ).toBeVisible();
    await page.getByRole("checkbox", { name: /safely stopped/i }).check();
    await page.getByRole("button", { name: "Capture what happened" }).click();
    await page
      .getByLabel("Your answer")
      .fill(
        "Jane confirmed that she owns the technical review and will schedule the rollout workshop.",
      );
    await page.getByRole("button", { name: "Save answer" }).click();
    await expect(
      page.getByRole("button", { name: "Review captured evidence" }),
    ).toBeVisible();
  });
  await test.step("16 Review Debrief", async () => {
    await page
      .getByRole("button", { name: "Review captured evidence" })
      .click();
    await expect(page.getByText("Reported by you").first()).toBeVisible();
    await expect(page.getByLabel("Evidence statement")).toHaveValue(
      "Jane confirmed that she owns the technical review and will schedule the rollout workshop.",
    );
  });
  await test.step("17 Review candidate Evidence", async () => {
    await expect(page.getByLabel("Evidence statement")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Accept", pressed: true }),
    ).toBeVisible();
    await captureFlagship(page, "evidence");
  });
  await test.step("18 Accept Evidence", async () => {
    await page
      .getByRole("button", { name: "Finish review and update intelligence" })
      .click();
    await expect(page.getByText("Debrief complete")).toBeVisible();
    await expect(
      page.getByText(
        "Reviewed evidence saved to the interaction and Revenue Brain.",
      ),
    ).toBeVisible();
    expect(state.evidenceAccepted).toBe(true);
    await captureFlagship(page, "interaction-review");
  });
  await test.step("19 Confirm Revenue Brain updates", async () => {
    await page.goto(`/companies/${ids.account}`);
    await expect(
      page.getByRole("heading", { name: "Reviewed interaction intelligence" }),
    ).toBeVisible();
    await expect(
      page.getByText(
        "Jane confirmed that she owns the technical review and will schedule the rollout workshop.",
      ),
    ).toBeVisible();
  });
  await test.step("20 Confirm Methodology updates", async () => {
    expect(methodology().state).toBe("current");
    expect(methodology().projection?.items[0]?.sources[0]?.sourceId).toBe(
      ids.evidence,
    );
  });
  await test.step("21 Review or create Action", async () => {
    expect(nextAction().sourceRefs).toEqual([
      expect.objectContaining({
        sourceId: "interaction-intelligence-flagship",
        label: "Reviewed post-interaction report",
      }),
    ]);
  });
  await test.step("22 Create Opportunity", async () => {
    await page.goto("/opportunities/new");
    await page
      .getByRole("combobox", { name: "Account", exact: true })
      .selectOption(ids.account);
    await page
      .getByLabel("Opportunity name")
      .fill("National operations rollout");
    await page.getByLabel("Estimated value").fill("420000");
    await page.getByLabel("Currency").selectOption("AUD");
    await page.getByLabel("Expected close date").fill("2026-09-30");
    await page
      .getByLabel("Description")
      .fill("Synthetic flagship Opportunity.");
    await page.getByRole("button", { name: "Create Opportunity" }).click();
    await expect(page).toHaveURL(`/opportunities/${ids.opportunity}`);
    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "National operations rollout",
      }),
    ).toBeVisible();
    expect(state.opportunityCreated).toBe(true);
  });
  await test.step("23 Confirm Account and Contact relationships", async () => {
    await expect(page.getByText(account.name).last()).toBeVisible();
    expect(contact.companyId).toBe(ids.account);
    expect(interaction().opportunityId).toBe(ids.opportunity);
  });
  await test.step("24 Open Pipeline", async () => {
    await page.goto("/opportunities");
    await expect(
      page.getByRole("heading", { level: 1, name: "Pipeline" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", {
        level: 3,
        name: "National operations rollout",
      }),
    ).toBeVisible();
  });
  await test.step("25 Move stage", async () => {
    const stageSelect = page.getByRole("combobox", { name: "Move stage" });
    await stageSelect.selectOption(ids.proposal);
    await expect(stageSelect).toHaveValue(ids.proposal);
    expect(state.stage).toBe("proposal");
  });
  await test.step("26 Open Opportunity", async () => {
    await page
      .getByRole("link", { name: "National operations rollout", exact: true })
      .click();
    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "National operations rollout",
      }),
    ).toBeVisible();
  });
  await test.step("27 Review deal state", async () => {
    await expect(
      page.getByRole("heading", { name: "Proposal", level: 2 }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Latest post-interaction report" }),
    ).toBeVisible();
    await expect(
      page.getByText(
        "Jane confirmed that she owns the technical review and will schedule the rollout workshop.",
      ),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Sales Methodology" }),
    ).toBeVisible();
    await expect(
      page.getByText(
        "Jane owns the technical review and will schedule the rollout workshop.",
      ),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Next actions" }),
    ).toBeVisible();
    await expect(
      page.getByText("Confirm the rollout workshop").first(),
    ).toBeVisible();
    await page.getByRole("button", { name: "Approve action" }).click();
    await expect(
      page.getByText("Action approved. Nothing was sent or updated."),
    ).toBeVisible();
    expect(state.actionApproved).toBe(true);
    await captureFlagship(page, "opportunity");
  });
  await test.step("28 Open current Business Case capability", async () => {
    await page.goto(
      `/create/business-cases/new?accountId=${ids.account}&opportunityId=${ids.opportunity}`,
    );
    await expect(
      page.getByRole("heading", { level: 1, name: "Create a Business Case" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "No approved Value Models" }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Manage Value Models" }),
    ).toBeVisible();
  });
  await test.step("29 Open Create Studio", async () => {
    await page.goto("/create");
    await expect(
      page.getByRole("heading", { level: 1, name: "Sales Content Studio" }),
    ).toBeVisible();
  });
  await test.step("30 Generate an approved synthetic presentation", async () => {
    await page.getByRole("link", { name: "New presentation" }).click();
    await page
      .getByRole("combobox", { name: "Account", exact: true })
      .selectOption(ids.account);
    await page
      .getByRole("combobox", { name: "Opportunity (optional)", exact: true })
      .selectOption(ids.opportunity);
    await page
      .getByRole("combobox", { name: "Known Contact (optional)", exact: true })
      .selectOption(ids.contact);
    await page
      .getByLabel("Template version")
      .selectOption(createTemplate.latestVersion.id);
    await page
      .getByLabel("Presentation title (optional)")
      .fill("Northstar solution overview");
    await page.getByRole("button", { name: "Review slide plan" }).click();
    await expect(page).toHaveURL(`/create/presentations/${ids.presentation}`);
    await expect(
      page.getByRole("heading", {
        name: "Review the deterministic slide plan",
      }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Generate from this plan" }).click();
    await expect(
      page.getByRole("heading", { name: "Claim and source manifest" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Keep with review" }).click();
    await expect(
      page.getByRole("button", { name: "Approve presentation" }),
    ).toBeEnabled();
    await page.getByRole("button", { name: "Approve presentation" }).click();
    await expect(
      page.getByRole("button", { name: "Download editable PPTX" }),
    ).toBeVisible();
    expect(state.presentationState).toBe("ready");
    await captureFlagship(page, "create");
  });
  await test.step("31 Return to Opportunity", async () => {
    await page.goto(`/opportunities/${ids.opportunity}`);
    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "National operations rollout",
      }),
    ).toBeVisible();
  });
  await test.step("32 Open Insights", async () => {
    await page.goto("/insights");
    await expect(
      page.getByRole("heading", { level: 1, name: "Sales insights" }),
    ).toBeVisible();
  });
  await test.step("33 Confirm Analytics", async () => {
    await expect(page.getByText(/Open opportunities/i).first()).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Active targets" }),
    ).toBeVisible();
  });
  await test.step("34 Confirm Target", async () => {
    await page.getByRole("tab", { name: "Targets" }).click();
    await expect(
      page.getByRole("heading", { name: "Targets", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("progressbar", { name: "Won value: 0% complete" }),
    ).toBeVisible();
    await captureFlagship(page, "target");
  });
  await test.step("35 Open Forecast", async () => {
    await page.getByRole("tab", { name: "Forecast" }).click();
    await expect(
      page.getByRole("heading", { name: "Seller forecast range" }),
    ).toBeVisible();
  });
  await test.step("36 Review seller forecast", async () => {
    await expect(page.getByText("National operations rollout")).toBeVisible();
    await expect(page.getByLabel("Seller category")).toHaveValue("likely");
    await captureFlagship(page, "forecast");
  });
  await test.step("37 Open Manager view as admin fixture", async () => {
    await page.goto(`/opportunities/${ids.opportunity}`);
    await expect(
      page.getByRole("heading", { name: "What matters for this deal" }),
    ).toBeVisible();
  });
  await test.step("38 Review manager questions", async () => {
    await expect(page.getByText("Questions to discuss")).toBeVisible();
    await expect(
      page.getByText("Who owns final commercial approval for the rollout?"),
    ).toBeVisible();
    await captureFlagship(page, "manager");
  });
  await test.step("39 Close Opportunity Won", async () => {
    await page.getByRole("button", { name: "Mark Won" }).click();
    const closeDialog = page.getByRole("dialog", { name: "Mark as Won" });
    await closeDialog
      .getByLabel("What helped us win? (optional)")
      .selectOption("solution_fit");
    await closeDialog.getByRole("button", { name: "Close Won" }).click();
    await expect(page.getByText("Closed Won").first()).toBeVisible();
    expect(state.closedWon).toBe(true);
    await captureFlagship(page, "opportunity-closed");
  });
  await test.step("40 Confirm Pipeline, Actual, Forecast removal, Target, Analytics and history", async () => {
    await page.goto("/opportunities");
    await page.getByRole("button", { name: "Closed" }).click();
    await expect(
      page.getByRole("link", {
        name: "National operations rollout",
        exact: true,
      }),
    ).toBeVisible();
    await page.goto("/insights");
    await expect(page.getByText("Open opportunities").first()).toBeVisible();
    await expect(page.getByText("$420,000", { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Targets" }).click();
    await expect(
      page.getByRole("progressbar", { name: "Won value: 84% complete" }),
    ).toBeVisible();
    await page.getByRole("tab", { name: "Forecast" }).click();
    await expect(page.getByText("Actual won")).toBeVisible();
    await expect(
      page.getByText("No open opportunities close in this period"),
    ).toBeVisible();
    await page.goto(`/opportunities/${ids.opportunity}`);
    await page.getByText("Stage history").click();
    await expect(page.getByText("Proposal → Closed Won")).toBeVisible();
  });
});
