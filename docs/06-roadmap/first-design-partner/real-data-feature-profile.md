# First-partner real-data feature profile

Status: **OWNER AND PARTNER APPROVAL REQUIRED**. The recommended product value-test profile is `NATIVE-AI-REVIEW-V1`, but it may be used only after the [AI processing gate](AI-real-data-processing-gate.md) passes. The fail-closed fallback `NATIVE-NO-EXTERNAL-AI-V1` is the only known-safe repository profile while external AI remains unapproved.

## Recommended profile: NATIVE-AI-REVIEW-V1

This profile tests the smallest useful Sales Brain loop: manually created/imported Native CRM data, deliberate Interaction/transcript input, reviewed AI Evidence, Revenue Brain, Methodology, Actions, Daily, Pipeline, Insights, Targets, Forecast and Manager Intelligence. It excludes provider research, live sending, live capture and external execution.

Accounts, Contacts, Opportunities, Tasks, Interactions and Daily do not have independent server flags; their applicable Core/tenant/role controls remain on. Evidence is not a freely supplied CSV field: in this profile it enters the review path only through the approved Interaction intelligence/debrief flow.

| Capability/flag | Required state | Reason/restriction |
| --- | --- | --- |
| `API_PRIVATE_BETA_REAL_DATA_ENABLED` | `true` | Only after all launch approvals and proofs |
| `API_PRIVATE_BETA_EXTERNAL_AI_APPROVED` | `true` | Must reference the approved OpenAI processing profile |
| `AI_PROVIDER` / `OPENAI_MODEL` | `openai` / exact approved model | No fallback; unavailable model fails closed |
| `API_FEATURE_OPENAI_PROVIDER_ENABLED` | `true` | Server-side provider kill switch |
| `API_FEATURE_REVENUE_BRAIN_ENABLED` | `true` | Core reviewed relationship intelligence |
| `API_FEATURE_OPPORTUNITY_WORKSPACE_ENABLED` | `true` | Core deal workspace |
| `API_FEATURE_AI_COMPANION_ENABLED` | `true` | BEFORE/AFTER shell only; recording/visual/live paths remain off |
| `API_FEATURE_AI_DEBRIEF_ENABLED` | `true` | Bounded typed debrief; review required |
| `API_FEATURE_VOICE_JOURNAL_ENABLED` | `false` | No audio/transcription in first profile |
| `API_FEATURE_VISUAL_EVIDENCE_ENABLED` | `false` | No image AI/source handling in first profile |
| `API_FEATURE_PRESENTATION_MODE_ENABLED` | `false` | No visual capture path |
| `API_FEATURE_RECORDING_CAPTURE_ENABLED` | `false` | No recording |
| `API_FEATURE_TRANSCRIPTION_ENABLED` | `false` | No audio transfer |
| `API_FEATURE_AUTO_GENERATE_INTELLIGENCE_AFTER_TRANSCRIPTION` | `false` | No automatic processing |
| All four online-meeting flags | `false` | No native/import/auto-ingest provider workflow; deliberate ordinary transcript entry remains available |
| `API_FEATURE_DOCUMENT_EVIDENCE_ENABLED` | `false` | Add only after separate source/provider/data-boundary approval |
| `API_FEATURE_EMAIL_EVIDENCE_ENABLED` | `false` | No mailbox; pasted email also excluded initially |
| `API_FEATURE_SALES_METHODOLOGY_ENABLED` | `true` | Core reviewed methodology |
| `API_FEATURE_ASK_REVENUEOS_ENABLED` | `true` | Bounded read-only, cited deterministic composition; no external call |
| Both live-intelligence flags | `false` | No live processing |
| `API_FEATURE_ACTION_LAYER_ENABLED` | `true` | Reviewed internal Actions |
| `API_FEATURE_ACTION_MANUAL_COMPLETION_ENABLED` | `true` | Internal completion only |
| `API_FEATURE_INTEGRATIONS_ENABLED` | `false` | No connector path |
| `API_FEATURE_ACTION_EXECUTION_ENABLED` | `false` | No external mutation |
| `API_FEATURE_MOCK_CONNECTORS_ENABLED` | `false` | Prohibited in production |
| `API_FEATURE_HUBSPOT_CRM_ENABLED` | `false` | Native CRM first |
| Native CRM, Pipeline, Analytics, Targets, Forecasting and Manager flags | `true` | Approved Core/Native workflow |
| `API_FEATURE_DATA_EXPORT_ENABLED` | `true` | Required lifecycle control |
| `API_FEATURE_ORGANISATION_DELETION_ENABLED` | `true` | Required supervised offboarding; admin exact confirmation still required |
| `API_FEATURE_PROSPECT_ENABLED` | `false` | Only mock provider exists; no Apollo |
| Engage, Campaigns and Events flags | `false` | No live/simulated outreach or event expansion |
| `API_FEATURE_CREATE_ENABLED` | `false` by default | Enable only if this partner is testing Create and file backup/restore proof passed |

Recommended initial usage ceilings for one supervised partner are 50 newly created generations and 75 OpenAI attempts per organisation per UTC day, subject to owner cost review. Existing hard configuration bounds remain authoritative. Set lower values if the expected workflow permits; do not raise them during an incident.

The exact expected safe flag output, before any partner-specific Create approval, is:

```json
{
  "actionExecution": false,
  "actionLayer": true,
  "actionManualCompletion": true,
  "aiCompanion": true,
  "aiDebrief": true,
  "askRevenueOS": true,
  "autoGenerateIntelligenceAfterTranscription": false,
  "create": false,
  "dataExport": true,
  "documentEvidence": false,
  "emailEvidence": false,
  "engage": false,
  "engageCampaigns": false,
  "engageEvents": false,
  "hubspotCrm": false,
  "integrations": false,
  "liveInteractionExternalAi": false,
  "liveInteractionIntelligence": false,
  "managerIntelligence": true,
  "mockConnectors": false,
  "nativeCrm": true,
  "nativePipeline": true,
  "onlineMeetingAutoIngest": false,
  "onlineMeetingCapture": false,
  "onlineMeetingImport": false,
  "onlineMeetingNativeIntegration": false,
  "openaiProvider": true,
  "opportunityWorkspace": true,
  "organisationDeletion": true,
  "presentationMode": false,
  "prospect": false,
  "recordingCapture": false,
  "revenueBrain": true,
  "salesAnalytics": true,
  "salesForecasting": true,
  "salesMethodology": true,
  "salesTargets": true,
  "transcription": false,
  "visualEvidence": false,
  "voiceJournal": false
}
```

## Fallback profile: NATIVE-NO-EXTERNAL-AI-V1

Use this while AI approval is absent. Set the AI, Revenue Brain, Companion, Debrief, Voice, visual, recording, transcription, online-meeting, document/email Evidence, Ask, live, Prospect, Engage/Campaign/Event and Create flags `false`; set all providers to `mock` only as disabled no-network adapters. Keep Opportunity Workspace, Methodology, Actions/manual completion, Native CRM, Pipeline, Analytics, Targets, Forecast, Manager, export and supervised organisation deletion `true`.

This fallback supports Core records, Interactions, Pipeline and deterministic business workflow, but **does not provide the full Revenue Brain/reviewed-AI value test**. Do not label disabled AI or a mock as Sales Brain intelligence. If the design-partner objective requires AI-derived Evidence/Revenue Brain, the launch is `NO-GO for that feature profile` until the AI gate passes.

When the external provider is disabled or unavailable, all affected customer-content features remain off and show an honest unavailable/not-enabled state. Existing approved records/history remain subject to ordinary authorisation and retention; no job is silently sent to another provider and no deterministic mock result is generated over customer content.

## Create exception

Create makes no AI-provider call, but it processes/stores customer content and the current real-data validation treats it as a customer-content capability. Enable it only after private durable object storage, Create generation/download, backup/restore/checksum and partner purpose are approved. The mandatory synthetic restore drill may use an operator-only Create entitlement as documented in the drill; the final partner profile must be restored exactly before data entry.

## Verification and kill switches

Save the approved `safe_feature_flags()` JSON as `approved-feature-flags.json` in the restricted launch record. Compare it byte-for-byte (after `jq -S`) with `production-preflight` output. Also verify module entitlements for the named tenant: Core plus CRM; no Prospect/Engage; Create only when approved.

On incident, disable the narrow affected server flag and worker together. Suspected tenant leak, unsafe AI output/data flow, Create corruption, auth revocation failure or external mutation triggers the global launch pause. Do not switch to mock while real customer-content features remain visible.
