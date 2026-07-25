from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from revenueos.contracts import APIModel
from revenueos.domain import MeetingStatus, OpportunityStage, OpportunityStatus
from revenueos.intelligence_contracts import MeetingIntelligenceResponse

IntelligenceReadiness = Literal["unavailable", "not_generated", "partial", "ready"]


class OpportunityListItemResponse(APIModel):
    id: UUID
    organisation_id: UUID
    company_id: UUID | None
    company_name: str | None
    name: str
    stage: OpportunityStage
    status: OpportunityStatus
    estimated_value: Decimal | None
    currency: str | None
    expected_close_date: date | None
    owner_user_id: UUID
    owner_name: str
    description: str | None
    latest_meeting_id: UUID | None
    latest_meeting_date: datetime | None
    latest_meeting_momentum: str | None
    latest_next_best_action: str | None
    created_at: datetime
    updated_at: datetime


class OpportunityWorkspaceOpportunityResponse(APIModel):
    id: UUID
    company_id: UUID | None
    company_name: str | None
    name: str
    stage: OpportunityStage
    status: OpportunityStatus
    estimated_value: Decimal | None
    currency: str | None
    expected_close_date: date | None
    owner_user_id: UUID
    owner_name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class OpportunityMeetingSummaryResponse(APIModel):
    id: UUID
    title: str
    meeting_date: datetime
    status: MeetingStatus
    company_id: UUID | None
    company_name: str | None
    participant_count: int
    transcript_available: bool
    transcript_version: int | None
    intelligence_readiness: IntelligenceReadiness
    intelligence_sections_available: int
    updated_at: datetime


class OpportunityWorkspaceResponse(APIModel):
    opportunity: OpportunityWorkspaceOpportunityResponse
    latest_meeting: OpportunityMeetingSummaryResponse | None
    recent_meetings: list[OpportunityMeetingSummaryResponse]
    intelligence: MeetingIntelligenceResponse | None
    intelligence_sections_available: int
    partial_data: bool
    generated_at: datetime
