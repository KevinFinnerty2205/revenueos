from datetime import datetime

import pytest
from pydantic import ValidationError

from revenueos.business_contracts import (
    CompanyCreate,
    ContactCreate,
    OpportunityCreate,
    TaskCreate,
)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (CompanyCreate, {"name": "", "employeeCount": -1}),
        (
            ContactCreate,
            {
                "companyId": "00000000-0000-4000-8000-000000000001",
                "firstName": "Casey",
                "lastName": "Jones",
                "email": "invalid",
            },
        ),
        (
            OpportunityCreate,
            {
                "companyId": "00000000-0000-4000-8000-000000000001",
                "name": "Renewal",
                "estimatedValue": -0.01,
                "currency": "AUD",
            },
        ),
        (TaskCreate, {"title": "Call customer", "dueAt": datetime(2026, 1, 1, 9, 0)}),
    ],
)
def test_contract_validation_rejects_invalid_models(
    model: type[CompanyCreate | ContactCreate | OpportunityCreate | TaskCreate],
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_contracts_forbid_unrecognised_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CompanyCreate.model_validate({"name": "Acme", "organisationId": "tenant-from-client"})


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "Renewal", "stage": "forecast"},
        {"name": "Renewal", "status": "at_risk"},
        {"name": "Renewal", "estimatedValue": "100.00"},
        {"name": "Renewal", "currency": "AUD"},
        {"name": "Renewal", "estimatedValue": "100.001", "currency": "AUD"},
        {"name": "Renewal", "expectedCloseDate": "2026-02-30"},
        {"name": "Renewal", "organisationId": "00000000-0000-4000-8000-000000000001"},
    ],
)
def test_opportunity_contract_rejects_invalid_or_client_owned_fields(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        OpportunityCreate.model_validate(payload)
