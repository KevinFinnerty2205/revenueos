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
                "value": -0.01,
                "probability": 101,
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
